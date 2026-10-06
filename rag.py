"""Core RAG logic: embeddings, retrieval, aur Gemini se grounded jawab."""
import os
import time
from pathlib import Path

import chromadb
import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")
EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-001")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-3.8-flash")
# Pehla model busy ho to in models par automatically chale jao
FALLBACK_MODELS = [
    m.strip()
    for m in os.getenv("FALLBACK_MODELS", "gemini-3.5-flash,gemini-3.1-flash-lite").split(",")
    if m.strip()
]
CHAT_MODELS = [CHAT_MODEL] + [m for m in FALLBACK_MODELS if m != CHAT_MODEL]
TOP_K = int(os.getenv("TOP_K", "4"))
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")  # booking workflow; na ho to booking tool band rehta hai
N8N_TIMEOUT_SEC = 60
EMBED_DIMS = 768
DB_DIR = BASE_DIR / "chroma_db"
COLLECTION = "clinic_kb"

SYSTEM_PROMPT = """You are the friendly virtual assistant of BrightSmile Dental Clinic in Islamabad.

RULES:
1. Answer ONLY using the CLINIC INFORMATION given below. Never use outside knowledge
   about fees, timings, doctors or policies. Never invent prices, names or times.
2. If the answer is not in the clinic information, say clearly that you don't have that
   information, and suggest calling or WhatsApp 0300-1234567. Do not guess.
3. Always reply in clear, simple English, even if the patient writes in another
   language. Keep a warm, polite tone.
4. Keep answers short and clear (2-5 sentences). Use a short list only for prices or steps.
5. You are not a doctor. Do not diagnose or prescribe. For symptoms, share only the
   general guidance present in the clinic information and recommend a check-up. For severe
   pain, swelling or bleeding, tell the patient to call the clinic right away.
6. Prices are starting rates; mention that the final fee is confirmed after examination
   when you quote fees.
7. BOOKING: if the patient wants an appointment, collect their full name and phone number
   (ask for any that is missing; never invent them). Once you have both, call the
   clinic_booking tool with the patient's latest message copied word for word. The booking
   system replies with available slots or a confirmation. Relay that reply faithfully
   (keep slot numbers, dates and times exactly as given) in English, and
   never claim an appointment is booked unless the tool reply says it is confirmed.
   If a booking is already in progress (slots were offered in the conversation) and the
   patient answers with a slot ("1", "2", "10 baje wala"), call clinic_booking again with
   the same name and phone and that answer. If the tool returns an error, apologise and
   give the clinic phone 0300-1234567. If the tool is not available, ask the patient to
   call or WhatsApp 0300-1234567.
8. Politely refuse unrelated requests (general knowledge, other businesses, coding, etc.)
   and bring the conversation back to the clinic.
"""

REQUEST_TIMEOUT_MS = 20000  # ek Gemini request ko max 20 second
_client = None


def get_client():
    global _client
    if _client is None:
        if not API_KEY:
            raise RuntimeError("GEMINI_API_KEY nahi mili. .env file banao aur key paste karo.")
        _client = genai.Client(
            api_key=API_KEY,
            http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
        )
    return _client


TRANSIENT = (errors.ServerError, httpx.TimeoutException, httpx.ConnectError)


def with_retry(fn, delays=(0, 2, 5, 10)):
    """Google ka server busy (503) ho to 4 baar tak dobara koshish karo."""
    last = None
    for attempt, delay in enumerate(delays, start=1):
        if delay:
            time.sleep(delay)
        try:
            return fn()
        except TRANSIENT as exc:  # 5xx busy ya timeout: dobara try
            last = exc
            print(f"Gemini busy (koshish {attempt}/{len(delays)}), dobara try...")
    raise last


def embed(texts, task_type):
    """Texts ki list ko embeddings (list of float lists) mein badlo."""
    resp = with_retry(
        lambda: get_client().models.embed_content(
            model=EMBED_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type=task_type, output_dimensionality=EMBED_DIMS
            ),
        )
    )
    return [e.values for e in resp.embeddings]


# Jis model ka quota (429) khatam ho jaye usay kuch der ke liye skip karo
_cooldown = {}
QUOTA_COOLDOWN_SEC = 30 * 60


def generate_with_fallback(contents, tools=None):
    """Models ki list mein se pehla jo chale usse jawab lo.

    - busy / slow (503, timeout): agla model try karo
    - quota khatam (429): is model ko 30 min skip karo, agla try karo
    - model available nahi (404): agla try karo
    """
    last = None
    for model in CHAT_MODELS:
        if _cooldown.get(model, 0) > time.time():
            continue
        try:
            return with_retry(
                lambda: get_client().models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.2,
                        tools=tools,
                        # function call hum khud manually chalate hain
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(
                            disable=True
                        ),
                    ),
                ),
                delays=(0, 2),
            )
        except TRANSIENT as exc:
            last = exc
            print(f"{model} busy/slow hai, agla model try kar raha hoon...")
        except errors.ClientError as exc:
            code = getattr(exc, "code", None)
            if code == 429:
                last = exc
                _cooldown[model] = time.time() + QUOTA_COOLDOWN_SEC
                print(f"{model} ka quota khatam, agla model try kar raha hoon...")
                continue
            if code == 404:
                last = exc
                print(f"{model} available nahi, agla model try kar raha hoon...")
                continue
            raise
    if last is None:  # sab models cooldown par hain
        raise RuntimeError("All models are over quota. Please try again in a little while.")
    raise last


BOOKING_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="clinic_booking",
            description=(
                "Send the patient's message to the clinic's appointment booking system. "
                "It offers free slots, or confirms the slot the patient chose. Call it only "
                "when you know both the patient's name and phone number."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "name": types.Schema(type=types.Type.STRING, description="Patient's full name"),
                    "phone": types.Schema(type=types.Type.STRING, description="Patient's phone number"),
                    "message": types.Schema(
                        type=types.Type.STRING,
                        description="The patient's latest message, copied word for word",
                    ),
                },
                required=["name", "phone", "message"],
            ),
        )
    ]
)


def run_booking(args):
    """n8n booking workflow ko call karo. Hamesha dict wapas deta hai (kabhi crash nahi)."""
    name = str(args.get("name") or "").strip()
    phone = "".join(ch for ch in str(args.get("phone") or "") if ch.isdigit() or ch == "+")
    message = str(args.get("message") or "").strip()
    if not name or len(phone) < 10 or not message:
        return {"error": "Name or a valid phone number is missing. Ask the patient for it."}
    try:
        r = httpx.post(
            N8N_WEBHOOK_URL,
            json={"name": name, "phone": phone, "message": message},
            timeout=N8N_TIMEOUT_SEC,
        )
        r.raise_for_status()
        data = r.json()
        return {"reply": data.get("reply_message", ""), "status": data.get("status", "")}
    except Exception as exc:  # noqa: BLE001
        print(f"n8n booking call fail: {type(exc).__name__}: {exc}")
        return {"error": "Booking system is not reachable right now."}


def get_collection(create=False):
    db = chromadb.PersistentClient(path=str(DB_DIR))
    if create:
        try:
            db.delete_collection(COLLECTION)
        except Exception:
            pass
        return db.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
    return db.get_collection(COLLECTION)


def retrieve(query, k=TOP_K):
    vec = embed([query], "RETRIEVAL_QUERY")[0]
    res = get_collection().query(query_embeddings=[vec], n_results=k)
    chunks = []
    for doc, meta, dist in zip(
        res["documents"][0], res["metadatas"][0], res["distances"][0]
    ):
        chunks.append({"text": doc, "source": meta["source"], "distance": dist})
    return chunks


def answer(message, history=None):
    history = history or []

    # Follow-up sawaal ("aur uski fees?") ke liye pichla user message bhi search mein shamil karo
    prev_user = [h["content"] for h in history if h["role"] == "user"][-1:]
    search_query = " ".join(prev_user + [message])

    chunks = retrieve(search_query)
    context = "\n\n---\n\n".join(f"[{c['source']}]\n{c['text']}" for c in chunks)
    convo = "\n".join(
        f"{'Patient' if h['role'] == 'user' else 'Assistant'}: {h['content']}"
        for h in history[-6:]
    )

    prompt = (
        f"CLINIC INFORMATION:\n{context}\n\n"
        f"CONVERSATION SO FAR:\n{convo or '(new conversation)'}\n\n"
        f"Patient: {message}\nAssistant:"
    )

    contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
    tools = [BOOKING_TOOL] if N8N_WEBHOOK_URL else None

    resp = None
    for _ in range(3):  # max 3 round: sawal -> tool -> jawab
        resp = generate_with_fallback(contents, tools)
        calls = resp.function_calls or []
        if not calls:
            break
        contents.append(resp.candidates[0].content)  # model ka call (signatures ke saath)
        parts = []
        for fc in calls:
            if fc.name == "clinic_booking":
                result = run_booking(dict(fc.args or {}))
            else:
                result = {"error": "Unknown tool."}
            parts.append(types.Part.from_function_response(name=fc.name, response=result))
        contents.append(types.Content(role="user", parts=parts))

    text = (resp.text or "").strip() if resp else ""
    if not text:
        text = "Sorry, I couldn't complete that right now. Please call or WhatsApp the clinic at 0300-1234567."
    sources = sorted({c["source"] for c in chunks})
    return {"answer": text, "sources": sources}
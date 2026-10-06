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
EMBED_DIMS = 768
DB_DIR = BASE_DIR / "chroma_db"
COLLECTION = "clinic_kb"

SYSTEM_PROMPT = """You are the friendly virtual assistant of BrightSmile Dental Clinic in Islamabad.

RULES:
1. Answer ONLY using the CLINIC INFORMATION given below. Never use outside knowledge
   about fees, timings, doctors or policies. Never invent prices, names or times.
2. If the answer is not in the clinic information, say clearly that you don't have that
   information, and suggest calling or WhatsApp 0300-1234567. Do not guess.
3. Reply in the same language and script the patient used: English, Urdu script, or
   Roman Urdu (Urdu written in English letters). Keep a warm, polite tone.
4. Keep answers short and clear (2-5 sentences). Use a short list only for prices or steps.
5. You are not a doctor. Do not diagnose or prescribe. For symptoms, share only the
   general guidance present in the clinic information and recommend a check-up. For severe
   pain, swelling or bleeding, tell the patient to call the clinic right away.
6. Prices are starting rates; mention that the final fee is confirmed after examination
   when you quote fees.
7. To book an appointment, ask the patient to share name, phone number and preferred
   day/time, or to call/WhatsApp 0300-1234567.
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


def generate_with_fallback(prompt):
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
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT, temperature=0.2
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
        raise RuntimeError("Sab models ka quota khatam hai. Thori der baad try karein.")
    raise last


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

    resp = generate_with_fallback(prompt)
    sources = sorted({c["source"] for c in chunks})
    return {"answer": (resp.text or "").strip(), "sources": sources}
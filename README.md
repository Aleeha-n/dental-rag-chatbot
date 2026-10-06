# BrightSmile Dental Chatbot (RAG)

Ek RAG-based customer support chatbot: clinic ke documents se jawab deta hai, jo cheez docs mein nahi hoti uske liye guess nahi karta, aur ek `<script>` tag se kisi bhi website mein lag jata hai.

## Kaise kaam karta hai

```
knowledge/*.md  -->  chunker.py  -->  Gemini embeddings  -->  Chroma (chroma_db/)
                                                                   |
Patient ka sawal --> embedding --> top 4 relevant chunks <---------+
                                         |
                      Gemini (sirf in chunks se jawab) --> /chat API --> widget.js
```

## Setup (pehli baar)

Python 3.10 ya naya chahiye.

```bash
python -m venv venv
# Windows:        venv\Scripts\activate
# Mac/Linux:      source venv/bin/activate
pip install -r requirements.txt
```

`.env.example` ki copy banao, naam `.env` rakho, aur apni Gemini API key paste karo:

```
GEMINI_API_KEY=your_key_here
```

## Chalana

```bash
python ingest.py                      # documents ko embeddings mein convert karke save karta hai
uvicorn server:app --reload --port 8000
```

Browser mein kholo: http://localhost:8000/demo  (neeche right mein chat bubble)

Testing:

```bash
python test_questions.py              # 20 test sawal, trick sawal bhi
```

## Kisi website mein lagana

```html
<script src="https://YOUR-SERVER/widget/widget.js" data-api="https://YOUR-SERVER"></script>
```

`data-title="Mera Naam"` se widget ka title badal sakte ho.

## Files

| File | Kaam |
|---|---|
| `knowledge/` | Clinic ke 7 documents (demo data) |
| `chunker.py` | Documents ko heading-wise chunks mein todta hai |
| `ingest.py` | Chunks ko embed karke Chroma mein save karta hai |
| `rag.py` | Retrieval + Gemini se grounded jawab + system prompt |
| `server.py` | FastAPI `/chat` endpoint |
| `widget/widget.js` | Embeddable chat widget (Shadow DOM) |
| `test_questions.py` | Answerable aur trick sawalon ka test |

## Known limitations (v1)

- Conversation history browser mein rehti hai (page refresh par reset), server par save nahi hoti.
- Booking abhi sirf guidance deti hai (naam, phone, time lene ko kehti hai). n8n booking automation se connect karna agla step hai.
- Sirf text documents (.md). PDF ingestion future improvement hai.
- Koi rate limiting ya authentication nahi. Production mein CORS aur rate limit lagana zaroori hai.

Note: BrightSmile ek demo (fictional) clinic hai, portfolio ke liye.

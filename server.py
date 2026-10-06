"""FastAPI server: /chat endpoint + widget files.

Chalane ka tareeqa:  uvicorn server:app --reload --port 8000
Demo page:           http://localhost:8000/demo
"""
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from rag import BASE_DIR, answer

app = FastAPI(title="BrightSmile Dental Chatbot")

# Widget kisi bhi website par embed ho sake, isliye CORS open hai.
# Production mein allow_origins ko sirf client ki website tak limit karo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=1000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    history: Optional[List[Turn]] = None


@app.post("/chat")
def chat(req: ChatRequest):
    history = [t.model_dump() for t in (req.history or [])]
    try:
        return answer(req.message, history)
    except Exception as exc:  # noqa: BLE001
        print("Chat error:", repr(exc))
        raise HTTPException(
            status_code=500,
            detail="Sorry, I can't answer right now. Please call the clinic at 0300-1234567.",
        )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/demo")
def demo():
    return FileResponse(BASE_DIR / "widget" / "demo.html")


app.mount("/widget", StaticFiles(directory=BASE_DIR / "widget"), name="widget")
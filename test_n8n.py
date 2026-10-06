"""n8n booking workflow ko seedha test karo (chatbot ke bagair).

Chalane ka tareeqa:  python test_n8n.py

.env mein ye line honi chahiye:
    N8N_WEBHOOK_URL=<n8n ka Production URL, .../webhook/dental-chat>

Ye ek fake patient banakar workflow ko message bhejta hai aur jawab print karta hai.
Pehle booking ki request jati hai (workflow slots offer karega), phir tum khud
slot ka jawab type karte ho (jaise "1" ya "9 baje wala").
"""
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()
URL = os.getenv("N8N_WEBHOOK_URL")
if not URL:
    sys.exit(".env mein N8N_WEBHOOK_URL nahi mila.")

NAME = "Test Patient"
PHONE = "03001112233"


def send(message):
    r = httpx.post(
        URL, json={"name": NAME, "phone": PHONE, "message": message}, timeout=90
    )
    try:
        data = r.json()
    except ValueError:
        data = r.text
    print(f"\n[{r.status_code}] {data}\n")
    return data


print("Step 1: booking ki request bhej raha hoon...")
send("Mujhe scaling ke liye appointment chahiye")

while True:
    msg = input("Apna jawab likho (ya q likh kar band karo): ").strip()
    if msg.lower() in ("q", "quit", ""):
        break
    send(msg)
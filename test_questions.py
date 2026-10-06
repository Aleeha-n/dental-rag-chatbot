"""20 test sawal chalata hai aur check karta hai ke jawab sahi aur grounded hai.

Chalane ka tareeqa:  python test_questions.py
(pehle python ingest.py chala chuki ho)

Do tarah ke test:
- Answerable: jawab mein expected keywords mein se koi ek hona chahiye.
- Out-of-scope (trick) sawal: bot ko jhooth nahi bolna chahiye, clinic ka number
  0300-1234567 dena chahiye. In ke jawab khud bhi parho (PASS ke bawajood).
"""
import time

from rag import answer as _answer


def answer(q):
    """Ek sawal fail ho to poora test band na ho."""
    try:
        return _answer(q)
    except Exception as exc:  # noqa: BLE001
        return {"answer": f"[ERROR] {type(exc).__name__}: {str(exc)[:120]}", "sources": []}


PHONE = "0300-1234567"

# (question, [expected keywords]) -- koi ek keyword mil jaye to PASS
ANSWERABLE = [
    ("Clinic kahan hai?", ["F-10", "Al-Noor"]),
    ("Scaling ki fees kitni hai?", ["4,000", "4000"]),
    ("What are your clinic timings?", ["9:00", "9 AM", "8:00", "8 PM"]),
    ("Sunday ko clinic khula hota hai?", ["closed", "band", "emergency"]),
    ("Do you have a lady dentist?", ["Sana", "Ayesha"]),
    ("Braces kitne ke hain?", ["90,000", "120,000", "150,000"]),
    ("Root canal mein kitna time lagta hai?", ["1-2", "one to two", "do visits", "1 se 2"]),
    ("Kya aap installments mein payment lete hain?", ["40%", "installment"]),
    ("Student discount milta hai?", ["10%"]),
    ("Tooth extraction ke baad kya karna chahiye?", ["gauze", "24"]),
    ("Dant toot kar gir gaya, kya karun?", ["milk", "doodh", "30"]),
    ("Who is the orthodontist and when is he available?", ["Hamza", "Monday", "Wednesday"]),
    ("Kya bachon ka ilaj hota hai?", ["Ayesha", "age 2", "2 saal", "2"]),
    ("Appointment cancel karne ki policy kya hai?", ["4 hours", "4 ghante", "4 ghanton"]),
    ("Which payment methods do you accept?", ["JazzCash", "Easypaisa", "cash", "Cash"]),
    ("Implant ki warranty kitni hai?", ["5 year", "5 saal"]),
]

# Jawab docs mein nahi hai -> bot ko phone number dena chahiye (guess nahi)
OUT_OF_SCOPE = [
    "Kya aap LASIK eye surgery karte hain?",
    "Dr. Ahmed ki fees kitni hai?",
    "Who is the prime minister of Pakistan?",
    "Mere daant mein dard hai, kya mujhe cavity hai? Pakka bata do.",
]


def main():
    passed, total = 0, len(ANSWERABLE) + len(OUT_OF_SCOPE)

    print("=== Answerable questions ===")
    for q, keys in ANSWERABLE:
        res = answer(q)
        ok = any(k.lower() in res["answer"].lower() for k in keys)
        passed += ok
        print(f"[{'PASS' if ok else 'FAIL'}] {q}\n   -> {res['answer']}\n   sources: {res['sources']}\n")
        time.sleep(4)  # free tier ki per-minute limit se bachne ke liye

    print("=== Out-of-scope / trick questions ===")
    for q in OUT_OF_SCOPE:
        res = answer(q)
        ok = PHONE in res["answer"]
        passed += ok
        print(f"[{'PASS' if ok else 'CHECK'}] {q}\n   -> {res['answer']}\n")
        time.sleep(4)

    print(f"Score: {passed}/{total}")


if __name__ == "__main__":
    main()
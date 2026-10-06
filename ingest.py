"""Ingestion: knowledge/ ke documents -> chunks -> embeddings -> Chroma.

Chalane ka tareeqa:  python ingest.py
Documents badlo to dobara chalao (purani DB replace ho jati hai).
"""
from chunker import load_and_chunk
from rag import BASE_DIR, EMBED_MODEL, embed, get_collection

BATCH = 50


def main():
    chunks = load_and_chunk(BASE_DIR / "knowledge")
    if not chunks:
        raise SystemExit("knowledge/ folder mein koi .md file nahi mili.")

    print(f"{len(chunks)} chunks bane. Embeddings ({EMBED_MODEL}) ban rahi hain...")
    collection = get_collection(create=True)

    for start in range(0, len(chunks), BATCH):
        batch = chunks[start : start + BATCH]
        vectors = embed([c["text"] for c in batch], "RETRIEVAL_DOCUMENT")
        collection.add(
            ids=[f"chunk-{start + i}" for i in range(len(batch))],
            documents=[c["text"] for c in batch],
            embeddings=vectors,
            metadatas=[{"source": c["source"], "heading": c["heading"]} for c in batch],
        )

    print(f"Done. {collection.count()} chunks Chroma mein save ho gaye.")
    per_file = {}
    for c in chunks:
        per_file[c["source"]] = per_file.get(c["source"], 0) + 1
    for name, n in per_file.items():
        print(f"  {name}: {n} chunks")


if __name__ == "__main__":
    main()

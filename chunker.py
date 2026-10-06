"""Markdown documents ko chhote, meaningful chunks mein todta hai.

Strategy:
- Har document ko "## " headings ke hisaab se sections mein todo.
- Har chunk ke shuru mein document title + section heading lagao,
  taake chunk akela bhi samajh aaye (e.g. "Fees ... | Payment methods").
- Bara section ho to lines ke groups mein todo (MAX_CHARS tak).
"""
from pathlib import Path

MAX_CHARS = 900


def _split_long(lines, max_chars):
    """Lines ko groups mein baanto, har group max_chars se chhota."""
    groups, current, size = [], [], 0
    for line in lines:
        if current and size + len(line) > max_chars:
            groups.append(current)
            current, size = [], 0
        current.append(line)
        size += len(line) + 1
    if current:
        groups.append(current)
    return groups


def chunk_markdown(text, source):
    lines = text.splitlines()
    title = source
    sections = []  # (heading, [lines])
    heading, body = "Overview", []

    for line in lines:
        if line.startswith("# ") and title == source:
            title = line[2:].strip()
        elif line.startswith("## "):
            if any(l.strip() for l in body):
                sections.append((heading, body))
            heading, body = line[3:].strip(), []
        else:
            body.append(line)
    if any(l.strip() for l in body):
        sections.append((heading, body))

    chunks = []
    for heading, body in sections:
        body = [l for l in body if l.strip()]
        for group in _split_long(body, MAX_CHARS):
            header = f"{title} | {heading}"
            chunks.append(
                {
                    "text": header + "\n" + "\n".join(group),
                    "source": source,
                    "heading": heading,
                }
            )
    return chunks


def load_and_chunk(folder):
    all_chunks = []
    for path in sorted(Path(folder).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        all_chunks.extend(chunk_markdown(text, path.name))
    return all_chunks

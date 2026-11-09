import csv
import io
import re
import textwrap

MAX_CHARS = 900     # a chunk never grows past this
MIN_CHARS = 250     # a topic shift only splits a chunk that is at least this long
TAIL_MIN = 120      # a tiny leftover is merged into the previous chunk

SENT_SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\'(\[])')
PAGE_NOISE = re.compile(r"^\W*(page\s+\d+(\s+of\s+\d+)?|\d+)\W*$|[-|]\s*page\s+\d+(\s+of\s+\d+)?\s*$",
                        re.IGNORECASE)
BULLET = re.compile(r"^([-*\u2022]|\d+[.)])\s+")
NUMBERED = re.compile(r"^(\d+(\.\d+)*[.)]?|section|chapter|article|appendix)\s+\S", re.IGNORECASE)


def is_heading(line):
    s = line.strip()
    if not s or len(s) > 80 or s[-1] in ".!?;,":
        return False
    words = s.split()
    if len(words) > 10:
        return False
    if s.endswith(":") or (s.isupper() and len(words) <= 8):
        return True
    if NUMBERED.match(s) and len(words) <= 8:
        return True
    return s.istitle()


def split_sentences(paragraph):
    parts, carry = [], ""
    for s in SENT_SPLIT.split(paragraph.strip()):
        s = (carry + " " + s).strip() if carry else s.strip()
        carry = ""
        if re.fullmatch(r"\d+[.)]", s):          # "1." belongs to the next sentence
            carry = s
        elif s:
            parts.append(s)
    if carry:
        parts.append(carry)
    out = []
    for s in parts:
        out.extend(textwrap.wrap(s, 600) if len(s) > 600 else [s])
    return out


def page_units(text, section=""):
    """Turn one page into (section, sentence) units. Returns (units, last_section)."""
    units, buf = [], []

    def flush():
        if buf:
            for s in split_sentences(" ".join(buf)):
                units.append((section, s))
            buf.clear()

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        if PAGE_NOISE.search(line):          # running headers and page numbers
            continue
        if is_heading(line):
            flush()
            section = line
            continue
        if BULLET.match(line):
            flush()
        buf.append(line)
    flush()
    return units, section


def build_chunks(units, sims=None):
    """Group sentences into chunks that follow the document's structure and topics.

    units: list of (section, sentence)
    sims:  sims[i] is the similarity between sentence i and i+1 (None = size and
           section rules only). The weakest 20 percent of links are topic shifts.
    """
    threshold = None
    if sims and len(sims) >= 6:
        ordered = sorted(sims)
        threshold = ordered[max(0, int(len(ordered) * 0.20) - 1)]

    chunks, cur, size, section = [], [], 0, None
    for i, (sec, sent) in enumerate(units):
        if cur:
            too_big = size + len(sent) + 1 > MAX_CHARS
            new_section = sec != section
            topic_shift = (threshold is not None and size >= MIN_CHARS
                           and sims[i - 1] <= threshold)
            if too_big or new_section or topic_shift:
                chunks.append((section, " ".join(cur)))
                cur, size = [], 0
        if not cur:
            section = sec
        cur.append(sent)
        size += len(sent) + 1
    if cur:
        chunks.append((section, " ".join(cur)))

    merged = []
    for sec, txt in chunks:
        if (merged and len(txt) < TAIL_MIN and merged[-1][0] == sec
                and len(merged[-1][1]) + len(txt) + 1 <= MAX_CHARS + 200):
            merged[-1] = (sec, merged[-1][1] + " " + txt)
        else:
            merged.append((sec, txt))
    return merged


def csv_chunks(raw, rows_per_chunk=12):
    """Tables are chunked by row groups, and every chunk repeats the header."""
    rows = [r for r in csv.reader(io.StringIO(raw)) if any(c.strip() for c in r)]
    if not rows:
        return []
    header_line = ", ".join(rows[0])
    body = rows[1:]
    if not body:
        return [("Header", header_line)]
    out = []
    for i in range(0, len(body), rows_per_chunk):
        group = body[i:i + rows_per_chunk]
        lines = [header_line] + [", ".join(r) for r in group]
        out.append((f"Rows {i + 1}-{i + len(group)}", "\n".join(lines)))
    return out
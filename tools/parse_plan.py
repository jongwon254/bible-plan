"""
Parses tools/raw_plan.txt (the church's Korean gospel-harmony reading plan,
pasted as-is) into data/plan.json for the web app.

Usage: paste new weeks at the end of raw_plan.txt (same ☆ M월 D일(요일) format),
then run: python3 tools/parse_plan.py
Review the printed summary/flags before committing — this does light typo
cleanup (missing colons, semicolon-for-colon typos) but never invents verse
numbers; anything it can't parse confidently is printed under FLAGGED.
"""
import re, json, datetime, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_PATH = os.path.join(BASE, "tools", "raw_plan.txt")
OUT_PATH = os.path.join(BASE, "data", "plan.json")

YEAR = 2026  # bump this if/when the plan crosses into a new year

BOOKS = "마태복음|누가복음|마가복음|요한복음|마태|마가|누가|요한|마|막|눅|요"
BOOK_START_RE = re.compile(r'^(' + BOOKS + r')\s*\d')
BOOK_MATCH_RE = re.compile(r'^(' + BOOKS + r')\s*(.*)$', re.DOTALL)
HEADER_RE = re.compile(r'☆\s*(\d{1,2})월\s*(\d{1,2})일?\s*\(\s*([^)]*?)\s*\)')
SPLIT_RE = re.compile(r'[,;]|\.\s+(?=(?:' + BOOKS + r'))')
PAREN_RE = re.compile(r'\(([^()]*)\)')


def normalize_ref(chunk):
    chunk = chunk.strip()
    note = None
    m = PAREN_RE.search(chunk)
    if m:
        note = m.group(1).strip()
        chunk = (chunk[:m.start()] + chunk[m.end():]).strip()
    chunk = chunk.replace(')', '').replace('(', '').strip()
    bm = BOOK_MATCH_RE.match(chunk)
    if not bm:
        return chunk, note, True
    book, rest = bm.group(1), bm.group(2).strip()
    rest = re.sub(r'\s*:\s*', ':', rest)
    rest = re.sub(r'\s*-\s*', '-', rest)
    if ':' not in rest:
        rest = re.sub(r'(\d)\s+(\d)', r'\1:\2', rest, count=1)
    if ':' not in rest and re.match(r'^\d+-\d+-\d+$', rest):
        rest = re.sub(r'^(\d+)-(\d+-\d+)$', r'\1:\2', rest)
    rest = re.sub(r'\s+', '', rest)
    flagged = (rest == '' or rest.startswith('-') or ':-' in rest)
    return book + rest, note, flagged


def parse_line_items(line):
    line = line.strip()
    line = re.sub(r'^\*+\s*', '', line)
    line = re.sub(r'(?<=\d);(?=\d)', ':', line)
    if not line:
        return []
    items = []
    if BOOK_START_RE.match(line):
        for p in SPLIT_RE.split(line):
            p = p.strip()
            if not p:
                continue
            if BOOK_START_RE.match(p):
                ref, note, flagged = normalize_ref(p)
                entry = {"type": "verse", "ref": ref}
                if note:
                    entry["note"] = note
                items.append((entry, flagged, p))
            else:
                items.append(({"type": "note", "text": p}, False, p))
    else:
        items.append(({"type": "note", "text": line}, False, line))
    return items


def main():
    raw = open(RAW_PATH, encoding='utf-8').read()
    matches = list(HEADER_RE.finditer(raw))
    days = []
    flags = []
    for i, m in enumerate(matches):
        month, day = int(m.group(1)), int(m.group(2))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        body = raw[start:end].lstrip()
        body = re.sub(r'^\)+\s*', '', body)
        items = []
        for l in body.split('\n'):
            for entry, flagged, raw_txt in parse_line_items(l):
                items.append(entry)
                if flagged:
                    flags.append((month, day, raw_txt, entry.get("ref")))
        date = datetime.date(YEAR, month, day)
        weekday = ["월", "화", "수", "목", "금", "토", "주일"][date.weekday()]
        days.append({
            "date": date,
            "id": date.isoformat(),
            "month": month,
            "day": day,
            "weekday": weekday,
            "items": items,
        })

    # Weeks run Sunday-Saturday. Week 1 starts on the Sunday on/before the
    # first day in the data, so a partial first week still counts as week 1.
    if days:
        first_date = days[0]["date"]
        anchor_sunday = first_date - datetime.timedelta(days=(first_date.weekday() + 1) % 7)
        for d in days:
            d["week"] = (d["date"] - anchor_sunday).days // 7 + 1
            del d["date"]

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(days, f, ensure_ascii=False, indent=2)

    total_verses = sum(1 for d in days for it in d["items"] if it["type"] == "verse")
    print(f"Parsed {len(days)} days, {total_verses} verse items -> {OUT_PATH}")
    if flags:
        print("\n=== FLAGGED for manual review (not auto-fixed) ===")
        for month, day, raw_txt, ref in flags:
            print(f"{month}/{day}: raw={raw_txt!r} -> parsed={ref!r}")


if __name__ == "__main__":
    main()

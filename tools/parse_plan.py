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

BOOKS = "마태복음|누가복음|마가복음|요한복음|사도행전|살전|살후|고전|고후|마태|마가|누가|요한|마|막|눅|요|행|갈|롬|골"
BOOK_START_RE = re.compile(r'^(' + BOOKS + r')\s*\d')
BOOK_MATCH_RE = re.compile(r'^(' + BOOKS + r')\s*(.*)$', re.DOTALL)
# Weekday parenthetical is optional — some entries in the source omit it entirely.
HEADER_RE = re.compile(r'☆\s*(\d{1,2})월\s*(\d{1,2})일?\s*(?:\(\s*[^)]*?\s*\))?')
SPLIT_RE = re.compile(r'[,;]|\.\s+(?=(?:' + BOOKS + r'))')
PAREN_RE = re.compile(r'\(([^()]*)\)')
# A verse continuing the previous item's book without restating it, e.g.
# "행7:1-8:13, 8:26-40" — the second chunk inherits 행 from the first.
BARE_REF_RE = re.compile(r'^\d+[:\-]')
# "행16,17,18장" is one whole-chapter reference written as a comma list.
CHAPTER_LIST_RE = re.compile(r'(?<![\w가-힣])(' + BOOKS + r')\s*(\d+(?:\s*,\s*\d+)+)\s*장')
# Hangul + digit that isn't a known book (e.g. a book abbreviation missing from
# BOOKS) would silently become a note, so flag it for review instead.
UNKNOWN_BOOK_RE = re.compile(r'^[가-힣]{1,3}\s*\d')

# Canonical chapter counts, for catching typos like "행26-29장" (Acts has 28).
CANON_BOOK = {
    "마태복음": "마", "마태": "마", "마": "마",
    "마가복음": "막", "마가": "막", "막": "막",
    "누가복음": "눅", "누가": "눅", "눅": "눅",
    "요한복음": "요", "요한": "요", "요": "요",
    "사도행전": "행", "행": "행",
    "갈": "갈", "롬": "롬", "골": "골",
    "살전": "살전", "살후": "살후", "고전": "고전", "고후": "고후",
}
BOOK_MAX_CHAPTER = {
    "마": 28, "막": 16, "눅": 24, "요": 21, "행": 28, "롬": 16,
    "고전": 16, "고후": 13, "갈": 6, "살전": 5, "살후": 3, "골": 4,
}


def chapters_in(rest):
    """Chapter numbers referenced by an already-normalized ref's non-book part."""
    chapters = []
    for i, part in enumerate(rest.split('-')):
        m = re.match(r'^(\d+):', part) or re.match(r'^(\d+)장', part)
        if not m and i == 0 and re.match(r'^\d+$', part):
            m = re.match(r'^(\d+)$', part)
        if m:
            chapters.append(int(m.group(1)))
    return chapters


def collapse_chapter_list(m):
    book = m.group(1)
    nums = [int(n) for n in re.split(r'\s*,\s*', m.group(2))]
    if nums == list(range(nums[0], nums[0] + len(nums))):
        return f"{book}{nums[0]}-{nums[-1]}장"
    return ", ".join(f"{book}{n}장" for n in nums)


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
    # Commentary written right after a ref without parentheses ("눅1:1-4 누가는 ...")
    # becomes the note; only 장 (chapter) is a legitimate hangul char in a ref.
    tail_idx = next((i for i, ch in enumerate(rest) if '가' <= ch <= '힣' and ch != '장'), None)
    if tail_idx is not None:
        tail = rest[tail_idx:].strip()
        rest = rest[:tail_idx]
        note = f"{tail} ({note})" if note else tail
    rest = re.sub(r'\s*:\s*', ':', rest)
    rest = re.sub(r'\s*-\s*', '-', rest)
    if ':' not in rest:
        rest = re.sub(r'(\d)\s+(\d)', r'\1:\2', rest, count=1)
    if ':' not in rest and re.match(r'^\d+-\d+-\d+$', rest):
        rest = re.sub(r'^(\d+)-(\d+-\d+)$', r'\1:\2', rest)
    rest = re.sub(r'\s+', '', rest).rstrip('.,;')
    # A 4+ digit number can't be a chapter/verse, so it's a typo like "2122" for "21-22".
    flagged = (rest == '' or rest.startswith('-') or ':-' in rest or re.search(r'\d{4,}', rest) is not None)
    return book + rest, note, flagged


def parse_line_items(line, state):
    line = line.strip()
    line = re.sub(r'^\*+\s*', '', line)
    line = re.sub(r'(?<=\d);(?=\d)', ':', line)
    line = CHAPTER_LIST_RE.sub(collapse_chapter_list, line)
    if not line:
        return []
    items = []
    if BOOK_START_RE.match(line) or (state["last_book"] and BARE_REF_RE.match(line)):
        for p in SPLIT_RE.split(line):
            p = p.strip()
            if not p:
                continue
            if BOOK_START_RE.match(p):
                state["last_book"] = BOOK_MATCH_RE.match(p).group(1)
                ref, note, flagged = normalize_ref(p)
                entry = {"type": "verse", "ref": ref}
                if note:
                    entry["note"] = note
                items.append((entry, flagged, p))
            elif state["last_book"] and BARE_REF_RE.match(p):
                ref, note, flagged = normalize_ref(state["last_book"] + p)
                entry = {"type": "verse", "ref": ref}
                if note:
                    entry["note"] = note
                items.append((entry, flagged, p))
            else:
                items.append(({"type": "note", "text": p}, bool(UNKNOWN_BOOK_RE.match(p)), p))
    else:
        items.append(({"type": "note", "text": line}, bool(UNKNOWN_BOOK_RE.match(line)), line))
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
        state = {"last_book": None}
        for l in body.split('\n'):
            for entry, flagged, raw_txt in parse_line_items(l, state):
                items.append(entry)
                if flagged:
                    flags.append((month, day, raw_txt, entry.get("ref")))
                elif entry["type"] == "verse":
                    bm = BOOK_MATCH_RE.match(entry["ref"])
                    canon = CANON_BOOK.get(bm.group(1)) if bm else None
                    max_ch = BOOK_MAX_CHAPTER.get(canon)
                    if max_ch:
                        bad = [c for c in chapters_in(bm.group(2)) if c < 1 or c > max_ch]
                        if bad:
                            flags.append((month, day, raw_txt,
                                          f"{entry['ref']} (chapter {bad[0]} > {canon} has {max_ch})"))
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

    # Weeks run Monday-Sunday (주일 closes each week, matching how the plan is
    # published). Week 1 starts on the Monday on/before the first day in the data.
    if days:
        first_date = days[0]["date"]
        anchor_monday = first_date - datetime.timedelta(days=first_date.weekday())
        for d in days:
            d["week"] = (d["date"] - anchor_monday).days // 7 + 1
            del d["date"]

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(days, f, ensure_ascii=False, indent=2)

    total_verses = sum(1 for d in days for it in d["items"] if it["type"] == "verse")
    print(f"Parsed {len(days)} days, {total_verses} verse items -> {OUT_PATH}")
    if flags:
        print("\n=== FLAGGED for manual review (not auto-fixed) ===")
        for month, day, raw_txt, ref in flags:
            print(f"{month}/{day}: raw={raw_txt!r} -> parsed={ref or '(kept as a note)'!r}")


if __name__ == "__main__":
    main()

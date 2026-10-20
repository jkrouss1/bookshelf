"""Find a cover for every book in the Google Sheet and save it to covers.json.

Run by .github/workflows/covers.yml every night. Books that already have a cover
are skipped, and each run stops after TIME_BUDGET, so a big backlog is worked
through over several runs and after that only new books are looked up.
Keys match coverKey() in index.html: normalized title | normalized first author.
"""
import csv
import io
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import requests
from PIL import Image

SHEET_ID = "1EcfuNdzY2i5wm-A5EJX2JzTOrFweOu60p0o1zfDDSAY"
SHEET_CSV = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Bookshelf&range=B5:F&headers=0"
OUT = Path(__file__).resolve().parent.parent / "covers.json"
RETRY_NONE_AFTER = 30 * 86400 * 1000  # ms, same as the page
TIME_BUDGET = 40 * 60  # seconds
HEADERS = {"User-Agent": "krouss.org bookshelf (cover lookup)"}


def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def get_json(url, params):
    for attempt in range(3):
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if r.status_code == 429:
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()
    return {}


def find_cover(title, author):
    d = get_json("https://openlibrary.org/search.json", {"title": title, "author": author, "limit": 3, "fields": "cover_i"})
    for doc in d.get("docs", []):
        if doc.get("cover_i"):
            return f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-M.jpg"
    d = get_json("https://www.googleapis.com/books/v1/volumes",
                 {"q": f"intitle:{title} inauthor:{author}", "maxResults": 3, "fields": "items(volumeInfo/imageLinks)"})
    for item in d.get("items", []):
        thumb = item.get("volumeInfo", {}).get("imageLinks", {}).get("thumbnail")
        if thumb:
            return thumb.replace("http:", "https:", 1).replace("&edge=curl", "")
    return None


def spine_color(src):
    """Average color of the cover's left edge, which is usually what the spine looks like."""
    r = requests.get(src, headers=HEADERS, timeout=15)
    r.raise_for_status()
    img = Image.open(io.BytesIO(r.content)).convert("RGB")
    if img.width < 10:
        return None, None
    strip = img.crop((0, 0, max(2, int(img.width * 0.08)), img.height)).resize((1, 1), Image.Resampling.BOX)
    red, green, blue = strip.getpixel((0, 0))
    lum = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255
    return f"#{red:02x}{green:02x}{blue:02x}", ("#1f1a14" if lum > 0.6 else "#f6efe2")


def save(covers):
    OUT.write_text(json.dumps(covers, indent=0, sort_keys=True, ensure_ascii=False))


def main():
    covers = json.loads(OUT.read_text()) if OUT.exists() else {}
    text = requests.get(SHEET_CSV, headers=HEADERS, timeout=30).text
    books = {}
    for row in csv.reader(io.StringIO(text)):
        title, author = (row + ["", ""])[0].strip(), (row + ["", ""])[1].strip()
        if not title or title == "Title":
            continue
        main_title = re.split(r":\s+", title)[0].strip()
        first_author = author.split(",")[0].strip()
        books[norm(title) + "|" + norm(first_author)] = (main_title, first_author)

    start = time.time()
    now = int(start * 1000)
    found = missing = 0
    for i, (key, (title, author)) in enumerate(books.items()):
        if time.time() - start > TIME_BUDGET:
            print("time budget reached; the next run continues from here", flush=True)
            break
        entry = covers.get(key)
        if entry and entry.get("src") and "color" in entry:
            continue
        if entry and entry.get("none") and now - entry["none"] < RETRY_NONE_AFTER:
            continue
        try:
            src = (entry or {}).get("src") or find_cover(title, author)
            if src:
                color, ink = spine_color(src)
                covers[key] = {"src": src, "color": color, "ink": ink}
                found += 1
            else:
                covers[key] = {"none": now}
                missing += 1
        except Exception as e:  # one bad book shouldn't stop the run
            print(f"skip {title!r}: {e}", file=sys.stderr)
        time.sleep(1)  # be polite to Open Library
        if (found + missing) % 25 == 0:
            save(covers)
            print(f"{i + 1}/{len(books)} checked · {found} covers added", flush=True)

    save(covers)
    print(f"{len(books)} books · {found} covers added · {missing} with no cover found")


if __name__ == "__main__":
    main()

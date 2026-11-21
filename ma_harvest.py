"""
Импорт каталога Encyclopaedia Metallum (metal-archives.com) — все метал-группы мира.
1) алфавитные списки: название, страна, жанр, статус
2) расширенный поиск по годам: год основания
Результат: таблица ma_band в rock.db (затем merge.py объединяет с Wikidata).
"""
import json, re, sqlite3, sys, time, html, concurrent.futures as cf
import requests

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
S = requests.Session(); S.headers.update({"User-Agent": UA, "Accept": "application/json, text/javascript, */*"})
BASE = "https://www.metal-archives.com"

db = sqlite3.connect("rock.db", timeout=60)
db.executescript("""
CREATE TABLE IF NOT EXISTS ma_band(ma_id INTEGER PRIMARY KEY, name TEXT, url TEXT, country TEXT, genre TEXT,
  status TEXT, formed INTEGER);
CREATE TABLE IF NOT EXISTS ma_progress(key TEXT PRIMARY KEY);
""")

import subprocess
def curl(url):
    p = subprocess.run(["curl", "-s", "-m", "60", "-A", UA, "-w", "\n%{http_code}", url], capture_output=True, text=True)
    body, _, code = p.stdout.rpartition("\n")
    return int(code or 0), body

def get(url, tries=8):
    # metal-archives блокирует python-клиенты по TLS-отпечатку, поэтому используем curl
    for i in range(tries):
        try:
            code, text = curl(url)
            if code == 200:
                return json.loads(text, strict=False)
            print("HTTP", code, url[:120], file=sys.stderr, flush=True)
            time.sleep(4 * (i + 1))
        except Exception as e:
            print("ERR", e, file=sys.stderr, flush=True); time.sleep(4 * (i + 1))
    return None

A_RE = re.compile(r"""<a href=['"]([^'"]+/bands/[^'"]+/(\d+))['"]>(.*?)</a>""", re.S)
strip = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()

def done(key): return db.execute("select 1 from ma_progress where key=?", (key,)).fetchone()
def mark(key): db.execute("insert or ignore into ma_progress values(?)", (key,)); db.commit()

# ---------- 1. алфавит ----------
letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["NBR", "~"]
def letter_pages(L):
    first = get(f"{BASE}/browse/ajax-letter/l/{L}/json/1?sEcho=1&iDisplayStart=0&iDisplayLength=500")
    if not first: return []
    tot = first["iTotalRecords"]
    return [(L, s) for s in range(0, tot, 500)]

jobs = []
for L in letters:
    for job in letter_pages(L):
        if not done(f"L:{job[0]}:{job[1]}"): jobs.append(job)
print("Страниц алфавита:", len(jobs), flush=True)

def fetch_letter(job):
    L, s = job
    time.sleep(0.3)
    return job, get(f"{BASE}/browse/ajax-letter/l/{L}/json/1?sEcho=1&iDisplayStart={s}&iDisplayLength=500")

n = 0
with cf.ThreadPoolExecutor(3) as ex:
    for job, d in ex.map(fetch_letter, jobs):
        if not d: continue
        for row in d["aaData"]:
            m = A_RE.search(row[0])
            if not m: continue
            url, mid, name = m.group(1), int(m.group(2)), strip(m.group(3))
            db.execute("""INSERT INTO ma_band(ma_id,name,url,country,genre,status) VALUES(?,?,?,?,?,?)
                          ON CONFLICT(ma_id) DO UPDATE SET name=excluded.name,url=excluded.url,country=excluded.country,
                          genre=excluded.genre,status=excluded.status""",
                       (mid, name, url, strip(row[1]), strip(row[2]), strip(row[3])))
        mark(f"L:{job[0]}:{job[1]}")
        n += 1
        if n % 20 == 0: print(f"  алфавит {n}/{len(jobs)}", flush=True)
print("Групп MA:", db.execute("select count(*) from ma_band").fetchone()[0], flush=True)

# ---------- 2. годы основания ----------
# расширенный поиск MA строго ограничивает частоту — идём последовательно с адаптивной паузой
def year_url(y, s):
    return (f"{BASE}/search/ajax-advanced/searching/bands/?bandName=&yearCreationFrom={y}&yearCreationTo={y}"
            f"&iDisplayStart={s}&iDisplayLength=200&sEcho=1")
delay = 1.5
def yget(url):
    global delay
    for i in range(30):
        time.sleep(delay)
        code, text = curl(url)
        if code == 200:
            delay = max(1.2, delay * 0.97)
            return json.loads(text, strict=False)
        if code == 429:
            delay = min(10, delay * 1.3)
            time.sleep(15 + 5 * i)
        else:
            time.sleep(5)
    return None

def save(rows, y):
    for row in rows:
        m = A_RE.search(row[0])
        if m: db.execute("UPDATE ma_band SET formed=? WHERE ma_id=?", (y, int(m.group(2))))

for y in range(1955, 2027):
    if done(f"Y:{y}"): continue
    d = yget(year_url(y, 0))
    if not d: continue
    save(d["aaData"], y); mark(f"Y:{y}:0")
    for s0 in range(200, d["iTotalRecords"], 200):
        if done(f"Y:{y}:{s0}"): continue
        dd = yget(year_url(y, s0))
        if dd: save(dd["aaData"], y); mark(f"Y:{y}:{s0}")
    mark(f"Y:{y}")
    print(f"  год {y}: {db.execute('select count(*) from ma_band where formed=?', (y,)).fetchone()[0]} групп, пауза {delay:.1f}s", flush=True)
print("С годом:", db.execute("select count(*) from ma_band where formed is not null").fetchone()[0])
print("ГОТОВО MA")

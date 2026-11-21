"""
Сборщик базы данных рок/метал-групп из Wikidata.
Источник: https://query.wikidata.org (открытые данные, CC0).
Создаёт SQLite-базу rock.db
"""
import csv, io, json, sqlite3, sys, time, concurrent.futures as cf
import requests

EP = "https://query.wikidata.org/sparql"
UA = "RockCatalogBot/1.0 (educational project; python-requests)"
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept": "application/sparql-results+json"})

def sparql(q, tries=6):
    for i in range(tries):
        try:
            r = S.post(EP, data={"query": q}, timeout=120)
            if r.status_code == 200:
                return json.loads(r.text, strict=False)["results"]["bindings"]
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(5 * (i + 1)); continue
            print("HTTP", r.status_code, r.text[:300], file=sys.stderr)
            time.sleep(3)
        except Exception as e:
            print("ERR", e, file=sys.stderr); time.sleep(5 * (i + 1))
    return []

qid = lambda u: u.rsplit("/", 1)[-1]
v = lambda row, k: row[k]["value"] if k in row else None

def year(s):
    if not s: return None
    try:
        s = s.lstrip("+")
        y = int(s.split("-")[0]) if not s.startswith("-") else None
        return y
    except Exception:
        return None

db = sqlite3.connect("rock.db", timeout=60)
db.executescript("""
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS genre(id TEXT PRIMARY KEY, name_ru TEXT, name_en TEXT, parent TEXT);
CREATE TABLE IF NOT EXISTS band(
  id TEXT PRIMARY KEY, name TEXT, name_ru TEXT, name_en TEXT, desc_ru TEXT, desc_en TEXT,
  formed INTEGER, dissolved INTEGER, country TEXT, country_id TEXT, origin TEXT,
  image TEXT, logo TEXT, website TEXT, wiki_ru TEXT, wiki_en TEXT, mbid TEXT,
  sitelinks INTEGER DEFAULT 0, labels TEXT, n_members INTEGER DEFAULT 0, done INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS band_genre(band TEXT, genre TEXT, PRIMARY KEY(band, genre));
CREATE TABLE IF NOT EXISTS person(
  id TEXT PRIMARY KEY, name TEXT, name_ru TEXT, name_en TEXT, born INTEGER, died INTEGER,
  image TEXT, instruments TEXT, wiki_en TEXT, wiki_ru TEXT);
CREATE TABLE IF NOT EXISTS membership(band TEXT, person TEXT, start INTEGER, end INTEGER,
  PRIMARY KEY(band, person));
CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, value TEXT, ts INTEGER);
""")

# ---------- 1. жанры ----------
print("Жанры...")
rows = sparql("""
SELECT ?g ?ru ?en ?p WHERE {
  ?g wdt:P279* wd:Q11399 .
  OPTIONAL { ?g rdfs:label ?ru FILTER(lang(?ru)='ru') }
  OPTIONAL { ?g rdfs:label ?en FILTER(lang(?en)='en') }
  OPTIONAL { ?g wdt:P279 ?p . ?p wdt:P279* wd:Q11399 }
}""")
for r in rows:
    db.execute("INSERT OR REPLACE INTO genre VALUES(?,?,?,?)",
               (qid(v(r, "g")), v(r, "ru"), v(r, "en"), qid(v(r, "p")) if v(r, "p") else None))
db.commit()
print(" жанров:", db.execute("select count(*) from genre").fetchone()[0])

# ---------- 2. группы и их жанры ----------
print("Группы x жанры...")
rows = sparql("""
SELECT DISTINCT ?b ?g WHERE {
  ?g wdt:P279* wd:Q11399 . ?b wdt:P136 ?g . ?b wdt:P31/wdt:P279* wd:Q215380 .
}""")
bands = set()
for r in rows:
    b, g = qid(v(r, "b")), qid(v(r, "g"))
    bands.add(b)
    db.execute("INSERT OR IGNORE INTO band(id) VALUES(?)", (b,))
    db.execute("INSERT OR IGNORE INTO band_genre VALUES(?,?)", (b, g))
db.commit()
print(" групп:", len(bands))

# ---------- 3. детали групп ----------
todo = [r[0] for r in db.execute("select id from band where done=0")]
print("К обработке:", len(todo))

def details(batch):
    vals = " ".join("wd:" + b for b in batch)
    info = sparql(f"""
SELECT ?b ?ru ?en ?bLabel ?dru ?den ?wru ?wen ?sl WHERE {{
  VALUES ?b {{ {vals} }}
  OPTIONAL {{ ?b rdfs:label ?ru FILTER(lang(?ru)='ru') }}
  OPTIONAL {{ ?b rdfs:label ?en FILTER(lang(?en)='en') }}
  OPTIONAL {{ ?b schema:description ?dru FILTER(lang(?dru)='ru') }}
  OPTIONAL {{ ?b schema:description ?den FILTER(lang(?den)='en') }}
  OPTIONAL {{ ?wru schema:about ?b ; schema:isPartOf <https://ru.wikipedia.org/> }}
  OPTIONAL {{ ?wen schema:about ?b ; schema:isPartOf <https://en.wikipedia.org/> }}
  OPTIONAL {{ ?b wikibase:sitelinks ?sl }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,mul,ru,de,fr,es,it,pt,sv,fi,no,pl,ja,uk,cs,nl" . }}
}}""")
    info += sparql(f"""
SELECT ?b ?inc ?dis ?c ?cLabel ?oLabel ?img ?logo ?web ?mb WHERE {{
  VALUES ?b {{ {vals} }}
  OPTIONAL {{ ?b wdt:P571 ?inc }}
  OPTIONAL {{ ?b wdt:P576 ?dis }}
  OPTIONAL {{ ?b wdt:P495 ?c }}
  OPTIONAL {{ ?b wdt:P740 ?o }}
  OPTIONAL {{ ?b wdt:P18 ?img }}
  OPTIONAL {{ ?b wdt:P154 ?logo }}
  OPTIONAL {{ ?b wdt:P856 ?web }}
  OPTIONAL {{ ?b wdt:P434 ?mb }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "ru,en,mul" . }}
}}""")
    labels = sparql(f"""
SELECT ?b (GROUP_CONCAT(DISTINCT ?ln; separator='|') AS ?l) WHERE {{
  VALUES ?b {{ {vals} }}
  ?b wdt:P264 ?lab . ?lab rdfs:label ?ln FILTER(lang(?ln)='en')
}} GROUP BY ?b""")
    mem = sparql(f"""
SELECT DISTINCT ?b ?p ?s ?e WHERE {{ VALUES ?b {{ {vals} }} ?b p:P527 ?st . ?st ps:P527 ?p . ?p wdt:P31 wd:Q5 .
  OPTIONAL {{ ?st pq:P580 ?s }} OPTIONAL {{ ?st pq:P582 ?e }} }}""")
    mem += sparql(f"""
SELECT DISTINCT ?b ?p ?s ?e WHERE {{ VALUES ?b {{ {vals} }} ?st ps:P463 ?b . ?p p:P463 ?st . ?p wdt:P31 wd:Q5 .
  OPTIONAL {{ ?st pq:P580 ?s }} OPTIONAL {{ ?st pq:P582 ?e }} }}""")
    return batch, info, labels, mem

def first_text(lst):
    for x in lst:
        if x: return x
    return None

persons_needed = set()
batches = [todo[i:i + 200] for i in range(0, len(todo), 200)]
done = 0
with cf.ThreadPoolExecutor(4) as ex:
    for batch, info, labels, mem in ex.map(details, batches):
        agg = {}
        for r in info:
            b = qid(v(r, "b"))
            a = agg.setdefault(b, {})
            for k in ["ru", "en", "bLabel", "dru", "den", "inc", "dis", "c", "cLabel", "oLabel",
                      "img", "logo", "web", "wru", "wen", "mb", "sl"]:
                if k not in a and v(r, k):
                    a[k] = v(r, k)
            # минимальный год основания
            if v(r, "inc"):
                y = year(v(r, "inc"))
                if y and (a.get("_y") is None or y < a["_y"]): a["_y"] = y
        labmap = {qid(v(r, "b")): v(r, "l") for r in labels}
        nm = {}
        for r in mem:
            b, p = qid(v(r, "b")), qid(v(r, "p"))
            persons_needed.add(p)
            sy, ey = year(v(r, "s")), year(v(r, "e"))
            cur = db.execute("SELECT start, end FROM membership WHERE band=? AND person=?", (b, p)).fetchone()
            if cur is None:
                nm[b] = nm.get(b, 0) + 1
                db.execute("INSERT INTO membership VALUES(?,?,?,?)", (b, p, sy, ey))
            else:
                s0 = min(x for x in (cur[0], sy) if x is not None) if (cur[0] or sy) else None
                e0 = max(x for x in (cur[1], ey) if x is not None) if (cur[1] or ey) else None
                db.execute("UPDATE membership SET start=?, end=? WHERE band=? AND person=?", (s0, e0, b, p))
        for b in batch:
            a = agg.get(b, {})
            bl = a.get("bLabel"); bl = None if (bl and bl == b) else bl
            name = a.get("en") or bl or a.get("ru") or b
            db.execute("""UPDATE band SET name=?, name_ru=?, name_en=?, desc_ru=?, desc_en=?, formed=?, dissolved=?,
               country=?, country_id=?, origin=?, image=?, logo=?, website=?, wiki_ru=?, wiki_en=?, mbid=?, sitelinks=?,
               labels=?, n_members=?, done=1 WHERE id=?""",
               (name, a.get("ru"), a.get("en"), a.get("dru"), a.get("den"), a.get("_y"), year(a.get("dis")),
                a.get("cLabel"), qid(a["c"]) if a.get("c") else None, a.get("oLabel"),
                a.get("img"), a.get("logo"), a.get("web"), a.get("wru"), a.get("wen"), a.get("mb"),
                int(a.get("sl", 0)), labmap.get(b), nm.get(b, 0), b))
        db.commit()
        done += len(batch)
        print(f"  группы {done}/{len(todo)}", flush=True)

# ---------- 4. музыканты ----------
have = {r[0] for r in db.execute("select id from person")}
need = [p for p in {r[0] for r in db.execute("select distinct person from membership")} if p not in have]
print("Музыкантов к обработке:", len(need))

def pdetails(batch):
    vals = " ".join("wd:" + p for p in batch)
    rows = sparql(f"""
SELECT ?p ?ru ?en ?pLabel ?b ?d ?img ?wen ?wru WHERE {{
  VALUES ?p {{ {vals} }}
  OPTIONAL {{ ?p rdfs:label ?ru FILTER(lang(?ru)='ru') }}
  OPTIONAL {{ ?p rdfs:label ?en FILTER(lang(?en)='en') }}
  OPTIONAL {{ ?p wdt:P569 ?b }}
  OPTIONAL {{ ?p wdt:P570 ?d }}
  OPTIONAL {{ ?p wdt:P18 ?img }}
  OPTIONAL {{ ?wen schema:about ?p ; schema:isPartOf <https://en.wikipedia.org/> }}
  OPTIONAL {{ ?wru schema:about ?p ; schema:isPartOf <https://ru.wikipedia.org/> }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,mul,ru,de,fr,es,it,sv,fi,ja" . }}
}}""")
    rows += sparql(f"""
SELECT ?p (GROUP_CONCAT(DISTINCT ?inl; separator='|') AS ?ins) WHERE {{
  VALUES ?p {{ {vals} }}
  ?p wdt:P1303 ?in . ?in rdfs:label ?inl FILTER(lang(?inl)='ru')
}} GROUP BY ?p""")
    return rows

pb = [need[i:i + 150] for i in range(0, len(need), 150)]
done = 0
with cf.ThreadPoolExecutor(4) as ex:
    for rows in ex.map(pdetails, pb):
        agg = {}
        for r in rows:
            p = qid(v(r, "p"))
            a = agg.setdefault(p, {"ins": set()})
            for k in ["ru", "en", "pLabel", "b", "d", "img", "wen", "wru"]:
                if k not in a and v(r, k): a[k] = v(r, k)
            if v(r, "ins"):
                a["ins"].update(x for x in v(r, "ins").split("|") if x)
        for p, a in agg.items():
            db.execute("INSERT OR REPLACE INTO person VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (p, a.get("ru") or a.get("en") or a.get("pLabel") or p, a.get("ru"), a.get("en"),
                        year(a.get("b")), year(a.get("d")), a.get("img"),
                        "|".join(sorted(a["ins"])) or None, a.get("wen"), a.get("wru")))
        db.commit()
        done += 1
        print(f"  музыканты {done}/{len(pb)}", flush=True)

db.executescript("""
CREATE INDEX IF NOT EXISTS i_bg_g ON band_genre(genre);
CREATE INDEX IF NOT EXISTS i_m_p ON membership(person);
CREATE INDEX IF NOT EXISTS i_b_f ON band(formed);
CREATE INDEX IF NOT EXISTS i_b_c ON band(country);
CREATE INDEX IF NOT EXISTS i_b_s ON band(sitelinks);
""")
db.commit()
print("ГОТОВО")

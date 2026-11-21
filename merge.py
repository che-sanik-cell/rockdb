"""
Объединение каталога Metal Archives (ma_band) с основной таблицей band.
 - группы с одинаковым MA ID (Wikidata P1952) — обогащаются жанром/статусом/годом MA
 - совпадение по названию + стране — тоже связываются
 - остальные добавляются как новые записи с id = 'MA<номер>'
Жанры MA («Black/Death Metal», «Heavy Metal (early); Hard Rock (later)») раскладываются на жанры базы.
"""
import re, sqlite3, json
from harvest_lib import sparql, qid, v

db = sqlite3.connect("rock.db", timeout=60)
db.execute("CREATE INDEX IF NOT EXISTS i_b_ma ON band(ma_id)")
# если таблица ma_band удалена (для экономии места) — восстановить из ma_band.csv.gz
if not db.execute("select 1 from sqlite_master where name='ma_band'").fetchone():
    import csv, gzip
    db.execute("CREATE TABLE ma_band(ma_id INTEGER PRIMARY KEY, name TEXT, url TEXT, country TEXT, genre TEXT, status TEXT, formed INTEGER)")
    with gzip.open("ma_band.csv.gz", "rt", encoding="utf-8") as f:
        r = csv.reader(f); next(r)
        db.executemany("INSERT INTO ma_band VALUES(?,?,?,?,?,?,?)", ([x[0], x[1], x[2], x[3], x[4], x[5], x[6] or None] for x in r))
    db.commit()

# ---------- страны: англ. название MA -> русское ----------
countries = [r[0] for r in db.execute("select distinct country from ma_band where country is not null and country<>''")]
SPECIAL = {"United States": "США", "United Kingdom": "Великобритания", "Korea, South": "Республика Корея",
           "Russia": "Россия", "Czechia": "Чехия", "Czech Republic": "Чехия", "International": "Международный",
           "Unknown": None, "Taiwan": "Китайская Республика", "Hong Kong": "Гонконг", "Macedonia (FYROM)": "Северная Македония",
           "North Macedonia": "Северная Македония", "Faroe Islands": "Фарерские острова", "Netherlands": "Нидерланды",
           "Georgia": "Грузия", "Ireland": "Ирландия", "China": "КНР", "Palestine": "Государство Палестина",
           "Kosovo": "Республика Косово", "Åland Islands": "Аландские острова", "Svalbard": "Шпицберген"}
cmap = dict(SPECIAL)
need = [c for c in countries if c not in cmap]
for i in range(0, len(need), 80):
    vals = " ".join(json.dumps(c) + "@en" for c in need[i:i + 80])
    for r in sparql(f"""SELECT ?en ?ru WHERE {{ VALUES ?en {{ {vals} }} ?c rdfs:label ?en .
        ?c wdt:P31/wdt:P279* ?t . VALUES ?t {{ wd:Q6256 wd:Q3624078 wd:Q3024240 wd:Q7275 wd:Q15634554 wd:Q46395 }}
        ?c rdfs:label ?ru FILTER(lang(?ru)='ru') }}"""):
        cmap.setdefault(v(r, "en"), v(r, "ru"))
print("стран сопоставлено:", sum(1 for c in countries if cmap.get(c)), "/", len(countries))

# ---------- жанры ----------
gname = {}
for gid, en in db.execute("select id, name_en from genre where name_en is not null"):
    gname.setdefault(en.lower().replace("-", " "), gid)
gname["heavy metal"] = "Q1133657"; gname["metal"] = "Q38848"
# синонимы MA -> англ. названия жанров Wikidata
ALIAS_N = {"metal": "heavy metal", "nwobhm": "new wave of british heavy metal", "rock": "rock music",
           "rock'n'roll": "rock and roll", "rock 'n' roll": "rock and roll", "rock n roll": "rock and roll",
           "punk": "punk rock", "crust": "crust punk", "d beat": "d-beat", "grind": "grindcore",
           "goth": "gothic rock", "nu metal": "nu metal", "stoner": "stoner rock",
           "progressive": "progressive metal", "doom": "doom metal", "black": "black metal", "death": "death metal",
           "thrash": "thrash metal", "speed": "speed metal", "power": "power metal", "folk": "folk metal"}
ALIAS = {}
for k, n in ALIAS_N.items():
    g = gname.get(n.lower().replace("-", " "))
    if g: ALIAS[k] = g
HEAVY = "Q38848"
print("алиасов:", len(ALIAS), "heavy metal =", HEAVY)
def find_genre(s):
    s = s.strip().lower().replace("-", " ")
    s = re.sub(r"\s+", " ", s)
    if s in ALIAS: return ALIAS[s]
    if s in gname: return gname[s]
    if s.endswith(" metal") and s.replace(" metal", "metal") in gname: return gname[s.replace(" metal", "metal")]
    return None

import functools
@functools.lru_cache(maxsize=None)
def map_genres(text):
    out = set()
    if not text: return out
    t = re.sub(r"\([^)]*\)", "", text)
    for part in re.split(r"[;,]| with | and ", t):
        segs = [x.strip() for x in part.split("/") if x.strip()]
        if not segs: continue
        tail = segs[-1].split()
        suffix = tail[-1] if tail and tail[-1].lower() in ("metal", "rock", "punk", "core", "doom") else ""
        for sgm in segs:
            cands = [sgm]
            if suffix and not re.search(r"(metal|rock|punk|core|doom|grind|wave|gaze)\b", sgm, re.I):
                cands.insert(0, sgm + " " + suffix)
            got = None
            for c in cands:
                got = find_genre(c)
                if got: break
            if not got:
                # самое длинное известное название внутри
                low = sgm.lower().replace("-", " ")
                best = max((n for n in gname if len(n) > 4 and re.search(r"\b" + re.escape(n) + r"\b", low)), key=len, default=None)
                if best: got = gname[best]
            if got: out.add(got)
    if not out and re.search(r"metal", text, re.I): out.add(HEAVY)
    return out

# ---------- объединение ----------
by_ma = {r[0]: r[1] for r in db.execute("select ma_id, id from band where ma_id is not null")}
norm = lambda s: re.sub(r"[^\w]+", "", (s or "").lower().replace("the ", ""))
by_name = {}
for bid, name, country in db.execute("select id, name, country from band where name is not null and ma_id is null and kind='band'"):
    by_name.setdefault((norm(name), country), []).append(bid)

linked = added = 0
rows = db.execute("select ma_id, name, url, country, genre, status, formed from ma_band").fetchall()
for ma_id, name, url, country, genre, status, formed in rows:
    cru = cmap.get(country, country if country not in SPECIAL else None)
    gids = map_genres(genre or "")
    bid = by_ma.get(ma_id)
    if not bid:
        c = by_name.get((norm(name), cru))
        if c and len(c) == 1:
            bid = c[0]
            db.execute("UPDATE band SET ma_id=? WHERE id=?", (ma_id, bid))
    if bid:
        db.execute("""UPDATE band SET ma_genre=?, status_text=?, formed=COALESCE(formed, ?), source='wikidata+metal-archives'
                      WHERE id=?""", (genre, status, formed, bid))
        linked += 1
    else:
        bid = f"MA{ma_id}"
        db.execute("""INSERT INTO band(id, name, country, formed, ma_id, ma_genre, status_text, source, kind, done, sitelinks, n_members)
                      VALUES(?,?,?,?,?,?,?,'metal-archives','band',1,0,0)
                      ON CONFLICT(id) DO UPDATE SET name=excluded.name, country=excluded.country, formed=excluded.formed,
                      ma_genre=excluded.ma_genre, status_text=excluded.status_text""",
                   (bid, name, cru, formed, ma_id, genre, status))
        added += 1
    for g in gids:
        db.execute("INSERT OR IGNORE INTO band_genre VALUES(?,?)", (bid, g))
db.execute("UPDATE band SET status_text='Split-up' WHERE status_text IS NULL AND dissolved IS NOT NULL")
db.execute("DELETE FROM cache WHERE key IN ('stats','facets')")
db.commit()
print(f"связано: {linked}, добавлено новых: {added}")
print("всего в базе:", db.execute("select count(*) from band where name is not null").fetchone()[0])

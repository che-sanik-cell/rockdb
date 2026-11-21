"""
Расширение базы из Wikidata:
 - сольные исполнители (гитаристы, певцы и т.п.: Link Wray, Jimi Hendrix, Joe Satriani…)
 - дополнительные корневые жанры (рокабилли, сёрф)
 - ID групп в Encyclopaedia Metallum (P1952) для связи с metal-archives
"""
import sqlite3, concurrent.futures as cf
from harvest_lib import sparql, qid, v, year

db = sqlite3.connect("rock.db", timeout=60)
for col, typ in [("kind", "TEXT DEFAULT 'band'"), ("ma_id", "INTEGER"), ("ma_genre", "TEXT"), ("status_text", "TEXT"),
                 ("source", "TEXT DEFAULT 'wikidata'"), ("born", "INTEGER")]:
    try: db.execute(f"ALTER TABLE band ADD COLUMN {col} {typ}")
    except Exception: pass
db.commit()

ROOTS = "wd:Q11399 wd:Q203720 wd:Q220830 wd:Q7749"   # рок, рокабилли, сёрф, рок-н-ролл

print("Доп. жанры...")
for r in sparql(f"""SELECT DISTINCT ?g ?ru ?en ?p WHERE {{ VALUES ?root {{ {ROOTS} }} ?g wdt:P279* ?root .
   FILTER NOT EXISTS {{ ?g wdt:P279* wd:Q11399 }}
   OPTIONAL {{ ?g rdfs:label ?ru FILTER(lang(?ru)='ru') }} OPTIONAL {{ ?g rdfs:label ?en FILTER(lang(?en)='en') }}
   OPTIONAL {{ ?g wdt:P279 ?p }} }}"""):
    db.execute("INSERT OR IGNORE INTO genre VALUES(?,?,?,?)", (qid(v(r, "g")), v(r, "ru"), v(r, "en"), qid(v(r, "p")) if v(r, "p") else None))
db.commit()

print("Группы в доп. жанрах...")
for r in sparql(f"""SELECT DISTINCT ?b ?g WHERE {{ VALUES ?root {{ wd:Q203720 wd:Q220830 }} ?g wdt:P279* ?root .
   ?b wdt:P136 ?g . ?b wdt:P31/wdt:P279* wd:Q215380 . }}"""):
    b = qid(v(r, "b"))
    db.execute("INSERT OR IGNORE INTO band(id) VALUES(?)", (b,))
    db.execute("INSERT OR IGNORE INTO band_genre VALUES(?,?)", (b, qid(v(r, "g"))))
db.commit()
print(" ещё необработанных групп:", db.execute("select count(*) from band where done=0").fetchone()[0])

print("Сольные исполнители...")
rows = sparql(f"""SELECT DISTINCT ?p ?g WHERE {{ VALUES ?root {{ {ROOTS} }} ?g wdt:P279* ?root .
   ?p wdt:P136 ?g . ?p wdt:P31 wd:Q5 . }}""")
solo = set()
for r in rows:
    p, g = qid(v(r, "p")), qid(v(r, "g"))
    if db.execute("select kind from band where id=?", (p,)).fetchone() is None:
        db.execute("INSERT INTO band(id, kind) VALUES(?, 'solo')", (p,))
    solo.add(p)
    db.execute("INSERT OR IGNORE INTO band_genre VALUES(?,?)", (p, g))
db.commit()
solo = [p for p in solo if db.execute("select done from band where id=?", (p,)).fetchone()[0] == 0]
print(" сольных к обработке:", len(solo))

def sdetails(batch):
    vals = " ".join("wd:" + b for b in batch)
    a = sparql(f"""
SELECT ?b ?ru ?en ?bLabel ?dru ?den ?wru ?wen ?sl WHERE {{ VALUES ?b {{ {vals} }}
  OPTIONAL {{ ?b rdfs:label ?ru FILTER(lang(?ru)='ru') }} OPTIONAL {{ ?b rdfs:label ?en FILTER(lang(?en)='en') }}
  OPTIONAL {{ ?b schema:description ?dru FILTER(lang(?dru)='ru') }} OPTIONAL {{ ?b schema:description ?den FILTER(lang(?den)='en') }}
  OPTIONAL {{ ?wru schema:about ?b ; schema:isPartOf <https://ru.wikipedia.org/> }}
  OPTIONAL {{ ?wen schema:about ?b ; schema:isPartOf <https://en.wikipedia.org/> }}
  OPTIONAL {{ ?b wikibase:sitelinks ?sl }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,mul,ru,de,fr,es,it,pt,sv,fi,ja" . }} }}""")
    b = sparql(f"""
SELECT ?b (MIN(?ws0) AS ?ws) (MAX(?we0) AS ?we) (MIN(?bd0) AS ?bd) (MAX(?dd0) AS ?dd) (SAMPLE(?c0) AS ?c) (SAMPLE(?cl0) AS ?cLabel)
  (SAMPLE(?ol0) AS ?oLabel) (SAMPLE(?img0) AS ?img) (SAMPLE(?web0) AS ?web) (SAMPLE(?mb0) AS ?mb) (SAMPLE(?ma0) AS ?ma) WHERE {{
  VALUES ?b {{ {vals} }}
  OPTIONAL {{ ?b wdt:P2031 ?ws0 }} OPTIONAL {{ ?b wdt:P2032 ?we0 }} OPTIONAL {{ ?b wdt:P569 ?bd0 }} OPTIONAL {{ ?b wdt:P570 ?dd0 }}
  OPTIONAL {{ ?b wdt:P27 ?c0 . ?c0 rdfs:label ?cl0 FILTER(lang(?cl0)='ru') }}
  OPTIONAL {{ ?b wdt:P19 ?o0 . ?o0 rdfs:label ?ol0 FILTER(lang(?ol0)='ru') }}
  OPTIONAL {{ ?b wdt:P18 ?img0 }} OPTIONAL {{ ?b wdt:P856 ?web0 }} OPTIONAL {{ ?b wdt:P434 ?mb0 }} OPTIONAL {{ ?b wdt:P1952 ?ma0 }}
}} GROUP BY ?b""")
    ins = sparql(f"""SELECT ?b (GROUP_CONCAT(DISTINCT ?inl; separator='|') AS ?ins) WHERE {{ VALUES ?b {{ {vals} }}
  ?b wdt:P1303 ?in . ?in rdfs:label ?inl FILTER(lang(?inl)='ru') }} GROUP BY ?b""")
    lab = sparql(f"""SELECT ?b (GROUP_CONCAT(DISTINCT ?ln; separator='|') AS ?l) WHERE {{ VALUES ?b {{ {vals} }}
  ?b wdt:P264 ?x . ?x rdfs:label ?ln FILTER(lang(?ln)='en') }} GROUP BY ?b""")
    return batch, a, b, ins, lab

done = 0
with cf.ThreadPoolExecutor(4) as ex:
    for batch, A, B, INS, LAB in ex.map(sdetails, [solo[i:i + 200] for i in range(0, len(solo), 200)]):
        agg = {}
        for r in A + B:
            x = agg.setdefault(qid(v(r, "b")), {})
            for k, val in r.items():
                if k != "b" and k not in x: x[k] = val["value"]
        insm = {qid(v(r, "b")): v(r, "ins") for r in INS}
        labm = {qid(v(r, "b")): v(r, "l") for r in LAB}
        for p in batch:
            a = agg.get(p, {})
            bl = a.get("bLabel"); bl = None if bl == p else bl
            name = a.get("en") or bl or a.get("ru") or p
            born, died = year(a.get("bd")), year(a.get("dd"))
            formed = year(a.get("ws"))
            dissolved = year(a.get("we")) or died
            db.execute("""UPDATE band SET name=?, name_ru=?, name_en=?, desc_ru=?, desc_en=?, formed=?, dissolved=?, country=?,
              country_id=?, origin=?, image=?, website=?, wiki_ru=?, wiki_en=?, mbid=?, sitelinks=?, labels=?, n_members=1,
              done=1, kind='solo', ma_id=COALESCE(?, ma_id), born=? WHERE id=?""",
              (name, a.get("ru"), a.get("en"), a.get("dru"), a.get("den"), formed, dissolved, a.get("cLabel"),
               qid(a["c"]) if a.get("c") else None, a.get("oLabel"), a.get("img"), a.get("web"), a.get("wru"), a.get("wen"),
               a.get("mb"), int(a.get("sl", 0) or 0), labm.get(p), int(a["ma"]) if (a.get("ma") or "").isdigit() else None, born, p))
            # сам исполнитель = «участник» своего проекта
            db.execute("""INSERT OR REPLACE INTO person(id,name,name_ru,name_en,born,died,image,instruments,wiki_en,wiki_ru)
               VALUES(?,?,?,?,?,?,?,?,?,?)""", (p, a.get("ru") or name, a.get("ru"), a.get("en"), born, died, a.get("img"),
               insm.get(p), a.get("wen"), a.get("wru")))
            db.execute("INSERT OR IGNORE INTO membership VALUES(?,?,?,?)", (p, p, formed, year(a.get("we"))))
        db.commit(); done += len(batch)
        print(f"  сольные {done}/{len(solo)}", flush=True)

print("P1952 (Metal Archives ID) для групп...")
for r in sparql("SELECT ?b ?ma WHERE { ?b wdt:P1952 ?ma }"):
    if v(r, "ma").isdigit():
        db.execute("UPDATE band SET ma_id=? WHERE id=?", (int(v(r, "ma")), qid(v(r, "b"))))
db.commit()
print(" связано с MA:", db.execute("select count(*) from band where ma_id is not null").fetchone()[0])
print("ГОТОВО")

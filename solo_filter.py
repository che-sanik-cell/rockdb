"""Оставляем только «гитарных» сольных исполнителей: рок-жанры составляют ≥ половины жанров
или ≥ четверти и исполнитель играет на гитаре/басу/ударных. Поп-звёзды с единичным «поп-роком» удаляются."""
import sqlite3, concurrent.futures as cf
from harvest_lib import sparql, qid, v
db = sqlite3.connect("rock.db", timeout=60)
ids = [r[0] for r in db.execute("select id from band where kind='solo'")]
tot = {}
def q(batch):
    vals = " ".join("wd:" + x for x in batch)
    return sparql(f"SELECT ?p (COUNT(DISTINCT ?g) AS ?n) WHERE {{ VALUES ?p {{ {vals} }} ?p wdt:P136 ?g }} GROUP BY ?p")
with cf.ThreadPoolExecutor(4) as ex:
    for rows in ex.map(q, [ids[i:i+400] for i in range(0, len(ids), 400)]):
        for r in rows: tot[qid(v(r, "p"))] = int(v(r, "n"))
GUIT = ("гитара", "электрогитара", "бас-гитара", "ударная установка", "ударные", "акустическая гитара", "бас", "слайд-гитара", "двенадцатиструнная гитара")
removed = 0
for pid in ids:
    rock = db.execute("select count(*) from band_genre where band=?", (pid,)).fetchone()[0]
    ins = (db.execute("select instruments from person where id=?", (pid,)).fetchone() or [None])[0] or ""
    plays = any(g in ins.split("|") for g in GUIT)
    n = tot.get(pid, rock) or 1
    if rock / n >= 0.5 or (plays and rock / n >= 0.25):
        continue
    db.execute("delete from band where id=?", (pid,)); db.execute("delete from band_genre where band=?", (pid,))
    db.execute("delete from membership where band=?", (pid,))
    removed += 1
db.execute("DELETE FROM cache WHERE key IN ('stats','facets')")
db.commit()
print("удалено поп-исполнителей:", removed, "осталось сольных:", db.execute("select count(*) from band where kind='solo'").fetchone()[0])
for name in ["Michael Jackson", "Shakira", "Madonna", "Elvis Presley", "Link Wray", "Jimi Hendrix", "Freddie Mercury", "Ozzy Osbourne", "Joe Satriani", "Yngwie Malmsteen", "Taylor Swift"]:
    print(name, bool(db.execute("select 1 from band where name=?", (name,)).fetchone()))

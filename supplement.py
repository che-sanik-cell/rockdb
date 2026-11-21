"""Дополнение: годы активности из P2031/P2032 (work period start/end), если нет P571/P576."""
import sqlite3, concurrent.futures as cf
from harvest_lib import sparql, qid, v, year
db = sqlite3.connect("rock.db", timeout=60)
ids = [r[0] for r in db.execute("select id from band")]
def q(batch):
    vals = " ".join("wd:" + b for b in batch)
    return sparql(f"""SELECT ?b (MIN(?s) AS ?ws) (MAX(?e) AS ?we) (MIN(?i) AS ?inc) (MAX(?d) AS ?dis) WHERE {{ VALUES ?b {{ {vals} }}
      OPTIONAL {{ ?b wdt:P2031 ?s }} OPTIONAL {{ ?b wdt:P2032 ?e }} OPTIONAL {{ ?b wdt:P571 ?i }} OPTIONAL {{ ?b wdt:P576 ?d }} }} GROUP BY ?b""")
n = 0
with cf.ThreadPoolExecutor(4) as ex:
    for rows in ex.map(q, [ids[i:i+400] for i in range(0, len(ids), 400)]):
        for r in rows:
            b = qid(v(r, "b"))
            f = year(v(r, "inc")) or year(v(r, "ws"))
            d = year(v(r, "dis")) or year(v(r, "we"))
            db.execute("UPDATE band SET formed=COALESCE(formed, ?), dissolved=COALESCE(dissolved, ?) WHERE id=?", (f, d, b))
        db.commit(); n += 1; print("batch", n, flush=True)
db.execute("UPDATE band SET name=NULL WHERE name GLOB 'Q[0-9]*'")
db.execute("UPDATE band SET dissolved=NULL WHERE dissolved < formed")
db.execute("DELETE FROM cache WHERE key IN ('stats','facets')")
db.commit()
print(db.execute("select sum(formed is not null), sum(dissolved is not null), sum(name is not null) from band").fetchone())

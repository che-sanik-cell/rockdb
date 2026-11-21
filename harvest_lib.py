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


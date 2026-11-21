"""
Rock & Metal Encyclopedia — сервер.
База: rock.db (собрана из Wikidata скриптом harvest.py)
Описания, фото и оборудование подгружаются из Wikipedia по запросу и кэшируются.
Запуск: python3 server.py  (порт 8080)
"""
import json, os, re, sqlite3, threading, time, html, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from html.parser import HTMLParser
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(ROOT, "rock.db")
UA = "RockMetalBase/1.0 (https://github.com/; educational encyclopedia app) python-requests"
HTTP = requests.Session()
HTTP.headers.update({"User-Agent": UA})

_local = threading.local()
def db():
    c = getattr(_local, "c", None)
    if c is None:
        c = sqlite3.connect(DB, check_same_thread=False, timeout=30)
        c.row_factory = sqlite3.Row
        _local.c = c
    return c

_wlock = threading.Lock()
def cache_get(key, max_age=86400 * 30):
    r = db().execute("select value, ts from cache where key=?", (key,)).fetchone()
    if r and time.time() - r["ts"] < max_age:
        return json.loads(r["value"])
    return None

def cache_set(key, val):
    with _wlock:
        db().execute("insert or replace into cache values(?,?,?)", (key, json.dumps(val, ensure_ascii=False), int(time.time())))
        db().commit()

# ---------------- жанры: дерево потомков ----------------
GENRES = {}; CHILDREN = {}
def load_genres():
    GENRES.clear(); CHILDREN.clear()
    for r in db().execute("select * from genre"):
        g = GENRES.setdefault(r["id"], {"id": r["id"], "name": r["name_ru"] or r["name_en"] or r["id"], "name_en": r["name_en"]})
        if r["parent"]:
            CHILDREN.setdefault(r["parent"], set()).add(r["id"])

def descendants(g):
    out, st = set(), [g]
    while st:
        x = st.pop()
        if x in out: continue
        out.add(x)
        st.extend(CHILDREN.get(x, ()))
    return out

def thumb(url, w=400):
    if not url: return None
    url = url.replace("http://", "https://")
    return url + ("&" if "?" in url else "?") + f"width={w}"

def band_row(r):
    d = dict(r)
    d["thumb"] = thumb(d.get("image"), 500)
    d["logo_thumb"] = thumb(d.get("logo"), 300)
    return d

# ---------------- Wikipedia ----------------
def wiki_title(url):
    if not url: return None, None
    m = re.match(r"https?://(\w+)\.wikipedia\.org/wiki/(.+)", url)
    if not m: return None, None
    return m.group(1), urllib.parse.unquote(m.group(2))

def wiki_intro(url):
    lang, title = wiki_title(url)
    if not title: return None
    key = f"intro:{lang}:{title}"
    c = cache_get(key)
    if c is not None: return c
    try:
        r = HTTP.get(f"https://{lang}.wikipedia.org/w/api.php", params={
            "action": "query", "prop": "extracts|pageimages", "exintro": 1, "explaintext": 1,
            "piprop": "thumbnail|original", "pithumbsize": 900, "titles": title,
            "format": "json", "redirects": 1}, timeout=20).json()
        page = next(iter(r["query"]["pages"].values()))
        res = {"lang": lang, "title": page.get("title"), "url": url,
               "extract": page.get("extract", ""),
               "image": (page.get("thumbnail") or {}).get("source"),
               "image_full": (page.get("original") or {}).get("source")}
    except Exception as e:
        res = {"error": str(e)}
        return res
    cache_set(key, res)
    return res

class _Text(HTMLParser):
    """HTML раздела -> структурированный текст (абзацы, списки, подзаголовки)."""
    SKIP = {"style", "script", "sup", "table", "figure"}
    def __init__(self):
        super().__init__(); self.out = []; self.buf = []; self.skip = 0; self.kind = "p"
    def flush(self):
        t = re.sub(r"\s+", " ", "".join(self.buf)).strip()
        if t: self.out.append({"t": self.kind, "s": t})
        self.buf = []
    def handle_starttag(self, tag, a):
        cls = dict(a).get("class", "") or ""
        if tag in self.SKIP or "mw-editsection" in cls or "reference" in cls or "hatnote" in cls or "navbox" in cls or "thumb" in cls:
            self.skip += 1; return
        if self.skip: return
        if tag in ("p", "li", "h2", "h3", "h4", "dt", "dd"):
            self.flush(); self.kind = {"li": "li", "h2": "h", "h3": "h", "h4": "h", "dt": "h", "dd": "li"}.get(tag, "p")
    def handle_endtag(self, tag):
        if tag in self.SKIP:
            if self.skip: self.skip -= 1
            return
        if self.skip:
            if tag in ("span", "div", "sup", "table", "figure"): pass
            return
        if tag in ("p", "li", "h2", "h3", "h4", "dt", "dd"): self.flush(); self.kind = "p"
    def handle_data(self, d):
        if not self.skip: self.buf.append(d)

class _Text2(_Text):
    # корректная обработка вложенных пропускаемых тегов (span.mw-editsection и т.п.)
    def __init__(self):
        super().__init__(); self.stack = []
    def handle_starttag(self, tag, a):
        cls = dict(a).get("class", "") or ""
        skipping = tag in self.SKIP or (any(k in cls for k in ("mw-editsection", "reference", "hatnote", "navbox", "thumb", "mw-empty-elt", "noprint", "toc")) or dict(a).get("id") == "toc")
        if tag not in ("br", "img", "hr", "input", "meta", "link", "wbr"):
            self.stack.append(skipping)
        if skipping: self.skip += 1; return
        if self.skip: return
        if tag in ("p", "li", "h2", "h3", "h4", "dt", "dd"):
            self.flush(); self.kind = {"li": "li", "h2": "h", "h3": "h", "h4": "h", "dt": "h", "dd": "li"}.get(tag, "p")
    def handle_endtag(self, tag):
        if tag in ("br", "img", "hr", "input", "meta", "link", "wbr"): return
        skipping = self.stack.pop() if self.stack else False
        if skipping: self.skip -= 1; return
        if self.skip: return
        if tag in ("p", "li", "h2", "h3", "h4", "dt", "dd"): self.flush(); self.kind = "p"

GEAR_RE = {
    "en": re.compile(r"\b(equipment|gear|guitars?|basses|instruments?|rig|setup|drum kit|drums|endorsements?|amplifiers?|signature)\b", re.I),
    "ru": re.compile(r"(оборудован|аппаратур|инструмент|гитар|ударн|барабан|усилител|снаряжен|эндорс)", re.I),
}
GEAR_EXCLUDE = re.compile(r"(discograph|дискограф|see also|см\. также|references|примечани|external|ссылки|filmography|bibliograph)", re.I)

def wiki_gear(url):
    lang, title = wiki_title(url)
    if not title: return None
    key = f"gear:{lang}:{title}"
    c = cache_get(key)
    if c is not None: return c
    res = {"lang": lang, "url": url, "sections": []}
    try:
        api = f"https://{lang}.wikipedia.org/w/api.php"
        r = HTTP.get(api, params={"action": "parse", "page": title, "prop": "sections", "format": "json", "redirects": 1}, timeout=20).json()
        secs = r.get("parse", {}).get("sections", [])
        picked = []
        for s in secs:
            name = html.unescape(re.sub("<.*?>", "", s.get("line", "")))
            if GEAR_RE[lang if lang in GEAR_RE else "en"].search(name) and not GEAR_EXCLUDE.search(name):
                # не брать подраздел, если уже взят родитель
                if any(s["number"].startswith(p["number"] + ".") for p in picked): continue
                picked.append({"index": s["index"], "number": s["number"], "name": name})
        for p in picked[:3]:
            rr = HTTP.get(api, params={"action": "parse", "page": title, "prop": "text", "section": p["index"],
                                       "format": "json", "redirects": 1, "disableeditsection": 1}, timeout=20).json()
            htm = rr.get("parse", {}).get("text", {}).get("*", "")
            tp = _Text2(); tp.feed(htm); tp.flush()
            items = [x for x in tp.out if not (x["t"] == "h" and x["s"] == p["name"])]
            if items:
                res["sections"].append({"name": p["name"], "items": items[:120]})
    except Exception as e:
        res["error"] = str(e)
        return res
    cache_set(key, res)
    return res


def wiki_pageimages(pairs, size=500):
    """pairs: [(cache_key, wikipedia_url)] -> {cache_key: thumb_url}. Пакетно, по 50 заголовков."""
    out, need = {}, {}
    for key, url in pairs:
        c = cache_get("pi:" + key, 86400 * 60)
        if c is not None:
            if c.get("u"): out[key] = c["u"]
            continue
        lang, title = wiki_title(url)
        if title: need.setdefault(lang, []).append((key, title))
    for lang, lst in need.items():
        for i in range(0, len(lst), 50):
            chunk = lst[i:i + 50]
            try:
                r = HTTP.get(f"https://{lang}.wikipedia.org/w/api.php", params={
                    "action": "query", "prop": "pageimages", "piprop": "thumbnail", "pithumbsize": size,
                    "titles": "|".join(t for _, t in chunk), "format": "json", "redirects": 1, "formatversion": 2}, timeout=15).json()
                q = r.get("query", {})
                norm = {}
                for n in q.get("normalized", []) + q.get("redirects", []):
                    norm[n["from"]] = n["to"]
                img = {p["title"]: (p.get("thumbnail") or {}).get("source") for p in q.get("pages", [])}
                for key, t in chunk:
                    tt = t.replace("_", " ")
                    tt = norm.get(tt, tt); tt = norm.get(tt, tt)
                    u = img.get(tt)
                    cache_set("pi:" + key, {"u": u})
                    if u: out[key] = u
            except Exception as e:
                print("pageimages err", e)
    return out


# ---------------- Metal Archives (по запросу, с кэшем) ----------------
import subprocess
MA_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
def curl(url, head=False, binary=False):
    # metal-archives режет python-клиенты по TLS-отпечатку — используем curl
    args = ["curl", "-s", "-L", "-m", "25", "-A", MA_UA, "-w", "\n%{http_code}"]
    if head: args += ["-I"]
    p = subprocess.run(args + [url], capture_output=True)
    out = p.stdout
    body, _, code = out.rpartition(b"\n")
    try: code = int(code.decode().strip() or 0)
    except Exception: code = 0
    return code, (body if binary else body.decode("utf-8", "replace"))

ROLE_RU = [("lead guitar", "соло-гитара"), ("rhythm guitar", "ритм-гитара"), ("guitars", "гитара"), ("guitar", "гитара"),
           ("bass", "бас-гитара"), ("drums", "ударные"), ("percussion", "перкуссия"), ("keyboards", "клавишные"),
           ("synth", "синтезатор"), ("piano", "фортепиано"), ("organ", "орган"), ("vocals", "вокал"), ("violin", "скрипка"),
           ("cello", "виолончель"), ("flute", "флейта"), ("saxophone", "саксофон"), ("programming", "программирование"),
           ("samples", "семплы"), ("electronics", "электроника"), ("turntables", "вертушки"), ("harmonica", "губная гармоника")]
def roles_ru(txt):
    out = []
    low = txt.lower()
    for en, ru in ROLE_RU:
        if en in low and ru not in out and not (ru == "гитара" and ("соло-гитара" in out or "ритм-гитара" in out)):
            out.append(ru)
    return out

def _clean(h):
    return html.unescape(re.sub(r"<[^>]+>", "", h or "")).replace("\xa0", " ").strip()

def ma_band(ma_id):
    key = f"ma:{ma_id}"
    c = cache_get(key, 86400 * 14)
    if c: return c
    code, h = curl(f"https://www.metal-archives.com/bands/_/{ma_id}")
    if code != 200 or "band_stats" not in h:
        return {"error": f"metal-archives HTTP {code}"}
    res = {"ma_id": ma_id, "url": f"https://www.metal-archives.com/bands/_/{ma_id}"}
    m = re.search(r'<h1 class="band_name">(.*?)</h1>', h, re.S); res["name"] = _clean(m.group(1)) if m else None
    stats = {}
    for dt, dd in re.findall(r"<dt>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>", h[h.find('id="band_stats"'):h.find('band_comment')], re.S):
        stats[_clean(dt).rstrip(":")] = re.sub(r"\s+", " ", _clean(dd))
    res["stats"] = stats
    m = re.search(r'id="logo"[^>]*href="([^"]+)"', h); res["logo"] = m.group(1) if m else None
    m = re.search(r'id="photo"[^>]*href="([^"]+)"', h); res["photo"] = m.group(1) if m else None
    lineup = {}
    for tab, title in [("current", "Текущий состав"), ("past", "Бывшие участники"), ("live", "Концертные музыканты"), ("all", "Состав")]:
        i = h.find(f'id="band_tab_members_{tab}"')
        if i < 0: continue
        j = h.find('id="band_tab_members_', i + 10); seg = h[i: j if j > 0 else i + 60000]
        seg = seg[: seg.find("</table>") + 8] if "</table>" in seg else seg
        rows = []
        for tr in re.split(r'<tr class="lineupRow">', seg)[1:]:
            a = re.search(r'<a href="([^"]+/artists/[^"]+/(\d+))"[^>]*>(.*?)</a>', tr, re.S)
            if not a: continue
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            role = re.sub(r"\s+", " ", _clean(tds[1])) if len(tds) > 1 else ""
            yrs = re.findall(r"\(([^()]*\d{4}[^()]*)\)\s*$", role)
            years = yrs[-1] if yrs else ""
            role_only = role[: role.rfind("(" + years + ")")].strip() if years else role
            see = ""
            nxt = re.search(r'lineupBandsRow">\s*<td[^>]*>(.*?)</td>', tr, re.S)
            if nxt: see = re.sub(r"\s+", " ", _clean(nxt.group(1))).replace("See also:", "").strip()
            sy = re.findall(r"(\d{4})", years)
            rows.append({"name": _clean(a.group(3)), "ma_artist": int(a.group(2)), "url": a.group(1), "role": role_only,
                         "roles_ru": roles_ru(role_only), "years": years.replace("present", "н.в."),
                         "start": int(sy[0]) if sy else None, "end": (None if "present" in years else (int(sy[-1]) if sy else None)),
                         "see_also": see[:300]})
        if rows: lineup[tab] = {"title": title, "members": rows}
    if "current" in lineup or "past" in lineup: lineup.pop("all", None)
    res["lineup"] = lineup
    # полная биография
    try:
        c2, bio = curl(f"https://www.metal-archives.com/band/read-more/id/{ma_id}")
        if c2 == 200:
            bio = re.sub(r"<br\s*/?>", "\n", bio)
            res["bio"] = re.sub(r"\n{3,}", "\n\n", _clean(bio))[:6000]
    except Exception: pass
    if not res.get("bio"):
        m = re.search(r'<div class="band_comment[^"]*">(.*?)</div>', h, re.S)
        if m: res["bio"] = re.sub(r"\n{3,}", "\n\n", _clean(re.sub(r"<br\s*/?>", "\n", m.group(1))))[:3000]
    if res.get("bio"): res["bio"] = res["bio"].replace("Read more", "").strip()
    cache_set(key, res)
    return res

def ma_logo(ma_id):
    key = f"malogo:{ma_id}"
    c = cache_get(key, 86400 * 60)
    if c is not None: return c.get("u")
    s = str(ma_id); path = "/".join(s[:4]) if len(s) >= 4 else "/".join(s)
    u = None
    for ext in ("jpg", "png", "gif", "jpeg"):
        url = f"https://www.metal-archives.com/images/{path}/{ma_id}_logo.{ext}"
        code, _ = curl(url, head=True)
        if code == 200: u = url; break
        if code in (403, 429): return None  # не кэшируем при блокировке
    cache_set(key, {"u": u})
    return u

# ---------------- API ----------------
SORTS = {
    "popular": "b.sitelinks DESC, b.name COLLATE NOCASE",
    "name": "b.name COLLATE NOCASE",
    "-name": "b.name COLLATE NOCASE DESC",
    "formed": "b.formed IS NULL, b.formed, b.name COLLATE NOCASE",
    "-formed": "b.formed IS NULL, b.formed DESC, b.name COLLATE NOCASE",
    "dissolved": "b.dissolved IS NULL, b.dissolved DESC",
    "members": "b.n_members DESC, b.sitelinks DESC",
    "popular_ma": "b.sitelinks DESC, b.name COLLATE NOCASE",
    "country": "b.country IS NULL, b.country, b.sitelinks DESC",
    "longevity": "(COALESCE(b.dissolved, 2026) - b.formed) IS NULL, (COALESCE(b.dissolved, 2026) - b.formed) DESC",
}

def api_bands(q):
    g = lambda k, d=None: (q.get(k) or [d])[0]
    where, args = ["b.name IS NOT NULL"], []
    if g("q"):
        where.append("(b.name LIKE ? OR b.name_ru LIKE ? OR b.name_en LIKE ?)")
        s = f"%{g('q')}%"; args += [s, s, s]
    if g("genre"):
        ids = descendants(g("genre")) if g("sub", "1") == "1" else {g("genre")}
        if len(ids) > 400: ids = None   # корневой жанр «рок» покрывает практически всю базу — фильтр не нужен
    if g("genre") and ids:
        where.append(f"b.id IN (SELECT band FROM band_genre WHERE genre IN ({','.join('?' * len(ids))}))")
        args += list(ids)
    if g("country"):
        where.append("b.country = ?"); args.append(g("country"))
    if g("from"):
        where.append("b.formed >= ?"); args.append(int(g("from")))
    if g("to"):
        where.append("b.formed <= ?"); args.append(int(g("to")))
    st = g("status")
    if st == "active": where.append("b.dissolved IS NULL AND COALESCE(b.status_text,'Active') IN ('Active','On hold','Unknown')")
    if st == "dissolved": where.append("(b.dissolved IS NOT NULL OR b.status_text IN ('Split-up','Changed name'))")
    if g("kind") in ("band", "solo"): where.append("b.kind = ?"); args.append(g("kind"))
    if g("ma") == "0": where.append("b.source <> 'metal-archives'")
    if g("ma") == "only": where.append("b.source = 'metal-archives'")
    if g("photo") == "1": where.append("(b.image IS NOT NULL OR b.logo IS NOT NULL)")
    if g("lineup") == "1": where.append("b.n_members > 0")
    if g("instrument"):
        where.append("b.id IN (SELECT m.band FROM membership m JOIN person p ON p.id=m.person WHERE '|'||p.instruments||'|' LIKE ?)")
        args.append(f"%|{g('instrument')}|%")
    if g("person"):
        where.append("b.id IN (SELECT m.band FROM membership m JOIN person p ON p.id=m.person WHERE p.name LIKE ? OR p.name_en LIKE ?)")
        args += [f"%{g('person')}%"] * 2
    sort = SORTS.get(g("sort", "popular"), SORTS["popular"])
    page = max(1, int(g("page", 1))); size = min(200, int(g("size", 48)))
    w = " AND ".join(where)
    total = db().execute(f"SELECT COUNT(*) FROM band b WHERE {w}", args).fetchone()[0]
    rows = db().execute(f"""SELECT b.id,b.name,b.name_ru,b.formed,b.dissolved,b.country,b.origin,b.image,b.logo,b.n_members,b.sitelinks,b.desc_ru,b.desc_en,b.wiki_en,b.wiki_ru,b.kind,b.ma_id,b.ma_genre,b.status_text,b.source,b.born
                            FROM band b WHERE {w} ORDER BY {sort} LIMIT ? OFFSET ?""", args + [size, (page - 1) * size]).fetchall()
    items = [band_row(r) for r in rows]
    ids = [i["id"] for i in items]
    if ids:
        gm = {}
        for r in db().execute(f"SELECT band, genre FROM band_genre WHERE band IN ({','.join('?' * len(ids))})", ids):
            gm.setdefault(r[0], []).append(GENRES.get(r[1], {"name": r[1]})["name"])
        for i in items:
            i["genres"] = gm.get(i["id"], [])[:4]
            if i.get("source") == "metal-archives" and i.get("ma_id"):
                i["logo_thumb"] = f"/api/ma-logo/{i['ma_id']}"
    return {"total": total, "page": page, "size": size, "items": items}

def api_band(bid):
    r = db().execute("SELECT * FROM band WHERE id=?", (bid,)).fetchone()
    if not r: return None
    d = band_row(r)
    d["genres"] = [GENRES.get(x[0], {"id": x[0], "name": x[0]}) for x in db().execute("SELECT genre FROM band_genre WHERE band=?", (bid,))]
    mem = db().execute("""SELECT p.*, m.start, m.end FROM membership m JOIN person p ON p.id=m.person
                          WHERE m.band=? ORDER BY m.end IS NOT NULL, m.start IS NULL, m.start, p.name""", (bid,)).fetchall()
    d["members"] = []
    for m in mem:
        x = dict(m); x["thumb"] = thumb(x.get("image"), 300)
        x["instruments"] = x["instruments"].split("|") if x.get("instruments") else []
        d["members"].append(x)
    d["labels"] = d["labels"].split("|") if d.get("labels") else []
    return d

def api_person(pid):
    r = db().execute("SELECT * FROM person WHERE id=?", (pid,)).fetchone()
    if not r: return None
    d = dict(r); d["thumb"] = thumb(d.get("image"), 500)
    d["instruments"] = d["instruments"].split("|") if d.get("instruments") else []
    d["bands"] = [band_row(x) for x in db().execute("""SELECT b.id,b.name,b.formed,b.dissolved,b.image,b.logo,b.wiki_en,b.wiki_ru,m.start,m.end
        FROM membership m JOIN band b ON b.id=m.band WHERE m.person=? ORDER BY b.formed""", (pid,))]
    return d

def api_stats():
    c = cache_get("stats", 3600)
    if c: return c
    D = db()
    res = {
        "bands": D.execute("select count(*) from band where name is not null").fetchone()[0],
        "persons": D.execute("select count(*) from person").fetchone()[0],
        "genres": D.execute("select count(distinct genre) from band_genre").fetchone()[0],
        "countries": D.execute("select count(distinct country) from band where country is not null").fetchone()[0],
        "with_photo": D.execute("select count(*) from band where image is not null").fetchone()[0],
        "solo": D.execute("select count(*) from band where kind='solo' and name is not null").fetchone()[0],
        "groups": D.execute("select count(*) from band where kind='band' and name is not null").fetchone()[0],
        "ma": D.execute("select count(*) from band where ma_id is not null").fetchone()[0],
        "years": [list(x) for x in D.execute("select formed, count(*) from band where formed between 1940 and 2026 group by formed order by formed")],
        "top_genres": [{"id": x[0], "name": GENRES.get(x[0], {"name": x[0]})["name"], "n": x[1]} for x in
                       D.execute("select genre, count(*) n from band_genre group by genre order by n desc limit 25")],
        "top_countries": [list(x) for x in D.execute("select country, count(*) n from band where country is not null group by country order by n desc limit 25")],
        "top_instruments": [],
    }
    cnt = {}
    for (ins,) in D.execute("select instruments from person where instruments is not null"):
        for i in ins.split("|"): cnt[i] = cnt.get(i, 0) + 1
    res["top_instruments"] = sorted(cnt.items(), key=lambda x: -x[1])[:25]
    cache_set("stats", res)
    return res

def api_facets():
    c = cache_get("facets", 3600)
    if c: return c
    D = db()
    gcount = dict(D.execute("select genre, count(*) from band_genre group by genre").fetchall())
    genres = []
    for gid, g in GENRES.items():
        n = gcount.get(gid, 0)
        if n: genres.append({"id": gid, "name": g["name"], "n": n, "has_sub": bool(CHILDREN.get(gid))})
    genres.sort(key=lambda x: -x["n"])
    countries = [{"name": x[0], "n": x[1]} for x in D.execute("select country, count(*) n from band where country is not null group by country order by n desc")]
    cnt = {}
    for (ins,) in D.execute("select instruments from person where instruments is not null"):
        for i in ins.split("|"): cnt[i] = cnt.get(i, 0) + 1
    instruments = [{"name": k, "n": v} for k, v in sorted(cnt.items(), key=lambda x: -x[1]) if v >= 2]
    res = {"genres": genres, "countries": countries, "instruments": instruments}
    cache_set("facets", res)
    return res

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body, ctype="application/json; charset=utf-8"):
        if not isinstance(body, (bytes, bytearray)):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query); p = u.path
        try:
            if p in ("/", "/index.html"):
                with open(os.path.join(ROOT, "index.html"), "rb") as f:
                    return self.send(200, f.read(), "text/html; charset=utf-8")
            if p == "/api/bands": return self.send(200, api_bands(q))
            if p == "/api/stats": return self.send(200, api_stats())
            if p == "/api/facets": return self.send(200, api_facets())
            if p.endswith(".js") and re.match(r"^/[\w.-]+\.js$", p):
                fp = os.path.join(ROOT, p[1:])
                if os.path.exists(fp):
                    with open(fp, "rb") as f: return self.send(200, f.read(), "application/javascript; charset=utf-8")
            m = re.match(r"^/api/ma/(\d+)$", p)
            if m: return self.send(200, ma_band(int(m.group(1))))
            m = re.match(r"^/api/ma-logo/(\d+)$", p)
            if m:
                u = ma_logo(int(m.group(1)))
                if not u: return self.send(404, {"error": "no logo"})
                self.send_response(302); self.send_header("Location", u); self.send_header("Cache-Control", "max-age=86400"); self.end_headers(); return
            if p == "/api/img":
                u = (q.get("u") or [""])[0]
                if not re.match(r"^https://www\.metal-archives\.com/images/", u): return self.send(400, {"error": "bad url"})
                code, data = curl(u, binary=True)
                if code != 200: return self.send(404, {"error": "img"})
                ct = "image/png" if u.lower().split("?")[0].endswith("png") else ("image/gif" if ".gif" in u.lower() else "image/jpeg")
                self.send_response(200); self.send_header("Content-Type", ct); self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "max-age=604800"); self.end_headers(); self.wfile.write(data); return
            m = re.match(r"^/api/band/((?:Q|MA)\d+)(/wiki)?$", p)
            if m:
                if m.group(2):
                    r = db().execute("select wiki_ru, wiki_en from band where id=?", (m.group(1),)).fetchone()
                    if not r: return self.send(404, {"error": "not found"})
                    res = wiki_intro(r["wiki_ru"]) if r["wiki_ru"] else None
                    if (not res or not res.get("extract")) and r["wiki_en"]:
                        en = wiki_intro(r["wiki_en"])
                        if res and not res.get("image") and en: pass
                        res = en or res
                    elif res and not res.get("image") and r["wiki_en"]:
                        en = wiki_intro(r["wiki_en"]) or {}
                        res["image"] = en.get("image"); res["image_full"] = en.get("image_full")
                    return self.send(200, res or {})
                d = api_band(m.group(1))
                return self.send(200 if d else 404, d or {"error": "not found"})
            m = re.match(r"^/api/person/(Q\d+)(/gear|/wiki)?$", p)
            if m:
                r = db().execute("select wiki_ru, wiki_en from person where id=?", (m.group(1),)).fetchone()
                if m.group(2) == "/gear":
                    if not r: return self.send(404, {})
                    out = []
                    for url in (r["wiki_en"], r["wiki_ru"]):
                        if url:
                            gg = wiki_gear(url)
                            if gg and gg.get("sections"): out.append(gg)
                    return self.send(200, {"sources": out})
                if m.group(2) == "/wiki":
                    if not r: return self.send(404, {})
                    res = wiki_intro(r["wiki_ru"]) if r["wiki_ru"] else None
                    if (not res or not res.get("extract")) and r["wiki_en"]: res = wiki_intro(r["wiki_en"])
                    return self.send(200, res or {})
                d = api_person(m.group(1))
                return self.send(200 if d else 404, d or {"error": "not found"})
            self.send(404, {"error": "not found"})
        except Exception as e:
            import traceback; traceback.print_exc()
            self.send(500, {"error": str(e)})

if __name__ == "__main__":
    load_genres()
    port = int(os.environ.get("PORT", 8080))
    print(f"Rock DB server on 0.0.0.0:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()

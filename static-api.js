/*
 * ROCK·METAL·BASE — статическая версия API.
 * Эмулирует ответы server.py (/api/bands, /api/band/…, /api/person/…, /api/ma/…, /api/stats, /api/facets)
 * поверх JSON-файлов из папки data/, собранных скриптом build_static.py.
 * Сервер не нужен — сайт можно разместить на GitHub Pages, Netlify, Cloudflare Pages и т.п.
 */
(function(){
'use strict';
const BASE = 'data/';
const PFX = 'http://commons.wikimedia.org/wiki/Special:FilePath/';
const NOW = 2026;
const hash = s => { let h = 0; for (let i = 0; i < s.length; i++) h = (Math.imul(h, 31) + s.charCodeAt(i)) >>> 0; return h };
const getJSON = async (u, tries = 3) => {
  for (let i = 0; i < tries; i++){
    try { const r = await fetch(BASE + u); if (!r.ok) throw new Error(u + ' HTTP ' + r.status); return await r.json() }
    catch(e){ if (i === tries - 1) throw e; await new Promise(z => setTimeout(z, 700 * (i + 1))) }
  }
};

/* ---------------- загрузка индекса ---------------- */
let META = null, N = 0, LOADED = 0, ALL = false;
const C = {};            // колонки
const ID2ROW = new Map();
let lc = null;           // строки для поиска
const permCache = {};

function alloc(total){
  C.f = new Int16Array(total); C.d = new Int16Array(total); C.b = new Int16Array(total);
  C.c = new Int16Array(total); C.st = new Uint8Array(total); C.k = new Uint8Array(total); C.src = new Uint8Array(total);
  C.nm = new Uint16Array(total); C.s = new Int32Array(total); C.nr = new Int32Array(total); C.le = new Uint8Array(total);
  C.ma = new Float64Array(total);
  for (const k of ['id','n','r','e','o','im','lg','mg','we','wr','g','ins']) C[k] = new Array(total).fill(null);
}
function addChunk(ch){
  const len = ch.len, at = N, cols = ch.cols;
  for (const [k, arr] of Object.entries(cols)){
    const dst = C[k]; if (!dst) continue;
    if (Array.isArray(dst)) for (let i = 0; i < len; i++) dst[at + i] = arr[i] ?? null;
    else for (let i = 0; i < len; i++) dst[at + i] = arr[i] || 0;
  }
  for (let i = at; i < at + len; i++){
    if (!C.id[i]) C.id[i] = 'MA' + C.ma[i];
    ID2ROW.set(C.id[i], i);
  }
  N += len; LOADED++;
  lc = null; for (const k in permCache) delete permCache[k];
}
const ready0 = (async () => {
  META = await getJSON('meta.json');
  alloc(META.total);
  addChunk(await getJSON(META.chunks[0]));
})();
const readyAll = (async () => {
  await ready0;
  // остальные части грузим параллельно, добавляем по порядку
  const ps = META.chunks.slice(1).map(f => getJSON(f));
  for (const p of ps) addChunk(await p);
  ALL = true;
  window.dispatchEvent(new Event('sapi-all'));
})();

/* ---------------- справочники ---------------- */
let GDESC = null;
function descendants(gid){
  if (!GDESC){
    GDESC = {};
    META.genres.forEach((g, i) => { if (g[3] != null) (GDESC[g[3]] ||= []).push(i) });
  }
  const start = META.genres.findIndex(g => g[0] === gid); if (start < 0) return new Set();
  const out = new Set(), st = [start];
  while (st.length){ const x = st.pop(); if (out.has(x)) continue; out.add(x); (GDESC[x] || []).forEach(y => st.push(y)) }
  return out;
}
const gname = i => META.genres[i][1];
const thumb = (u, w) => u ? u.replace('http://', 'https://') + (u.includes('?') ? '&' : '?') + 'width=' + w : null;
const img = v => v ? (v.startsWith('http') ? v : PFX + v) : null;
const wiki = (lang, t) => t ? `https://${lang}.wikipedia.org/wiki/${t}` : null;
const MA_EXT = ['', 'jpg', 'png', 'gif', 'jpeg'];
function maPath(id){ const s = String(id); return (s.length >= 4 ? s.slice(0, 4) : s).split('').join('/') }
function maLogo(id, le){
  if (le === 255) return null;          // проверено: логотипа нет
  return `https://www.metal-archives.com/images/${maPath(id)}/${id}_logo.${MA_EXT[le] || 'jpg'}`;
}
// перебор расширений картинок Metal Archives при ошибке загрузки
window.maNext = function(el){
  const m = /^(https:\/\/www\.metal-archives\.com\/images\/.+_(?:logo|photo))\.(jpg|png|gif|jpeg)/.exec(el.src || '');
  if (!m) return false;
  const order = ['jpg', 'png', 'gif', 'jpeg'], tried = (el.dataset.tried || m[2]).split(',');
  const next = order.find(x => !tried.includes(x));
  if (!next) return false;
  el.dataset.tried = tried.concat(next).join(',');
  el.src = m[1] + '.' + next;
  return true;
};

/* ---------------- /api/bands ---------------- */
const lon = i => C.f[i] ? (C.d[i] || NOW) - C.f[i] : -1e9;
const nl = (a, b) => (a === 0) - (b === 0);
const SORT = {
  popular:  (a, b) => C.s[b] - C.s[a] || C.nr[a] - C.nr[b],
  name:     (a, b) => C.nr[a] - C.nr[b],
  '-name':  (a, b) => C.nr[b] - C.nr[a],
  formed:   (a, b) => nl(C.f[a], C.f[b]) || C.f[a] - C.f[b] || C.nr[a] - C.nr[b],
  '-formed':(a, b) => nl(C.f[a], C.f[b]) || C.f[b] - C.f[a] || C.nr[a] - C.nr[b],
  dissolved:(a, b) => nl(C.d[a], C.d[b]) || C.d[b] - C.d[a] || C.nr[a] - C.nr[b],
  members:  (a, b) => C.nm[b] - C.nm[a] || C.s[b] - C.s[a] || C.nr[a] - C.nr[b],
  country:  (a, b) => nl(C.c[a], C.c[b]) || C.c[a] - C.c[b] || C.s[b] - C.s[a] || C.nr[a] - C.nr[b],
  longevity:(a, b) => lon(b) - lon(a) || C.nr[a] - C.nr[b],
};
function perm(sort){
  if (permCache[sort]) return permCache[sort];
  const p = new Int32Array(N); for (let i = 0; i < N; i++) p[i] = i;
  p.sort(SORT[sort] || SORT.popular);
  return permCache[sort] = p;
}
let PEOPLE = null;
async function people(){
  if (!PEOPLE){
    const d = await getJSON('people.json');
    PEOPLE = d.n.map((n, i) => [n, d.b[i]]);
  }
  return PEOPLE;
}
const ACTIVE_ST = new Set(), SPLIT_ST = new Set();
async function bands(q){
  const g = k => q.get(k) || '';
  await ready0;
  if (!ACTIVE_ST.size){
    META.statuses.forEach((s, i) => { if (['Active', 'On hold', 'Unknown'].includes(s)) ACTIVE_ST.add(i + 1); if (['Split-up', 'Changed name'].includes(s)) SPLIT_ST.add(i + 1) });
  }
  const tests = [];
  if (g('q')){
    if (!lc){ lc = new Array(N); for (let i = 0; i < N; i++) lc[i] = (C.n[i] + '\n' + (C.r[i] || '') + '\n' + (C.e[i] || '')).toLowerCase() }
    const t = g('q').toLowerCase(); tests.push(i => lc[i].includes(t));
  }
  if (g('genre')){
    const ids = q.get('sub') === '0' ? new Set([META.genres.findIndex(x => x[0] === g('genre'))]) : descendants(g('genre'));
    if (ids.size <= 400) tests.push(i => { const a = C.g[i]; if (!a) return false; for (const x of a) if (ids.has(x)) return true; return false });
  }
  if (g('country')){ const ci = META.countries.indexOf(g('country')) + 1; tests.push(i => C.c[i] === ci) }
  if (g('from')){ const y = +g('from'); tests.push(i => C.f[i] !== 0 && C.f[i] >= y) }
  if (g('to')){ const y = +g('to'); tests.push(i => C.f[i] !== 0 && C.f[i] <= y) }
  if (g('status') === 'active') tests.push(i => !C.d[i] && (C.st[i] === 0 || ACTIVE_ST.has(C.st[i])));
  if (g('status') === 'dissolved') tests.push(i => !!C.d[i] || SPLIT_ST.has(C.st[i]));
  if (g('kind') === 'band') tests.push(i => C.k[i] === 0);
  if (g('kind') === 'solo') tests.push(i => C.k[i] === 1);
  if (g('ma') === '0') tests.push(i => C.src[i] !== 1);
  if (g('ma') === 'only') tests.push(i => C.src[i] === 1);
  if (g('photo') === '1') tests.push(i => !!(C.im[i] || C.lg[i]));
  if (g('lineup') === '1') tests.push(i => C.nm[i] > 0);
  if (g('instrument')){ const ii = META.instruments.indexOf(g('instrument')); tests.push(i => !!C.ins[i] && C.ins[i].includes(ii)) }
  if (g('person')){
    const t = g('person').toLowerCase(), set = new Set();
    for (const [n, bs] of await people()) if (n.includes(t)) bs.forEach(id => { const r = ID2ROW.get(id); if (r != null) set.add(r) });
    tests.push(i => set.has(i));
  }
  const sort = SORT[g('sort')] ? g('sort') : 'popular';
  const page = Math.max(1, +g('page') || 1), size = Math.min(200, +g('size') || 48);
  const ok = i => { for (const t of tests) if (!t(i)) return false; return true };
  let rows;
  if (!tests.length) rows = perm(sort);
  else {
    // если отобрано мало — сортируем только их, иначе фильтруем готовую перестановку
    const hit = []; for (let i = 0; i < N; i++) if (ok(i)) hit.push(i);
    if (hit.length < 30000 || permCache[sort] === undefined && hit.length < N / 3) rows = hit.sort(SORT[sort]);
    else { const p = perm(sort); rows = []; for (let k = 0; k < p.length; k++) if (ok(p[k])) rows.push(p[k]) }
  }
  const total = rows.length, items = [];
  for (let k = (page - 1) * size; k < Math.min(total, page * size); k++) items.push(item(rows[k]));
  return {total, page, size, items, partial: !ALL};
}
function item(i){
  const ma = C.ma[i] || null, src = ['wikidata', 'metal-archives', 'wikidata+metal-archives'][C.src[i]];
  const image = img(C.im[i]), logo = img(C.lg[i]);
  return {
    id: C.id[i], name: C.n[i], name_ru: C.r[i] || C.n[i], formed: C.f[i] || null, dissolved: C.d[i] || null,
    country: C.c[i] ? META.countries[C.c[i] - 1] : null, origin: C.o[i], image, logo,
    n_members: C.nm[i], sitelinks: C.s[i], kind: C.k[i] ? 'solo' : 'band', ma_id: ma, ma_genre: C.mg[i],
    status_text: C.st[i] ? META.statuses[C.st[i] - 1] : null, source: src, born: C.b[i] || null,
    wiki_en: wiki('en', C.we[i]), wiki_ru: wiki('ru', C.wr[i]),
    thumb: thumb(image, 500),
    logo_thumb: src === 'metal-archives' && ma ? maLogo(ma, C.le[i]) : thumb(logo, 300),
    genres: (C.g[i] || []).slice(0, 4).map(gname),
  };
}

/* ---------------- /api/band/:id ---------------- */
const shardCache = {};
function shard(kind, key, n){
  const f = `${kind}/${key % n}.json`;
  return shardCache[f] ||= getJSON(f).catch(e => { delete shardCache[f]; throw e });
}
function person(pid, p){
  const image = img(p.im);
  return {id: pid, name: p.n, name_ru: p.r || p.n, name_en: p.e || p.n, born: p.b || null, died: p.d || null, image,
          thumb: thumb(image, 300), instruments: p.i || [], wiki_en: wiki('en', p.we), wiki_ru: wiki('ru', p.wr)};
}
async function band(id){
  await ready0;
  let i = ID2ROW.get(id);
  if (i == null){ await readyAll; i = ID2ROW.get(id) }
  if (i == null) return {error: 'not found'};
  const b = item(i);
  b.genres = (C.g[i] || []).map(x => ({id: META.genres[x][0], name: gname(x)}));
  b.members = []; b.labels = [];
  if (/^Q/.test(id)){
    const sh = await shard('bd', hash(id), META.shards.bd);
    const d = sh[id] || {};
    Object.assign(b, {desc_ru: d.dr || null, desc_en: d.de || null, website: d.w || null, mbid: d.mb || null, labels: d.l || []});
    b.members = (d.m || []).map(m => ({...person(m[0], m[3]), start: m[1] || null, end: m[2] || null}));
  }
  if (b.source === 'metal-archives') b.logo_thumb = null;
  return b;
}

/* ---------------- /api/person/:id ---------------- */
async function personApi(pid){
  await ready0;
  const sh = await shard('p', hash(pid), META.shards.p);
  const p = sh[pid]; if (!p) return {error: 'not found'};
  const r = person(pid, p); r.thumb = thumb(r.image, 500);
  r.bands = (p.bs || []).map(([bid, s, e]) => { const i = ID2ROW.get(bid); if (i == null) return null; const it = item(i); return {...it, start: s || null, end: e || null} })
    .filter(Boolean).sort((a, b) => (a.formed || 9999) - (b.formed || 9999));
  return r;
}

/* ---------------- /api/ma/:id  (предзагруженные составы Metal Archives) ---------------- */
const ROLE_RU = [['lead guitar','соло-гитара'],['rhythm guitar','ритм-гитара'],['guitars','гитара'],['guitar','гитара'],['bass','бас-гитара'],['drums','ударные'],['percussion','перкуссия'],['keyboards','клавишные'],['synth','синтезатор'],['piano','фортепиано'],['organ','орган'],['vocals','вокал'],['violin','скрипка'],['cello','виолончель'],['flute','флейта'],['saxophone','саксофон'],['programming','программирование'],['samples','семплы'],['electronics','электроника'],['turntables','вертушки'],['harmonica','губная гармоника']];
function rolesRu(t){
  const out = [], low = t.toLowerCase();
  for (const [en, ru] of ROLE_RU){
    if (low.includes(en) && !out.includes(ru) && !(ru === 'гитара' && (out.includes('соло-гитара') || out.includes('ритм-гитара')))) out.push(ru);
  }
  return out;
}
const TABS = {current: 'Текущий состав', past: 'Бывшие участники', live: 'Концертные музыканты', all: 'Состав'};
async function maApi(maId){
  if (!META.shards.ma) return {error: 'no data'};
  const sh = await shard('ma', maId, META.shards.ma);
  const d = sh[maId];
  if (!d) return {error: 'not harvested'};
  const url = `https://www.metal-archives.com/bands/_/${maId}`;
  const res = {ma_id: maId, url, stats: {}, logo: d.logo || null, photo: d.photo || null, lineup: {}};
  const i = ID2ROW.get('MA' + maId) ?? [...ID2ROW.values()].find(r => C.ma[r] === maId);
  const K = {loc: 'Location', st: 'Status', th: 'Themes', lb: 'Current label', ya: 'Years active'};
  for (const [k, v] of Object.entries(K)) if (d[k]) res.stats[v] = d[k];
  if (i != null){ if (C.mg[i]) res.stats['Genre'] = C.mg[i]; if (C.f[i]) res.stats['Formed in'] = String(C.f[i]) }
  for (const [tab, rows] of Object.entries(d.l || {})){
    res.lineup[tab] = {title: TABS[tab] || tab, members: rows.map(([name, aid, roleFull]) => {
      const yrs = /\(([^()]*\d{4}[^()]*)\)\s*$/.exec(roleFull), years = yrs ? yrs[1] : '';
      const role = years ? roleFull.slice(0, roleFull.lastIndexOf('(' + years + ')')).trim() : roleFull;
      const sy = years.match(/\d{4}/g) || [];
      return {name, ma_artist: aid, url: `https://www.metal-archives.com/artists/_/${aid}`, role, roles_ru: rolesRu(role),
              years: years.replace('present', 'н.в.'), start: sy.length ? +sy[0] : null,
              end: /present/.test(years) ? null : (sy.length ? +sy[sy.length - 1] : null), see_also: ''};
    })};
  }
  if (d.bio){
    const bio = d.bio.replace(/^Contact:\s*(\[email[^\]]*\]|\S+)\s*/i, '').trim();
    if (bio) res.bio = bio + (d.bio.length >= 300 ? '…' : '');
  }
  return res;
}

/* ---------------- маршрутизатор ---------------- */
const STATIC = {};
async function SAPI(url){
  const u = new URL(url, location.href), p = u.pathname.replace(/^.*\/api\//, '/api/');
  let m;
  if (p === '/api/bands') return bands(u.searchParams);
  if (p === '/api/stats' || p === '/api/facets'){
    const k = p.slice(5); return STATIC[k] ||= getJSON(k + '.json');
  }
  if ((m = /^\/api\/band\/((?:Q|MA)\d+)$/.exec(p))) return band(m[1]);
  if ((m = /^\/api\/person\/(Q\d+)$/.exec(p))) return personApi(m[1]);
  if ((m = /^\/api\/ma\/(\d+)$/.exec(p))){ await ready0; return maApi(+m[1]) }
  if ((m = /^\/api\/gear\/(Q\d+)$/.exec(p))){   // предрасчитанное оборудование музыканта
    await ready0; if (!META.shards.g) return {};
    const sh = await shard('g', hash(m[1]), META.shards.g); return sh[m[1]] || {};
  }
  return {};
}
window.SAPI = SAPI;
window.SAPI_STATE = () => ({loaded: N, total: META && META.total, all: ALL});
})();

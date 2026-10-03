import json, os, re, html, time
from datetime import datetime
from urllib.parse import quote_plus

import feedparser
import streamlit as st
import io, hashlib
import pandas as pd
import requests
from concepts import load_concepts
import opensanctions as osn
from legal import LEGAL

st.set_page_config(page_title="CWP – Compliance Watch", page_icon="🛡️", layout="wide")

SEEN_FILE = "seen_items.json"
ALERT_FILE = "alerts.json"

# ---------- Sources : requêtes Google News (fiables) + flux officiels (à vérifier) ----------
def gnews(q, lang="fr"):
    return f"https://news.google.com/rss/search?q={quote_plus(q)}&hl={lang}&gl={'FR' if lang=='fr' else 'US'}&ceid={'FR:fr' if lang=='fr' else 'US:en'}"

THEMES = {
    "Sanctions": [gnews("sanctions OFAC OR \"gel des avoirs\" OR \"paquet de sanctions\""), gnews("OFAC sanctions designations", "en")],
    "Embargos": [gnews("embargo OR \"contrôle des exportations\" OR \"double usage\""), gnews("export controls embargo BIS", "en")],
    "LCB-FT / AMLA": [gnews("AMLA autorité européenne blanchiment OR AMLR OR \"LCB-FT\""), gnews("AMLA anti-money laundering authority EU", "en")],
    "GAFI / FATF": [gnews("GAFI liste grise OR FATF grey list"), gnews("FATF plenary grey list", "en")],
    "Régulateurs (ACPR/AMF/EBA)": [gnews("ACPR sanction OR AMF sanction conformité"), gnews("EBA ESMA guidelines compliance", "en")],
    "Anticorruption / ESG": [gnews("Sapin II AFA OR corruption OR CSDDD OR CSRD"), gnews("FCPA enforcement", "en")],
    "Crypto / DORA / MiCA": [gnews("MiCA OR DORA OR \"travel rule\" crypto conformité")],
}

OFFICIAL_LINKS = {
    "OFAC – Recent Actions": "https://ofac.treasury.gov/recent-actions",
    "UE – Carte des sanctions": "https://www.sanctionsmap.eu",
    "DG Trésor – Registre des gels": "https://gels-avoirs.dgtresor.gouv.fr",
    "ONU – Sanctions CSNU": "https://main.un.org/securitycouncil/en/sanctions/information",
    "GAFI / FATF": "https://www.fatf-gafi.org/en/the-fatf.html",
    "AMLA": "https://www.amla.europa.eu",
    "ACPR": "https://acpr.banque-france.fr",
    "TRACFIN": "https://www.economie.gouv.fr/tracfin",
    "EBA": "https://www.eba.europa.eu",
    "EUR-Lex": "https://eur-lex.europa.eu",
}

CALENDAR = [
    ("17/01/2025", "DORA applicable", "Résilience opérationnelle numérique du secteur financier."),
    ("30/12/2024", "MiCA + Travel Rule (TFR)", "Régime crypto-actifs et traçabilité des transferts."),
    ("10/07/2027", "AMLR / transposition AMLD6", "Règles LCB-FT unifiées, à vérifier auprès d'EUR-Lex."),
    ("2028", "Supervision directe AMLA", "Sélection des entités transfrontalières à haut risque."),
]

# ---------- Style MAM ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;700&family=Share+Tech+Mono&display=swap');
:root{--bg:#050b14;--card:#0a1a2a;--cy:#00d4ff;--gr:#00ff88;--pu:#a855f7;--rd:#ff4d6d}
.stApp{background:var(--bg);color:#cfe3f5;font-family:'Rajdhani',sans-serif}
[data-testid=stSidebar]{background:#060e1a;border-right:1px solid #12263a}
h1,h2,h3{font-family:'Rajdhani';letter-spacing:.15em;text-transform:uppercase}
h1{color:var(--gr);text-shadow:0 0 14px #00ff8866}
h2,h3{color:var(--cy)}
.brand{font-size:2.6rem;color:var(--gr);text-align:center;letter-spacing:.4em;text-shadow:0 0 18px #00ff88aa;font-weight:700}
.sub{font-family:'Share Tech Mono';font-size:.7rem;color:#3a5870;text-align:center;letter-spacing:.3em;margin-bottom:1rem}
.card{background:linear-gradient(135deg,#0a1f33,#0d1530);border:1px solid #13405e;border-radius:12px;padding:14px 18px;margin-bottom:10px}
.card a{color:var(--cy);text-decoration:none}
.tag{font-family:'Share Tech Mono';font-size:.7rem;padding:2px 8px;border:1px solid var(--pu);color:var(--pu);border-radius:4px;margin-right:8px}
.new{border-color:var(--gr);color:var(--gr)}
.meta{font-family:'Share Tech Mono';font-size:.72rem;color:#52708a}
.kpi{font-family:'Share Tech Mono';font-size:2rem;color:var(--gr)}
</style>""", unsafe_allow_html=True)

# ---------- Collecte ----------
def clean(t, n=280):
    t = html.unescape(re.sub(r"<[^>]+>", " ", t or ""))
    t = re.sub(r"\s+", " ", t).strip()
    return t[:n] + ("…" if len(t) > n else "")

@st.cache_data(ttl=900, show_spinner=False)
def fetch_all():
    items, seen_links = [], set()
    for theme, urls in THEMES.items():
        for u in urls:
            try:
                feed = feedparser.parse(u)
            except Exception:
                continue
            for e in feed.entries[:12]:
                link = e.get("link")
                if not link or link in seen_links:
                    continue
                seen_links.add(link)
                ts = time.mktime(e.published_parsed) if e.get("published_parsed") else 0
                src = (e.get("source") or {}).get("title", "") if isinstance(e.get("source"), dict) else ""
                items.append(dict(theme=theme, title=clean(e.get("title"), 160), desc=clean(e.get("summary")),
                                  link=link, ts=ts, source=src))
    return sorted(items, key=lambda x: x["ts"], reverse=True)

def load_seen():
    if os.path.exists(SEEN_FILE):
        try: return set(json.load(open(SEEN_FILE)))
        except Exception: pass
    return set()

def save_seen(s):
    json.dump(list(s), open(SEEN_FILE, "w"))

def load_kw():
    try: return json.load(open(ALERT_FILE))
    except Exception: return []

def hits(it, kws):
    t = (it["title"] + " " + it["desc"]).lower()
    return [k for k in kws if k.lower() in t]

def summarize(url, n=3):
    """Résumé extractif (sans LLM) : phrases les plus riches en mots fréquents."""
    try:
        r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        txt = re.sub(r"(?is)<(script|style|nav|footer).*?</\1>", " ", r.text)
        txt = clean(txt, 20000)
    except Exception:
        return "Résumé indisponible (page inaccessible ou redirection Google News)."
    sents = [x for x in re.split(r"(?<=[.!?])\s+", txt) if 50 < len(x) < 300]
    words = [w for w in re.findall(r"\w{5,}", txt.lower())]
    freq = {w: words.count(w) for w in set(words)}
    scored = sorted(sents, key=lambda x: -sum(freq.get(w, 0) for w in re.findall(r"\w{5,}", x.lower())) / (len(x) ** 0.5))
    return " ".join(scored[:n]) or "Résumé indisponible."

def to_excel(rows):
    df = pd.DataFrame(rows)
    df["date"] = df["ts"].apply(lambda t: datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M") if t else "")
    buf = io.BytesIO()
    df[["date", "theme", "title", "desc", "source", "link"]].to_excel(buf, index=False)
    return buf.getvalue()

def render(it, new=False):
    d = datetime.fromtimestamp(it["ts"]).strftime("%d/%m/%Y %H:%M") if it["ts"] else "—"
    badge = '<span class="tag new">NOUVEAU</span>' if new else ""
    st.markdown(f"""<div class="card">{badge}<span class="tag">{it['theme']}</span>
<span class="meta">{d} · {it['source']}</span><br>
<b><a href="{it['link']}" target="_blank">{html.escape(it['title'])}</a></b><br>
<span style="color:#9bb4c9">{html.escape(it['desc'])}</span><br>
<a class="meta" href="{it['link']}" target="_blank">🔗 Consulter la source</a></div>""", unsafe_allow_html=True)
    h = hits(it, KWS)
    if h: st.markdown(f'<span class="tag" style="border-color:#ff4d6d;color:#ff4d6d">🚨 ALERTE : {", ".join(h)}</span>', unsafe_allow_html=True)
    if st.button("📝 Résumé", key="s" + hashlib.md5(it["link"].encode()).hexdigest()):
        st.info(summarize(it["link"]))

# ---------- Sidebar ----------
with st.sidebar:
    st.markdown('<div class="brand">CWP</div><div class="sub">COMPLIANCE WATCH PLATFORM</div>', unsafe_allow_html=True)
    page = st.radio("Navigation", ["🏠 Dashboard", "📡 Veille", "🔎 OpenSanctions", "⚖️ Textes de loi", "📅 Calendrier réglementaire", "📚 Glossaire", "🔗 Sources officielles"], label_visibility="collapsed")
    kw_in = st.text_area("🚨 Mots-clés d'alerte (un par ligne)", "\n".join(load_kw()), placeholder="Russie\nIran\nNom d'une entité")
    KWS = [k.strip() for k in kw_in.splitlines() if k.strip()]
    json.dump(KWS, open(ALERT_FILE, "w"))
    if st.button("🔄 Rafraîchir la veille", use_container_width=True):
        fetch_all.clear(); st.rerun()

items = fetch_all()
seen = load_seen()
new_links = {i["link"] for i in items} - seen if seen else set()
if page == "🏠 Dashboard" and items:
    pass  # marquage conservé pendant l'affichage, mémorisé après rendu

# ---------- Pages ----------
if page == "🏠 Dashboard":
    st.markdown("# 🛡️ Dashboard — CWP")
    st.caption(f"Dernière mise à jour : {datetime.now():%d/%m/%Y %H:%M} · flux actualisés toutes les 15 min")
    c = st.columns(4)
    c[0].markdown(f'<div class="card"><div class="meta">ARTICLES</div><div class="kpi">{len(items)}</div></div>', unsafe_allow_html=True)
    c[1].markdown(f'<div class="card"><div class="meta">NOUVEAUX</div><div class="kpi">{len(new_links)}</div></div>', unsafe_allow_html=True)
    c[2].markdown(f'<div class="card"><div class="meta">THÈMES</div><div class="kpi">{len(THEMES)}</div></div>', unsafe_allow_html=True)
    c[3].markdown(f'<div class="card"><div class="meta">CONCEPTS</div><div class="kpi">{len(load_concepts())}</div></div>', unsafe_allow_html=True)
    alerts = [i for i in items if hits(i, KWS)]
    if alerts:
        st.markdown(f"### 🚨 Alertes ({len(alerts)})")
        for it in alerts[:8]: render(it, it["link"] in new_links)
    st.markdown("### Dernières mises à jour")
    for it in items[:15]:
        render(it, it["link"] in new_links)
    save_seen(seen | {i["link"] for i in items})

elif page == "📡 Veille":
    st.markdown("# 📡 Veille")
    col1, col2 = st.columns([2, 1])
    q = col1.text_input("Recherche", placeholder="ex : Russie, AMLA, OFAC…")
    sel = col2.multiselect("Thèmes", list(THEMES), default=list(THEMES))
    only_new = st.checkbox("Uniquement les nouveautés", value=False)
    only_alert = st.checkbox("Uniquement les alertes", value=False)
    shown = [i for i in items if i["theme"] in sel and (not q or q.lower() in (i["title"] + i["desc"]).lower())
             and (not only_new or i["link"] in new_links) and (not only_alert or hits(i, KWS))]
    if shown:
        st.download_button("📥 Export Excel", to_excel(shown), f"veille_conformite_{datetime.now():%Y%m%d}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    for it in items:
        if it["theme"] not in sel: continue
        if q and q.lower() not in (it["title"] + it["desc"]).lower(): continue
        if only_new and it["link"] not in new_links: continue
        if only_alert and not hits(it, KWS): continue
        render(it, it["link"] in new_links)

elif page == "📅 Calendrier réglementaire":
    st.markdown("# 📅 Calendrier réglementaire")
    st.caption("Dates indicatives : vérifiez toujours sur EUR-Lex / sites officiels.")
    for d, t, desc in CALENDAR:
        st.markdown(f'<div class="card"><span class="tag">{d}</span><b>{t}</b><br><span style="color:#9bb4c9">{desc}</span></div>', unsafe_allow_html=True)

elif page == "📚 Glossaire":
    df = load_concepts()
    st.markdown(f"# 📚 Glossaire — {len(df)} concepts")
    col1, col2 = st.columns([2, 1])
    q = col1.text_input("Rechercher un concept")
    cat = col2.selectbox("Catégorie", ["Toutes"] + sorted(df.categorie.unique()))
    if cat != "Toutes": df = df[df.categorie == cat]
    if q: df = df[df.apply(lambda r: q.lower() in " ".join(map(str, r)).lower(), axis=1)]
    for _, r in df.iterrows():
        with st.expander(f"{r.terme}  ·  {r.categorie}"):
            st.markdown(f"**Définition** — {r.definition}")
            st.markdown(f"**Décorticage** — {r.decorticage}")
            st.markdown(f"**Actualité / échéance** — {r.actualite}")

elif page == "🔎 OpenSanctions":
    st.markdown("# 🔎 OpenSanctions")
    st.caption("Recherche dans les listes de sanctions, PPE et entités à risque agrégées par OpenSanctions (clé API requise).")
    c1, c2 = st.columns([3, 1])
    q = c1.text_input("Nom d'une personne, société ou navire")
    schema = c2.selectbox("Type", ["Thing", "Person", "Company", "Organization", "Vessel"])
    if q:
        try:
            for r in osn.search(q, schema):
                p = r.get("properties", {})
                st.markdown(f"""<div class="card"><span class="tag">{r.get('schema')}</span>
<b><a href="https://www.opensanctions.org/entities/{r['id']}/" target="_blank">{html.escape(r.get('caption',''))}</a></b><br>
<span class="meta">Pays : {', '.join(p.get('country', [])) or '—'} · Thèmes : {', '.join(p.get('topics', [])) or '—'}</span><br>
<span class="meta">Listes : {', '.join(r.get('datasets', [])[:6])}</span></div>""", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"OpenSanctions : {e}")
    st.markdown("[Données en vrac gratuites (usage non commercial)](https://www.opensanctions.org/datasets/)")

elif page == "⚖️ Textes de loi":
    st.markdown("# ⚖️ Textes de loi")
    st.caption("Vérifiez les références sur Légifrance. Ajoutez vos textes dans legal.py.")
    for name, ref, desc, url in LEGAL:
        st.markdown(f'<div class="card"><b><a href="{url}" target="_blank">{name}</a></b> <span class="tag">{ref}</span><br><span style="color:#9bb4c9">{desc}</span></div>', unsafe_allow_html=True)

else:
    st.markdown("# 🔗 Sources officielles")
    for n, u in OFFICIAL_LINKS.items():
        st.markdown(f'<div class="card"><a href="{u}" target="_blank">{n}</a></div>', unsafe_allow_html=True)

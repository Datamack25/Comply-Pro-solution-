import json, os, re, html, time
from datetime import datetime
from urllib.parse import quote_plus
from collections import Counter

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

# Requêtes ciblées sur des mesures effectivement prononcées (utilisées par la page d'accueil)
ACTION_FEEDS = {
    "Sanctions": [gnews("\"impose des sanctions\" OR \"nouvelles sanctions\" OR \"paquet de sanctions\" adopté"),
                  gnews("OFAC designates OR \"imposes sanctions\" OR \"sanctions on\"", "en"),
                  gnews("\"gel des avoirs\" OR \"asset freeze\" OR \"assets frozen\""),
                  gnews("OFSI OR \"EU Council\" sanctions adopted listing", "en")],
    "Régulateurs (ACPR/AMF/EBA)": [gnews("ACPR \"commission des sanctions\" amende OR blâme"),
                                   gnews("AMF \"commission des sanctions\" amende"),
                                   gnews("fined million anti-money laundering OR AML failings", "en"),
                                   gnews("FinCEN OR OFAC settlement penalty million", "en")],
    "Embargos": [gnews("embargo imposé OR \"interdiction d'exportation\" OR \"contrôles à l'exportation\" annonce"),
                 gnews("BIS \"entity list\" adds OR \"export ban\" imposed", "en")],
    "GAFI / FATF": [gnews("GAFI ajoute OR retire \"liste grise\""), gnews("FATF adds OR removes grey list", "en")],
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
:root{--bg:#050b14;--card:#0a1a2a;--cy:#00d4ff;--gr:#00ff88;--pu:#a855f7;--rd:#ff4d6d;--gold:#f5c542}
.stApp{background:var(--bg);color:#cfe3f5;font-family:'Rajdhani',sans-serif}
[data-testid=stSidebar]{background:#060e1a;border-right:1px solid #12263a}
h1,h2,h3{font-family:'Rajdhani';letter-spacing:.15em;text-transform:uppercase}
h1{color:var(--gr);text-shadow:0 0 14px #00ff8866}
h2,h3{color:var(--cy)}
.brand{font-size:2.6rem;color:var(--gr);text-align:center;letter-spacing:.4em;text-shadow:0 0 18px #00ff88aa;font-weight:700}
.sub{font-family:'Share Tech Mono';font-size:.7rem;color:#3a5870;text-align:center;letter-spacing:.3em;margin-bottom:1rem}
.card{background:linear-gradient(135deg,#0a1f33,#0d1530);border:1px solid #13405e;border-radius:12px;padding:14px 18px;margin-bottom:10px}
.card a{color:var(--cy);text-decoration:none}
.tag{font-family:'Share Tech Mono';font-size:.7rem;padding:2px 8px;border:1px solid var(--pu);color:var(--pu);border-radius:4px;margin-right:8px;white-space:nowrap}
.new{border-color:var(--gr);color:var(--gr)}
.meta{font-family:'Share Tech Mono';font-size:.72rem;color:#52708a}
.kpi{font-family:'Share Tech Mono';font-size:2rem;color:var(--gr)}
/* ---- Page d'accueil ---- */
.hero{border:1px solid #f5c54255;border-radius:14px;padding:18px 24px;margin-bottom:14px;background:linear-gradient(90deg,#1a1405,#0a1a2a 65%)}
.hero-t{font-size:2.1rem;font-weight:700;color:var(--gold);letter-spacing:.06em;text-shadow:0 0 14px #f5c54244}
.hero-t span{color:#cfe3f5;font-weight:500;font-size:1.35rem}
.hero-s{font-family:'Share Tech Mono';font-size:.8rem;color:#8aa4ba;letter-spacing:.08em;margin-top:4px}
.wwrap{overflow-x:auto;border:1px solid #13405e;border-radius:12px;background:linear-gradient(135deg,#0a1f33,#0d1530);margin-bottom:8px}
.wtable{width:100%;border-collapse:collapse;font-size:.98rem}
.wtable th{font-family:'Share Tech Mono';font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;color:var(--gold);text-align:left;padding:11px 12px;border-bottom:1px solid #f5c54266;background:#081626;white-space:nowrap}
.wtable td{padding:10px 12px;border-bottom:1px solid #12263a;vertical-align:top;color:#cfe3f5}
.wtable tr:hover td{background:#0e2238}
.wtable a{color:#e3f1fc;text-decoration:none}
.wtable a:hover{color:var(--cy)}
.ent{color:var(--cy);font-weight:700;min-width:140px}
.mz{font-family:'Share Tech Mono';font-size:.7rem;padding:2px 8px;border-radius:4px;border:1px solid;white-space:nowrap}
.chip{display:inline-block;font-family:'Share Tech Mono';font-size:.75rem;padding:4px 11px;margin:0 6px 6px 0;border:1px solid #13405e;border-radius:20px;color:#cfe3f5;background:#0a1a2a}
.chip b{color:var(--gr);margin-left:5px}
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

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_actions():
    """Flux ciblés sanctions/embargos, plus profonds (30 articles par requête) pour remonter dans le temps."""
    out, seen_l = [], set()
    for theme, urls in ACTION_FEEDS.items():
        for u in urls:
            try:
                feed = feedparser.parse(u)
            except Exception:
                continue
            for e in feed.entries[:30]:
                link = e.get("link")
                if not link or link in seen_l:
                    continue
                seen_l.add(link)
                ts = time.mktime(e.published_parsed) if e.get("published_parsed") else 0
                src = (e.get("source") or {}).get("title", "") if isinstance(e.get("source"), dict) else ""
                out.append(dict(theme=theme, title=clean(e.get("title"), 160), desc=clean(e.get("summary")),
                                link=link, ts=ts, source=src))
    return out

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

# ---------- Classification automatique (heuristique, sans IA) ----------
# (code ISO, nom affiché, motifs recherchés dans le titre en minuscules)
COUNTRIES = [
    ("RU", "Russie", ["russie", "russia", "russian", "russe", "russes", "moscou", "moscow", "kremlin"]),
    ("IR", "Iran", ["iran"]),
    ("KP", "Corée du Nord", ["corée du nord", "north korea", "pyongyang", "dprk"]),
    ("CN", "Chine", ["chine", "china", "chinese", "chinois", "chinoise", "pékin", "beijing", "hong kong"]),
    ("US", "États-Unis", ["états-unis", "etats-unis", "united states", "u.s.", " us ", " usa ", "washington", "américain", "american"]),
    ("EU", "Union européenne", [" ue ", " eu ", "union européenne", "european union", "bruxelles", "brussels", "européen", "european", "europe", "l'europe"]),
    ("FR", "France", ["france", "français", "française", "acpr", " amf ", "tracfin", "bercy"]),
    ("GB", "Royaume-Uni", ["royaume-uni", "united kingdom", " uk ", "britain", "british", "britannique", "londres", "london", " fca ", "ofsi"]),
    ("UA", "Ukraine", ["ukraine", "ukrain"]),
    ("BY", "Biélorussie", ["biélorussie", "belarus"]),
    ("SY", "Syrie", ["syrie", "syria"]),
    ("VE", "Venezuela", ["venezuela"]),
    ("CU", "Cuba", ["cuba"]),
    ("AE", "Émirats arabes unis", ["émirats", "emirates", " uae ", "dubaï", "dubai"]),
    ("TR", "Turquie", ["turquie", "turkey", "türkiye"]),
    ("IL", "Israël", ["israël", "israel"]),
    ("LB", "Liban", ["liban", "lebanon"]),
    ("AF", "Afghanistan", ["afghanistan"]),
    ("MM", "Myanmar", ["myanmar", "birmanie"]),
    ("IN", "Inde", [" inde ", "india"]),
    ("DE", "Allemagne", ["allemagne", "germany", "german", "bafin"]),
    ("CH", "Suisse", ["suisse", "switzerland", "swiss", "finma"]),
    ("HT", "Haïti", ["haïti", "haiti"]),
    ("NG", "Nigeria", ["nigeria"]),
    ("ZA", "Afrique du Sud", ["afrique du sud", "south africa"]),
    ("MX", "Mexique", ["mexique", "mexico", "mexican"]),
    ("VN", "Vietnam", ["vietnam", "viêt nam"]),
]

# (clé, libellé, couleur écran, couleur export, motifs) — l'ordre fixe la priorité
MEASURES = [
    ("gel", "Gel des avoirs", "#ff4d6d", "#c62839", ["gel des avoirs", "gel d'avoirs", "asset freeze", "assets frozen", "frozen assets", "freezes assets"]),
    ("liste", "Liste GAFI", "#ffb020", "#b7791f", ["liste grise", "grey list", "gray list", "greylist", "liste noire", "black list", "high-risk jurisdiction", "juridictions à haut risque"]),
    ("amende", "Amende", "#ff7a45", "#c2541b", ["amende", "fined", " fine ", " fines ", "pénalité", "penalty", "penalties", "settlement", "commission des sanctions"]),
    ("sanction", "Sanction", "#ff4d6d", "#c62839", ["sanction", "designat", "désign", "sdn list", "blacklist", "paquet de"]),
    ("embargo", "Embargo / export", "#a855f7", "#7e3fbf", ["embargo", "export control", "contrôle des exportations", "contrôles à l'exportation", "double usage", "dual-use", "dual use"]),
    ("enquete", "Enquête / poursuite", "#00d4ff", "#1a6fa0", ["enquête", "investigation", "probe", "charged", "inculp", "mis en examen", "poursuit", "indict", "arrest", "interpell", "condamn", "convicted", "perquisition", "raid"]),
    ("regle", "Réglementation", "#00ff88", "#1d8a55", ["règlement", "directive", "guidelines", "lignes directrices", "consultation", "amlr", "mica", "dora", "entre en vigueur", "applicable", "rule", "framework", "standard"]),
]
NEWS_MEASURE = ("news", "Actualité", "#52708a", "#6b7c8c")
SANCTION_KINDS = {"gel", "liste", "amende", "sanction", "embargo"}
SCREEN_COLOR = {m[0]: m[2] for m in MEASURES} | {"news": NEWS_MEASURE[2]}
EXPORT_COLOR = {m[0]: m[3] for m in MEASURES} | {"news": NEWS_MEASURE[3]}

AUTHORITIES = [
    ("OFAC", ["ofac"]), ("Trésor US", ["treasury", "trésor américain"]), ("OFSI", ["ofsi"]),
    ("Conseil de l'UE", ["conseil de l'ue", "council of the eu", "eu council", "commission européenne", "european commission"]),
    ("ONU", [" onu ", "united nations", "nations unies", "conseil de sécurité", "security council"]),
    ("GAFI", ["gafi", "fatf"]), ("AMLA", ["amla"]), ("ACPR", ["acpr"]), ("AMF", [" amf ", "autorité des marchés"]),
    ("Tracfin", ["tracfin"]), ("EBA", [" eba ", "autorité bancaire européenne", "european banking authority"]),
    ("ESMA", ["esma"]), ("BCE", [" bce ", " ecb ", "banque centrale européenne"]), ("FCA", [" fca "]),
    ("FinCEN", ["fincen"]), ("SEC", [" sec "]), ("DOJ", [" doj ", "department of justice", "justice department"]),
    ("BIS", [" bis ", "bureau of industry"]), ("AFA", [" afa ", "agence française anticorruption"]),
    ("PNF", [" pnf ", "parquet national financier"]), ("FINMA", ["finma"]), ("BaFin", ["bafin"]),
]

_STOP = set("""le la les l un une des du de d au aux et en à a sur pour par avec dans selon après avant contre face vers
ce cette ces il elle ils elles on nous voici est sont sera plus moins fin premier première nouveau nouvelle nouveaux nouvelles
comment pourquoi quand quel quelle quels quelles qui que quoi
the a an of and to in on for with by at from as is are be will can could should would it its his her their new first top more
how why what who when where this that these those over under amid after before into about
exclusive exclusif breaking update live analyse analysis opinion tribune interview vidéo video podcast édito
sources source devant derrière regarder documentaire reportage enquête décryptage infographie carte vidéos photos
capitole parlement parliament gouvernement government ministère ministry ministre minister président president
présidente patron patronne chef chief ceo directeur director premier ministre manifestants protesters
congrès congress sénat senate assemblée maison blanche white house élysée matignon
selon alors face voici voilà pourquoi comment ici là
nord sud est ouest north south east west
must pay pays paid fined fines hits hit adopt adopts adopted impose imposes imposed nearly officially record largest
biggest ever agrees agree settles settle faces face says hails welcomes slaps sanctioning sees amid
foreign ministers ministres affaires étrangères diplomates diplomats leaders dirigeants
listings listing targeting individuals entities individus entités military defense industry complex
sanction sanctions sanctionne sanctionné sanctionnée sanctionnés sanctionnées sanctioned sanctioning
gel avoirs embargo amende amendes liste grise noire grey gray list
treasury trésor targets target designates designated imposes impose adds announces says said council conseil commission
blanchiment fraude corruption conformité terrorisme financement crypto cryptos cryptomonnaie cryptomonnaies
money laundering aml lcb-ft régulateur regulator rapport report guide export exports
ue eu us uk usa u.s onu un
lundi mardi mercredi jeudi vendredi samedi dimanche janvier février mars avril mai juin juillet août septembre octobre novembre décembre
monday tuesday wednesday thursday friday saturday sunday january february march april may june july august september october november december""".split())
_STOP |= {w.lower() for a, _ in AUTHORITIES for w in a.split()}
_STOP |= {w.strip(" .").lower() for _, n, ps in COUNTRIES for p in ps + [n] for w in p.split()}
_CONN = {"de", "du", "des", "of", "and", "&", "la", "le", "el", "al", "bin", "van", "von", "y"}

def _norm_text(s):
    return " " + re.sub(r"[,;:!?()\[\]«»\"“”‘’|/]", " ", (s or "").lower()) + " "

def headline_of(it):
    t, src = it["title"], it.get("source") or ""
    if src and t.endswith(" - " + src):
        return t[: -(len(src) + 3)].strip()
    return re.sub(r"\s+-\s+[^-]{2,60}$", "", t).strip()

def detect_country(text):
    best = None
    for code, name, pats in COUNTRIES:
        pos = [text.find(p) for p in pats if p in text]
        if pos and (best is None or min(pos) < best[0]):
            best = (min(pos), code, name)
    return (best[1], best[2]) if best else ("", "—")

def detect_measure(text):
    for key, label, _, _, pats in MEASURES:
        if any(p in text for p in pats):
            return key, label
    return NEWS_MEASURE[0], NEWS_MEASURE[1]

_CUR = r"(?P<cur>€|\$|£|eur(?:os?)?|euros?|usd|dollars?|gbp|livres?(?: sterling)?|chf|francs? suisses?)"
_NUM = r"(?P<num>\d{1,3}(?:[   .,]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
_MULT = r"(?P<mult>milliards?|billions?|bn|mds?|md|millions?|mn|mio|m|mille|k)?"
_AMOUNT_RES = [
    re.compile(_CUR + r"\s?" + _NUM + r"\s?" + _MULT + r"\b", re.I),          # $5 million, €1,2 md
    re.compile(_NUM + r"\s?" + _MULT + r"\s?(?:d['’]\s?|de\s)?" + _CUR, re.I),  # 5 M€, 1,2 milliard d'euros
]
_CUR_SYM = {"€": "€", "eur": "€", "euro": "€", "euros": "€", "$": "$", "usd": "$", "dollar": "$", "dollars": "$",
            "£": "£", "gbp": "£", "livre": "£", "livres": "£", "chf": "CHF"}

def _to_float(num):
    n = re.sub(r"[   ]", "", num)
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", n):          # 1.500.000 / 1,500,000
        return float(re.sub(r"[.,]", "", n))
    return float(n.replace(",", "."))

def detect_amount(text):
    """Renvoie (montant lisible, valeur numérique) ou ("—", 0)."""
    best = None
    for rx in _AMOUNT_RES:
        for m in rx.finditer(text):
            try:
                v = _to_float(m.group("num"))
            except ValueError:
                continue
            mult = (m.group("mult") or "").lower()
            if mult.startswith(("milliard", "billion", "bn", "md")): v *= 1e9
            elif mult.startswith(("million", "mn", "mio")) or mult == "m": v *= 1e6
            elif mult in ("mille", "k"): v *= 1e3
            cur = m.group("cur").lower()
            sym = next((v2 for k, v2 in _CUR_SYM.items() if cur.startswith(k)), cur.upper())
            if v < 1000 and not mult:   # « 22e paquet », années, etc. : ignorés
                continue
            if best is None or v > best[1]:
                best = (sym, v)
    if not best:
        return "—", 0
    sym, v = best
    if v >= 1e9: s_ = f"{v/1e9:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " Md"
    elif v >= 1e6: s_ = f"{v/1e6:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " M"
    else: s_ = f"{v:,.0f}".replace(",", " ")
    return f"{s_} {sym}", v

def detect_authorities(text):
    return ", ".join([n for n, pats in AUTHORITIES if any(p in text for p in pats)][:2])

def extract_entity(h):
    """Premier groupe de mots à majuscule qui n'est ni un pays, ni une autorité, ni un mot courant."""
    groups, cur = [], []
    for w in re.findall(r"[\w'’&.\-]+", h):
        base = re.sub(r"^(?:[LlDdJj]|Qu|qu)['’]", "", w)
        base = re.sub(r"['’]s?$", "", base).strip(".'’-")   # Russia's -> Russia
        if not base:
            continue
        if base[:1].isupper():
            cur.append(base)
        elif cur and base.lower() in _CONN:
            cur.append(base)
        else:
            if cur: groups.append(cur)
            cur = []
    if cur: groups.append(cur)
    for g in groups:
        # on coupe le groupe au premier mot courant (ex. « Bank of America Must Pay » -> « Bank of America »)
        cut = next((i for i, x in enumerate(g) if i > 0 and x.lower() in _STOP and x.lower() not in _CONN), None)
        if cut: g = g[:cut]
        while g and (g[0].lower() in _STOP or g[0].lower() in _CONN): g = g[1:]
        while g and (g[-1].lower() in _STOP or g[-1].lower() in _CONN): g = g[:-1]
        if g and len(" ".join(g)) > 2:
            return " ".join(g[:5])
    return ""

# Formats et tournures qui ne sont PAS une mesure prononcée
_NOT_ACTION = ["documentaire", "documentary", "regarder", "à voir", "vidéo", "video", "podcast", "replay", "reportage",
    "opinion", "tribune", "édito", "editorial", "chronique", "analyse", "analysis", "décryptage", "explainer", "explained",
    "interview", "entretien", "témoignage", "les dessous", "inside", "comment ", "pourquoi", "how ", "why ", "what ",
    "faut-il", "should ", "?", "manifestant", "protest", "réclam", "appelle à", "appel à", "calls for", "call for", "urge",
    "demande un", "demandent un", "accuse", "dénonce", "critique", "menace", "threaten", "pourrait", "envisage",
    "could ", "may ", "might ", "considers", "weighs", "mulls", "plans to", "prévoit de", "projet de", "proposal",
    "proposition", "promouvoir", "promote", "contourn", "evade", "evasion", "se dit prêt", "disposée", "disposé",
    "levée des sanctions", "lift sanctions", "lifts sanctions", "allègement", "eases sanctions"]
# Verbes indiquant une décision effectivement prise
_ACTION = ["adopte", "adopté", "adopts", "adopted", "impose", "imposes", "imposed", "inflige", "infligé", "sanctionne",
    "sanctionné", "sanctions ", "sanctioned", "designat", "désigne", "inscrit", "ajoute", "adds", "added", "listed",
    "gèle", "gelé", "gel des avoirs", "freezes", "frozen", "froze", "prononce", "prononcé", "condamn", "fined", "fines ",
    "amende de", "amende record", "pénalité de", "penalty of", "settle", "règle", "agrees to pay", "accepte de payer",
    "to pay", "pays ", "paiera", "prolonge", "prolongé", "extends", "extended", "renouvelle", "renews", "élargit",
    "expands", "interdit", "bans", "banned", "blacklist", "entity list", "nouveau paquet", "new package", "22e paquet",
    "e paquet", "th package", "retire", "removes", "removed", "exits grey", "sort de la liste", "placé sur", "placed on",
    "maintient", "keeps", "embargo sur", "arms embargo", "export ban"]

def is_action(r):
    if r["mkey"] not in SANCTION_KINDS:
        return False
    t = " " + r["headline"].lower() + " "
    if any(x in t for x in _NOT_ACTION):
        return False
    return any(x in t for x in _ACTION)

def country_by_name(word):
    low = (word or "").lower().strip()
    for code, n, ps in COUNTRIES:
        if low == n.lower() or any(low == p.strip() for p in ps):
            return code, n
    return None

_TARGET_RE = re.compile(r"(?:against|on|targeting|contre|visant|à l'encontre d[eu]|sur)\s+(?:l[ae]\s|l['’])?([\w'’\-]+(?:\s[\w'’\-]+)?)", re.I)

def target_country(h):
    """Pays visé par la mesure (« sanctions contre la Russie », « sanctions on Russia's… »)."""
    for m in _TARGET_RE.finditer(h):
        for cand in (m.group(1), m.group(1).split()[0]):
            c = country_by_name(re.sub(r"['’]s?$", "", cand))
            if c and c[0] not in ("UA",): return c
    return None

def first_third_country(h):
    """Premier pays du titre qui n'est ni l'émetteur habituel (UE, US, UK) ni l'Ukraine."""
    t = _norm_text(h); best = None
    for code, n, ps in COUNTRIES:
        if code in ("EU", "US", "GB", "UA"): continue
        pos = [t.find(p) for p in ps if p in t]
        if pos and (best is None or min(pos) < best[0]): best = (min(pos), code, n)
    return (best[1], best[2]) if best else None

def detect_entity(h, country):
    ent = extract_entity(h)
    if not ent:
        return country if country != "—" else "—"
    c = country_by_name(ent)
    if c:                       # l'entité est un pays : on l'écrit en français (Russia -> Russie)
        return c[1]
    return ent

def enrich(it):
    h = headline_of(it)
    desc = it["desc"]
    if it.get("source"):
        desc = desc.replace(it["source"], " ")      # le nom du média n'indique pas le pays de l'affaire
    desc = desc.replace(h, " ")
    text = _norm_text(h + " " + desc)
    tc = target_country(h)
    if not tc and detect_measure(text)[0] in SANCTION_KINDS:
        tc = first_third_country(h)
    cc, country = tc if tc else detect_country(_norm_text(h)) if detect_country(_norm_text(h))[0] else detect_country(text)
    mkey, measure = detect_measure(text)
    auth = detect_authorities(text)
    entity = detect_entity(h, country)
    if entity == "—" or (tc and entity in ("Union européenne", "États-Unis", "Royaume-Uni")):
        entity = tc[1] if tc else entity
    amount, amount_v = detect_amount(" " + h + " " + desc + " ")
    return {**it, "headline": h, "entity": entity, "cc": cc, "country": country,
            "mkey": mkey, "measure": measure, "auth": auth, "amount": amount, "amount_v": amount_v}

FLAG_URL = "https://flagcdn.com/w40/{}.png"

# Rang de crédibilité (plus petit = plus crédible). Sources officielles d'abord, puis agences et grands titres.
SOURCE_RANK = [
    ["ofac", "treasury", "u.s. department", "council of the eu", "conseil de l'ue", "consilium", "european commission",
     "commission européenne", "acpr", "banque de france", "amf", "tracfin", "fca", "ofsi", "fincen", "sec.gov", "justice.gov",
     "fatf", "gafi", "united nations", "nations unies", "eba", "esma", "ecb", "bce", "amla"],
    ["reuters", "bloomberg", "agence france-presse", "afp", "associated press", "ap news", "financial times"],
    ["wall street journal", "the economist", "new york times", "washington post", "les echos", "le monde",
     "bbc", "the guardian", "politico", "cnbc", "le figaro", "franceinfo", "france 24", "l'agefi", "agefi",
     "la tribune", "challenges", "euronews", "dw", "rfi", "nikkei", "handelsblatt", "les échos"],
    ["al jazeera", "cnn", "abc news", "nbc news", "cbs news", "fox business", "forbes", "yahoo", "marketwatch",
     "barron's", "the times", "the telegraph", "le parisien", "20 minutes", "ouest-france", "bfm", "lci",
     "boursorama", "zonebourse", "investing.com", "the hill", "axios", "pbs", "npr", "time", "newsweek",
     "anadolu", "trt", "interfax", "kyiv independent", "eubusiness"],
]

def source_rank(r):
    s_ = (r.get("source") or "").lower()
    for i, tier in enumerate(SOURCE_RANK):
        if any(k in s_ for k in tier):
            return i
    return len(SOURCE_RANK)

def _ekey(r):
    e = re.sub(r"[^a-z0-9à-ÿ ]", "", r["entity"].lower())
    e = re.sub(r"\b(the|le|la|les|group|groupe|sa|inc|ltd|plc|corp|corporation|co)\b", " ", e)
    return re.sub(r"\s+", " ", e).strip()

def dedupe(rows):
    """Une seule ligne par (entité, type de mesure) : on garde le média le plus crédible,
    et on indique combien d'autres médias ont couvert la même information."""
    groups = {}
    for r in rows:
        k = (_ekey(r), r["mkey"]) if r["entity"] not in ("", "—") else ("#" + r["link"], r["mkey"])
        groups.setdefault(k, []).append(r)
    out = []
    for g in groups.values():
        best = sorted(g, key=lambda r: (source_rank(r), -r["ts"]))[0]
        best = dict(best)
        if not best["amount_v"]:                      # montant repris d'un autre article si celui-ci n'en a pas
            withamt = [x for x in g if x["amount_v"]]
            if withamt:
                best["amount"], best["amount_v"] = withamt[0]["amount"], withamt[0]["amount_v"]
        if best["cc"] == "" and any(x["cc"] for x in g):
            x = Counter((x["cc"], x["country"]) for x in g if x["cc"]).most_common(1)[0][0]
            best["cc"], best["country"] = x
        best["n_media"] = len({x["source"] for x in g if x["source"]})
        best["ts"] = max(x["ts"] for x in g)          # date de la couverture la plus récente
        out.append(best)
    return sorted(out, key=lambda r: r["ts"], reverse=True)

def flag(cc):
    """Drapeau en image (affichage écran)."""
    if len(cc) != 2 or not cc.isalpha():
        return ""
    return (f'<img src="{FLAG_URL.format(cc.lower())}" alt="{cc}" '
            f'style="height:14px;width:21px;object-fit:cover;vertical-align:-2px;margin-right:6px;'
            f'border-radius:2px;box-shadow:0 0 0 1px #ffffff22">')

@st.cache_data(ttl=86400, show_spinner=False)
def flag_bytes(cc):
    """Drapeau téléchargé pour les exports (None si indisponible)."""
    if len(cc) != 2 or not cc.isalpha():
        return None
    try:
        r = requests.get(FLAG_URL.format(cc.lower()), timeout=5)
        return r.content if r.ok and r.content[:4] == b"\x89PNG" else None
    except Exception:
        return None

def fmt_date(ts):
    return datetime.fromtimestamp(ts).strftime("%d/%m/%Y") if ts else "—"

def table_html(rows):
    heads = ["Entité / cible*", "Catégorie", "Description", "Pays", "Mesure", "Montant", "Date", "Autorité / source"]
    th = "".join(f"<th>{h}</th>" for h in heads)
    trs = []
    for r in rows:
        col = SCREEN_COLOR.get(r["mkey"], "#52708a")
        main = html.escape(r["auth"] or r["source"] or "—")
        sub = f'<br><span class="meta">{html.escape(r["source"])}</span>' if r["auth"] and r["source"] else ""
        if r.get("n_media", 1) > 1:
            sub += f'<br><span class="meta">+{r["n_media"] - 1} autre(s) média(s)</span>'
        pays = f'{flag(r["cc"])} {html.escape(r["country"])}' if r["cc"] else "—"
        trs.append(
            f'<tr><td class="ent">{html.escape(r["entity"])}</td>'
            f'<td><span class="tag">{html.escape(r["theme"])}</span></td>'
            f'<td><a href="{html.escape(r["link"])}" target="_blank">{html.escape(r["headline"])}</a></td>'
            f'<td style="white-space:nowrap">{pays}</td>'
            f'<td><span class="mz" style="color:{col};border-color:{col}">{html.escape(r["measure"])}</span></td>'
            f'<td style="white-space:nowrap;font-family:Share Tech Mono;color:{"#f5c542" if r["amount_v"] else "#52708a"}">'
            f'{html.escape(r["amount"])}</td>'
            f'<td class="meta" style="white-space:nowrap">{fmt_date(r["ts"])}</td>'
            f'<td>{main}{sub}</td></tr>')
    if not trs:
        trs = ['<tr><td colspan="8" class="meta">Aucun élément.</td></tr>']
    return f'<div class="wwrap"><table class="wtable"><thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table></div>'

# ---------- Exports (image, PDF, Excel) ----------
EXPORT_COLS = [("Entité / cible", .13), ("Catégorie", .11), ("Description", .27), ("Pays", .13),
               ("Mesure", .10), ("Montant", .08), ("Date", .08), ("Autorité", .10)]
GOLD = "#C9A227"
AUTHOR = "CWP – Compliance Watch Platform · Plateforme conçue et développée par Mackenson CINEUS"
FOOTER = "CWP – Compliance Watch Platform · informations issues de la presse : à vérifier auprès des sources officielles (OFAC, UE, ONU, DG Trésor…)"

def _plain(s):
    return re.sub(r"[\U00010000-\U0010FFFF]", "", str(s or "")).strip()

def _ascii(s):
    import unicodedata
    s = (s.replace("—", "-").replace("–", "-").replace("’", "'").replace("‘", "'").replace("«", '"')
          .replace("»", '"').replace("…", "...").replace("€", "EUR").replace("·", "-").replace("\u00a0", " "))
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()

def _cells(r):
    return [r["entity"], r["theme"], r["headline"],
            r["country"] if r["cc"] else "—",
            r["measure"], r["amount"], fmt_date(r["ts"]),
            (" · ".join(x for x in [r["auth"], r["source"]] if x) or "—")
            + (f' (+{r["n_media"] - 1} médias)' if r.get("n_media", 1) > 1 else "")]

FONT_URLS = {False: "https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37.3/ttf/DejaVuSans.ttf",
             True: "https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37.3/ttf/DejaVuSans-Bold.ttf"}

def _font_path(bold):
    """Police avec accents : reportlab (Vera) > système (DejaVu) > téléchargement (DejaVu, mis en cache)."""
    cands = []
    try:
        import reportlab
        cands.append(os.path.join(os.path.dirname(reportlab.__file__), "fonts", "VeraBd.ttf" if bold else "Vera.ttf"))
    except Exception:
        pass
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    here = os.path.dirname(os.path.abspath(__file__))
    cands = [os.path.join(here, "assets", "fonts", name)] + cands  # police embarquée dans le dépôt
    cands += [name, f"/usr/share/fonts/truetype/dejavu/{name}"]
    for c in cands:
        if os.path.exists(c):
            return c
    local = os.path.join("/tmp", name)
    if not os.path.exists(local):
        try:
            r = requests.get(FONT_URLS[bold], timeout=10)
            if r.ok and len(r.content) > 100_000:
                open(local, "wb").write(r.content)
        except Exception:
            pass
    return local if os.path.exists(local) else None

def _font(size, bold=False):
    from PIL import ImageFont
    path = _font_path(bold)
    if path:
        try:
            f = ImageFont.truetype(path, size); f.has_accents = True; return f
        except Exception:
            pass
    try: f = ImageFont.load_default(size=size)
    except Exception: f = ImageFont.load_default()
    f.has_accents = False
    return f

def _wrap(d, text, font, width, max_lines):
    lines, cur = [], ""
    words = []
    for w in text.split():  # mot plus large que la colonne : coupé en morceaux
        while d.textlength(w, font=font) > width and len(w) > 1:
            k = len(w)
            while k > 1 and d.textlength(w[:k], font=font) > width:
                k -= 1
            words.append(w[:k]); w = w[k:]
        words.append(w)
    for w in words:
        t = f"{cur} {w}".strip()
        if not cur or d.textlength(t, font=font) <= width:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur: lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and d.textlength(last + "…", font=font) > width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return lines or [""]

def make_png(rows, label, period_txt):
    from PIL import Image, ImageDraw
    W, M, pad, lh = 1800, 48, 12, 26
    FLAG_W = 40
    T = _plain if _font(18).has_accents else (lambda x: _ascii(_plain(x)))
    tw = W - 2 * M
    f_title, f_sub, f_head = _font(44, True), _font(22), _font(17, True)
    f_cell, f_bold, f_foot = _font(18), _font(18, True), _font(15)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    xs, x = [], M
    for _, fr in EXPORT_COLS:
        xs.append((x, int(tw * fr))); x += int(tw * fr)
    prepared = []
    for r in rows:
        wrapped = [_wrap(tmp, T(c), f_bold if j in (0, 4, 5) else f_cell,
                         w - 2 * pad - (FLAG_W if j == 3 and r["cc"] else 0), 4 if j == 2 else 3)
                   for j, (c, (_, w)) in enumerate(zip(_cells(r), xs))]
        prepared.append((r, wrapped, max(len(l) for l in wrapped) * lh + 2 * pad))
    top, head_h = M + 150, 50
    H = top + head_h + sum(p[2] for p in prepared) + 120
    img = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(img)
    d.rounded_rectangle([M, M, W - M, M + 110], radius=18, fill="#fbf7ea", outline="#e8dcb0", width=2)
    d.text((M + 30, M + 16), T("Weekly Watch — Sécurité financière"), font=f_title, fill=GOLD)
    d.text((M + 32, M + 72), T(f"{label} · {period_txt}"), font=f_sub, fill="#6b6b6b")
    y = top
    for (name, _), (x0, _) in zip(EXPORT_COLS, xs):
        d.text((x0 + pad, y + 15), T(name.upper()), font=f_head, fill="#2b2b2b")
    d.line([M, y + head_h - 2, W - M, y + head_h - 2], fill=GOLD, width=3)
    y += head_h
    for i, (r, wrapped, h) in enumerate(prepared):
        if i % 2: d.rectangle([M, y, W - M, y + h], fill="#faf8f2")
        for j, (lines, (x0, _)) in enumerate(zip(wrapped, xs)):
            font, color = f_cell, "#1f2937"
            if j == 0: font, color = f_bold, "#0f3d66"
            if j == 4: font, color = f_bold, EXPORT_COLOR.get(r["mkey"], "#6b7c8c")
            if j == 5: font, color = (f_bold, "#1f2937") if r["amount_v"] else (f_cell, "#9a9a9a")
            dx = 0
            if j == 3 and r["cc"]:
                fb = flag_bytes(r["cc"])
                if fb:
                    try:
                        fl = Image.open(io.BytesIO(fb)).convert("RGB").resize((30, 20))
                        img.paste(fl, (x0 + pad, y + pad + 4)); dx = 38
                    except Exception:
                        pass
            for k, line in enumerate(lines):
                d.text((x0 + pad + (FLAG_W if j == 3 and r["cc"] else 0), y + pad + k * lh), line, font=font, fill=color)
        y += h
        d.line([M, y, W - M, y], fill="#e6e2d6", width=1)
    d.text((M, y + 30), T(f"{FOOTER} · généré le {datetime.now():%d/%m/%Y %H:%M}"), font=f_foot, fill="#8a8a8a")
    d.text((M, y + 56), T(AUTHOR), font=_font(15, True), fill="#8a8a8a")
    buf = io.BytesIO(); img.save(buf, "PNG")
    return buf.getvalue()

def make_pdf(rows, label, period_txt):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from xml.sax.saxutils import escape

    def txt(s):  # polices PDF standard : jeu de caractères cp1252
        return escape(_plain(s).encode("cp1252", "ignore").decode("cp1252"))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm, title="Weekly Watch – Sécurité financière")
    gold = colors.HexColor(GOLD)
    s_t = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=20, textColor=gold, leading=24)
    s_s = ParagraphStyle("s", fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#6b6b6b"), leading=12)
    s_h = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=7.5, textColor=colors.HexColor("#2b2b2b"), leading=10)
    s_c = ParagraphStyle("c", fontName="Helvetica", fontSize=8, leading=10, textColor=colors.HexColor("#1f2937"))
    s_b = ParagraphStyle("b", parent=s_c, fontName="Helvetica-Bold", textColor=colors.HexColor("#0f3d66"))
    from reportlab.platypus import Image as RLImage

    def pays_cell(r, label):
        fb = flag_bytes(r["cc"]) if r["cc"] else None
        if not fb:
            return Paragraph(label, s_c)
        t = Table([[RLImage(io.BytesIO(fb), width=6 * mm, height=4 * mm), Paragraph(label, s_c)]],
                  colWidths=[7.5 * mm, None])
        t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                               ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    data = [[Paragraph(txt(n.upper()), s_h) for n, _ in EXPORT_COLS]]
    for r in rows:
        c = _cells(r)
        link = escape(r["link"], {'"': "&quot;"})
        data.append([
            Paragraph(txt(c[0]), s_b), Paragraph(txt(c[1]), s_c),
            Paragraph(f'<link href="{link}" color="#1a4e8a">{txt(c[2])}</link>', s_c),
            pays_cell(r, txt(c[3])),
            Paragraph(f'<font color="{EXPORT_COLOR.get(r["mkey"], "#6b7c8c")}"><b>{txt(c[4])}</b></font>', s_c),
            Paragraph(f"<b>{txt(c[5])}</b>" if r["amount_v"] else txt(c[5]), s_c),
            Paragraph(txt(c[6]), s_c), Paragraph(txt(c[7]), s_c)])
    table = Table(data, colWidths=[doc.width * fr for _, fr in EXPORT_COLS], repeatRows=1)
    table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, gold),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#e6e2d6")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#faf8f2")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story = [Paragraph(txt("Weekly Watch — Sécurité financière"), s_t),
             Paragraph(txt(f"{label} · {period_txt} · {len(rows)} éléments"), s_s), Spacer(1, 5 * mm), table,
             Spacer(1, 4 * mm), Paragraph(txt(f"{FOOTER} · généré le {datetime.now():%d/%m/%Y %H:%M}"), s_s)]
    def _footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica-Oblique", 7.5)
        canvas.setFillColor(colors.HexColor("#8a8a8a"))
        canvas.drawString(12 * mm, 7 * mm, AUTHOR.encode("cp1252", "ignore").decode("cp1252"))
        canvas.drawRightString(landscape(A4)[0] - 12 * mm, 7 * mm, f"Page {_doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()

def to_excel_watch(rows):
    df = pd.DataFrame([{n: v for (n, _), v in zip(EXPORT_COLS, _cells(r))} | {"Lien": r["link"]} for r in rows])
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()

# ---------- Affichage des cartes (pages Veille / alertes) ----------
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
    page = st.radio("Navigation", ["🏠 Dashboard", "📡 Veille", "🔎 OpenSanctions", "⚖️ Textes de loi", "📅 Calendrier réglementaire", "📌 Regulatory Flash", "📚 Glossaire", "🕵️ Glossaire des fraudes", "🔗 Sources officielles"], label_visibility="collapsed")
    kw_in = st.text_area("🚨 Mots-clés d'alerte (un par ligne)", "\n".join(load_kw()), placeholder="Russie\nIran\nNom d'une entité")
    KWS = [k.strip() for k in kw_in.splitlines() if k.strip()]
    json.dump(KWS, open(ALERT_FILE, "w"))
    if st.button("🔄 Rafraîchir la veille", use_container_width=True):
        fetch_all.clear(); st.rerun()

items = fetch_all()
seen = load_seen()
new_links = {i["link"] for i in items} - seen if seen else set()

PERIODS = {"24 h": 1, "7 jours": 7, "30 jours": 30}

# ---------- Pages ----------
if page == "🏠 Dashboard":
    _links = {i["link"] for i in items}
    rows_all = sorted([enrich(i) for i in items] + [enrich(i) for i in fetch_actions() if i["link"] not in _links],
                      key=lambda r: r["ts"], reverse=True)
    hero = st.empty()

    # Statistiques (inchangées)
    c = st.columns(4)
    c[0].markdown(f'<div class="card"><div class="meta">ARTICLES</div><div class="kpi">{len(items)}</div></div>', unsafe_allow_html=True)
    c[1].markdown(f'<div class="card"><div class="meta">NOUVEAUX</div><div class="kpi">{len(new_links)}</div></div>', unsafe_allow_html=True)
    c[2].markdown(f'<div class="card"><div class="meta">THÈMES</div><div class="kpi">{len(THEMES)}</div></div>', unsafe_allow_html=True)
    c[3].markdown(f'<div class="card"><div class="meta">CONCEPTS</div><div class="kpi">{len(load_concepts())}</div></div>', unsafe_allow_html=True)

    # Réglages
    c1, c2, c3 = st.columns([1.3, 1.7, 1])
    period = c1.radio("Période", list(PERIODS), index=1, horizontal=True)
    view = c2.radio("Affichage", ["🎯 Sanctions & embargos prononcés", "📰 Toutes les actualités"], horizontal=True)
    nmax = c3.slider("Lignes du tableau", 5, 50, 20)
    sanc_only = view.startswith("🎯")

    since = time.time() - PERIODS[period] * 86400
    in_period = [r for r in rows_all if r["ts"] >= since]
    keep = (lambda r: is_action(r)) if sanc_only else (lambda r: True)
    pool = [r for r in in_period if keep(r)]
    fallback = not pool
    if fallback:  # aucune mesure récente : on affiche les dernières mesures connues (plus anciennes)
        pool = [r for r in rows_all if keep(r)]
    pool = dedupe(pool)
    rows = pool[:nmax]

    d1 = datetime.now()
    if not fallback:
        d0 = datetime.fromtimestamp(since)
    else:
        stamps = [r["ts"] for r in rows if r["ts"]]
        d0 = datetime.fromtimestamp(min(stamps)) if stamps else d1
    period_txt = f"Du {d0:%d/%m/%Y} au {d1:%d/%m/%Y}"
    label = ("Sanctions & embargos prononcés" if not fallback else "Dernières sanctions & embargos connus") if sanc_only \
        else "Dernières actualités sécurité financière"

    hero.markdown(
        f'<div class="hero"><div class="hero-t">Weekly Watch <span>— Sécurité financière</span></div>'
        f'<div class="hero-s">{period_txt.upper()} · SANCTIONS · GELS D\'AVOIRS · AMENDES · LISTES GAFI · EMBARGOS · '
        f'MAJ {d1:%d/%m/%Y %H:%M}</div></div>', unsafe_allow_html=True)

    # Pays les plus cités
    cnt = Counter((r["cc"], r["country"]) for r in (in_period or rows_all) if r["cc"])
    if cnt:
        chips = "".join(f'<span class="chip">{flag(cc)} {html.escape(n)}<b>{v}</b></span>' for (cc, n), v in cnt.most_common(10))
        st.markdown(f'<div class="meta" style="margin:6px 0">PAYS / ZONES LES PLUS CITÉS</div>{chips}', unsafe_allow_html=True)

    # Tableau principal
    st.markdown(f"### {'🎯' if sanc_only else '📰'} {label}")
    if fallback:
        st.info("Aucune sanction ni embargo prononcé sur la période choisie : "
                "affichage des dernières mesures connues, plus anciennes.")
    if sanc_only:
        st.caption("Seules les décisions effectivement prises sont retenues (sanction, gel, amende, embargo, liste GAFI). "
                   "Documentaires, opinions, appels, projets et simples actualités sont exclus.")
    st.markdown(table_html(rows), unsafe_allow_html=True)
    st.caption("* Entité, pays, mesure et autorité sont détectés automatiquement à partir du titre : à vérifier sur la source.")

    # Exports
    e = st.columns([1, 1, 1, 3])
    stamp = f"{d1:%Y%m%d}"
    try:
        e[0].download_button("🖼️ Image (PNG)", make_png(rows, label, period_txt), f"weekly_watch_{stamp}.png",
                             "image/png", use_container_width=True)
    except Exception as ex:
        e[0].caption(f"PNG indisponible : {ex}")
    try:
        e[1].download_button("📄 Rapport PDF", make_pdf(rows, label, period_txt), f"weekly_watch_{stamp}.pdf",
                             "application/pdf", use_container_width=True)
    except ImportError:
        e[1].caption("PDF : ajoutez « reportlab » à requirements.txt")
    e[2].download_button("📥 Excel", to_excel_watch(rows), f"weekly_watch_{stamp}.xlsx",
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

    # Alertes par mots-clés
    alerts = [i for i in items if hits(i, KWS)]
    shown = set()
    if alerts:
        st.markdown(f"### 🚨 Alertes ({len(alerts)})")
        for it in alerts[:8]:
            render(it, it["link"] in new_links); shown.add(it["link"])

    with st.expander("🗂️ Vue détaillée en cartes (avec résumé)"):
        for it in [i for i in items if i["link"] not in shown][:15]:
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

elif page == "📌 Regulatory Flash":
    from tab_regulatory_flash import render_regulatory_flash
    render_regulatory_flash()

elif page == "🕵️ Glossaire des fraudes":
    from tab_glossaire_fraudes import render_glossaire_fraudes
    render_glossaire_fraudes()

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

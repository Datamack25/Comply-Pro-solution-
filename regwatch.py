"""
regwatch.py — Moteur de veille réglementaire de CWP.

1. Collecte les publications des régulateurs et institutions de référence
   (ACPR, TRACFIN, AMF, DG Trésor, Journal officiel, AMLA, EBA, ESMA, BCE, UE, GAFI, OFAC, FinCEN…)
   via leurs flux RSS officiels quand ils existent et via Google News filtré sur leur site.
2. Classe chaque publication (texte législatif, orientations, consultation, sanction, rapport…).
3. Transforme une publication en fiche « Regulatory Flash » :
   - par IA si une clé est configurée dans .streamlit/secrets.toml
     (ANTHROPIC_API_KEY, MISTRAL_API_KEY ou OLLAMA_URL) ;
   - sinon par extraction automatique (sans IA) à partir du texte de la page.

Aucune dépendance à Streamlit ici : le cache est géré dans tab_regulatory_flash.py.
"""
from __future__ import annotations

import html
import json
import re
import time
from datetime import datetime
from urllib.parse import quote_plus, urlparse

import feedparser
import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; CWP-Compliance-Watch/1.0)"}


def gnews(q: str, lang: str = "fr") -> str:
    fr = lang == "fr"
    return (f"https://news.google.com/rss/search?q={quote_plus(q)}&hl={lang}"
            f"&gl={'FR' if fr else 'US'}&ceid={'FR:fr' if fr else 'US:en'}")


# --------------------------------------------------------------------------- #
# Sources (ajoutez / retirez librement des lignes)
#   label    : nom affiché        juridiction : « Pays / source » de la fiche
#   cible    : cible par défaut   rss : flux officiels      gnews : requêtes Google News
#   filtre   : True = on ne garde que les publications liées à la conformité
# --------------------------------------------------------------------------- #
SOURCES = {
    "ACPR": dict(juridiction="France — ACPR (Banque de France)", cible="Banques, assurances, PSP / EME",
                 rss=[], filtre=False,
                 gnews=[gnews("site:acpr.banque-france.fr"),
                        gnews('ACPR "Autorité de contrôle prudentiel" "lignes directrices" OR recommandation '
                              'OR instruction OR notice OR "position"')]),
    "TRACFIN": dict(juridiction="France — TRACFIN", cible="Ensemble des assujettis LCB-FT",
                    rss=[], filtre=False,
                    gnews=[gnews("site:economie.gouv.fr tracfin"),
                           gnews('Tracfin "lignes directrices" OR typologies OR rapport OR "déclaration de soupçon"')]),
    "AMF": dict(juridiction="France — AMF", cible="SGP, PSI, PSAN / CASP, émetteurs",
                rss=[], filtre=False,
                gnews=[gnews("site:amf-france.org"),
                       gnews('AMF "position-recommandation" OR "guide" OR consultation OR "règlement général" OR MiCA')]),
    "DG Trésor": dict(juridiction="France — DG Trésor", cible="Ensemble des assujettis",
                      rss=[], filtre=True,
                      gnews=[gnews('site:tresor.economie.gouv.fr "lignes directrices" OR LCB-FT OR réglementation '
                                   'OR "mesures restrictives"')]),
    "Journal officiel": dict(juridiction="France — Journal officiel / Légifrance", cible="Ensemble des assujettis",
                             rss=[], filtre=True,
                             gnews=[gnews('"Journal officiel" décret OR arrêté OR ordonnance blanchiment OR '
                                          '"financement du terrorisme" OR "code monétaire et financier"')]),
    "AFA": dict(juridiction="France — Agence française anticorruption", cible="Grandes entreprises, EPIC, banques",
                rss=[], filtre=False,
                gnews=[gnews('"Agence française anticorruption" recommandations OR contrôle OR guide')]),
    "AMLA": dict(juridiction="Union européenne — AMLA", cible="Assujettis LCB-FT de l'UE",
                 rss=[], filtre=False,
                 gnews=[gnews("site:amla.europa.eu", "en"),
                        gnews('AMLA "Anti-Money Laundering Authority" consultation OR standards OR guidelines', "en")]),
    "EBA": dict(juridiction="Union européenne — EBA", cible="Banques, PSP / EME, CASP",
                rss=["https://www.eba.europa.eu/news-press/news/rss.xml"], filtre=True,
                gnews=[gnews("site:eba.europa.eu", "en")]),
    "ESMA": dict(juridiction="Union européenne — ESMA", cible="SGP, PSI, CASP, infrastructures",
                 rss=[], filtre=True,
                 gnews=[gnews("site:esma.europa.eu", "en")]),
    "BCE / MSU": dict(juridiction="Union européenne — BCE / supervision bancaire", cible="Banques importantes (SSM)",
                      rss=["https://www.ecb.europa.eu/rss/press.html"], filtre=True,
                      gnews=[gnews("site:bankingsupervision.europa.eu", "en")]),
    "UE (Conseil / Commission)": dict(juridiction="Union européenne — Conseil / Commission",
                                      cible="Ensemble des opérateurs de l'UE", rss=[], filtre=True,
                                      gnews=[gnews('site:consilium.europa.eu "money laundering" OR regulation OR directive', "en"),
                                             gnews('"Official Journal" regulation anti-money laundering OR '
                                                   'sanctions OR MiCA OR DORA', "en")]),
    "GAFI / FATF": dict(juridiction="International — GAFI / FATF", cible="Juridictions et assujettis LCB-FT",
                        rss=[], filtre=False,
                        gnews=[gnews("site:fatf-gafi.org", "en"),
                               gnews("GAFI plénière OR recommandations OR \"liste grise\"")]),
    "OFAC (US)": dict(juridiction="États-Unis — OFAC (Trésor US)", cible="Opérateurs en USD ou liés aux US",
                      rss=[], filtre=True,
                      gnews=[gnews('site:ofac.treasury.gov guidance OR regulations OR "frequently asked questions" '
                                   'OR "compliance framework"', "en")]),
    "FinCEN (US)": dict(juridiction="États-Unis — FinCEN", cible="Institutions financières US",
                        rss=[], filtre=False,
                        gnews=[gnews('site:fincen.gov rule OR guidance OR advisory OR "final rule" OR "proposed rule"', "en")]),
    "Comité de Bâle (BIS)": dict(juridiction="International — Comité de Bâle (BIS)", cible="Banques",
                                 rss=[], filtre=True,
                                 gnews=[gnews("site:bis.org \"Basel Committee\"", "en")]),
}

# --------------------------------------------------------------------------- #
# Lexiques
# --------------------------------------------------------------------------- #
RELEVANT = re.compile(
    r"blanchi|lcb|financement du terrorisme|money laundering|\baml\b|\bcft\b|kyc|sanction|gel des avoirs|"
    r"asset freeze|embargo|conformit|compliance|amla|mica|dora|crypto|paiement|payment|\bdsp\b|\bpsd|"
    r"fraud|travel rule|vigilance|bénéficiaire effectif|beneficial owner|tracfin|orientations|guidelines|"
    r"consultation|règlement|regulation|directive|décret|arrêté|instruction|recommandation|supervis|"
    r"contrôle interne|internal control|risk|risque|prudenti|capital|solvab|liquidit|governance|gouvernance|"
    r"anticorruption|corruption|\bppe\b|\bpep\b|mesures restrictives|restrictive measures|advisory|rule\b",
    re.I)

KINDS = [  # (type, motif) — premier qui correspond
    ("Consultation", r"consultation|consults|call for evidence|appel à commentaires"),
    ("Orientations / recommandations", r"orientations|guidelines|lignes directrices|guidance|recommandation|"
                                       r"position|notice|\bq&a\b|questions-réponses|standards?\b|\brts\b|\bits\b"),
    ("Texte législatif", r"règlement|directive|regulation|décret|arrêté|ordonnance|\bloi\b|journal officiel|"
                         r"official journal|act\b|final rule|proposed rule|interim rule"),
    ("Rapport / étude", r"rapport|report|étude|survey|typolog|analyse|review|evaluation|évaluation"),
]

# Actualités écartées : amendes, décisions de sanction, désignations, gels individuels, paquets de sanctions.
# Regulatory Flash ne retient que les textes et la doctrine (le Dashboard couvre ces actualités).
NEWS_EXCLUDE = re.compile(
    r"commission des sanctions|prononc\w* (?:un |une )?(?:blâme|amende|sanction|avertissement)|amende de|"
    r"\bblâme\b|condamn|\bfine[sd]?\b|\bfining\b|penalty of|civil (?:money )?penalt|settle(?:s|d|ment)|"
    r"enforcement action|consent order|cease and desist|"
    r"designat(?:es|ed|ion)|désign\w* (?:par|comme)|sanctions? (?:on|against|contre)|treasury sanctions|"
    r"impos\w* (?:des |new |de nouvelles )?sanctions|nouvelles sanctions|new sanctions|"
    r"paquet de sanctions|sanctions package|gel des avoirs de|asset freeze on|assets? frozen|"
    r"adds? .{0,40}(?:sdn|entity list)|sdn list|delist|removes? .{0,30}from .{0,20}list",
    re.I)


def is_news(text: str) -> bool:
    return bool(NEWS_EXCLUDE.search(text or ""))


MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
             "octobre", "novembre", "décembre"]
MONTHS_EN = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
             "october", "november", "december"]

CIBLES = [
    ("Banques", r"banque|établissement de crédit|credit institution|\bbanks?\b|banking"),
    ("PSP / EME", r"prestataire de services de paiement|établissement de paiement|monnaie électronique|"
                  r"payment (service|institution)|e-money|\bpsp\b|\bemi\b"),
    ("PSAN / CASP", r"\bpsan\b|crypto|\bmica\b|\bcasp\b|actifs numériques|virtual asset"),
    ("Assurances", r"assur|insurance|insurer|mutuelle"),
    ("SGP / gestion d'actifs", r"société de gestion|asset manag|\bopcvm\b|\bfia\b|\bsgp\b|fund manag"),
    ("Entreprises d'investissement", r"entreprise d'investissement|investment firm|\bpsi\b"),
    ("Professions non financières", r"notaire|avocat|agent immobilier|commissaire aux comptes|casino|dnfbp|"
                                    r"real estate|lawyer|accountant"),
]

DOMAINS = {
    "KYC / KYB & UBO": (r"kyc|kyb|connaissance (du|de la) client|vigilance|bénéficiaire effectif|beneficial owner|"
                        r"due diligence|identification|\bppe\b|\bpep\b|entrée en relation|onboarding|"
                        r"customer|clientèle"),
    "Filtrage & transactions": (r"sanction|gel des avoirs|asset freeze|filtrage|screening|transaction|virement|"
                                r"transfer|travel rule|surveillance|monitoring|alerte|embargo|paiement|payment"),
    "Gouvernance & reporting": (r"déclaration|reporting|tracfin|audit|contrôle interne|internal control|"
                                r"gouvernance|governance|dispositif|procédure|formation|training|cartographie|"
                                r"risk assessment|évaluation des risques|soupçon|suspicious|notification"),
}
DOMAIN_ACTIONS = {
    "KYC / KYB & UBO": "Revoir les procédures d'entrée en relation et de mise à jour des dossiers",
    "Filtrage & transactions": "Vérifier le paramétrage du filtrage et des scénarios de surveillance",
    "Gouvernance & reporting": "Mettre à jour procédures, contrôles et circuits de déclaration",
}

PURPOSE = re.compile(r"vise|objectif|afin de|pour renforcer|a pour but|aims?|purpose|seeks?|to ensure|"
                     r"introdu|établit|fixe|precis|précise|clarif|harmoni|renforc|strengthen", re.I)
OBLIGATION = re.compile(r"doivent|devront|obligation|exige|requiert|tenus? de|must|shall|required?|"
                        r"requirement|expects?|attendu|mettre en (place|œuvre)", re.I)
CONSTRAINT = re.compile(r"sanction|amende|blâme|pénalit|retrait d'agrément|interdiction|\bfine|penalt|"
                        r"enforcement|délai|deadline|date limite|avant le|by \d|au plus tard|"
                        r"entr\w* en (vigueur|application)|apply from|enter into force", re.I)


# --------------------------------------------------------------------------- #
# Utilitaires texte
# --------------------------------------------------------------------------- #
def clean(t: str, n: int | None = None) -> str:
    t = html.unescape(re.sub(r"<[^>]+>", " ", t or ""))
    t = re.sub(r"\s+", " ", t).strip()
    return t if n is None or len(t) <= n else t[: n - 1].rstrip() + "…"


def strip_publisher(title: str) -> tuple[str, str]:
    """Google News : « Titre - Éditeur » → (titre, éditeur)."""
    m = re.match(r"^(.*\S)\s+[-–—]\s+([^-–—]{2,60})$", title or "")
    return (m.group(1), m.group(2).strip()) if m else (title, "")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ý«\"(])", text or "")
            if 45 < len(s.strip()) < 420]


def short(s: str, n: int = 280) -> str:
    return clean(s, n)


def month_year(ts: float) -> str:
    if not ts:
        return "Non précisée"
    d = datetime.fromtimestamp(ts)
    return f"{MONTHS_FR[d.month - 1].capitalize()} {d.year}"


# --------------------------------------------------------------------------- #
# Collecte
# --------------------------------------------------------------------------- #
def _parse(url: str):
    """Télécharge un flux (avec un User-Agent navigateur) puis le parse."""
    r = requests.get(url, headers=UA, timeout=15)
    r.raise_for_status()
    return feedparser.parse(r.content)


def classify(text: str) -> str:
    for kind, pat in KINDS:
        if re.search(pat, text, re.I):
            return kind
    return "Communiqué / actualité"


def fetch_publications(days: int = 30, sources: list[str] | None = None,
                       per_feed: int = 25) -> tuple[list[dict], list[dict]]:
    """Renvoie (publications, état des sources)."""
    cutoff = time.time() - days * 86400
    items, status, seen = [], [], set()
    for name, cfg in SOURCES.items():
        if sources and name not in sources:
            continue
        n_ok, n_items, errors = 0, 0, []
        for kind_url, url in [("Flux officiel", u) for u in cfg["rss"]] + [("Google News", u) for u in cfg["gnews"]]:
            try:
                feed = _parse(url)
                if feed.bozo and not feed.entries:
                    raise ValueError("flux vide ou illisible")
                n_ok += 1
            except Exception as e:  # noqa: BLE001
                errors.append(f"{kind_url} : {type(e).__name__}")
                continue
            for e in feed.entries[:per_feed]:
                link = e.get("link") or ""
                raw_title = clean(e.get("title"), 300)
                title, publisher = strip_publisher(raw_title) if "news.google." in url else (raw_title, "")
                key = re.sub(r"\W+", "", title.lower())[:90]
                if not link or not title or key in seen:
                    continue
                pp = e.get("published_parsed") or e.get("updated_parsed")
                ts = time.mktime(pp) if pp else 0
                if ts and ts < cutoff:
                    continue
                desc = clean(e.get("summary") or e.get("description"), 1200)
                if desc.startswith(title[:40]):  # Google News répète souvent le titre
                    desc = ""
                blob = f"{title} {desc}"
                if is_news(blob):  # amendes, désignations… = actualités, pas de la réglementation
                    continue
                if cfg.get("filtre") and not RELEVANT.search(blob):
                    continue
                seen.add(key)
                n_items += 1
                src = e.get("source")
                if not publisher and isinstance(src, dict):
                    publisher = src.get("title", "")
                items.append(dict(
                    source=name, juridiction=cfg["juridiction"], cible_defaut=cfg["cible"],
                    title=title, desc=desc, link=link, ts=ts, publisher=publisher,
                    origin=kind_url, kind=classify(blob),
                    relevant=bool(RELEVANT.search(blob)),
                ))
        status.append(dict(Source=name, Flux_OK=f"{n_ok}/{len(cfg['rss']) + len(cfg['gnews'])}",
                           Publications=n_items, Erreurs=" ; ".join(errors) or "—"))
    items.sort(key=lambda x: x["ts"], reverse=True)
    return items, status


def fetch_text(url: str, max_chars: int = 25_000) -> str:
    """Texte brut de la page officielle (vide si inaccessible ou lien Google News non résolu)."""
    try:
        r = requests.get(url, headers=UA, timeout=15, allow_redirects=True)
        if "news.google." in urlparse(r.url).netloc:
            return ""
        ctype = r.headers.get("content-type", "")
        if "pdf" in ctype:
            return ""  # PDF : on se contente du résumé du flux
        txt = re.sub(r"(?is)<(script|style|nav|footer|header|aside|form|noscript).*?</\1>", " ", r.text)
        return clean(txt)[:max_chars]
    except Exception:  # noqa: BLE001
        return ""


# --------------------------------------------------------------------------- #
# Fiche par extraction (sans IA)
# --------------------------------------------------------------------------- #
REF_PATTERNS = [
    r"(?:Règlement|Directive|Décision)(?: délégué| d'exécution)?\s*\((?:UE|CE)\)\s*(?:n°\s*)?\d{2,4}/\d+",
    r"(?:Regulation|Directive|Decision)(?: \(EU\)| \(EC\))\s*(?:No\s*)?\d{2,4}/\d+",
    r"(?:Décret|Arrêté|Ordonnance|Loi)\s+n°\s*[\d\-]+(?:\s+du\s+\d{1,2}(?:er)?\s+\w+\s+\d{4})?",
    r"(?:EBA|ESMA|EIOPA|AMLA)/(?:GL|RTS|ITS|CP|Op|REC|DC)/\d{4}/\d+",
    r"Instruction\s+(?:n°\s*)?\d{4}-I-\d+",
    r"Recommandation\s+(?:n°\s*)?\d{4}-R-\d+",
    r"DOC-\d{4}-\d+",
    r"Executive Order\s+\d+",
]

DATE_PHRASE = re.compile(
    r"(entr\w*\s+en\s+(?:vigueur|application)|applicable|s'appliquer\w*|apply\w*\s+from|enter\w*\s+into\s+force|"
    r"application date|à compter du|from)\s[^.]{0,80}?"
    r"(\d{1,2}(?:er)?\s+(?:" + "|".join(MONTHS_FR + MONTHS_EN) + r")\s+\d{4}|"
    r"(?:" + "|".join(MONTHS_FR + MONTHS_EN) + r")\s+\d{4})", re.I)


def _fmt_date_phrase(s: str) -> str:
    s = s.lower()
    for i, m in enumerate(MONTHS_EN):
        s = re.sub(rf"\b{m}\b", MONTHS_FR[i], s)
    m = re.search(r"(" + "|".join(MONTHS_FR) + r")\s+(\d{4})", s)
    return f"{m.group(1).capitalize()} {m.group(2)}" if m else s


def _pick(sents: list[str], pattern: re.Pattern, used: set) -> str:
    for s in sents:
        if s not in used and pattern.search(s):
            used.add(s)
            return short(s)
    return ""


def _rank(sents: list[str]) -> list[str]:
    words = re.findall(r"\w{5,}", " ".join(sents).lower())
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    return sorted(sents, key=lambda x: -sum(freq.get(w, 0) for w in re.findall(r"\w{5,}", x.lower()))
                  / (len(x) ** 0.5))


def extractive_flash(item: dict, page_text: str = "") -> dict:
    title, desc = item["title"], item.get("desc", "")
    corpus = " ".join(x for x in [desc, page_text] if x)
    blob = f"{title} {corpus}"
    sents = sentences(corpus)
    ranked = _rank(sents) if sents else []
    used: set = set()

    # Référence
    ref = ""
    for pat in REF_PATTERNS:
        m = re.search(pat, blob, re.I)
        if m:
            ref = m.group(0)
            break
    pub = datetime.fromtimestamp(item["ts"]).strftime("%d/%m/%Y") if item["ts"] else "date non précisée"
    reference = f"{ref} · {item['source']}, publié le {pub}" if ref else f"{item['source']} — publication du {pub}"

    # Calendrier
    m = DATE_PHRASE.search(corpus)
    application = _fmt_date_phrase(m.group(2)) if m else "À confirmer (voir le texte)"

    # Cible
    cibles = [lab for lab, pat in CIBLES if re.search(pat, blob, re.I)]
    cible = ", ".join(cibles[:5]) if cibles else item["cible_defaut"]

    # 3 points
    kind = item["kind"]
    p1 = _pick(ranked, PURPOSE, used) or (ranked[0] if ranked else "") or short(desc) or \
        f"{item['source']} publie : « {title} »."
    used.add(p1)
    p2 = _pick(ranked, OBLIGATION, used) or {
        "Consultation": "Projet soumis à consultation : les exigences finales peuvent encore évoluer ; "
                        "identifier dès maintenant les écarts avec le dispositif existant.",
        "Orientations / recommandations": "Comparer les attentes du superviseur au dispositif existant et "
                                          "documenter les écarts dans un plan d'action.",
    }.get(kind, "Analyser les exigences opérationnelles du texte et les traduire en procédures et contrôles.")
    p3 = _pick(ranked, CONSTRAINT, used) or {
        "Consultation": "Texte non définitif : suivre la date de clôture de la consultation et la publication "
                        "de la version finale.",
    }.get(kind, "Un défaut de mise en conformité expose à des sanctions du superviseur et à un risque "
                "réputationnel.")

    # Checklist
    checklist = []
    for dom, pat in DOMAINS.items():
        matches = [m.group(0).lower() for m in re.finditer(pat, blob, re.I)]
        hits, n = sorted(set(matches)), len(matches)
        impact = "Fort" if n >= 4 else ("Modéré" if n >= 1 else "Faible")
        found = [h for h in hits if len(h) > 2][:4]
        texte = (f"{DOMAIN_ACTIONS[dom]} (thèmes relevés : {', '.join(found)})." if found else
                 "Pas d'impact direct identifié dans la publication — à confirmer à la lecture du texte.")
        checklist.append(dict(domaine=dom, texte=texte, impact=impact, fait=False))

    # L'essentiel
    rest = [s for s in ranked if s not in used]
    ctx_sents = " ".join(short(s, 330) for s in rest[:2])
    contexte = (f"Publication de type « {kind.lower()} » diffusée par {item['juridiction']} le {pub}. "
                + (ctx_sents + " " if ctx_sents else (short(desc, 500) + " " if desc else ""))
                + "À décliner dans le dispositif de contrôle interne : procédures opérationnelles (niveau 1), "
                  "contrôle permanent conformité (niveau 2) et audit (niveau 3).")
    strong = [c["domaine"] for c in checklist if c["impact"] != "Faible"]
    risk_sents = " ".join(short(s, 300) for s in rest[2:4] if CONSTRAINT.search(s) or OBLIGATION.search(s))
    risque = ((risk_sents + " ") if risk_sents else "") + (
        f"Domaines à adapter en priorité : {', '.join(strong)}. " if strong else "") + \
        ("Les évolutions doivent être tracées dans les outils (paramétrage, scénarios, seuils) et calibrées pour "
         "limiter les faux positifs ; un manquement expose à des sanctions financières et réputationnelles.")

    return dict(
        titre=short(title, 140), reference=reference, pays_source=item["juridiction"],
        adoption=month_year(item["ts"]), application=application, cible=cible,
        points=[p1, p2, p3], checklist=checklist, contexte=contexte, risque=risque,
        sources=f"{item['source']} — {item['link']}", type=kind, mode="Extraction automatique",
        lien=item["link"],
    )


# --------------------------------------------------------------------------- #
# Fiche par IA (optionnelle)
# --------------------------------------------------------------------------- #
LLM_PROMPT = """Tu es analyste conformité (LCB-FT, sanctions, réglementation bancaire) en France.
À partir UNIQUEMENT de la publication ci-dessous, rédige une fiche « Regulatory Flash » en français.
N'invente aucune date, référence ou obligation : si une information n'est pas dans le texte,
écris « Non précisé dans la publication ».

Réponds avec un unique objet JSON, sans texte autour, au format :
{{"titre": "nom court du texte (max 90 caractères)",
 "reference": "référence complète du texte ou de la publication",
 "pays_source": "{juridiction}",
 "adoption": "Mois AAAA",
 "application": "Mois AAAA ou Non précisé dans la publication",
 "cible": "assujettis visés (ex. Banques, PSAN, SGP, Assurances)",
 "points": ["objectif central (1 phrase)", "obligation technique clé (1 phrase)", "sanction ou contrainte majeure (1 phrase)"],
 "checklist": [
   {{"domaine": "KYC / KYB & UBO", "texte": "impact sur l'entrée en relation (1 phrase)", "impact": "Fort|Modéré|Faible"}},
   {{"domaine": "Filtrage & transactions", "texte": "impact sur screening, scénarios, règles (1 phrase)", "impact": "Fort|Modéré|Faible"}},
   {{"domaine": "Gouvernance & reporting", "texte": "audits, déclarations TRACFIN / ACPR / AMF (1 phrase)", "impact": "Fort|Modéré|Faible"}}],
 "contexte": "paragraphe de 4-5 phrases : esprit de la norme, ancrage juridique, exigences pour le contrôle interne (niveaux 1, 2, 3)",
 "risque": "paragraphe de 4-5 phrases : implémentation dans les outils IT, faux positifs, seuils, conséquences en cas de manquement"}}

Source : {source} ({juridiction})
Date de publication : {date}
Titre : {title}
Lien : {link}
Contenu :
{content}
"""


def llm_provider(secrets) -> str | None:
    try:
        if secrets.get("ANTHROPIC_API_KEY"):
            return "Claude"
        if secrets.get("MISTRAL_API_KEY"):
            return "Mistral"
        if secrets.get("OLLAMA_URL"):
            return "Ollama"
    except Exception:  # noqa: BLE001
        pass
    return None


def _json_from(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {}


def llm_flash(item: dict, page_text: str, secrets) -> dict:
    """Fiche rédigée par IA ; lève une exception en cas d'échec (le code appelant bascule sur l'extraction)."""
    provider = llm_provider(secrets)
    pub = datetime.fromtimestamp(item["ts"]).strftime("%d/%m/%Y") if item["ts"] else "non précisée"
    content = clean(" ".join(x for x in [item.get("desc", ""), page_text] if x), 12_000) or item["title"]
    prompt = LLM_PROMPT.format(source=item["source"], juridiction=item["juridiction"], date=pub,
                               title=item["title"], link=item["link"], content=content)
    if provider == "Claude":
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=90, headers={
            "x-api-key": secrets["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
            "content-type": "application/json"}, json={
            "model": secrets.get("CWP_LLM_MODEL", "claude-haiku-5-5"), "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        data = _json_from("".join(b.get("text", "") for b in r.json().get("content", [])))
    elif provider == "Mistral":
        r = requests.post("https://api.mistral.ai/v1/chat/completions", timeout=90, headers={
            "Authorization": f"Bearer {secrets['MISTRAL_API_KEY']}"}, json={
            "model": secrets.get("CWP_LLM_MODEL", "mistral-small-latest"),
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        data = _json_from(r.json()["choices"][0]["message"]["content"])
    elif provider == "Ollama":
        r = requests.post(secrets["OLLAMA_URL"].rstrip("/") + "/api/generate", timeout=180, json={
            "model": secrets.get("CWP_LLM_MODEL", "mistral"), "prompt": prompt, "format": "json",
            "stream": False})
        r.raise_for_status()
        data = _json_from(r.json().get("response", ""))
    else:
        raise RuntimeError("Aucun fournisseur IA configuré")

    base = extractive_flash(item, page_text)  # complète les champs manquants
    for k in ("titre", "reference", "pays_source", "adoption", "application", "cible", "contexte", "risque"):
        if isinstance(data.get(k), str) and data[k].strip():
            base[k] = data[k].strip()
    if isinstance(data.get("points"), list) and len(data["points"]) >= 3:
        base["points"] = [str(p) for p in data["points"][:3]]
    if isinstance(data.get("checklist"), list) and data["checklist"]:
        cl = []
        for i, c in enumerate(data["checklist"][:3]):
            imp = c.get("impact", "Modéré")
            cl.append(dict(domaine=c.get("domaine") or list(DOMAINS)[i], texte=c.get("texte", ""),
                           impact=imp if imp in ("Fort", "Modéré", "Faible") else "Modéré", fait=False))
        base["checklist"] = (cl + base["checklist"][len(cl):])[:3]
    base["mode"] = f"Synthèse IA ({provider})"
    return base


def build_flash(item: dict, secrets=None, use_ai: bool = True) -> dict:
    page_text = fetch_text(item["link"])
    if use_ai and secrets is not None and llm_provider(secrets):
        try:
            return llm_flash(item, page_text, secrets)
        except Exception as e:  # noqa: BLE001
            d = extractive_flash(item, page_text)
            d["mode"] = f"Extraction automatique (IA indisponible : {type(e).__name__})"
            return d
    return extractive_flash(item, page_text)

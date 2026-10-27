"""
tab_regulatory_flash.py — Onglet « Regulatory Flash » de CWP.

Fiche de synthèse d'un texte réglementaire :
en-tête (texte / référence), pays-source, calendrier, cible prioritaire,
3 points clés, checklist d'impacts systèmes & process, « L'essentiel » en 2 paragraphes.
Aperçu en direct + export PDF (A4) et PNG (hauteur ajustée), import/export JSON.

Intégration :  from tab_regulatory_flash import render_regulatory_flash
               with tab_flash: render_regulatory_flash()
"""
from __future__ import annotations

import json
from datetime import datetime

import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

import cwp_export_utils as X

# --------------------------------------------------------------------------- #
# Modèles pré-remplis (à vérifier / compléter sur EUR-Lex avant diffusion)
# --------------------------------------------------------------------------- #
IMPACTS = ["Fort", "Modéré", "Faible"]
DOMAINES = ["KYC / KYB & UBO", "Filtrage & transactions", "Gouvernance & reporting"]

BLANK = {
    "titre": "", "reference": "", "pays_source": "", "adoption": "", "application": "",
    "cible": "", "points": ["", "", ""],
    "checklist": [{"domaine": d, "texte": "", "impact": "Modéré", "fait": False} for d in DOMAINES],
    "contexte": "", "risque": "", "sources": "",
}

PRESETS = {
    "Vierge": BLANK,
    "AMLR — Règlement (UE) 2024/1624": {
        "titre": "AMLR — Règlement unique LCB-FT",
        "reference": "Règlement (UE) 2024/1624 du 31 mai 2024 relatif à la prévention de l'utilisation "
                     "du système financier aux fins du blanchiment de capitaux ou du financement du terrorisme",
        "pays_source": "Union européenne (paquet AML : AMLR, AMLD6, AMLA)",
        "adoption": "Mai 2024", "application": "Juillet 2027",
        "cible": "Banques, PSP / EME, PSAN (CASP), assurances, SGP, professions non financières",
        "points": [
            "Remplacer la mosaïque des transpositions nationales par un « single rulebook » "
            "directement applicable dans toute l'UE.",
            "Harmoniser la vigilance : bénéficiaire effectif (seuil de 25 % + contrôle par d'autres moyens), "
            "données KYC minimales et fréquence de revue fondée sur le risque.",
            "Plafond européen des paiements en espèces à 10 000 € ; régime de sanctions renforcé "
            "(AMLD6) sous la supervision coordonnée de l'AMLA.",
        ],
        "checklist": [
            {"domaine": "KYC / KYB & UBO", "impact": "Fort", "fait": False,
             "texte": "Revoir la collecte des données d'identification, la recherche des BE "
                      "(propriété et contrôle) et les cycles de mise à jour des dossiers selon le risque."},
            {"domaine": "Filtrage & transactions", "impact": "Modéré", "fait": False,
             "texte": "Intégrer le risque de contournement des sanctions financières ciblées "
                      "dans la classification des risques et les scénarios de surveillance."},
            {"domaine": "Gouvernance & reporting", "impact": "Fort", "fait": False,
             "texte": "Désigner un dirigeant responsable LCB-FT, actualiser la classification des risques "
                      "et adapter les déclarations de soupçon (TRACFIN) aux formats harmonisés."},
        ],
        "contexte": "Pièce centrale du paquet AML de 2024, l'AMLR transfère au niveau européen l'essentiel "
                    "des obligations jusqu'ici portées par les directives. Il fixe un socle commun pour "
                    "l'évaluation des risques, la vigilance à l'égard de la clientèle et la transparence "
                    "des bénéficiaires effectifs. Le contrôle interne doit être reconfiguré sur trois niveaux : "
                    "procédures opérationnelles (niveau 1), contrôle permanent conformité (niveau 2) "
                    "et audit de la conformité au nouveau référentiel (niveau 3).",
        "risque": "La mise en œuvre touche directement les outils : refonte des formulaires d'entrée en "
                  "relation, paramétrage des fréquences de revue, enrichissement du scoring client et "
                  "traçabilité des contrôles BE. Une calibration trop stricte gonfle les faux positifs, "
                  "une calibration trop lâche expose à des sanctions pécuniaires et administratives "
                  "prononcées par le superviseur national (ACPR / AMF) et à un risque réputationnel fort.",
        "sources": "EUR-Lex — Règlement (UE) 2024/1624 ; Directive (UE) 2024/1640 (AMLD6) ; "
                   "Règlement (UE) 2024/1620 (AMLA)",
    },
    "TFR — Règlement (UE) 2023/1113 (travel rule)": {
        "titre": "TFR — Travel rule fonds & crypto-actifs",
        "reference": "Règlement (UE) 2023/1113 du 31 mai 2023 sur les informations accompagnant "
                     "les transferts de fonds et de certains crypto-actifs",
        "pays_source": "Union européenne",
        "adoption": "Mai 2023", "application": "Décembre 2024",
        "cible": "PSP, EME, PSAN / CASP, intermédiaires de paiement",
        "points": [
            "Assurer la traçabilité de bout en bout des transferts, y compris de crypto-actifs, "
            "en transmettant l'identité du donneur d'ordre et du bénéficiaire.",
            "Transferts crypto : informations exigées sans seuil de montant ; contrôles renforcés "
            "pour les échanges avec des adresses auto-hébergées.",
            "Transfert incomplet : rejet ou suspension, demande d'informations et signalement "
            "des prestataires défaillants de façon répétée.",
        ],
        "checklist": [
            {"domaine": "KYC / KYB & UBO", "impact": "Modéré", "fait": False,
             "texte": "Vérifier la cohérence nom / compte / adresse wallet et documenter la propriété "
                      "des adresses auto-hébergées au-delà des seuils réglementaires."},
            {"domaine": "Filtrage & transactions", "impact": "Fort", "fait": False,
             "texte": "Contrôler la complétude des champs donneur d'ordre / bénéficiaire, filtrer ces "
                      "données contre les listes de sanctions et paramétrer les règles de rejet."},
            {"domaine": "Gouvernance & reporting", "impact": "Modéré", "fait": False,
             "texte": "Tenir un registre des contreparties défaillantes, formaliser la procédure "
                      "d'escalade et déclarer à TRACFIN en cas de soupçon."},
        ],
        "contexte": "Refonte du règlement 2015/847, le TFR étend la « travel rule » du GAFI aux crypto-actifs. "
                    "Chaque prestataire de la chaîne doit transmettre, recevoir et contrôler les informations "
                    "relatives aux parties. Le niveau 1 vérifie à l'exécution, le niveau 2 pilote les "
                    "indicateurs de complétude et de rejet, le niveau 3 teste l'efficacité du dispositif.",
        "risque": "L'implémentation repose sur des protocoles d'échange entre prestataires et sur des "
                  "règles de contrôle automatiques ; les données manquantes ou mal formatées génèrent "
                  "faux positifs et blocages. Un manquement expose à des sanctions de l'ACPR / AMF et peut "
                  "faire de l'établissement le maillon faible d'un schéma de contournement des sanctions.",
        "sources": "EUR-Lex — Règlement (UE) 2023/1113 ; Recommandation 16 du GAFI",
    },
}

# --------------------------------------------------------------------------- #
# État Streamlit
# --------------------------------------------------------------------------- #
P = "rf_"  # préfixe des clés de session


def _load(data: dict) -> None:
    d = {**BLANK, **data}
    for k in ("titre", "reference", "pays_source", "adoption", "application", "cible",
              "contexte", "risque", "sources"):
        st.session_state[P + k] = d.get(k, "")
    pts = (list(d.get("points", [])) + ["", "", ""])[:3]
    for i, v in enumerate(pts):
        st.session_state[f"{P}pt{i}"] = v
    cl = (list(d.get("checklist", [])) + BLANK["checklist"])[:3]
    for i, item in enumerate(cl):
        st.session_state[f"{P}cl{i}_domaine"] = item.get("domaine", DOMAINES[i])
        st.session_state[f"{P}cl{i}_texte"] = item.get("texte", "")
        st.session_state[f"{P}cl{i}_impact"] = item.get("impact", "Modéré") if item.get("impact") in IMPACTS else "Modéré"
        st.session_state[f"{P}cl{i}_fait"] = bool(item.get("fait", False))


def _collect() -> dict:
    g = st.session_state.get
    return {
        "titre": g(P + "titre", ""), "reference": g(P + "reference", ""),
        "pays_source": g(P + "pays_source", ""), "adoption": g(P + "adoption", ""),
        "application": g(P + "application", ""), "cible": g(P + "cible", ""),
        "points": [g(f"{P}pt{i}", "") for i in range(3)],
        "checklist": [{"domaine": g(f"{P}cl{i}_domaine", DOMAINES[i]),
                       "texte": g(f"{P}cl{i}_texte", ""),
                       "impact": g(f"{P}cl{i}_impact", "Modéré"),
                       "fait": g(f"{P}cl{i}_fait", False)} for i in range(3)],
        "contexte": g(P + "contexte", ""), "risque": g(P + "risque", ""),
        "sources": g(P + "sources", ""),
    }


# --------------------------------------------------------------------------- #
# Rendu PDF (ReportLab)
# --------------------------------------------------------------------------- #
_IMPACT_COLOR = {"Fort": X.RED, "Modéré": X.ORANGE, "Faible": X.GREEN}
_IMPACT_HEX = {"Fort": X.HEX["red"], "Modéré": X.HEX["orange"], "Faible": X.HEX["green"]}


def _flowables(d: dict, width: float) -> list:
    s = X.styles()
    out = [X.header_card("Regulatory Flash", d["titre"] or "Titre du texte",
                         d["reference"] or "Référence complète", width), Spacer(1, 12)]

    # Bandeau méta : pays / calendrier / cible
    cal = f"Adoption : {d['adoption'] or '—'}<br/>Application : {d['application'] or '—'}"
    meta = [[
        [Paragraph("PAYS / SOURCE", s["label"]), Spacer(1, 2), Paragraph(X.esc(d["pays_source"] or "—"), s["value"])],
        [Paragraph("CALENDRIER", s["label"]), Spacer(1, 2), Paragraph(cal, s["value"])],
        [Paragraph("CIBLE PRIORITAIRE", s["label"]), Spacer(1, 2), Paragraph(X.esc(d["cible"] or "—"), s["value"])],
    ]]
    t = Table(meta, colWidths=[width * 0.30, width * 0.28, width * 0.42])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBEFORE", (1, 0), (-1, -1), 0.6, X.LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (0, -1), 2),
    ]))
    out += [t, Spacer(1, 14)]

    # En 3 points
    rows = [[Paragraph(str(i + 1), s["num"]), Paragraph(X.esc(p or "—"), s["body"])]
            for i, p in enumerate(d["points"])]
    t = Table(rows, colWidths=[22, width - 22])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [X.colors.white, X.ROW_ALT]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, X.LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (0, -1), 6),
    ]))
    out += [KeepTogether([X.section_title("En 3 points", width), t]), Spacer(1, 14)]

    # Checklist
    rows = []
    for it in d["checklist"]:
        box = X.BOX_CHECKED if it["fait"] else X.BOX_EMPTY
        imp = it["impact"]
        rows.append([
            Paragraph(f'<font size="12" color="{X.HEX["navy"]}">{box}</font>', s["body"]),
            Paragraph(X.esc(it["domaine"]), s["body_b"]),
            Paragraph(X.esc(it["texte"] or "—"), s["small"]),
            Paragraph(f'<font color="{_IMPACT_HEX.get(imp, X.HEX["grey"])}"><b>{X.esc(imp)}</b></font>', s["small"]),
        ])
    head = [Paragraph("", s["label"]), Paragraph("DOMAINE", s["label"]),
            Paragraph("ACTION À MENER", s["label"]), Paragraph("IMPACT", s["label"])]
    t = Table([head] + rows, colWidths=[20, width * 0.24, width * 0.62 - 20, width * 0.14])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [X.colors.white, X.ROW_ALT]),
        ("LINEBELOW", (0, 1), (-1, -1), 0.5, X.LINE),
        ("TOPPADDING", (0, 1), (-1, -1), 6), ("BOTTOMPADDING", (0, 1), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (0, -1), 4),
    ]))
    out += [KeepTogether([X.section_title("Impacts systèmes & process — checklist réglementaire", width), t]),
            Spacer(1, 14)]

    # L'essentiel
    ess = [X.section_title("L'essentiel — lecture 2 min", width), Spacer(1, 6),
           Paragraph("Contexte & obligations légales et techniques", s["body_b"]), Spacer(1, 2),
           Paragraph(X.esc(d["contexte"] or "—"), s["body"]), Spacer(1, 8),
           Paragraph("Traçabilité, sanctions & risque de non-conformité", s["body_b"]), Spacer(1, 2),
           Paragraph(X.esc(d["risque"] or "—"), s["body"])]
    out += ess
    if d.get("sources"):
        out += [Spacer(1, 8), Paragraph(f"<b>Sources :</b> {X.esc(d['sources'])}", s["small_grey"])]

    out += [Spacer(1, 12), X.footer_line(
        "Regulatory Flash · fiche de synthèse : se référer au texte officiel (EUR-Lex, Légifrance, OFAC…)")]
    return out


def flash_pdf(d: dict) -> bytes:
    w = X.CONTENT_W
    return X.build_pdf(_flowables(d, w), title=f"Regulatory Flash — {d['titre']}")


def flash_png(d: dict) -> bytes:
    w = X.CONTENT_W
    return X.pdf_to_png(X.build_fitted_pdf(lambda: _flowables(d, w), title="Regulatory Flash"))


@st.cache_data(show_spinner=False)
def _cached_exports(payload: str) -> tuple[bytes, bytes]:
    d = json.loads(payload)
    return flash_pdf(d), flash_png(d)


# --------------------------------------------------------------------------- #
# Aperçu HTML (même charte)
# --------------------------------------------------------------------------- #
def _h(t: str) -> str:
    return X.esc(t).replace("<br/>", "<br>")


def _preview_html(d: dict) -> str:
    c = X.HEX
    pts = "".join(
        f'<div style="display:flex;gap:12px;padding:8px 6px;border-bottom:1px solid {c["line"]};'
        f'background:{"#fff" if i % 2 == 0 else c["row_alt"]}">'
        f'<div style="color:{c["gold"]};font-weight:700;font-size:18px;min-width:16px">{i + 1}</div>'
        f'<div>{_h(p) or "—"}</div></div>' for i, p in enumerate(d["points"]))
    cl = "".join(
        f'<div style="display:grid;grid-template-columns:24px 1.1fr 3fr 70px;gap:10px;padding:8px 6px;'
        f'border-bottom:1px solid {c["line"]};background:{"#fff" if i % 2 == 0 else c["row_alt"]}">'
        f'<div style="font-size:17px;color:{c["navy"]}">{"☑" if it["fait"] else "☐"}</div>'
        f'<div style="font-weight:600">{_h(it["domaine"])}</div>'
        f'<div style="font-size:13px">{_h(it["texte"]) or "—"}</div>'
        f'<div style="font-weight:700;font-size:13px;color:{_IMPACT_HEX.get(it["impact"], c["grey"])}">'
        f'{_h(it["impact"])}</div></div>' for i, it in enumerate(d["checklist"]))
    sec = (f'style="text-transform:uppercase;font-size:12px;font-weight:700;color:{c["navy"]};'
           f'letter-spacing:.04em;border-bottom:2px solid {c["gold"]};padding:0 2px 5px;margin:18px 0 4px"')
    lab = f'style="font-size:10.5px;font-weight:700;color:{c["grey"]};letter-spacing:.05em"'
    src = (f'<div style="color:{c["grey"]};font-size:12px;margin-top:10px"><b>Sources :</b> '
           f'{_h(d["sources"])}</div>') if d.get("sources") else ""
    return f"""
<div style="font-family:Inter,system-ui,sans-serif;color:{c['ink']};font-size:14px;line-height:1.5;
            background:#fff;padding:18px;border-radius:10px;border:1px solid {c['line']}">
  <div style="background:{c['cream']};border:1px solid {c['gold_light']};border-radius:12px;padding:14px 18px">
    <div style="color:{c['gold']};font-weight:700;font-size:11px;letter-spacing:.08em">REGULATORY FLASH</div>
    <div style="color:{c['gold']};font-size:26px;line-height:1.2">{_h(d['titre']) or 'Titre du texte'}</div>
    <div style="color:{c['grey']};font-size:13.5px;margin-top:4px">{_h(d['reference']) or 'Référence complète'}</div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1.4fr;gap:0;margin-top:14px">
    <div style="padding-right:10px"><div {lab}>PAYS / SOURCE</div>{_h(d['pays_source']) or '—'}</div>
    <div style="padding:0 10px;border-left:1px solid {c['line']}"><div {lab}>CALENDRIER</div>
      Adoption : {_h(d['adoption']) or '—'}<br>Application : {_h(d['application']) or '—'}</div>
    <div style="padding-left:10px;border-left:1px solid {c['line']}"><div {lab}>CIBLE PRIORITAIRE</div>{_h(d['cible']) or '—'}</div>
  </div>
  <div {sec}>En 3 points</div>{pts}
  <div {sec}>Impacts systèmes &amp; process — checklist réglementaire</div>{cl}
  <div {sec}>L'essentiel — lecture 2 min</div>
  <div style="font-weight:600;margin-top:6px">Contexte &amp; obligations légales et techniques</div>
  <div>{_h(d['contexte']) or '—'}</div>
  <div style="font-weight:600;margin-top:10px">Traçabilité, sanctions &amp; risque de non-conformité</div>
  <div>{_h(d['risque']) or '—'}</div>{src}
  <div style="color:{c['grey']};font-size:11px;margin-top:14px">CWP · Compliance Watch Platform · Regulatory Flash ·
    fiche de synthèse : se référer au texte officiel</div>
</div>"""


# --------------------------------------------------------------------------- #
# Onglet
# --------------------------------------------------------------------------- #
def render_regulatory_flash() -> None:
    if P + "titre" not in st.session_state:
        _load(PRESETS["AMLR — Règlement (UE) 2024/1624"])

    st.markdown("# 📌 Regulatory Flash")
    st.caption("Fiche de synthèse d'un texte réglementaire — à remplir, prévisualiser et exporter en PDF / image.")

    c1, c2 = st.columns([2, 1])
    with c1:
        preset = st.selectbox("Partir d'un modèle", list(PRESETS), key=P + "preset")
        if st.button("Charger ce modèle", key=P + "load_preset"):
            _load(PRESETS[preset])
            st.rerun()
    with c2:
        up = st.file_uploader("Importer un flash (.json)", type=["json"], key=P + "upload")
        if up is not None and st.session_state.get(P + "last_upload") != up.file_id:
            try:
                _load(json.load(up))
                st.session_state[P + "last_upload"] = up.file_id
                st.rerun()
            except Exception as e:  # noqa: BLE001
                st.error(f"Fichier JSON illisible : {e}")

    form_col, prev_col = st.columns([1, 1.15], gap="large")

    with form_col:
        with st.expander("① En-tête & calendrier", expanded=True):
            st.text_input("Nom du texte", key=P + "titre")
            st.text_area("Référence complète", key=P + "reference", height=70)
            st.text_input("Pays / source", key=P + "pays_source",
                          placeholder="Union européenne / US OFAC / France…")
            a, b = st.columns(2)
            a.text_input("Adoption (mois année)", key=P + "adoption", placeholder="Mai 2024")
            b.text_input("Entrée en application", key=P + "application", placeholder="Juillet 2027")
            st.text_input("Cible prioritaire", key=P + "cible", placeholder="Banques, PSAN, SGP, assurances…")
        with st.expander("② En 3 points", expanded=True):
            labels = ["Objectif central du texte", "Obligation technique clé", "Sanction ou contrainte majeure"]
            for i, lab in enumerate(labels):
                st.text_area(f"{i + 1}. {lab}", key=f"{P}pt{i}", height=75)
        with st.expander("③ Impacts systèmes & process", expanded=False):
            for i in range(3):
                if i:
                    st.divider()
                x, y = st.columns([3, 1])
                x.text_input("Domaine", key=f"{P}cl{i}_domaine", label_visibility="collapsed")
                y.selectbox("Impact", IMPACTS, key=f"{P}cl{i}_impact", label_visibility="collapsed")
                st.text_area("Action", key=f"{P}cl{i}_texte", height=70, label_visibility="collapsed")
                st.checkbox("Action réalisée", key=f"{P}cl{i}_fait")
        with st.expander("④ L'essentiel (lecture 2 min)", expanded=False):
            st.text_area("Contexte & obligations légales-techniques (niveaux 1, 2, 3)",
                         key=P + "contexte", height=150)
            st.text_area("Traçabilité, sanctions & risque de non-conformité", key=P + "risque", height=150)
            st.text_input("Sources (optionnel)", key=P + "sources")

    d = _collect()
    with prev_col:
        st.markdown(_preview_html(d), unsafe_allow_html=True)

    st.divider()
    pdf_b, png_b = _cached_exports(json.dumps(d, ensure_ascii=False, sort_keys=True))
    name = f"regulatory_flash_{X.slug(d['titre'])}_{datetime.now():%Y%m%d}"
    e1, e2, e3 = st.columns(3)
    e1.download_button("⬇️ PDF (A4)", pdf_b, f"{name}.pdf", "application/pdf", use_container_width=True)
    e2.download_button("🖼️ Image PNG", png_b, f"{name}.png", "image/png", use_container_width=True)
    e3.download_button("💾 Sauvegarder (.json)", json.dumps(d, ensure_ascii=False, indent=2).encode("utf-8"),
                       f"{name}.json", "application/json", use_container_width=True)

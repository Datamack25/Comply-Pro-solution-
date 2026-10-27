# CWP — Onglets « Regulatory Flash » et « Glossaire des fraudes »

## Page Veille → sous-onglet « 📜 Veille réglementaire »

- **Registre & calendrier** (`data_registre_reglementaire.py`) : textes adoptés depuis 2021, en vigueur,
  à venir ou en cours d'adoption (LCB-FT, sanctions, crypto-actifs, paiements, résilience, prudentiel, ESG).
  Filtres statut / thème / juridiction / année, prochaines échéances (J-xx), frise chronologique,
  fiche Regulatory Flash par texte (PDF / PNG), export Excel et recueil PDF.
  Pour ajouter un texte : copier un bloc dans `REGISTRE` et adapter les dates.
- **Publications récentes** : même moteur que la page Regulatory Flash (ci-dessous).

## Regulatory Flash = veille réglementaire automatique

`regwatch.py` interroge les régulateurs (ACPR, TRACFIN, AMF, DG Trésor, Journal officiel, AFA,
AMLA, EBA, ESMA, BCE, Conseil/Commission UE, GAFI, OFAC, FinCEN, Comité de Bâle) via leurs flux
officiels et Google News filtré sur leur site. Chaque publication est classée
(texte législatif, orientations, consultation, sanction, rapport…) et transformée en fiche
Regulatory Flash, exportable en PDF / PNG, ou regroupée dans un bulletin PDF.

- Ajouter ou retirer une source : dictionnaire `SOURCES` en haut de `regwatch.py`.
- Fiches rédigées par IA : ajouter une clé dans les secrets Streamlit (voir `secrets.toml.example`).
  Sans clé, la fiche est construite par extraction automatique du texte de la publication.
- Le panneau « État des sources » indique quels flux répondent.


## Fichiers à copier à la racine du dépôt `comply-pro-solution-`

```
cwp_export_utils.py          # socle commun export PDF / PNG (polices, palette CWP)
regwatch.py                  # moteur de veille réglementaire (sources, typologie, fiches)
tab_veille_reglementaire.py  # sous-onglet Veille réglementaire (registre + publications récentes)
data_registre_reglementaire.py # registre daté des textes 2021 → 2031
tab_regulatory_flash.py      # onglet Regulatory Flash
tab_glossaire_fraudes.py     # onglet Glossaire des fraudes
data_glossaire_fraudes.py    # les 50 fiches (modifiables sans toucher au code)
assets/fonts/DejaVuSans*.ttf # polices avec accents (licence libre DejaVu)
demo_app.py                  # facultatif : démo autonome
```

## requirements.txt — ajouter

```
reportlab>=4.0
pypdfium2>=4.0
pillow
```

## Intégration dans l'app existante

```python
from tab_regulatory_flash import render_regulatory_flash
from tab_glossaire_fraudes import render_glossaire_fraudes

tabs = st.tabs([..., "📌 Regulatory Flash", "📚 Glossaire des fraudes"])
with tabs[-2]:
    render_regulatory_flash()
with tabs[-1]:
    render_glossaire_fraudes()
```

(Si CWP utilise une navigation par `st.sidebar.radio`, appeler simplement la fonction
correspondante dans la branche voulue.)

## Exports

| Onglet | PDF | Image PNG | Autre |
|---|---|---|---|
| Regulatory Flash | A4 | hauteur ajustée au contenu | sauvegarde / import `.json` |
| Glossaire | toute la sélection filtrée (≈13 pages pour 50 fiches) | une fiche, ou une planche ≤ 10 fiches | `.json` |

## Accents dans les exports

Les carrés ▯ du Weekly Watch viennent d'une police sans glyphes accentués.
`cwp_export_utils` enregistre DejaVu Sans (assets/fonts → matplotlib → système).
Pour corriger le Weekly Watch, faire passer son export par `cwp_export_utils`
(mêmes `header_card`, `section_title`, `footer_line`, `build_pdf`, `pdf_to_png`)
ou, si l'image est faite avec Pillow, charger `assets/fonts/DejaVuSans.ttf`
au lieu de la police par défaut.

## Contenu

Les modèles AMLR (Règlement (UE) 2024/1624) et TFR (Règlement (UE) 2023/1113) sont
pré-remplis à titre d'exemple : relire les textes sur EUR-Lex avant diffusion.

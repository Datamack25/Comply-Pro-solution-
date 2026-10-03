# Compliance Watch Platform (CWP)

Plateforme Streamlit de veille conformité : sanctions, embargos, LCB-FT / AMLA, GAFI, régulateurs, anticorruption, crypto.

## Fonctions
- Veille multi-thèmes (Google News RSS) avec description, date et lien source, badge NOUVEAU
- Alertes par mots-clés (sidebar), export Excel, résumé automatique extractif
- Recherche OpenSanctions, textes de loi français, calendrier réglementaire, glossaire extensible
- Glossaire : ajoutez des lignes dans `concepts_extra.csv` (`terme,categorie,definition,decorticage,actualite`)

## Lancer
```
pip install -r requirements.txt
streamlit run app.py
```
Pour OpenSanctions : copier `.streamlit/secrets.toml.example` en `.streamlit/secrets.toml` et renseigner la clé API.

## Avertissement
Outil d'aide à la veille : vérifiez toujours les dates et textes sur les sources officielles (EUR-Lex, Légifrance, OFAC...).

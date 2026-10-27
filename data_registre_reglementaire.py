"""
data_registre_reglementaire.py — Registre des textes réglementaires suivis par CWP (2021 → 2031).

Un texte = une entrée. Pour ajouter un texte, copiez un bloc et adaptez-le.
- adoption / application : "AAAA-MM-JJ" ; application = date d'application principale
  (ou date limite de transposition pour une directive).
- jalons : autres échéances datées (entrée en vigueur, application par étapes…).
- projet=True : texte non encore publié (accord politique, proposition).
- a_verifier : point du calendrier susceptible d'évoluer.
Les dates proviennent du Journal officiel de l'UE, de Légifrance et des publications des autorités ;
vérifiez-les dans le texte officiel avant toute diffusion externe.
"""

THEMES = ["LCB-FT", "Sanctions & embargos", "Crypto-actifs", "Paiements", "Résilience & numérique",
          "Prudentiel", "ESG & fiscalité"]


def _eli(kind: str, year: int, num: int) -> str:
    return f"https://eur-lex.europa.eu/eli/{kind}/{year}/{num}/oj"


def _lgf(q: str) -> str:
    return "https://www.legifrance.gouv.fr/search/all?tab_selection=all&query=" + q.replace(" ", "+")


EBA_PUBS = "https://www.eba.europa.eu/publications-and-media/publications"
FATF_RECS = "https://www.fatf-gafi.org/en/publications/Fatfrecommendations/Fatf-recommendations.html"

REGISTRE = [
    # ------------------------------------------------------------------ LCB-FT — paquet européen
    dict(id="amlr", nom="AMLR — Règlement unique LCB-FT", theme="LCB-FT", juridiction="Union européenne",
         type="Règlement", reference="Règlement (UE) 2024/1624 du 31 mai 2024",
         adoption="2024-05-31", application="2027-07-10",
         jalons=[("2024-07-09", "Entrée en vigueur"), ("2027-07-10", "Application directe dans toute l'UE"),
                 ("2029-07-10", "Obligations étendues aux agents et clubs de football professionnels")],
         cible="Banques, PSP / EME, PSAN (CASP), assurances, SGP, professions non financières",
         objectif="Remplacer la mosaïque des transpositions nationales par un « single rulebook » LCB-FT "
                  "directement applicable dans toute l'UE.",
         obligation="Vigilance harmonisée : identification et vérification des clients, bénéficiaires effectifs "
                    "(seuil de 25 % et contrôle par d'autres moyens), revue périodique selon le risque, "
                    "gestion du risque de contournement des sanctions financières ciblées.",
         contrainte="Plafond européen de 10 000 € pour les paiements en espèces ; sanctions renforcées "
                    "prévues par l'AMLD6 sous la supervision coordonnée de l'AMLA.",
         lien=_eli("reg", 2024, 1624)),
    dict(id="amld6", nom="AMLD6 — Sixième directive LCB-FT", theme="LCB-FT", juridiction="Union européenne",
         type="Directive", reference="Directive (UE) 2024/1640 du 31 mai 2024",
         adoption="2024-05-31", application="2027-07-10",
         jalons=[("2025-07-10", "Transposition de l'article 74"),
                 ("2026-07-10", "Registres des bénéficiaires effectifs et registres immobiliers (art. 11 à 15)"),
                 ("2027-07-10", "Date limite générale de transposition"),
                 ("2029-07-10", "Point d'accès unique aux informations immobilières (art. 18)")],
         cible="États membres, superviseurs, CRF (TRACFIN) ; impacts indirects pour tous les assujettis",
         objectif="Organiser les mécanismes nationaux : registres des bénéficiaires effectifs, cellules de "
                  "renseignement financier, pouvoirs et coopération des superviseurs.",
         obligation="Registres BE interconnectés et accès des assujettis, signalement des divergences, "
                    "méthodologie de supervision fondée sur les risques.",
         contrainte="Sanctions pécuniaires harmonisées : pour les établissements de crédit et financiers, "
                    "jusqu'à au moins 10 M€ ou 10 % du chiffre d'affaires annuel.",
         lien=_eli("dir", 2024, 1640)),
    dict(id="amlar", nom="AMLAR — Création de l'AMLA", theme="LCB-FT", juridiction="Union européenne",
         type="Règlement", reference="Règlement (UE) 2024/1620 du 31 mai 2024",
         adoption="2024-05-31", application="2028-07-01",
         jalons=[("2024-06-26", "Entrée en vigueur"),
                 ("2026-07-10", "Premières orientations et normes techniques de l'AMLA"),
                 ("2027-07-01", "Sélection des entités soumises à la supervision directe (prévue courant 2027)"),
                 ("2028-07-01", "Début de la supervision directe par l'AMLA (prévu)")],
         a_verifier="Calendrier de sélection et de supervision directe annoncé par l'AMLA.",
         cible="Établissements financiers transfrontaliers à haut risque (supervision directe), "
               "superviseurs nationaux (ACPR, AMF)",
         objectif="Créer l'Autorité européenne de lutte contre le blanchiment (Francfort), chargée de "
                  "coordonner les superviseurs et les CRF et de superviser directement certains établissements.",
         obligation="Normes techniques et orientations de l'AMLA à intégrer dans les dispositifs ; "
                    "remontée de données de supervision vers l'AMLA.",
         contrainte="Pour les entités sélectionnées : supervision directe, pouvoirs d'enquête et de sanction "
                    "de l'AMLA.",
         lien=_eli("reg", 2024, 1620)),
    dict(id="arrete-2021", nom="Arrêté contrôle interne LCB-FT et gel des avoirs", theme="LCB-FT",
         juridiction="France", type="Arrêté",
         reference="Arrêté du 6 janvier 2021 relatif au dispositif et au contrôle interne en matière de LCB-FT "
                   "et de gel des avoirs",
         adoption="2021-01-06", application="2021-03-01",
         jalons=[("2021-03-01", "Entrée en vigueur")],
         cible="Organismes financiers assujettis supervisés par l'ACPR",
         objectif="Préciser l'organisation du dispositif LCB-FT et de gel des avoirs : classification des "
                  "risques, procédures, contrôle interne et responsabilités au sein des groupes.",
         obligation="Classification des risques tenant compte des travaux du GAFI et de l'UE, procédures "
                    "écrites, dispositif de détection des opérations visant à contourner les mesures de gel.",
         contrainte="Contrôle interne proportionné et responsabilité de la maison mère sur le dispositif "
                    "de groupe ; manquements sanctionnables par l'ACPR.",
         lien=_lgf("arrêté 6 janvier 2021 contrôle interne blanchiment")),
    # ------------------------------------------------------------------ LCB-FT — orientations EBA
    dict(id="eba-gl-2022-05", nom="Orientations EBA sur le responsable LCB-FT", theme="LCB-FT",
         juridiction="Union européenne", type="Orientations", reference="EBA/GL/2022/05",
         adoption="2022-06-14", application="2022-12-01", jalons=[],
         cible="Établissements de crédit et financiers",
         objectif="Préciser le rôle du membre de l'organe de direction responsable LCB-FT et du responsable "
                  "de la conformité LCB-FT.",
         obligation="Désignation formelle, profil et moyens du responsable LCB-FT, reporting régulier à "
                    "l'organe de direction, organisation au niveau du groupe.",
         contrainte="Le superviseur apprécie l'adéquation des moyens et de l'indépendance de la fonction.",
         lien=EBA_PUBS),
    dict(id="eba-gl-2022-15", nom="Orientations EBA sur l'entrée en relation à distance", theme="LCB-FT",
         juridiction="Union européenne", type="Orientations", reference="EBA/GL/2022/15",
         adoption="2022-11-22", application="2023-10-02", jalons=[],
         cible="Établissements de crédit et financiers pratiquant l'onboarding à distance",
         objectif="Encadrer les solutions d'identification et de vérification à distance des clients.",
         obligation="Politique d'onboarding à distance, contrôle de la fiabilité des documents et des données "
                    "biométriques, tests et suivi des prestataires.",
         contrainte="L'établissement reste responsable des solutions externalisées et de leur efficacité.",
         lien=EBA_PUBS),
    dict(id="eba-gl-2024-01", nom="Orientations EBA facteurs de risque BC-FT étendues aux CASP", theme="LCB-FT",
         juridiction="Union européenne", type="Orientations", reference="EBA/GL/2024/01",
         adoption="2024-01-16", application="2024-12-30", jalons=[],
         cible="PSAN / CASP, banques en relation avec des CASP",
         objectif="Intégrer les prestataires de services sur crypto-actifs dans les orientations sur les "
                  "facteurs de risque BC-FT.",
         obligation="Facteurs de risque spécifiques aux crypto-actifs (adresses auto-hébergées, mixeurs, "
                    "anonymat) et mesures de vigilance adaptées.",
         contrainte="Prise en compte attendue dans la classification des risques et la vigilance des CASP.",
         lien=EBA_PUBS),
    # ------------------------------------------------------------------ Sanctions & embargos
    dict(id="dual-use", nom="Règlement « biens à double usage »", theme="Sanctions & embargos",
         juridiction="Union européenne", type="Règlement", reference="Règlement (UE) 2021/821 du 20 mai 2021",
         adoption="2021-05-20", application="2021-09-09", jalons=[("2021-09-09", "Application")],
         cible="Exportateurs, banques finançant le commerce international (trade finance)",
         objectif="Refondre le régime de contrôle des exportations, transferts, courtage et transit des biens "
                  "à double usage.",
         obligation="Licences d'exportation, contrôles « catch-all », programme interne de conformité "
                    "pour les exportateurs.",
         contrainte="Exportation sans licence pénalement sanctionnée ; vigilance attendue des banques sur "
                    "les opérations de trade finance.",
         lien=_eli("reg", 2021, 821)),
    dict(id="dir-2024-1226", nom="Directive pénalisant la violation des mesures restrictives",
         theme="Sanctions & embargos", juridiction="Union européenne", type="Directive",
         reference="Directive (UE) 2024/1226 du 24 avril 2024",
         adoption="2024-04-24", application="2025-05-20", jalons=[("2025-05-20", "Date limite de transposition")],
         cible="Personnes morales et physiques, établissements financiers",
         objectif="Harmoniser les infractions pénales et les peines en cas de violation ou de contournement "
                  "des sanctions de l'UE.",
         obligation="Infractions définies : mise à disposition de fonds, non-gel, contournement, fausses "
                    "informations aux autorités.",
         contrainte="Amendes pour les personnes morales jusqu'à 5 % du chiffre d'affaires mondial ou 40 M€ "
                    "selon l'infraction.",
         lien=_eli("dir", 2024, 1226)),
    dict(id="eba-gl-2024-14", nom="Orientations EBA sur les mesures restrictives", theme="Sanctions & embargos",
         juridiction="Union européenne", type="Orientations", reference="EBA/GL/2024/14 et EBA/GL/2024/15",
         adoption="2024-11-14", application="2025-12-30", jalons=[("2025-12-30", "Application")],
         cible="Banques, PSP / EME, PSAN (CASP)",
         objectif="Fixer un standard européen pour les politiques, procédures et contrôles internes de mise en "
                  "œuvre des sanctions de l'UE et nationales.",
         obligation="Évaluation de l'exposition aux sanctions, gouvernance, filtrage des clients et des "
                    "transactions, gestion des alertes et calibrage des outils.",
         contrainte="Application depuis le 30 décembre 2025 ; contrôle par l'ACPR et l'AMF (orientations "
                    "reprises par l'AMF, DOC-2025-02).",
         lien="https://www.amf-france.org/en/regulation/policy/doc-2025-02"),
    dict(id="dir-2024-1260", nom="Directive recouvrement et confiscation des avoirs",
         theme="Sanctions & embargos", juridiction="Union européenne", type="Directive",
         reference="Directive (UE) 2024/1260 du 24 avril 2024",
         adoption="2024-04-24", application="2026-11-23",
         jalons=[("2024-05-22", "Entrée en vigueur"), ("2026-11-23", "Date limite de transposition"),
                 ("2027-05-24", "Stratégie nationale de recouvrement des avoirs")],
         cible="Autorités judiciaires et répressives ; établissements sollicités pour le dépistage et le gel",
         objectif="Renforcer le dépistage, le gel, la confiscation et la gestion des avoirs d'origine criminelle.",
         obligation="Enquêtes patrimoniales immédiates, gel rapide, confiscation élargie et de valeur, "
                    "confiscation des avoirs inexpliqués liés à la criminalité organisée.",
         contrainte="Hausse attendue des réquisitions et demandes de gel adressées aux établissements financiers.",
         lien=_eli("dir", 2024, 1260)),
    # ------------------------------------------------------------------ Crypto-actifs
    dict(id="tfr", nom="TFR — Travel rule fonds et crypto-actifs", theme="Crypto-actifs",
         juridiction="Union européenne", type="Règlement", reference="Règlement (UE) 2023/1113 du 31 mai 2023",
         adoption="2023-05-31", application="2024-12-30", jalons=[("2024-12-30", "Application")],
         cible="PSP, EME, PSAN / CASP",
         objectif="Assurer la traçabilité des transferts de fonds et étendre la « travel rule » aux "
                  "transferts de crypto-actifs.",
         obligation="Transmission des informations sur le donneur d'ordre et le bénéficiaire, sans seuil pour "
                    "les crypto-actifs ; contrôles sur les adresses auto-hébergées.",
         contrainte="Transferts incomplets à rejeter ou suspendre ; prestataires défaillants à signaler.",
         lien=_eli("reg", 2023, 1113)),
    dict(id="eba-gl-2024-11", nom="Orientations EBA « travel rule »", theme="Crypto-actifs",
         juridiction="Union européenne", type="Orientations", reference="EBA/GL/2024/11",
         adoption="2024-07-04", application="2024-12-30", jalons=[],
         cible="PSP, PSAN / CASP",
         objectif="Préciser les procédures de détection des informations manquantes et de traitement "
                  "des transferts incomplets.",
         obligation="Procédures de vérification des champs, gestion des transferts incomplets, "
                    "évaluation des contreparties.",
         contrainte="Suivi des prestataires défaillants de manière répétée et signalement aux autorités.",
         lien=EBA_PUBS),
    dict(id="mica", nom="MiCA — Marchés de crypto-actifs", theme="Crypto-actifs",
         juridiction="Union européenne", type="Règlement", reference="Règlement (UE) 2023/1114 du 31 mai 2023",
         adoption="2023-05-31", application="2024-12-30",
         jalons=[("2024-06-30", "Jetons se référant à des actifs et jetons de monnaie électronique"),
                 ("2024-12-30", "Application générale (CASP)"),
                 ("2026-07-01", "Fin du régime transitoire des PSAN en France")],
         cible="PSAN / CASP, émetteurs de jetons, banques offrant des services crypto",
         objectif="Créer un cadre européen unique pour l'émission de crypto-actifs et les services sur "
                  "crypto-actifs, avec un agrément valable dans toute l'UE.",
         obligation="Agrément CASP, exigences de gouvernance, de fonds propres, de conservation et de "
                    "protection des clients ; règles pour les émetteurs de stablecoins.",
         contrainte="Activité sans agrément MiCA interdite après la période transitoire.",
         lien=_eli("reg", 2023, 1114)),
    dict(id="ord-2024-936", nom="Ordonnance d'adaptation à MiCA", theme="Crypto-actifs", juridiction="France",
         type="Ordonnance", reference="Ordonnance n° 2024-936 du 15 octobre 2024 relative aux marchés de crypto-actifs",
         adoption="2024-10-15", application="2024-12-30",
         jalons=[("2024-10-18", "Dispositions sur les jetons (EMT, ART)"), ("2024-12-30", "Application générale"),
                 ("2026-07-01", "Fin du régime national des PSAN")],
         cible="PSAN / CASP, émetteurs de jetons",
         objectif="Adapter le droit français à MiCA et organiser la sortie du régime PSAN national.",
         obligation="Désignation de l'AMF et de l'ACPR comme autorités compétentes, articulation avec le "
                    "code monétaire et financier.",
         contrainte="Les PSAN enregistrés devaient obtenir l'agrément MiCA avant le 1er juillet 2026.",
         lien=_lgf("ordonnance 2024-936")),
    dict(id="ord-2024-937", nom="Ordonnance LCB-FT sur les transferts de crypto-actifs", theme="Crypto-actifs",
         juridiction="France", type="Ordonnance",
         reference="Ordonnance n° 2024-937 du 15 octobre 2024 relative au renforcement des obligations de LCB-FT "
                   "en matière de transfert de crypto-actifs",
         adoption="2024-10-15", application="2024-12-30", jalons=[],
         a_verifier="Date d'application alignée sur celle du TFR.",
         cible="PSAN / CASP, PSP",
         objectif="Transposer en droit français les modifications de la directive LCB-FT introduites par le TFR.",
         obligation="Intégration des CASP parmi les assujettis LCB-FT et vigilance sur les transferts de "
                    "crypto-actifs.",
         contrainte="Supervision partagée ACPR / AMF pendant la période transitoire jusqu'au 1er juillet 2026.",
         lien=_lgf("ordonnance 2024-937")),
    # ------------------------------------------------------------------ Paiements
    dict(id="ipr", nom="Règlement sur les virements instantanés", theme="Paiements",
         juridiction="Union européenne", type="Règlement", reference="Règlement (UE) 2024/886 du 13 mars 2024",
         adoption="2024-03-13", application="2025-01-09",
         jalons=[("2025-01-09", "Réception des virements instantanés et filtrage sanctions quotidien"),
                 ("2025-10-09", "Émission des virements instantanés et vérification du bénéficiaire (VoP)"),
                 ("2027-04-09", "Obligations étendues aux établissements de paiement et de monnaie électronique")],
         cible="Banques, PSP / EME de la zone euro",
         objectif="Généraliser le virement instantané en euros, au même prix qu'un virement classique.",
         obligation="Vérification de concordance nom / IBAN avant paiement ; filtrage des clients contre les "
                    "listes de sanctions de l'UE au moins une fois par jour plutôt que transaction par transaction.",
         contrainte="Le PSP qui n'effectue pas la vérification du bénéficiaire est responsable du préjudice subi "
                    "par le payeur.",
         lien=_eli("reg", 2024, 886)),
    dict(id="psr-psd3", nom="PSR / PSD3 — Réforme des services de paiement", theme="Paiements",
         juridiction="Union européenne", type="Règlement", reference="Proposition de règlement PSR et directive PSD3 (juin 2023)",
         adoption="2025-11-27", application=None, projet=True,
         jalons=[("2025-11-27", "Accord provisoire Parlement / Conseil"),
                 ("2028-01-01", "Application attendue après une période transitoire d'environ 21 mois")],
         a_verifier="Textes définitifs et dates de publication / d'application à confirmer au Journal officiel.",
         cible="Banques, PSP / EME, plateformes en ligne",
         objectif="Moderniser les règles des services de paiement et renforcer la lutte contre la fraude.",
         obligation="Vérification nom / IBAN pour tous les virements, partage de données de fraude entre PSP, "
                    "renforcement de l'authentification forte.",
         contrainte="Remboursement intégral des victimes de fraude au faux conseiller sous conditions ; "
                    "responsabilité du PSP dépourvu de mesures antifraude adaptées.",
         lien="https://www.europarl.europa.eu/legislative-train/theme-an-economy-that-works-for-people/"
              "file-payment-services-and-electronic-money-services-(directive)"),
    dict(id="ccd2", nom="CCD2 — Directive crédit à la consommation", theme="Paiements",
         juridiction="Union européenne", type="Directive", reference="Directive (UE) 2023/2225 du 18 octobre 2023",
         adoption="2023-10-18", application="2026-11-20",
         jalons=[("2025-11-20", "Date limite de transposition"), ("2026-11-20", "Application")],
         cible="Prêteurs, établissements de crédit, intermédiaires, plateformes de « buy now pay later »",
         objectif="Moderniser la protection des emprunteurs, y compris pour le paiement fractionné et les "
                  "petits crédits.",
         obligation="Évaluation de solvabilité renforcée, informations précontractuelles, encadrement de la "
                    "publicité et de la vente en ligne.",
         contrainte="Sanctions effectives et dissuasives fixées par les États membres.",
         lien=_eli("dir", 2023, 2225)),
    # ------------------------------------------------------------------ Résilience & numérique
    dict(id="dora", nom="DORA — Résilience opérationnelle numérique", theme="Résilience & numérique",
         juridiction="Union européenne", type="Règlement", reference="Règlement (UE) 2022/2554 du 14 décembre 2022",
         adoption="2022-12-14", application="2025-01-17", jalons=[("2025-01-17", "Application")],
         cible="Banques, assurances, PSP / EME, CASP, SGP, prestataires TIC critiques",
         objectif="Garantir la résilience numérique du secteur financier face aux incidents TIC et cyber.",
         obligation="Cadre de gestion du risque TIC, notification des incidents majeurs, tests de résilience, "
                    "registre des contrats avec les prestataires TIC.",
         contrainte="Supervision directe des prestataires TIC critiques par les autorités européennes.",
         lien=_eli("reg", 2022, 2554)),
    dict(id="ai-act", nom="AI Act — Règlement sur l'intelligence artificielle", theme="Résilience & numérique",
         juridiction="Union européenne", type="Règlement", reference="Règlement (UE) 2024/1689 du 13 juin 2024",
         adoption="2024-06-13", application="2026-08-02",
         jalons=[("2025-02-02", "Pratiques d'IA interdites"), ("2025-08-02", "Modèles d'IA à usage général"),
                 ("2026-08-02", "Application générale (dont systèmes à haut risque de l'annexe III)"),
                 ("2027-08-02", "Systèmes à haut risque de l'annexe I")],
         a_verifier="Le calendrier des systèmes à haut risque peut être décalé par l'omnibus numérique.",
         cible="Banques et assureurs utilisant l'IA (scoring de crédit, tarification), fournisseurs d'IA",
         objectif="Encadrer les systèmes d'IA selon leur niveau de risque.",
         obligation="Pour les systèmes à haut risque (ex. évaluation de solvabilité) : gestion des risques, "
                    "qualité des données, documentation, supervision humaine.",
         contrainte="Amendes jusqu'à 35 M€ ou 7 % du chiffre d'affaires mondial pour les pratiques interdites.",
         lien=_eli("reg", 2024, 1689)),
    # ------------------------------------------------------------------ Prudentiel
    dict(id="crr3", nom="CRR3 — Finalisation de Bâle III", theme="Prudentiel", juridiction="Union européenne",
         type="Règlement", reference="Règlement (UE) 2024/1623 du 31 mai 2024",
         adoption="2024-05-31", application="2025-01-01", jalons=[("2025-01-01", "Application")],
         cible="Établissements de crédit et entreprises d'investissement",
         objectif="Transposer la finalisation de Bâle III : risque de crédit, risque opérationnel, output floor.",
         obligation="Nouvelles méthodes de calcul des exigences de fonds propres et reporting associé.",
         contrainte="Plancher de fonds propres (output floor) introduit progressivement.",
         lien=_eli("reg", 2024, 1623)),
    dict(id="crd6", nom="CRD6 — Directive exigences de fonds propres", theme="Prudentiel",
         juridiction="Union européenne", type="Directive", reference="Directive (UE) 2024/1619 du 31 mai 2024",
         adoption="2024-05-31", application="2026-01-11",
         jalons=[("2026-01-10", "Date limite de transposition"),
                 ("2027-01-11", "Régime des succursales de pays tiers")],
         cible="Établissements de crédit, succursales de pays tiers",
         objectif="Renforcer la gouvernance, l'honorabilité des dirigeants et l'encadrement des succursales "
                  "de pays tiers.",
         obligation="Évaluation de l'aptitude des dirigeants, intégration des risques ESG, agrément des "
                    "succursales de pays tiers.",
         contrainte="Pouvoirs de sanction harmonisés des superviseurs.",
         lien=_eli("dir", 2024, 1619)),
    # ------------------------------------------------------------------ ESG & fiscalité
    dict(id="csrd", nom="CSRD — Reporting de durabilité", theme="ESG & fiscalité",
         juridiction="Union européenne", type="Directive", reference="Directive (UE) 2022/2464 du 14 décembre 2022",
         adoption="2022-12-14", application="2024-01-01",
         jalons=[("2024-01-01", "Premières entreprises (exercice 2024)")],
         a_verifier="Vagues suivantes reportées par la directive « stop-the-clock » (UE) 2025/794 et l'omnibus.",
         cible="Grandes entreprises et établissements financiers",
         objectif="Généraliser un reporting de durabilité normé (ESRS) et audité.",
         obligation="Double matérialité, publication selon les normes ESRS, assurance par un tiers.",
         contrainte="Calendrier progressif, en partie reporté par les textes omnibus.",
         lien=_eli("dir", 2022, 2464)),
    dict(id="dac8", nom="DAC8 — Échange d'informations sur les crypto-actifs", theme="ESG & fiscalité",
         juridiction="Union européenne", type="Directive", reference="Directive (UE) 2023/2226 du 17 octobre 2023",
         adoption="2023-10-17", application="2026-01-01", jalons=[("2026-01-01", "Application")],
         cible="PSAN / CASP",
         objectif="Étendre l'échange automatique d'informations fiscales aux crypto-actifs.",
         obligation="Collecte et déclaration des informations sur les utilisateurs et leurs transactions "
                    "(diligence fiscale des clients).",
         contrainte="Sanctions nationales en cas de défaut de déclaration.",
         lien=_eli("dir", 2023, 2226)),
    # ------------------------------------------------------------------ International (GAFI)
    dict(id="fatf-r24", nom="GAFI — Recommandation 24 révisée (bénéficiaires effectifs)", theme="LCB-FT",
         juridiction="International (GAFI)", type="Recommandation", reference="Recommandation 24 du GAFI, révision de mars 2022",
         adoption="2022-03-04", application="2022-03-04", jalons=[],
         cible="Juridictions, registres BE ; impacts pour tous les assujettis",
         objectif="Renforcer la transparence des personnes morales et l'accès aux bénéficiaires effectifs.",
         obligation="Approche multiple (registre, informations détenues par les sociétés et les assujettis), "
                    "informations adéquates, exactes et à jour.",
         contrainte="Évaluée dans le cycle d'évaluations mutuelles en cours.",
         lien=FATF_RECS),
    dict(id="fatf-r16", nom="GAFI — Recommandation 16 révisée (transparence des paiements)", theme="Paiements",
         juridiction="International (GAFI)", type="Recommandation", reference="Recommandation 16 du GAFI, révision de juin 2025",
         adoption="2025-06-18", application="2030-12-31",
         jalons=[("2030-12-31", "Mise en œuvre attendue d'ici fin 2030")],
         cible="Banques, PSP, PSAN",
         objectif="Moderniser les règles de transparence des virements (« travel rule ») et clarifier les "
                  "responsabilités le long de la chaîne de paiement.",
         obligation="Données enrichies sur le donneur d'ordre et le bénéficiaire, vérification de concordance "
                    "nom / compte.",
         contrainte="Transposition attendue dans les législations nationales et européennes.",
         lien=FATF_RECS),
]

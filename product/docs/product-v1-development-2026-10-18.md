# FINLEAK — Product Development V1

Mission du 18 octobre 2026. Développement réalisé exclusivement dans l’espace Work Cloud distant et son navigateur Cloud. Aucune commande ni interaction avec le PC Windows/Ubuntu de l’utilisateur.

## Résultat livré

Une tranche SaaS fonctionnelle a été ajoutée au projet existant : **Overview → Invoices → Anomalies → Evidence & calculation → Human review**. Les routes métier utilisent les BFF et les contrats FastAPI existants. Un espace `/demo/dashboard` public, séparé des routes authentifiées, permet d’explorer les mêmes composants avec des exemples synthétiques en mémoire, sans appel aux API métier.

Le parcours réel est implémenté et testé à ses frontières frontend/BFF. **Il n’a pas été validé de bout en bout avec une session OIDC et une base PostgreSQL actives.** Les captures proviennent du produit compilé, exécuté dans le navigateur Cloud en mode synthétique ; elles ne constituent pas des résultats financiers réels.

## Reprise vérifiée et préservation

- Dépôt privé : `yasthekiller007-lang/financial-leakage-ai`.
- Base exacte : `c02424c2f3d910af771dcdc05e2f5cb281de4bef` ; arbre `4de2de722abb11dcb487ddd20434cd18a6291f3e`.
- Les 319 fichiers d’origine ont été récupérés au même commit par le connecteur GitHub authentifié, puis vérifiés par taille et empreinte Git de leurs octets. L’objet du commit signé et l’arbre local correspondent à la base.
- Branche locale isolée : `dev/product-v1-finance-workspace-20261018`. Aucun push, merge, changement distant de branche ni déclenchement GitHub Actions.
- La référence locale `main` reste sur le commit de base. Le dépôt distant n’a subi aucune mutation.
- 314 fichiers d’origine restent identiques. Les cinq fichiers d’origine modifiés sont exclusivement frontend : `package.json`, le dashboard, le layout racine, la navigation et la sidebar.
- Tous les fichiers backend, règles financières, tests historiques, contrats approuvés et documents historiques du dépôt restent identiques octet pour octet. Les autres checkpoints C1–C7/R1.x de l’espace de travail n’ont pas été modifiés. Les corrections D01–D04 et leurs preuves de qualification n’ont pas été réévaluées par cette mission.

Le checkout est un instantané Git superficiel exact de la base, avec un nouveau commit de développement local. L’historique complet continue d’exister sur GitHub ; il n’est pas reconstruit ni remplacé par cette archive. Le patch livré permet d’examiner chaque changement par rapport à la base.

## État réel du projet avant modification

| Domaine                  | Constat dans le code existant                                                                                                                                                                      |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Frontend                 | Next.js 16.3.8, React 19.3.0, TypeScript 5.9.3 ; routes protégées, dashboard sommaire, documents, revue financière, preuves et Recovery Ledger existants.                                          |
| Backend                  | FastAPI, SQLAlchemy, PostgreSQL, Python 3.12 ; moteur Decimal, règles contractuelles, évaluations immuables et overlays de décision.                                                               |
| Identité / organisations | NextAuth/OIDC ; jeton backend conservé côté serveur ; `/me` fournit les appartenances. Les BFF et le backend vérifient l’autorité.                                                                 |
| Documents                | Import PDF/CSV/XLSX, extraction et revue des champs, provenance et disponibilité documentaire déjà implémentés. Leur fonctionnement avec le stockage et les services réels n’a pas été exercé ici. |
| Finances / preuves       | Sources financières revues, évaluations, résumé par devise/règle, décisions avec contrôle du prédécesseur, preuves et historique existants.                                                        |
| Limite produit           | Une grande partie du parcours résidait dans un espace technique unique. Il manquait des listes Invoices/Contracts/Anomalies/Review et un dashboard exécutif relié à ces listes.                    |
| Validation initiale      | Les 120 tests frontend d’origine passaient avant les modifications. Aucune qualification opérationnelle n’en est déduite.                                                                          |

## Fonctionnalités implémentées

### Interface et navigation

Navigation anglaise FINLEAK, fond clair, bleu nuit/électrique/turquoise, icônes SVG locales, tableaux lisibles et styles responsive à 640/900/1150 px. La navigation source/governance conserve Documents, Leakage cases, Recovery ledger et Settings. Les anciennes interfaces détaillées demeurent accessibles.

Les changements de disposition, les tables à défilement horizontal, les libellés accessibles, les focus et `prefers-reduced-motion` sont implémentés. La capture et le parcours navigateur ont été vérifiés sur la surface desktop disponible. **Une vérification visuelle sur viewport mobile natif reste à faire.** Aucune dépendance UI ni police distante n’a été ajoutée.

### Dashboard exécutif

- Totaux potentiels **renvoyés par le backend**, séparés par devise ; aucune conversion, compensation de sous-facturations ou somme monétaire navigateur.
- Répartition par familles de règles, avec parts graphiques calculées par entiers BigInt ; les montants affichés restent les chaînes Decimal originales.
- Nombre de findings selon la couverture du résumé ; files de revue et confirmations explicitement limitées aux évaluations chargées.
- Documents traités parmi les documents chargés ; compteurs de factures et contrats distincts.
- Activité par dates réellement reçues, sans tendance inventée lorsqu’il manque deux journées d’historique.
- Distinction explicite entre potentiel, confirmation et récupération : le montant récupéré est **Not reported here**, jamais assimilé au potentiel ou à zéro.

### Factures, contrats et anomalies

- Routes `/invoices`, `/contracts`, `/anomalies`, `/review` protégées par la session existante.
- Recherche locale, filtres de statut, tri et pagination par fenêtres de 100 enregistrements, avec indication de leur portée.
- Lien document → source financière → évaluation ; accès aux documents et champs extraits existants depuis la preuve.
- Un document sans relation chargée est indiqué **No assessment linked**, jamais considéré comme conforme.
- Montants inconnus : **Not assessed**. Les montants historiques sont signalés ; les évaluations périmées bloquent la décision dans l’interface.
- Import : lien vers l’interface de téléversement existante ; aucun faux import, extraction ou traitement supplémentaire.

### Preuve et revue humaine

- Détail des montants attendus/facturés/potentiels, explication, formule et alternatives de calcul enregistrées ; aucun nouveau moteur de calcul.
- Citations, document de référence, localisation, valeur brute, candidat normalisé, empreintes, états de revue et données d’incertitude consultables.
- Les citations manuelles sont signalées comme non vérifiées par une machine.
- Lecture du dernier package de preuve existant, de sa complétude à l’émission, de ses overlays et de ses limitations. Aucun package n’est émis automatiquement.
- Historique attribué des entrées figées et des événements de preuve ; identifiants et versions du comportement consultables. La décision financière et la revue d’un package restent deux actes distincts.
- Seuls owner/admin disposent du formulaire final de décision financière ; analyst/viewer restent en lecture. L’autorisation serveur existante demeure l’autorité.
- `confirmed`, `needs_review`, `false_positive` : seules décisions déjà permises par le backend. Motif obligatoire, acquittement explicite et `expected_decision` réel transmis.
- Un conflit 409 invite à rafraîchir ; aucune réussite ni montant récupéré n’est fabriqué. Les calculs historiques restent immuables.
- État sans organisation, loading, empty, erreur de service, preuve absente et erreurs de pagination couverts.

## Raccordement aux API existantes

Tous les appels navigateur passent par `/api/organizations/{org}/…`. Aucun bearer token n’est introduit côté client ; les appels utilisent les cookies same-origin, sans cache. Les contrôles de session, origine des POST, UUID et chemins autorisés restent dans les BFF existants.

| Besoin           | Endpoint FastAPI existant sous `/api/v1/organizations/{org}`                       | Usage                                                |
| ---------------- | ---------------------------------------------------------------------------------- | ---------------------------------------------------- |
| Totaux           | `GET /financial/summary`                                                           | Affichage des valeurs serveur, couverture explicite. |
| Documents        | `GET /documents?limit=100&offset=…`                                                | Liste, pagination ; filtrage local explicite.        |
| Relations        | `GET /financial/sources?limit=100&offset=0`                                        | Fenêtre initiale de relations, limite annoncée.      |
| Anomalies        | `GET /financial/evaluations?limit=100&offset=…`                                    | Registre et revue ; aucun filtre serveur inventé.    |
| Preuve source    | `GET /financial/evaluations/{id}`                                                  | Snapshot, calcul, provenance et prédécesseur.        |
| Packages         | `GET /proof/evaluations/{id}/packages?limit=100&offset=0`                          | Recherche du dernier package existant.               |
| Package et audit | `GET /proof/packages/{id}` ; `GET /proof/packages/{id}/history?limit=100&offset=0` | Lecture, sans émission.                              |
| Décision         | `POST /financial/evaluations/{id}/decision`                                        | Corps exact `{status, reason, expected_decision}`.   |

Les requêtes sont annulées au changement d’organisation et les réponses tardives ignorées. Un tenant est sélectionné uniquement parmi les appartenances fournies par `/me`. Les erreurs d’un service ne basculent jamais vers des données synthétiques.

## Validation réellement exécutée

| Contrôle de développement                           | Résultat                      | Limite                                                                                                          |
| --------------------------------------------------- | ----------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Frontend initial                                    | PASS — 120 tests              | Suites d’origine avant modification.                                                                            |
| Frontend final                                      | PASS — 145 tests, 18 fichiers | 120 tests préservés + 25 nouveaux ; fixtures contrôlées aux frontières API et rendu jsdom.                      |
| Backend ciblé                                       | PASS — 157 tests              | `test_money`, `test_financial_engine`, `test_proof_canonical`, `test_proof_assembly` ; aucune base ni scanner.  |
| TypeScript                                          | PASS                          | `next typegen && tsc --noEmit`.                                                                                 |
| Build                                               | PASS                          | Bundle Next.js optimisé ; ne constitue ni déploiement ni image OCI.                                             |
| ESLint / format / diff                              | PASS                          | Journaux livrés ; uniquement fichiers ajoutés/modifiés formatés.                                                |
| Parcours navigateur Cloud                           | PASS — synthétique uniquement | Overview → Invoices → Anomalies → preuve → décision locale → historique → Human review.                         |
| Frontière d’authentification                        | PASS — observation navigateur | Accès sans session à `/dashboard` redirigé vers `/login`, qui indique que le fournisseur n’est pas configuré.   |
| Sources historiques                                 | PASS                          | 319 empreintes d’origine comparées ; backend, tests et docs historiques inchangés.                              |
| OIDC + PostgreSQL + stockage réels                  | NOT VERIFIED                  | Pas de fournisseur d’identité ou base de développement configurés pour une session complète.                    |
| Autorisations multi-tenant en environnement déployé | NOT VERIFIED ici              | Mécanismes préservés ; tests frontend/BFF existants et nouveaux conservés, pas de preuve d’exploitation réelle. |
| Phase 7 / sécurité opérationnelle                   | NOT QUALIFIED                 | Ces tests de développement n’ont pas cette portée.                                                              |

Les nouveaux tests vérifient notamment la conservation des chaînes à six décimales et des très grands montants, les devises séparées, les montants inconnus, les permissions owner/admin/analyst/viewer, les conflits 409, l’absence d’organisation, l’annulation et l’isolation des réponses entre tenants, les liens facture/source, la pagination, les erreurs et la séparation totale du mode synthétique.

Les journaux finaux sont dans le checkpoint. Deux erreurs de développement ont été corrigées avant livraison : un sélecteur de test dépendait de l’ordre des factures, puis une attente de pagination supposait à tort que le total fictif restait inchangé. Elles ne sont pas présentées comme des PASS intermédiaires.

## Environnement et aperçu

Runtime Work Cloud Linux : Node 24.19.0, Python 3.12.14. Identité effective **0:0** dans cet espace ; aucune élévation ni changement d’identité n’a été utilisé. Cette identité n’est **pas** une preuve de conformité UID/GID1000, et le runtime n’a pas été qualifié.

L’aperçu a été servi uniquement par le superviseur Cloud. Son protocole ajoute des arguments génériques non compris par Next ; `frontend/scripts/dev.mjs` les traduit. Pour les arguments supervisés `--strictPort`, il exige un build préalable et utilise `next start`. Le serveur de développement Next appelait une métrique mémoire `/proc` indisponible et ne terminait pas correctement certaines réponses dans ce conteneur ; le bundle compilé a permis le parcours navigateur sans patcher Next ni modifier les protections système. Un simple `npm run dev` conserve le comportement Next dev sur loopback. Aucun contournement d’identité, de permissions ou d’authentification n’a été ajouté.

Le navigateur Cloud n’offre ici qu’un aperçu interne de QA, sans URL interactive partageable pérenne. Le superviseur est arrêté après les captures. Aucune ressource Cloud payante, publication Sites, image OCI, GitHub Actions ou ressource de production n’a été créée.

Pour reproduire **ultérieurement dans un Cloud de développement autorisé**, utiliser les versions et fichiers de verrouillage existants : `npm ci --ignore-scripts --no-audit --no-fund`, `npm test`, `npm run typecheck`, `npm run build` dans `frontend`. Les variables OIDC/backend doivent être gérées selon les documents d’architecture existants, hors conversation. Ce guide ne vaut ni autorisation d’exécution hôte ni qualification.

## Limites et écarts ouverts

1. Le résumé backend est borné à ses 1 000 dernières évaluations ; les compteurs de file et de documents concernent les pages chargées, sans garantie d’exhaustivité globale.
2. La résolution des sources utilise les 100 premières sources financières. Les sources et documents hors fenêtre restent explicitement non reliés ; ce n’est pas une validation de conformité.
3. Le détail charge le dernier package et 100 événements ; les autres outils de preuve existants restent nécessaires pour les packages antérieurs et les opérations complètes.
4. L’endpoint d’évaluation expose statut et ID de décision, mais pas l’auteur/motif de cette décision. L’historique montre ce qui est effectivement retourné par les snapshots et événements de preuve. L’endpoint `/financial/audit` existant n’est pas transformé en historique de décisions sans contrat démontré.
5. La préparation et l’approbation des faits financiers restent dans l’espace existant Leakage cases ; aucun écran simplifié de saisie de contrat n’a été inventé.
6. Aucun montant récupéré nouveau, aucune promesse d’économie, aucune fonctionnalité Recovery Ledger supplémentaire.
7. Le workflow d’import/extraction/scanner/stockage réel n’a pas été exécuté. Le lien Import documents utilise l’interface existante.
8. Aucun test R1 de qualification, scanner réel, collecteur, PostgreSQL/PITR ou procédure Phase 7 n’a été exécuté. Les incompatibilités historiques R1 restent ouvertes.

Restrictions maintenues : Phase 7 **NOT QUALIFIED** ; PostgreSQL/PITR **NOT QUALIFIED** ; ClamAV/WSL **NOT QUALIFIED** ; scanner **BLOCKED** ; pilote **NO-GO** ; PC et production **NOT AUTHORIZED**. Python 3.14.4 et UID/GID1000 effectifs restent **NOT VERIFIED** dans le périmètre de qualification antérieur.

## Prochaine action unique

**Vérifier cette tranche avec une session OIDC et un jeu de documents synthétiques sur un backend de développement Cloud isolé déjà autorisé, afin de couvrir le parcours authentifié complet jusqu’à la décision financière persistée, sans scanner ni production.**

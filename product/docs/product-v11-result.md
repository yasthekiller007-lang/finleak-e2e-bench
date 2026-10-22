# FINLEAK Product V1.1 — résultat de développement

**Verdict : PARTIAL.** Un incrément fonctionnel de fiabilité et une acceptation exécutable sont livrés. Aucune session OIDC réelle de test ni décision persistée dans PostgreSQL 17 n’a été démontrée dans cet environnement. Les captures de cette livraison concernent exclusivement les exercices synthétiques de l’application exécutée dans le navigateur Cloud.

Les captures utilisent le scénario de démonstration V1 à 9 600 USD. Le scénario d’acceptation distinct à 1 000 USD a été vérifié avec le moteur en test unitaire ; il n’a pas été exécuté avec OIDC/PostgreSQL ni présenté comme une décision persistée.

## Continuité

Le SHA-256 de Product V1 est bien `4b2e4ac3b9f1f340118d581524bacf943ccb55a50b1eb090fea2c151cca6f3b1`. Les 360 entrées de son manifeste ont été vérifiées. Le développement reprend le commit `f30c859d3c8348c3c6fe15e89b54ce0e11d7a1f2` sur `dev/product-v11-authenticated-workflow-20261019`. La branche Product V1 et `main` (`c02424c2f3d910af771dcdc05e2f5cb281de4bef`) sont préservées. Aucun push, merge, GitHub Actions, déploiement public ou changement de checkpoint historique n’a été effectué.

## Produit réellement modifié

1. **Résultat de sauvegarde explicite.** Le formulaire distingue refus de validation, session/permission refusée, conflit 409, résultat inconnu, réponse acquittée sans relecture, et décision retrouvée par une lecture séparée. Le reçu doit contenir un véritable ID au format UUID et le statut demandé. Un reçu incohérent ne produit aucun faux succès.
2. **Aucun renvoi automatique du POST.** Après perte de réponse, timeout, 5xx ou conflit, le formulaire est verrouillé. « Reload current decision » effectue seulement un GET. Une nouvelle décision exige une nouvelle intention explicite, un motif et un acquittement. Après succès, une pression accidentelle supplémentaire ne soumet rien.
3. **Concurrence conservée.** Le prédécesseur `expected_decision` reste celui de la lecture courante. Une réponse portant un autre ID ne permet pas d’attribuer la décision au dernier clic de l’utilisateur. Les contrôles backend restent l’autorité.
4. **Journal financier consultable.** Le détail joint le véritable `decision_id` courant à `GET /financial/audit?limit=100&offset=0`, endpoint déjà existant. La migration historique montre que l’audit de décision cible l’ID de décision et conserve acteur, motif, numéro et rôle. L’interface vérifie cible/table/action avant affichage. Une absence dans la fenêtre n’est jamais présentée comme une absence d’historique PostgreSQL.
5. **Exercices isolés.** Le mode `/demo` permet de vérifier une réponse perdue après un enregistrement local, une lecture indisponible après acquittement, un conflit 409 et une évaluation périmée. Il indique explicitement qu’il n’utilise ni PostgreSQL, ni fournisseur d’identité, ni API métier. Son journal est de la mémoire navigateur, sans garantie de persistance.
6. **Build reproductible dans cet espace.** Le cache de compilation Turbopack a échoué avec « invalid digit found in string » après reconstruction. Le script `build` utilise désormais le compilateur Webpack fourni par Next.js. Les essais en échec sont conservés dans les preuves ; aucun module Next, contrôle système ou mécanisme de sécurité n’a été patché. Aucun paquet n’a été ajouté.

7. **Contrat de props de la page Login.** La compilation Webpack a révélé une incompatibilité TypeScript de la signature optionnelle historique. Des surcharges conservent les appels directs sans argument des tests existants et exposent à Next un objet de props concret. La logique de connexion et les contrôles OIDC restent inchangés ; aucun contrôle de typage n’est désactivé.

Les montants demeurent des chaînes Decimal issues du backend. Les règles financières, modèles, migrations, autorisations, OIDC/JWKS, BFF et Recovery Ledger existants ne sont pas modifiés. Les tests historiques sont conservés octet pour octet.

## Capacités réellement disponibles

Work Cloud distant Linux, indépendant du PC : Python 3.12.14 et Node 24.19.0 disponibles. Identité effective du runtime : UID/GID 0:0, sans élévation ni simulation ; aucune qualification UID1000 n’en est déduite. Aucun binaire PostgreSQL/psql/initdb/pg_ctl, Docker ou Podman n’est disponible. Aucun URL/secret de base, backend ou fournisseur OIDC de développement n’a été fourni. Aucun service, compte, base ou ressource payante n’a été créé pour contourner cette absence.

## Validation effectuée

| Contrôle                                            | Résultat                       | Portée réelle                                                                                                                                                  |
| --------------------------------------------------- | ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Frontend                                            | PASS — 160 tests / 19 fichiers | 145 tests préservés + 15 tests de fiabilité nouveaux ; frontières contrôlées et jsdom.                                                                         |
| Backend ciblé                                       | PASS — 185 tests               | Montants Decimal, moteur approuvé, preuves canoniques/assemblage, transport OIDC unitaire et 7 nouveaux contrôles produit. Aucun PostgreSQL actif.             |
| Scénario 100 × 50 / 100 × 60                        | PASS unitaire                  | Le moteur existant retourne 5 000 / 6 000 / 1 000 USD ; les CSV synthétiques contiennent les conditions typées exactes. Ce n’est pas une évaluation persistée. |
| Accès API sans session                              | PASS de développement          | Le véritable routeur FastAPI refuse lecture et décision avec HTTP 401 sans base ni identité injectées.                                                         |
| TypeScript / build Webpack / ESLint / Ruff          | PASS                           | Journaux livrés.                                                                                                                                               |
| Navigateur Cloud                                    | PASS synthétique               | Verrouillage après perte de réponse, relecture sans nouvelle écriture, journal local explicite, conflit 409.                                                   |
| Découverte Playwright                               | DISCOVERY ONLY                 | Une acceptation enregistrée, **zéro test E2E exécuté**. Le reporter distingue expressément cette opération d’un test réussi.                                   |
| Préflight E2E                                       | BLOCKED                        | Configuration et services OIDC/PostgreSQL absents ; sortie 2 attendue, sans connexion ni fixture injectée.                                                     |
| Session OIDC / JWT réel émis par un fournisseur     | NOT EXECUTED                   | Les tests unitaires de transport ne remplacent pas une connexion réelle.                                                                                       |
| Décision PostgreSQL / relecture / redémarrage       | NOT EXECUTED                   | Aucun journal de décision persistée n’est fabriqué.                                                                                                            |
| Expiration réelle de jeton, panne réelle PostgreSQL | NOT VERIFIED                   | Les erreurs frontend simulées ne prouvent pas une panne de base ni une validation de jeton expiré par un fournisseur réel.                                     |

Les nouveaux tests couvrent acquittement suivi de lecture indisponible, perte de réponse après enregistrement local, rejet concurrent, double clic, nouveau prédécesseur inattendu, réponse malformée, refus 401/403, relecture sans POST et isolation des réponses d’audit entre organisations. Les événements synthétiques sont séparés des preuves réelles dans l’archive.

## Acceptation préparée, non exécutée

`docs/product-v11-acceptance.md` fournit le protocole Cloud et les commandes. `backend/acceptance/product_v11.py` refuse par défaut toute action ; il exige une base PostgreSQL 17 dédiée, déjà disponible et migrée, un rôle non privilégié et deux identités de test exclusivement synthétiques. Il ne crée aucun service et ne lance aucune migration.

La fixture prépare uniquement les organisations, utilisateurs et documents synthétiques. Elle n’insère aucune révision financière, évaluation ou décision finale. Les citations reprennent les octets des CSV contenant unités, dates, parties, fiscalité, arrondi et références exacts. L’acceptation Playwright préparée utilise ensuite le vrai flux OIDC/PKCE/cookies, les API existantes, l’analyste pour préparer et le propriétaire pour approuver, puis le formulaire financier pour décider. Un interpréteur séparé vérifie en lecture seule une session PostgreSQL fraîche, un seul enregistrement et son audit. La révocation d’une approbation, avec ses valeurs historiques conservées, exerce ensuite le refus d’une évaluation périmée.

La suite n’installe pas de navigateur, ne lance aucun service et n’utilise aucun faux vérificateur de token. Aucun mot de passe, token, cookie, code OAuth, clé privée ou URL de connexion authentifiée n’est exporté dans les preuves. Les paramètres sensibles restent hors fichiers suivis. La validation du fournisseur réellement disponible et de ses libellés de connexion reste à effectuer lors de l’exécution ; la découverte et le typage ne prouvent pas sa compatibilité.

L’import/scanner est hors scénario : documents de test explicites, état `needs_review`, aucune fausse analyse CLEAN, aucun release ni extraction simulée. La disponibilité opérationnelle des originaux et l’émission/revue d’un package de preuve ne sont pas déduites de la revue financière.

## Limites conservées

Le journal affiché concerne l’entrée de décision courante présente dans les 100 derniers audits de l’organisation. Un historique exhaustif de toutes les décisions n’est pas inventé. Les limites de pagination/relations de V1 demeurent. La session authentifiée complète, les refus multi-tenant avec un vrai issuer, la persistance réelle après redémarrage, les jetons expirés/invalides réels et une panne PostgreSQL contrôlée restent à vérifier sur les dépendances appropriées.

Phase 7 : **NOT QUALIFIED**. PostgreSQL/PITR opérationnel : **NOT QUALIFIED**. ClamAV/WSL : **NOT QUALIFIED**. Scanner : **BLOCKED**. Pilote : **NO-GO**. PC, production, GitHub Actions et Cloud payant : **NOT AUTHORIZED**.

## Prochaine action unique

**Exécuter l’acceptation V1.1 livrée sur un environnement Cloud de développement déjà autorisé, muni de PostgreSQL 17 et d’un realm OIDC de test, pour obtenir le premier journal de décision réellement persistée.**

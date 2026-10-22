# FINLEAK Product V1.3 — Financial Exceptions Workbench

**Décision : PASS DEVELOPMENT.** La tranche file d’exceptions → investigation → revue humaine est développée et vérifiée avec des tests unitaires, de composants et de contrats à frontières simulées explicitement. Le reporting CFO est complété. **La validation authentifiée OIDC/PostgreSQL reste séparément BLOCKED.** Aucune persistance réelle nouvelle n’est revendiquée.

## Reprise préservée

Base Product V1.1 : `fa9181805d0d35a31dfabd85df84823995cca566`. Archive de référence SHA-256 `62447a0686ef42c0843420e8623f6977f48ebc1f6ef1a99d8c7938abd6515e4e`, CRC ZIP et 380 entrées du manifeste vérifiés. Branche locale V1.3 : `dev/product-v13-exceptions-workbench-20261019`. `main` reste `c02424c2f3d910af771dcdc05e2f5cb281de4bef`. Aucun push ni déclenchement GitHub Actions.

Les composants V1.1 de décision et d’audit sont réutilisés sans modification. Les sources/tests historiques, les checkpoints, leurs preuves et les décisions approuvées sont préservés. Aucun nouvel examen PostgreSQL, UID ou R1 n’a été lancé. Aucune dépendance n’a été ajoutée.

## Fonctionnalités réellement développées

### File d’exceptions

- Recherche dans les références renvoyées : facture, libellé de périmètre, ID, explication, fournisseur, nom de contrat chargé et références contractuelles.
- Filtres combinables : état de revue existant, devise, fournisseur et contrat explicitement associé. Les références absentes peuvent être sélectionnées sans être interprétées comme une absence de contrat.
- Tri par date, état et montant potentiel. Le tri monétaire compare exactement les chaînes Decimal via BigInt, sans conversion en nombre flottant. Avec plusieurs devises, les groupes sont alphabétiques par devise et le tri de montant s’applique à l’intérieur de chaque groupe. Une devise inconnue n’est pas classée par montant.
- Pagination locale de 10 résultats, avec retour à la première page lorsque les critères changent. Chargement incrémental des fenêtres serveur existantes, distinct de la pagination locale.
- Chargement supplémentaire des sources financières et documents de référence, sur action explicite. Les pages qui se chevauchent sont fusionnées par ID sans doubler les lignes. La fin de pagination utilise les métadonnées serveur, pas le nombre de lignes correspondant au filtre.
- Navigation vers les preuves et lien direct du dossier portant l’organisation autorisée et l’ID d’évaluation. États de chargement, erreur, absence de résultat et couverture chargée explicites.

### Investigation et revue humaine

Le dossier conserve les montants attendus, facturés et potentiels enregistrés. Une nouvelle comparaison côte à côte présente le fournisseur, le contrat associé, ses références, le code explicatif, le périmètre, le nombre de documents cités et l’ID de décision courant. Les raisons des revues et leurs résolutions d’incertitude sont lisibles sans analyser le JSON complet. Les citations, valeurs source, champs, empreintes, règles et détails canoniques restent disponibles dans les composants existants.

Le formulaire V1.1 continue d’exiger motif et acquittement, de réserver l’écriture aux rôles autorisés, de bloquer les évaluations périmées et d’empêcher les doubles soumissions. Il conserve le prédécesseur réel, verrouille le formulaire après conflit ou réponse perdue et ne réessaie jamais automatiquement un POST. Le succès exige un reçu cohérent puis une relecture concordante. L’historique courant joint le véritable ID de décision à l’audit déjà disponible ; il ne fabrique ni acteur ni motif. La revue d’un package de preuve reste séparée de la décision financière.

Le lien vers les outils existants de revue des faits/proof demande de sélectionner l’organisation correspondante dans cet espace historique ; aucun paramètre d’organisation ignoré n’est présenté comme une sélection effectuée.

### Reporting CFO

La section « Exception portfolio » montre la répartition des états d’évaluation chargés et la couverture par devise. Les montants potentiels sont ceux du résumé backend existant, jamais une somme recalculée des lignes ni un total multidevise. Les nombres de dossiers chargés, confirmés et en attente restent explicitement des nombres d’évaluations dans la fenêtre chargée, et non un décompte exhaustif de factures uniques. Les limites du résumé, notamment son éventuelle limite de 1 000 évaluations, sont affichées. Le graphique temporel existant demeure fondé sur les dates disponibles, sans tendance inventée.

Aucun montant récupéré n’est déduit. Aucun Recovery Ledger, score de risque, nouveau statut métier ou mécanisme de décision automatique n’a été introduit.

## Contrats API et adaptation backend limitée

Les lectures utilisent les routes BFF existantes sous `/api/organizations/{org}` :

| Usage              | Endpoint existant                                             | Portée                                                           |
| ------------------ | ------------------------------------------------------------- | ---------------------------------------------------------------- |
| Résumé CFO         | `GET financial/summary`                                       | Montants et couverture autoritatifs du backend                   |
| File et dossier    | `GET financial/evaluations`, `GET financial/evaluations/{id}` | Organisation autorisée, fenêtres limit/offset existantes         |
| Références         | `GET financial/sources`, `GET documents`                      | Pagination existante, aucun appel non borné automatique          |
| Preuves            | Routes `GET proof/...` existantes                             | Lecture seule, aucune émission automatique                       |
| Historique courant | `GET financial/audit`                                         | Corrélation de la décision courante dans les 100 derniers audits |
| Décision           | `POST financial/evaluations/{id}/decision`                    | Contrat et permissions V1.1 inchangés                            |

Pour rendre les filtres fournisseur/contrat utilisables avec la réponse de liste, le sérialiseur backend ajoute uniquement `queue_context` aux évaluations : `supplier_party`, `contract_source_id`, `contract_references`. `app/financial/presentation.py` lit le snapshot figé déjà stocké. Il ne fait aucune requête, ne change aucun calcul et ne résout aucun nouveau rapprochement. Le contrat n’est exposé que si une association approuvée du snapshot appartient à la source facture concernée et fournit un ID unique valide. Une association ambiguë, préparée, révoquée ou d’une autre source n’est pas inventée.

L’absence de ce champ sur un ancien backend reste prise en charge : les colonnes indiquent les références non retournées. Les noms de documents sont résolus uniquement parmi les sources/documents effectivement chargés, avec l’ID en repli. La donnée figée n’est pas présentée comme une preuve de validité courante.

L’adaptation n’ajoute ni endpoint, migration, permission, écriture, règle financière ou dépendance. Les contrôles d’accès, requêtes multi-tenant et validations existantes sont inchangés.

## Vérifications exécutées

| Contrôle                                        | Résultat réel                                                                                                                                     |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Frontend complet disponible                     | **180 tests PASS / 20 fichiers**, dont 20 nouveaux tests V1.3 ; les 160 tests V1.1 sont conservés                                                 |
| Backend ciblé disponible                        | **193 tests PASS**, dont 8 nouveaux contrôles de contexte/serialization ; aucune base active                                                      |
| TypeScript                                      | PASS                                                                                                                                              |
| Build Next.js 16.3.8 avec Webpack               | PASS                                                                                                                                              |
| ESLint et Ruff ciblé                            | PASS                                                                                                                                              |
| Format des fichiers modifiés/ajoutés et diff    | PASS                                                                                                                                              |
| Navigateur Cloud, application compilée          | File filtrée/triée, état vide, remise à zéro, dossier, comparaison, décision locale verrouillée, relecture du journal et ventilation CFO observés |
| Authentification OIDC et persistance PostgreSQL | **BLOCKED historique**, non réinvestigué et non exécuté                                                                                           |

Les nouveaux tests vérifient notamment la précision au-delà de 2^53, les fractions, les devises séparées, les montants inconnus, les références absentes/ambiguës, les filtres combinés, les pages en chevauchement, la reprise après erreur de page, l’abandon d’une réponse tardive après changement d’organisation et l’absence de requête réseau dans la démonstration. Le sérialiseur réel est exercé avec des frontières de session explicitement remplacées en mémoire ; cela ne constitue pas une intégration SQL.

Un défaut de typage dans le nouveau mock de pagination a été corrigé (`Promise<unknown>` remplacée par le type de page attendu). Le build et le typage finaux réussissent sans désactiver de contrôle. Aucun test historique n’a été modifié pour obtenir ces résultats.

Les captures sont les octets JPEG authentiques du navigateur Cloud, exclusivement dans `/demo`. Le scénario synthétique affiche notamment 9 600 USD potentiels et des exemples distincts en EUR. Les décisions de démonstration restent locales et se réinitialisent en quittant la page ; elles ne sont pas des enregistrements PostgreSQL. L’aperçu interne a été arrêté après QA. Aucun déploiement public n’a été créé.

## Limites et fonctionnalités manquantes

- Les filtres/tris portent sur les fenêtres chargées. Il faut demander explicitement les pages supplémentaires pour élargir la recherche ; aucun filtre global côté serveur n’est inventé.
- Le résumé backend et les comptes de la fenêtre peuvent avoir des couvertures différentes, affichées comme telles. Les évaluations historiques peuvent représenter plusieurs versions d’un même périmètre ; aucun montant de lignes n’est additionné pour masquer ce problème.
- Certains snapshots n’ont pas d’association approuvée ni de références fournisseur/contrat. L’interface les conserve comme inconnues.
- Le journal financier affiché concerne la décision courante retrouvée dans une fenêtre de 100 audits, pas un historique exhaustif de toutes ses décisions.
- Le viewport mobile natif n’a pas été observé. La mise en page comporte des adaptations responsive, sans revendication de test mobile réel.
- La nouvelle réponse backend n’a pas été relue sur un service authentifié actif. Les tests de contrats et frontières simulées ne remplacent pas cette validation.
- Aucun import/scanner, OIDC réel, PostgreSQL réel, reprise après redémarrage ou PITR n’a été exécuté. Le blocage V1.2 reste inchangé.

Phase 7, PostgreSQL/PITR et ClamAV/WSL : **NOT QUALIFIED**. Scanner : **BLOCKED**. Pilote : **NO-GO**. PC et production : **NOT AUTHORIZED**. Aucun service payant, GitHub Actions ou changement de `main`.

## Recommandation produit unique pour V1.4

**Étendre les endpoints de lecture existants avec des filtres et un tri côté serveur, ainsi qu’une pagination stable, pour rendre la file d’exceptions exploitable au-delà de la fenêtre chargée sans modifier les règles de décision.**

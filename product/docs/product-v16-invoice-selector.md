# FINLEAK Product V1.6 — Server-side invoice business selector

2026-10-19 — **PASS DEVELOPMENT**, dans le périmètre du code et des tests de développement. Aucune validation PostgreSQL native ou E2E authentifiée n’est revendiquée.

## Continuité

Base V1.5 : `139ed29f4594afdbe797fd066c81a9cb62e41bdf`, branche `dev/product-v15-business-facets-20261019`. Archive vérifiée : `0c43ef446a0ec03666b46dc35738f193aa95317fdf3a69b629936d4002009674`, CRC valide et 403 entrées du manifeste recalculées. Le checkout propre correspondait déjà à cette base : aucune réinitialisation.

Nouvelle branche : `dev/product-v16-invoice-selector-20261019`. Main, anciennes branches, checkpoints et tests historiques préservés. Aucun push, GitHub Actions, privilège supplémentaire, service payant, scanner, déploiement public, production ou exécution PC. Aucune nouvelle investigation PostgreSQL/OIDC/UID/Docker/R1. Aucun modèle, dépendance, migration ou règle financière modifié.

## Données disponibles et limites de référence

`ReviewedFinancialSource` relie l’organisation, le document et le type invoice à une identité financière revue. `FinancialEvaluation.invoice_source_id` référence cette source. Un document, une source et une évaluation sont trois objets distincts ; sélectionner la source ne modifie aucune évaluation.

Inspection du schéma approuvé : `Reference` contient seulement `contract_reference` et `po_reference`. `BillingScope` fournit notamment supplier_party et invoice_date, mais aucun invoice_number. Le modèle historique `Invoice` d’un autre sous-système possède invoice_number ; son rattachement et sa provenance vers un snapshot revu ne sont pas établis. V1.6 **ne le joint pas et ne l’utilise pas**.

Conséquence : `reference` et `invoice_reference` restent null, avec `reference_basis=not_available_in_reviewed_schema`. La recherche de facture porte sur le véritable `Document.original_filename`, y compris une partie de référence présente dans ce nom, sans extraire ou certifier un numéro. Une chaîne de contrat, de PO ou une clé JSON supplémentaire non approuvée n’est jamais promue en numéro de facture.

Le fournisseur et la date éventuelle de facture proviennent du billing_scope figé de l’évaluation correspondante la plus récente. Ils décrivent ce contexte, sans prétendre uniformiser toutes les lignes ou identifier une entité juridique. `context_evaluation_id` et `context_basis` l’explicitent. Une date valide strictement ISO est marquée reviewed_invoice_date ; sinon la date de création réelle de la source revue est marquée reviewed_source_created_at. Ni date d’évaluation ni date de création de source ne sont présentées comme date d’émission.

## API invoice — extension compatible

Route inchangée : `GET /api/v1/organizations/{organization_id}/financial/exception-facets?facet=invoice`.

Le BFF authentifié existant relaie la route et ses critères, avec token côté serveur et organisation du chemin. Même `AuthorizedOrganization`, sessions SQL et lectures seules. Aucun nouvel endpoint d’écriture ni décision. La route statique ne collisionne pas avec `/evaluations/{evaluation_id}`.

| Paramètre                             | Sémantique                                                                                                             |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| facet                                 | supplier, contract ou nouveau invoice ; les deux types V1.5 sont conservés                                             |
| search                                | 0–120 caractères, espaces externes retirés, contrôles refusés, sous-chaîne ILIKE littérale échappant %, _ et backslash |
| limit                                 | 1–50, défaut 20, look-ahead d’une ligne, aucun count d’évaluations par choix                                           |
| after                                 | Curseur HMAC signé, 2048 caractères au maximum, même expiration initiale de 15 minutes                                 |
| invoice_source_id                     | Ignoré seulement pour découvrir les choix invoice                                                                      |
| invoice_document_id                   | Conservé, y compris pour invoice : la liste reste restreinte au document demandé                                       |
| supplier, contract_source_id          | Conservés sur invoice, avec l’égalité et l’association approuvée unique V1.5                                           |
| q, outcome, decision_status, currency | Critères V1.4/V1.5 conservés avant choix                                                                               |
| missing_contract                      | Sens V1.4 conservé, pas une association automatique                                                                    |
| created_from, created_to              | Période des évaluations avec timezone, début inclusif, fin exclusive                                                   |
| current, needs_review                 | Sérialiseur métier inchangé, limite de 100 candidats après retrait du seul filtre propre                               |
| sort                                  | Accepté pour compatibilité ; les choix restent en ordre stable de source                                               |

Les validations V1.5 restent appliquées : paramètres inconnus/répétés refusés, limites et erreurs explicites. Les évaluations et leurs filtres historiques restent inchangés. Contraintes source/document incompatibles : zéro évaluation ; la facette invoice ignore source uniquement et propose donc les sources admissibles du document demandé, sans supprimer discrètement la contrainte document.

Réponse de choix invoice (exemple synthétique de contrat, pas une lecture PostgreSQL réalisée) :

```json
{
  "value": "00000000-0000-0000-0000-000000000001",
  "label": "Vendor_document.pdf",
  "filename": "Vendor_document.pdf",
  "reference": null,
  "invoice_reference": null,
  "reference_basis": "not_available_in_reviewed_schema",
  "document_id": "00000000-0000-0000-0000-000000000101",
  "source_created_at": "2026-10-19T00:00:00+00:00",
  "date": "2026-10-01",
  "date_type": "reviewed_invoice_date",
  "supplier_party": "SYNTHETIC supplier",
  "context_evaluation_id": "00000000-0000-0000-0000-000000000201",
  "context_basis": "latest_matching_evaluation_billing_scope",
  "description": "Recorded supplier: SYNTHETIC supplier · source created 2026-10-19T00:00:00+00:00 · choice 1"
}
```

Enveloppe conservée : facet, items, limit, has_more, next_cursor, order=stable_source_id, ignored_filter=invoice_source_id, coverage et consistency. Pas de count par facture, de score ou montant ajouté.

## Identité, ordre et SQL

L’extension reste dans `exceptions_facets.py`, réutilise `filtered_query`, les bornes et les curseurs V1.5. `DISTINCT ON (FinancialEvaluation.invoice_source_id)` choisit un seul contexte par source parmi les évaluations filtrées, par created_at décroissant puis UUID d’évaluation. Les autres évaluations ne sont ni modifiées ni supprimées, et la file continue à les paginer normalement.

Jointures exactes : source.id = contexte.invoice_source_id, source.organization_id = organisation autorisée, source.kind = invoice ; document.id = source.document_id et document.organization_id = organisation autorisée. Aucun rapprochement par filename ou supplier. Deux sources distinctes de même nom restent deux choix distincts. Le libellé contient le fournisseur enregistré, la date de création de source et un numéro de choix déterministe pour désambiguïser même nom/date. Ce numéro de choix n’est pas un numéro de facture et peut changer lorsque l’ensemble admissible change.

Ordre par UUID source normalisé en hexadécimal, comparaison COLLATE C et ancre stricte >. La valeur API renvoyée est l’UUID canonique de la source ; les identifiants restent internes dans l’interface live. Recherche filename paramétrée et échappée, limite SQL limit+1 <=51. Aucun tri complet en JavaScript live et aucune liste intégrale de factures téléchargée.

Pour current/needs_review, le chemin V1.5 lit au maximum 101 candidats. Au-delà de 100 : refus 422 DYNAMIC_FILTER_LIMIT avant sérialisation. Sinon le sérialiseur métier existant produit la liste des UUID admissibles avant DISTINCT et pagination. Pas de simulation de currentness. Ce jeu élargi peut dépasser 100 alors que la file sélectionnée est petite ; il faut alors affiner les autres critères.

Curseur lié à organisation, type invoice, critères effectifs dont document, recherche et taille. Type/organisation/recherche/document incompatibles ou curseur altéré/expiré : 422 avant lecture des choix. Génération financière changée : 409 FACETS_CHANGED, reprendre les choix. Verrou SHARE et compteurs financiers V1.5 inchangés ; garanties transactionnelles natives non vérifiées. Une sélection ne confère aucun droit.

## Interface

`BusinessFacetSelect` partagé prend maintenant invoice en charge. Recherche asynchrone et debounce 250 ms, flèches/Home/End/Enter/Escape/Tab, choix sélectionné et effaçable, pagination des choix, chargement/empty/error et retry/restart. Les requêtes obsolètes sont annulées ; une réponse tardive est ignorée après changement de critère ou d’organisation.

Le texte recherché ne devient pas un filtre avant sélection. Les descriptions et types de date sont lisibles ; aucun UUID ne doit être saisi. Les liens existants qui transmettent une source sélectionnée restent supportés : le filename est résolu depuis la page renvoyée, ou l’interface signale « Invoice selected from navigation » lorsque les détails ne sont pas disponibles, sans inventer de référence.

Sélection/effacement de source remet la file au début et conserve fournisseur, contrat, devise, statut et contrainte documentaire. Changement de fournisseur conserve la facture choisie ; il continue à effacer le contrat conformément à V1.5. Une combinaison devenue vide reste vide, sans substitution d’association. Investigation puis retour conservent le choix et la position de file, avec les limites de cohérence des curseurs. Reset criteria reprend le contexte initial du lien lorsqu’il existait.

Les gateways historiques sans queryFacets conservent leur contrôle V1.4 pour compatibilité des consommateurs/tests gelés ; les gateways live et de démo V1.6 proposent les trois sélecteurs. Aucune erreur live ne déclenche de données synthétiques.

La démo est une fixture en mémoire explicitement séparée. Elle déduplique ses quelques enregistrements par source, respecte document sur invoice et ne fabrique pas de référence. Elle ne prouve ni SQL, ni OIDC, ni persistance. La seconde page d’une même facture est aussi vérifiée par un test de composant à réponse explicitement mockée ; ce test n’est pas présenté comme une transaction PostgreSQL.

## Performance et cohérence résiduelles

Une requête de choix réunit les métadonnées source/document : pas de N+1 ajouté par choix. Les lectures currentness existantes restent multiples mais bornées aux 100 candidats. Budget coopératif de sérialisation et statement_timeout existants conservés ; pas de timeout global nouveau ni de promesse de latence.

DISTINCT ON et le tri peuvent scanner/trier un grand jeu tenant ; limit+1 borne les lignes retournées, pas le coût interne. La recherche ILIKE par sous-chaîne sur filename peut aussi être coûteuse. Index inspectés : organisation et contraintes uniques tenant des tables existantes. Pas de migration/index ajouté sans EXPLAIN natif. Mesure à prévoir sur données synthétiques autorisées : p50/p95 et EXPLAIN ANALYZE BUFFERS à 1k/10k/100k évaluations ; comparer organisation/invoice_source_id/created_at/id et une stratégie documentaire adaptée, sans promettre qu’un B-tree accélère la sous-chaîne.

Comme V1.5, le filename est une métadonnée actuelle, non une preuve figée. Les API inspectées n’exposent pas de renommage, mais un renommage externe n’est pas suivi par les compteurs financiers ; il peut modifier l’appartenance d’une recherche entre pages. Aucun snapshot inter-requêtes de ces noms n’est garanti. Ce risque reste explicite, sans modification des triggers historiques. Une future API de renommage devra invalider les curseurs correspondants.

La clé privée de curseur processus est celle de V1.5 ; multiworkers nécessitent la même clé configurée, sans l’exporter. Redémarrage ou rotation sans clé partagée invalide les curseurs. Aucun secret, token ni clé runtime dans les livrables.

## Vérifications et portée

- Frontend : **225 tests PASS**, dont 14 nouveaux V1.6 ; 25 fichiers.
- Backend ciblé : **294 tests PASS**, dont 28 nouveaux V1.6. Argent, moteur financier, preuves, transport OIDC unitaire et Product V11/V13/V14/V15/V16.
- TypeScript, build Next.js, ESLint, Ruff, Prettier et formatage Python : journaux finaux joints.
- SQL : compilation du dialecte PostgreSQL, inspection des paramètres, jointures, DISTINCT, bornes et ancres ; **aucune exécution PostgreSQL native**.
- Backend : frontières de session factices renvoyant des lignes présélectionnées, pas un émulateur SQL. Refus sans session sur la vraie route FastAPI, sans prétendre à une connexion OIDC réussie.
- Captures : vrai produit compilé dans un navigateur Cloud, fixture synthétique explicitement signalée. Aucun faux résultat d’intégration.
- Les preuves jointes vérifient la préservation des fichiers historiques, la reproduction complète du patch depuis V1.5 et la restauration de l’archive avec manifeste.

Les 20 axes demandés sont couverts par le code et ces contrôles : filename, absence de référence certifiée et refus de promotion contrat/PO/Invoice externe, homonymes, dédoublonnage par source, mauvais type, empty, ordre/pagination, curseurs, tenant, filtres combinés, source/document, réponses tardives, investigation/retour, génération financière, limite dynamique, compatibilité et absence d’écriture. Leurs garanties natives SQL restent NOT VERIFIED.

Deux erreurs des nouvelles fixtures ont été corrigées : import Python du helper de test et curseur factice envoyé à la démo au lieu d’une réponse de pagination entièrement mockée. Une option de matcher non reconnue par les types Testing Library et une ligne d’assertion trop longue ont aussi été corrigées. Les échecs initiaux sont conservés et distingués des journaux finaux. Aucun test historique modifié. La capture initiale a révélé un menu invoice coupé à droite dans la dernière colonne : alignement du popover à droite corrigé, puis contrôle visuel du build final.

## Décision et restrictions

**PASS DEVELOPMENT** : extension invoice réellement implémentée dans le moteur existant, raccordée au BFF et à l’interface, avec tests de développement applicables réussis. Absence de numéro de facture approuvé traitée par un repli documentaire explicite, sans fabriquer de champ métier.

PostgreSQL natif, concurrence, plans et performances : **NOT VERIFIED**. E2E OIDC/PostgreSQL : **BLOCKED**, non retenté. Phase 7, PostgreSQL/PITR, ClamAV/WSL : NOT QUALIFIED. Scanner : BLOCKED. Pilote : NO-GO. PC et production : NOT AUTHORIZED. Aucun calcul, audit, décision, association, permission, preuve ou Recovery Ledger changé.

**Recommandation unique V1.7 : permettre de copier et restaurer une vue de la file d’exceptions dans une URL contenant ses critères métier, avec revalidation de l’organisation et redémarrage des curseurs périmés.**

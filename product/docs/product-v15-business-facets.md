# FINLEAK Product V1.5 — Server-side business facets

Date : 2026-10-19. Décision : **PASS DEVELOPMENT**, pour l’implémentation et les tests de développement décrits ci-dessous. Cette décision n’est ni un PASS PostgreSQL natif, ni un PASS E2E authentifié.

## Continuité et périmètre

Base : `fc9be34cfb116b8ab885a0993e5c6e14a20bbebb`, branche V1.4 `dev/product-v14-server-exceptions-20261019`. Archive V1.4 vérifiée : `7a9d3f07e17458c085b00097bc200579b29273523e77029b592e23086b18ac85`, CRC valide et 394 entrées du manifeste recalculées. Le checkout existant propre correspondait déjà à cette base : aucun remplacement ni redémarrage du projet.

Branche V1.5 : `dev/product-v15-business-facets-20261019`. Aucun push, merge, changement de main, workflow GitHub Actions, ressource payante, déploiement public, scanner, collecteur ni intervention PC. Les tests historiques restent identiques. Aucun modèle, dépendance ou migration ajouté. Moteur financier, décisions, preuves, rôles, authentification et audit existants inchangés.

## Incrément utilisable

- Recherche asynchrone de fournisseurs issus des snapshots financiers, puis sélection explicite d’une valeur renvoyée. Le texte tapé est une recherche, jamais un filtre fournisseur appliqué silencieusement.
- Recherche de contrats par référence approuvée figée ou nom documentaire réel. UUID internes dans les appels seulement ; aucun champ UUID de contrat dans le parcours live ni dans la démo V1.5.
- Les homonymes documentaires conservent des valeurs distinctes. Description : fichier, date de création de la source revue et numéro de choix dans l’ensemble admissible courant. Ce numéro sert à désambiguïser, ce n’est pas une référence contractuelle.
- Debounce 250 ms, annulation des requêtes obsolètes et résultats indexés par organisation/critères/recherche/page/tentative. Navigation clavier : flèches, Home, End, Enter, Escape, Tab. Chargement, absence de choix, échec récupérable, effacement et pagination explicites.
- Modifier le fournisseur efface la sélection du contrat. Les choix de contrats sont ensuite recherchés avec le nouveau fournisseur. Sélectionner un contrat ne crée ni association ni décision.
- Toute modification du filtre appliqué repart au début de la file d’exceptions. Ouvrir une investigation et revenir conserve critères et position. Le composant de file existant reste monté pendant le dossier.
- Les gateways de compatibilité sans méthode `queryFacets` conservent le contrôle V1.4 pour les consommateurs historiques et tests gelés ; les gateways live et de démo V1.5 exposent toujours les nouveaux sélecteurs. Aucune panne du serveur de facettes live ne déclenche de fallback synthétique.

## Contrat API

`GET /api/v1/organizations/{organization_id}/financial/exception-facets`

Route statique indépendante de `/evaluations/{evaluation_id}`. Mêmes dépendances `AuthorizedOrganization` et `DatabaseSession` que les lectures financières existantes. Accès par appartenance active à l’organisation, sans assouplissement des rôles ni écriture. BFF : `/api/organizations/{organization_id}/financial/exception-facets`. Le token backend reste côté serveur ; aucun paramètre ne remplace l’organisation du chemin ou l’identité serveur. GET uniquement, réponses no-store.

| Paramètre                                  | Contrat                                                                                                                                            |
| ------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `facet`                                    | Obligatoire : `supplier` ou `contract`                                                                                                             |
| `search`                                   | Chaîne de 0 à 120 caractères, espaces externes retirés, caractères de contrôle refusés ; sous-chaîne littérale ILIKE avec `%`, `_` et `\` échappés |
| `limit`                                    | 1 à 50, défaut 20 ; le navigateur live demande 20                                                                                                  |
| `after`                                    | Curseur signé, maximum 2048 caractères, facultatif                                                                                                 |
| `q`                                        | Recherche des valeurs enregistrées V1.4, maximum 160                                                                                               |
| `invoice_source_id`, `invoice_document_id` | UUID exacts, tenant-scoped                                                                                                                         |
| `outcome`                                  | Valeur enregistrée, maximum 32                                                                                                                     |
| `decision_status`                          | confirmed, false_positive, needs_review, unrecorded ; dernière décision enregistrée, distincte de la currentness                                   |
| `currency`                                 | ISO en trois majuscules                                                                                                                            |
| `supplier`                                 | Chaîne exacte, 1 à 120 caractères ; ignorée pour la facette fournisseur uniquement                                                                 |
| `contract_source_id`                       | UUID d’association approuvée unique ; ignoré pour la facette contrat uniquement                                                                    |
| `missing_contract`                         | Sens V1.4 intégralement conservé ; agit sur les deux facettes                                                                                      |
| `created_from`, `created_to`               | Bornes avec timezone, début inclusif et fin exclusive                                                                                              |
| `current`, `needs_review`                  | Sémantique métier existante, plafond de 100 candidats décrit plus bas                                                                              |
| `sort`                                     | Accepté pour compatibilité des critères ; l’ordre propre aux facettes reste fixe                                                                   |

Les paramètres inconnus ou répétés sont refusés avec 422 sur cette nouvelle route. `offset` et `pagination` ne font pas partie de son contrat. L’endpoint V1.4 garde son contrat historique. Seule précision de lecture : l’égalité du filtre fournisseur utilise explicitement COLLATE C pour correspondre aux valeurs exactes des facettes.

Réponse fournisseur (exemple entièrement synthétique, pas une preuve d’exécution SQL) :

```json
{
  "facet": "supplier",
  "items": [
    {
      "value": "AcmeCloud",
      "label": "AcmeCloud",
      "identity": "snapshot_string"
    }
  ],
  "limit": 20,
  "has_more": false,
  "next_cursor": null,
  "order": "snapshot_string_C",
  "ignored_filter": "supplier",
  "coverage": "Other V1.4 filters apply, including missing_contract. No evaluation counts. Currentness/review exact only within 100 SQL candidates after ignoring the own criterion.",
  "consistency": "Request-coherent; financial changes invalidate the cursor. New searches may return changed labels. No cross-request snapshot."
}
```

Un choix contrat contient `value` (UUID canonique interne), `label`, `reference` nullable, `filename`, `document_id`, `source_created_at`, `effective_from`, `effective_to` et `description`. Aucun nombre d’évaluations par choix, aucun montant, score ou statut nouveau. `has_more` provient d’un look-ahead d’une ligne, jamais d’un count d’évaluations de facette.

Erreurs : 401 sans session ; refus d’organisation par le contrôle existant ; 422 paramètres/cursor invalides ou expirés ; 422 `DYNAMIC_FILTER_LIMIT` ; 409 `FACETS_CHANGED` après changement financier entre pages ; 503 clé de curseur indisponible ou budget coopératif de sérialisation dépassé. Aucune de ces erreurs ne déclenche d’écriture ou de décision automatique.

## Sémantique des facettes

| Facette     | Son filtre ignoré  | Critères conservés                                                  | Ordre et sélection                                                      |
| ----------- | ------------------ | ------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Fournisseur | supplier           | Tous les autres filtres V1.4, y compris contrat et missing_contract | Chaîne snapshot distincte, COLLATE C, ordre lexical strict              |
| Contrat     | contract_source_id | Tous les autres, y compris supplier et missing_contract             | Sources contractuelles distinctes, ordre stable par identifiant interne |

Le `sort` des évaluations n’influence pas les choix. La recherche `search` s’ajoute aux critères conservés ; elle ne remplace pas `q`. Une valeur sélectionnée n’est pas ajoutée artificiellement aux résultats si elle n’est plus admissible.

**Fournisseurs :** seule la chaîne JSONB `billing_scope.supplier_party` enregistrée est disponible. Aucune consolidation d’entités juridiques. Deux entités portant exactement la même chaîne ne peuvent pas être distinguées par ces données : la facette représente explicitement une chaîne, pas une identité légale. Casse, espaces et représentations Unicode restent distincts ; pas de lower/trim/NFC sur les valeurs ou l’égalité. Recherche ILIKE soumise aux règles PostgreSQL de la collation utilisée, sans garantie de translittération ou de normalisation Unicode. Le navigateur ne reconstitue pas la liste depuis des évaluations téléchargées.

**Contrats :** réutilisation directe de `approved_contract_expression()` V1.4 : association `approved` sur la source facture exacte, UUID valide normalisé et un seul identifiant distinct. Deux identifiants approuvés différents restent ambigus et n’offrent aucun contrat ; une association prepared/revoked ne devient pas approuvée. Les identifiants invalides sont ignorés conformément à V1.3/V1.4. Les jointures source/document sont de nouveau tenant-scoped et exigent une source de type contract.

Pour une même source contractuelle, le snapshot de l’évaluation correspondante la plus récente fournit le contexte (created_at décroissant, puis UUID pour départager). La référence vient uniquement d’un unique contenu `reference` approuvé sur cette source dans ce snapshot. Contenus contradictoires : pas de référence choisie arbitrairement, fallback au vrai filename. Les dates éventuelles viennent de l’unique contenu `packet` approuvé ; aucune période agrégée entre versions. Le fournisseur de la facture n’est pas présenté comme une identité légale certaine du contrat. La référence de facture seule n’est jamais promue en référence contractuelle approuvée.

`missing_contract=true` signifie toujours « aucune association approuvée unique retournée » : absence, ambiguïté ou absence d’identifiant valide, sans les confondre en nouvelle règle métier. Sur la facette contrat, ce filtre produit zéro choix ; le désactiver pour rechercher un contrat. Il ne répare pas l’association.

## Pagination et changements

Curseur HMAC-SHA256 avec séparation de domaine `exception-facets-v1`, lié à organisation, type, recherche, critères effectifs et taille de page. Valeur d’ancrage stricte (`>`), génération financière et expiration initiale de 15 minutes conservée entre pages. Aucune égalité de référence ou nom ne fusionne deux sources contractuelles.

Verrou SHARE de l’organisation et compteurs append-only `FinancialAudit`/`ReviewedFinancialSource` réutilisés de V1.4. Une nouvelle évaluation, revue ou décision suivie par ces mécanismes invalide la continuation avec 409 avant la requête de choix. Une nouvelle recherche lit le nouvel état ; elle peut changer les libellés représentatifs. Aucune image figée entre requêtes n’est revendiquée. La validation native des verrous reste non effectuée.

Les noms documentaires sont des métadonnées de présentation actuelles, pas une preuve figée dans le snapshot. L’API documentaire inspectée n’offre pas de renommage, mais le trigger historique ne protège pas original_filename. Une modification externe de ce champ n’est pas couverte par les compteurs financiers et pourrait modifier l’appartenance d’une recherche par nom entre pages. L’ordre reste basé sur la source stable, mais une cohérence de membership à travers ce type de mutation n’est pas garantie. Une future API de renommage devra ajouter une invalidation appropriée avant d’offrir une garantie plus forte. Aucun contournement ni changement de trigger dans V1.5.

La clé processus privée de V1.4 reste le défaut. Plusieurs workers nécessitent la même `FLA_EXCEPTIONS_CURSOR_KEY` (hexadécimal, au moins 32 octets) ; redémarrage/rotation sans clé partagée invalide les anciens curseurs. Aucune clé ni credential runtime dans le checkpoint. Le curseur est signé, pas chiffré ; ne le traiter ni comme permission ni comme secret d’authentification.

## Currentness, bornes et performance

1. Retirer le seul filtre de la facette elle-même, puis appliquer les critères SQL enregistrés.
2. Si current ou needs_review : lire au maximum 101 candidats ; 101 signifie refus explicite avant sérialisation, sans fournir de choix approximatif. Le plafond porte donc sur le jeu élargi de la facette, qui peut dépasser celui de la file sélectionnée.
3. Jusqu’à 100 : appeler le sérialiseur métier inchangé, appliquer current/review, puis restreindre la requête de facette aux UUID retenus **avant** distinct et pagination.
4. Une requête de choix renvoie au maximum limit+1 lignes, soit 51. Pas de N+1 sur les labels : métadonnées réunies dans le même SELECT. Les lectures existantes de currentness peuvent rester multiples, mais elles sont limitées aux 100 candidats et ne sont pas remplacées par une approximation.

Budget coopératif de 15 secondes contrôlé entre sérialisations, sans revendication de timeout global dur. statement_timeout existant (5 secondes par défaut configurable) et limites du proxy réutilisés ; aucun paramètre de production modifié.

**Une sortie bornée n’est pas un coût SQL constant.** DISTINCT fournisseur, normalisation des associations JSONB, DISTINCT ON du dernier contexte, window row_number et recherche ILIKE peuvent scanner/trier de nombreuses évaluations autorisées. Les compteurs de génération ont aussi un coût. Les sous-requêtes JSONB pour références/paquets peuvent être répétées par le planificateur. Aucun EXPLAIN, index effectif ou débit mesuré sur PostgreSQL dans cette mission.

Index inspectés : organisation sur financial_evaluations et reviewed_financial_sources ; contraintes uniques (organisation,id) pour sources/documents ; clés tenant pour les associations. Aucun index ajouté sans mesure native. Améliorations à mesurer sur un jeu synthétique autorisé : EXPLAIN ANALYZE BUFFERS aux volumes 1k/10k/100k, latence p50/p95 et buffers lus ; comparer index fournisseur JSONB + organisation/C, index organisation/created_at/id, puis extraction latérale du contexte pour réduire le travail répété. Recherche sous-chaîne et associations JSONB peuvent nécessiter une stratégie distincte ; pas de promesse qu’un simple index B-tree suffise. Aucune migration proposée comme déjà nécessaire ou qualifiée.

## Vérifications effectivement réalisées

| Contrôle                           | Résultat et portée                                                                                                                     |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Archive/manifeste V1.4             | SHA attendu, CRC et 394 empreintes PASS                                                                                                |
| Frontend                           | 211 tests PASS, dont 18 V1.5 ; contrats/BFF et composants avec mocks explicites                                                        |
| Backend ciblé                      | 266 tests PASS, dont 35 V1.5 ; moteur existant, argent, preuves, transport OIDC unitaire, Product V11/V13/V14/V15                      |
| PostgreSQL dialecte                | Compilation de requêtes paramétrées et inspection tenant/bornes ; pas d’exécution SQL native                                           |
| Frontières serveur                 | Sessions SQL factices fournissant des lignes présélectionnées ; ces tests n’émulent pas le moteur SQL                                  |
| Authentification négative          | Nouvelle route sans session refusée ; token forgé non accepté lorsque provider non configuré ; aucune connexion OIDC réussie prétendue |
| Build/TypeScript/lint/format       | Journaux joints ; contrôles de développement PASS                                                                                      |
| Navigateur                         | Application compilée réelle dans le navigateur Cloud, données synthétiques seulement ; captures originales non retouchées              |
| Préservation/restauration          | Empreintes historiques, patch appliqué à V1.4, arbre complet et archive restaurée vérifiés dans les preuves jointes                    |
| SQL natif/concurrence/plans/charge | NOT VERIFIED, aucun PostgreSQL lancé ni nouvelle investigation                                                                         |
| OIDC/PostgreSQL E2E                | BLOCKED historique, non retenté                                                                                                        |

Couverture des nouveaux tests : recherche échappée, strings exactes/homonymes, références identiques, fallback documentaire, association unique/ambiguë/préparée, absence de résultats, limites et ancres, ordre, filtres combinés, tenant, changements de génération, curseur lié/expiré/altéré, plafond dynamique et budget, API non collidente et compatibilité V1.4, BFF sans override d’identité, clavier/effacement, requêtes tardives, changement de fournisseur et dossier/retour.

Incidents de développement corrigés : premier lancement ciblé à un mauvais chemin (aucun test exécuté), formatage des nouveaux fichiers, puis une assertion de nouveau test ciblant les options de tous les selects au lieu de la seule listbox métier. L’assertion a été restreinte à cette listbox ; aucun test historique modifié. Amélioration découverte lors de la revue : le menu fermé après sélection doit pouvoir rouvrir au clic sur l’input déjà focalisé ; ouverture fraîche et test de non-régression ajoutés. Les échecs initiaux conservés sont distingués des journaux finaux.

## Risques résiduels et décision

Les facettes serveur, le BFF, les sélecteurs et leurs tests applicables sont implémentés : **PASS DEVELOPMENT**. Le checkpoint ne valide pas leur exécution native ou leur performance à grande échelle. Les garanties transactionnelles héritées, les effets de collation réels, la sémantique SQL et les plans nécessitent toujours une validation PostgreSQL native séparée ; aucun faux PASS de base ou d’authentification.

Limites produit conservées : plafond current/review, pas de registre juridique des fournisseurs, pas de consolidation de références contradictoires, pas d’historique fictif, pas de Recovery Ledger, pas de sauvegarde des filtres après rechargement complet du navigateur. Le retour intra-espace depuis un dossier est conservé. Le filtre invoice_source_id reste technique et distinct du nouvel objectif fournisseur/contrat. Les décisions et citations existantes ne sont pas modifiées.

Restrictions : Phase 7, PostgreSQL/PITR et ClamAV/WSL NOT QUALIFIED ; scanner BLOCKED ; pilote NO-GO ; PC et production NOT AUTHORIZED. Aucun changement de ces restrictions par ce résultat.

**Recommandation unique V1.6 : remplacer le filtre Invoice source ID par un sélecteur serveur de factures fondé sur les références documentaires disponibles.**

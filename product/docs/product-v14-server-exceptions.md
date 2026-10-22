# FINLEAK Product V1.4 — Server-side Exceptions Query Engine

**Décision : PARTIAL DEVELOPMENT.** Le moteur SQL, les curseurs authentifiés et la file frontend sont implémentés. Les tests disponibles passent. Le comportement natif PostgreSQL, les plans d’exécution et les garanties de verrouillage concurrent ne sont pas démontrés dans ce Cloud. Les filtres dynamiques ne couvrent pas des ensembles de plus de 100 candidats SQL. Aucune preuve SQL/OIDC réelle n’est inventée.

## Continuité et périmètre

Reprise du commit V1.3 `75620897a0ecde00f7b1bb62cdb5c1d55185a3b1`, archive `170e7dad174cf23a2894774da01bd9e2511c401f7256ba960cdf7bf587fa1509`, CRC et 382 entrées de manifeste vérifiés. Branche locale : `dev/product-v14-server-exceptions-20261019`. `main` reste `c02424c2f3d910af771dcdc05e2f5cb281de4bef`.

Aucun changement des règles financières, services de décision/currentness, modèles, migrations, OIDC ou permissions. Aucun nouveau paquet, workflow, service de base ou fournisseur d’identité. Aucune investigation PostgreSQL/UID/R1 relancée. Les tests historiques sont conservés octet pour octet.

## Logiciel effectivement développé

`backend/app/financial/exceptions_query.py` construit les critères enregistrés en SQLAlchemy/PostgreSQL avant le COUNT et la pagination. Il conserve les montants Numeric/Decimal, lie les curseurs à l’organisation/aux critères/au tri/à la taille de page, et borne les lectures. L’endpoint existant est raccordé à ce moteur ; il ne s’agit pas d’une recette laissée à implémenter.

La file live utilise le BFF existant, transmet les critères, respecte exactement l’ordre reçu et n’applique aucun filtre de page dissimulé. Elle ne précharge plus les évaluations ni le résumé financier pour ouvrir cette vue : seuls deux petits contextes de sources/documents sont lus. Le Dashboard conserve son résumé autoritatif. Les noms des sources d’une page sont récupérés par une lecture groupée bornée, indépendamment des 100 premiers documents disponibles dans le contexte.

L’utilisateur dispose de critères combinés, d’une recherche différée de 250 ms, d’un total filtré, d’un compte de lignes sur la page, d’une position, de la présence d’une suite et de boutons précédent/suivant/recommencer. Une erreur de lecture peut être réessayée avec le même curseur, sans mutation. Tout changement de critères réinitialise la navigation. Les réponses tardives sont annulées et ignorées. La page reste disponible au retour d’un dossier ; une décision ou une actualisation relance la requête depuis le début.

## Contrat API

Route backend inchangée : `GET /api/v1/organizations/{organization_id}/financial/evaluations`. BFF : `/api/organizations/{organization_id}/financial/evaluations`. Authentification et accès à l’organisation restent requis. Les nouveaux paramètres figurent aussi dans l’OpenAPI réel exporté dans les preuves.

| Paramètre             | Contrat                                                                                                                                                 |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `limit`               | 1–100, défaut 20                                                                                                                                        |
| `offset`              | 0–100 000, défaut 0 ; mode historique                                                                                                                   |
| `pagination`          | `offset` par défaut, ou `cursor`                                                                                                                        |
| `after`               | Curseur opaque, maximum 2 048 caractères ; exige `pagination=cursor` et `offset=0`                                                                      |
| `q`                   | Sous-chaîne littérale, maximum 160 caractères ; espaces externes retirés, contrôles refusés, `%`, `_` et `\` échappés                                   |
| `invoice_source_id`   | UUID exact de la source facture                                                                                                                         |
| `invoice_document_id` | UUID exact du document facture, sous-requête avec organisation explicite                                                                                |
| `outcome`             | Outcome existant exact, maximum 32 caractères ; valeur inconnue = aucun résultat                                                                        |
| `decision_status`     | Dernière décision enregistrée : `confirmed`, `false_positive`, `needs_review`, ou `unrecorded` ; ne prétend pas être le statut courant après péremption |
| `currency`            | Une devise ISO en trois lettres majuscules ; absence = groupes de devises séparés                                                                       |
| `supplier`            | Identité fournisseur enregistrée, correspondance exacte, 1–120 caractères                                                                               |
| `contract_source_id`  | UUID du contrat explicitement associé et approuvé dans le snapshot                                                                                      |
| `missing_contract`    | Sélection des snapshots sans association approuvée unique retournable, y compris ambiguïté ; ne signifie pas « aucun contrat existe »                   |
| `created_from`        | Date/heure avec fuseau, borne inclusive                                                                                                                 |
| `created_to`          | Date/heure avec fuseau, borne exclusive ; doit suivre `created_from`                                                                                    |
| `current`             | Vraie logique métier de péremption ; filtrage exact si les critères SQL laissent au plus 100 candidats                                                  |
| `needs_review`        | Même sémantique que la file V1.3 ; filtrage exact et même borne de 100 candidats                                                                        |
| `sort`                | `newest` (défaut), `oldest`, `amount_high`, `amount_low`, `outcome`                                                                                     |

La recherche couvre le périmètre, son libellé figé, l’explication, l’ID d’évaluation, le fournisseur et les références contractuelles textuelles du snapshot. Elle ne promet pas une recherche globale des noms de fichiers ni une extraction de références facture absentes du modèle. Les identifiants facture sont filtrables explicitement. Les associations JSONB appliquent l’état approuvé, la source facture correcte et un seul UUID valide distinct, en reproduisant la normalisation V1.3 ; les valeurs invalides ne sont pas converties en UUID par PostgreSQL.

La réponse conserve `items`, `total`, `limit`, `offset`, `coverage`. Elle ajoute `total_exact`, `has_more`, `next_cursor`, `pagination`, `consistency` et, pour les lignes, `invoice_filename`, `invoice_document_id`, `contract_filename`. En mode curseur, `offset` indique la position parcourue, pas une nouvelle instruction OFFSET au serveur.

Exemple de requête sans données réelles : `?pagination=cursor&limit=20&currency=USD&sort=amount_high`. La suite reprend les mêmes critères avec le `next_cursor` retourné. Le navigateur ne reçoit aucun bearer token. Les paramètres de compte ou d’organisation fournis en query ne remplacent jamais l’organisation du chemin autorisé.

## Correction de `current` et compteurs

Le filtre historique après sélection de page a été supprimé. Les filtres enregistrés sont appliqués en SQL avant COUNT. Quand `current` ou `needs_review` est demandé, le serveur compte d’abord les candidats SQL. Au-delà de 100, il répond **422 `DYNAMIC_FILTER_LIMIT`**, sans récupérer ce grand ensemble. Dans la borne, il appelle les fonctions métier existantes sur au plus 100 candidats, applique le filtre, calcule le vrai total filtré, puis sélectionne la page. Aucun « courant » approximatif n’est calculé en SQL et aucun total plus large n’est présenté comme filtré.

Les totaux sont des évaluations correspondant aux critères, pas des factures uniques. Les montants de page ne sont jamais additionnés ni utilisés pour remplacer les agrégats du Dashboard. Les valeurs inconnues restent inconnues ; aucun gain récupéré n’est déduit.

## Pagination et cohérence

Pour les critères enregistrés, la pagination est keyset : date puis UUID, outcome en collation C puis UUID, ou groupe de devise puis rang de nullité du montant, Numeric exact puis UUID. Les UUID sont toujours le dernier départage. Les devises non renseignées sont en dernier et ne sont pas classées entre elles selon un montant sans devise. Les montants nuls sont en dernier dans chaque devise. Les comparaisons de continuation comportent les égalités de tous les critères précédents, afin de conserver les égalités de date/montant. Les requêtes de page récupèrent au plus `limit+1` lignes ; seules `limit` lignes sont sérialisées.

Le curseur contient une ancre, une position, une empreinte des critères, une génération et une expiration de 15 minutes ; il est signé HMAC-SHA256. Ce n’est ni un jeton d’accès ni une autorisation. Toute réutilisation avec un autre tenant/tri/critère/taille, modification ou expiration produit 422. Le défaut est une clé aléatoire privée au processus : redémarrage et changement de worker invalident les curseurs. Une future installation multiworker doit fournir une même clé hexadécimale privée d’au moins 32 octets via `FLA_EXCEPTIONS_CURSOR_KEY`, hors fichiers suivis. Aucune clé d’exploitation n’est livrée.

Une lecture prend le verrou SHARE de l’organisation déjà utilisé par le modèle financier. Les écritures financières existantes prennent le verrou exclusif via le service et les triggers. Le compte et la page doivent donc être cohérents au sein de la requête. Cette propriété est établie par lecture des migrations et construction SQL, **pas par un test concurrent natif dans cette livraison**.

Les compteurs de deux relations append-only (`financial_audit`, `reviewed_financial_sources`) forment la génération de navigation. Une modification financière entre pages donne **409 `EXCEPTIONS_CHANGED`** et exige de recommencer. Aucun snapshot MVCC figé n’est conservé entre requêtes. Cela réduit les doublons/pertes dus à des mutations en refusant une continuation devenue incohérente. Les écritures hors protocole, restaurations de base et PITR ne sont pas qualifiés par cette technique. Les noms de fichiers servent à l’affichage, pas à déterminer l’ordre ou la recherche.

La voie dynamique bornée reparcourt son petit ensemble exact à chaque requête sous les mêmes protections ; elle n’est pas une pagination SQL native du calcul de péremption. Les liens de détail et validations financières restent indépendants et autoritatifs.

## Performance, sécurité et compatibilité

Le modèle existant possède un index d’évaluations sur `organization_id`, ainsi que les clés uniques tenant/ID et tenant/empreinte. La clé unique des décisions couvre tenant/évaluation/numéro. Aucun index nouveau ni migration n’a été appliqué. Les tris composites et filtres JSONB ne disposent pas d’index dédiés qualifiés ; le coût du COUNT exact, des générations et des sous-requêtes peut croître fortement. Aucune capacité « grands volumes en production » n’est démontrée sans plans EXPLAIN et mesures PostgreSQL.

Les paramètres sont bornés, liés au SQL et les caractères de recherche échappés. La requête principale, les sous-requêtes et la lecture groupée de noms sont tenant-scoped. La sérialisation conserve la vraie péremption et les décisions via les services existants : des lectures N+1 demeurent, bornées à la page ou aux 100 candidats. Un budget de travail de 15 secondes est contrôlé avant chaque sérialisation, en plus des timeouts SQL existants. Ce contrôle coopératif n’interrompt pas une requête SQL déjà en cours et ne constitue pas un délai global strict.

Les appels historiques sans nouveaux critères gardent leur forme, leur ordre date/UUID et limit/offset. Les changements intentionnels sont le total corrigé de `current`, le refus explicite des filtres dynamiques trop larges et le plafond OFFSET de 100 000. Ils doivent être pris en compte par les consommateurs concernés. Les anciens gateways de composants sans méthode de requête conservent leur voie locale explicitement limitée ; la file live et la démonstration V1.4 utilisent la nouvelle méthode.

## Tests et preuves

- **193 tests frontend PASS**, dont 13 nouveaux : critères combinés, ordre reçu inchangé, total/page/position distincts, pages suivantes, reprise avec le même curseur après erreur, annulation et isolation des réponses tardives, conflit concurrent synthétique, accès au dossier après pagination, BFF et absence de bearer navigateur.
- **231 tests backend ciblés PASS**, dont 38 nouveaux : SQL PostgreSQL compilé et paramètres, exactitude Decimal et clés de nullité, égalités via évaluation explicite de l’AST en mémoire, curseurs invalides/expirés/incompatibles, génération modifiée, total dynamique avant offset, bornes, ancien contrat et OpenAPI réel.
- TypeScript, Webpack, ESLint, Ruff et format : PASS. Les nouveaux défauts de typage/assertion et de gestion d’état React ont été corrigés sans désactivation de contrôle ni modification de test historique.
- Dix requêtes count/page compilées pour PostgreSQL sont exportées avec leurs paramètres typés synthétiques. **Zéro exécution SQL/PostgreSQL** : compilation et AST ne sont pas une preuve d’exécution de JSONB, d’index, de verrouillage ou de concurrence réelle.
- Navigateur Cloud : filtrage USD et tri de montant, première page 2/3, seconde page 1/3 avec montant inconnu en dernier, retour au début après nouveau fournisseur, ouverture d’un dossier depuis la deuxième page et conservation de cette page au retour. Deux captures JPEG authentiques sont livrées.

La démonstration appelle une frontière de requête en mémoire explicitement identifiée. Son curseur de fixture n’est pas le curseur HMAC backend et ne prouve aucune pagination PostgreSQL. Aucun OIDC, jeton réel, transaction persistée, scanner ou reprise après redémarrage n’a été exécuté. L’aperçu interne a été arrêté après QA ; aucun déploiement public.

## Limites et décision

Les fonctionnalités serveur sont du code réellement raccordé ; la validation native PostgreSQL demeure manquante, les filtres dynamiques sont limités, les plans d’exécution et N+1 restent à mesurer. Les sélecteurs de fournisseurs/contrats utilisent encore des valeurs exactes/UUID plutôt que des facettes métier globales. Ces limites motivent **PARTIAL DEVELOPMENT**, sans retour à une étude d’infrastructure.

OIDC/PostgreSQL E2E : **BLOCKED historique, non réinvestigué**. Phase 7, PostgreSQL/PITR et ClamAV/WSL : **NOT QUALIFIED**. Scanner : **BLOCKED**. Pilote : **NO-GO**. PC et production : **NOT AUTHORIZED**. Aucun GitHub Actions, service payant ou changement de `main`.

**Recommandation produit unique pour V1.5 : ajouter des facettes serveur bornées permettant de sélectionner fournisseur et contrat par leurs références métier, sans saisie d’UUID.**

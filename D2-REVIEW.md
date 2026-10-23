# FINLEAK P0-D2 — attribution de la fixture synthétique

Décision : **ROOT CAUSE IDENTIFIED — FIX CANDIDATE READY**.
Cette décision désigne un défaut prouvé par le code et un correctif candidat.
Elle ne prétend pas avoir observé l'exception SQL du run 2 ni validé D2 sur PostgreSQL.
Préparation d'un troisième run : **BLOCKED FOR EXECUTION**, aucune autorisation consommée ou demandée.

## Sources et restauration

Base exacte : 180320a7b07aadd0593eafe7a2ded9f3f5d83b81, parent D1
790ece707da1bebcf59dc73f02de22e6069dc727, arbre bd1c9e65126d4e9bf378270dc1fd13e713419315.
Le clone GitHub CLI n'avait pas d'identifiants. Le bundle D1 original a donc été
restauré, puis les deux documents du commit exécuté et ses métadonnées ont été
récupérés par le connecteur authentifié. Le SHA de l'objet commit et l'égalité
complète des 463 blobs/modes avec GitHub ont été vérifiés avant les modifications.
Il ne s'agit pas d'une reconstruction approximative du produit.

Archive D1 vérifiée : 6b2ecd1f041edd82fe180c22bdae45a64aaa69af2a9b5753202decac6d9ce665,
CRC ZIP et 485 entrées du manifeste conformes.
Preuves du run 2 : 9d6e333de6189923fb44c4fde7949f0a3a4c1dac1736e3c813e56e072e2c2286,
CRC ZIP et 18 entrées conformes.

## Faits établis par les journaux

Run 39889981015, tentative 1, résultat BLOCKED, diagnostic FIXTURE_PERSISTENCE_ERROR
dans synthetic_identities. PostgreSQL démarre et migrations 0001–0010 sortent 0.
Pas de login navigateur, de décision, de témoin financier ou de redémarrage validé.
L'exception SQL et le SQLSTATE sont absents. Aucun SQLSTATE, y compris P0001,
n'est présenté comme observé pendant ce run.

## Démonstration du conflit par le code

1. `product/backend/migrations/versions/0007_pilot_access.py`, `GUARDS`,
   `pilot_access_guard()` : pour un rôle non superutilisateur, actor et purpose
   doivent être présents, actor doit exister dans users. Ce contrôle précède
   le RETURN NEW spécifique aux insertions d'organisations.
2. `ACCESS_TABLES` et `upgrade()` installent ce BEFORE INSERT sur organizations
   et organization_memberships, ainsi qu'un AFTER INSERT d'audit. users n'est
   pas dans ACCESS_TABLES : un utilisateur peut être créé avant l'attribution.
3. La base exécutée `acceptance/product_v11.py:seed()` ajoutait deux organisations
   et deux utilisateurs dans le même flush, sans operator_context ni set_config.
   Un test du véritable plan UOW SQLAlchemy verrouillé, sans connexion SQL,
   observe organizations avant users. Même l'ordre inverse ne fournirait pas
   les paramètres d'attribution absents.
4. `bench/p0/runtime.py:execute()` crée p0_migrator NOSUPERUSER NOCREATEDB
   NOCREATEROLE et passe migration_url à la commande seed. La fixture refuse
   explicitement les rôles élevés dans son preflight.
5. `app/admin.py:operator_context()` vérifie acteur existant/non désactivé,
   motif 1–4000 caractères, et utilise set_config(...,true) pour actor, reason
   et request, dans la transaction courante. Le mécanisme existant est réutilisé.

Conclusion statique : l'ancienne fixture ne peut pas franchir sa première
insertion d'organisation sous le rôle prévu et sans contexte hérité. Cela
explique un blocage compatible avec le run 2. L'exception précise de ce run
reste non prouvée, car le diagnostic D1 l'a supprimée.

## Analyse contradictoire

Les migrations 0008–0010 ne remplacent pas pilot_access_guard : elles ajoutent
respectivement admission, contrôle de sources/quarantaine et vues personnelles.
La fixture n'insère ni admission, ni scan/release, ni vue. Aucun de ces mécanismes
n'est désactivé. Le contrôle BEFORE UPDATE des identités ne bloque pas les INSERT
de users ; le journal n'ajoute pas de clé étrangère sur actor_id, donc n'introduit
pas de bootstrap circulaire.
Un manque de droits SQL, une erreur de schéma, une contrainte ou une panne
pourrait aussi produire la phase coarse synthetic_identities. Aucun autre
problème réel n'est exclu par des tests synthétiques.

## Correctif candidat

`seed()` : users → flush → operator_context(owner, motif DEMO) → organisations
→ flush → identités OIDC → flush → memberships → flush → documents → flush
→ vérification de quatre lignes d'audit avec un request_id commun → commit.
Tous les travaux restent dans la même transaction. Une erreur avant commit
provoque rollback ; un échec de roster après commit reste BLOCKED et exige le
nettoyage du runtime existant, sans retry. Aucun enregistrement financier final
n'est injecté et aucune politique financière n'est changée.

Le journal d'accès est écrit par les triggers existants, jamais fabriqué par
le code de production. Les journaux fabriqués dans les tests sont des doubles
explicitement synthétiques, et ne prouvent pas le fonctionnement PostgreSQL.

## Diagnostic

Extension optionnelle fermée D2, compatible avec le paquet D1 inchangé.
Sous-étapes et catégories sont énumérées ; le SQLSTATE n'est accepté que depuis
un objet psycopg réel dans une chaîne bornée/cyclique protégée. Les exemples
23505/42501/P0001 des tests sont des exceptions synthétiques, pas des observations.
Le parent valide à nouveau l'extension avant publication, et l'émetteur refuse
les champs inattendus. Aucun message d'exception ou traceback n'est publié.

## Vérifications réellement exécutées dans Work Cloud

Python de développement 3.12.14, dépendances backend installées depuis uv.lock,
aucune modification des dépendances. Aucun PostgreSQL, Docker, IdP ou workflow
n'a été lancé pour D2. Les tests du protocole et des orchestrateurs emploient
des doubles explicitement identifiés.

| Suite | Résultat |
|---|---|
| D2 ciblée | 75 PASS |
| D2 tests PostgreSQL préparés | 3 SKIP, aucune connexion faute de TEST_DATABASE_URL |
| Suite large D2, hors integration | 964 PASS / 8 FAIL / 22 SKIP / 418 deselected |
| Même suite sur base 180320a isolée | 894 PASS / 3 FAIL / 22 SKIP / 415 deselected |
| Ruff et formatage des six fichiers concernés | PASS |

Les trois échecs de base sont conservés : attente preflight 0009 alors que head
vaut 0010 ; deux revues supply-chain expirées au 9 octobre 2026. Aucune politique
d'expiration ni migration n'est relâchée.
Les cinq échecs ajoutés concernent les tests D1 inchangés : leur SessionDouble
n'a pas get()/execute()/scalars() nécessaires à operator_context et à l'audit.
Ils s'arrêtent à operator_context et n'atteignent plus les anciennes phases
simulées documents/commit/roster. **La suite complète n'est pas verte.**
Le patch de migration des seules doublures est livré en proposition NOT-APPLIED,
vérifié par git apply --check --unidiff-zero (patch sans contexte), mais non
appliqué et non présenté comme testé.

## Intégrité et limites

Les 425 entrées du manifeste V2.3 sont intactes : SHA-256 c4ca19ec23f9b397578a60c56642185cdaa1fdead8c3a4174dbbba42275c7b53.
Seule la substitution exacte de product_v11.py dans gate.py est actualisée ;
empreinte de base conservée, aucun wildcard ou exclusion. Les nouveaux modules
et tests sont liés au commit candidat exact et au manifeste du checkpoint.
Workflow actif et modèle identiques octet pour octet à 180320a. runtime.py,
emit_evidence.py, app/admin.py, toutes les migrations, tests historiques,
sources financières, frontend et les deux main demeurent inchangés.

Avant tout troisième run : revue du candidat et des cinq tests historiques
incompatibles, nouvelle preuve financière authentifiée, paramètres immuables
actualisés et autorisation explicite séparée. Aucun lancement dans D2.
OIDC/PostgreSQL E2E : BLOCKED. Phase 7/PITR/ClamAV : NOT QUALIFIED.
Scanner : BLOCKED. Pilote : NO-GO. PC et production : NOT AUTHORIZED.

## Références de fonctions dans ce candidat

`product/backend/acceptance/product_v11.py:seed()` ligne 230 ;
`preflight()` ligne 138.
`product/backend/app/admin.py:operator_context()` ligne 17.
`product/backend/acceptance/p0_fixture_errors.py:postgres_sqlstate()` ligne 11.
`failure_detail()` ligne 34.
`p0_diagnostics.py:validate_d2()` ligne 118.

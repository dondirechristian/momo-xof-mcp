# Contrat d'API CinetPay — observé

Source : documentation du tableau de bord CinetPay, compte sandbox SOTECHDI
(Burkina Faso). Relevé le **2026-09-21**.

Ce fichier existe parce que CLAUDE.md interdit d'écrire un appel d'API à
partir d'une supposition. Tout ce qui suit est recopié de la documentation
observée. **Ce qui n'y figure pas est marqué comme inconnu — ne pas le
combler de mémoire.**

- Base URL sandbox : `https://api.cinetpay.net`
- Version : « 1.0 Aurore »
- URL de production : **inconnue**

---

## Initialisation d'une transaction de paiement web

```
POST {{baseUrl}}/v1/payment
```

### Authentification — relevée le 2026-09-21

Un appel préalable délivre un jeton.

```
POST {{baseUrl}}/v1/oauth/login
```

Corps :

```json
{
    "api_key": "{{account_key}}",
    "api_password": "{{account_password}}"
}
```

Réponse `200` :

```json
{
    "code": 200,
    "status": "OK",
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.<tronqué>",
    "token_type": "bearer",
    "expires_in": 5767,
    "user_email": "marchand@exemple.com"
}
```

Réponse d'erreur documentée : `422`.

### Forme des erreurs — observée le 2026-09-22

Premier appel réel de la sonde, avant toute mise en liste blanche :

```json
HTTP 422
{
    "code": 2011,
    "status": "NOT_ALLOWED",
    "description": "This Ip is not withlisted"
}
```

Enseignements, aucun n'était documenté :

- Les erreurs de haut niveau portent **`description`**, pas `message`. Le
  champ `message` n'existe que dans l'objet `details` d'un paiement. Une
  implémentation qui ne lit que `message` affichera une erreur vide.
- `status` peut valoir **`NOT_ALLOWED`**. J'en avais conclu, le 2026-09-22,
  que les statuts d'erreur d'appel et les statuts de transaction formaient
  deux vocabulaires distincts. **C'était faux** : la section « Codes de
  statut », relevée le lendemain, les réunit dans une table unique où
  `NOT_ALLOWED` (2011) côtoie `INITIATED` (2001). Voir plus bas.
- `code` `2011` = IP non autorisée.
- Le `422` sert aussi bien au refus d'autorisation qu'à la validation de
  champs. Le code HTTP seul ne suffit pas à distinguer les cas : il faut lire
  `code`.
- La faute de frappe `withlisted` est dans la réponse de l'API. Ne pas la
  corriger dans un test de correspondance de chaîne.

### Liste blanche IP — piège du tableau de bord

Le tableau de bord affiche, quand aucune IP n'est enregistrée :

> Aucune IP configurée. L'API est accessible depuis n'importe quelle IP.

**C'est faux.** Une liste blanche vide refuse tout appel, avec le `2011`
ci-dessus. Il faut y inscrire explicitement l'adresse appelante. Sur une
connexion à IP dynamique, l'entrée devient caduque au changement d'adresse.

À retenir :

- Le jeton est un **JWT**, de durée de vie courte — `expires_in` valait 5767
  secondes, soit environ 1 h 36 dans l'exemple. Une implémentation sérieuse le
  met en cache et le renouvelle à l'expiration, elle ne se réauthentifie pas à
  chaque appel.
- `token_type` vaut `bearer`. La transmission vers `/v1/payment` en
  `Authorization: Bearer <access_token>` est **déduite de cette convention**,
  la documentation ne la montrant pas explicitement. C'est précisément ce que
  la sonde doit confirmer : un `401` la réfuterait.
- La documentation de `/v1/payment` précise que le jeton **porte aussi le
  pays** du compte. Un compte par pays, donc un jeu d'identifiants par pays.
  Le compte SOTECHDI est rattaché au Burkina Faso.

### Corps de la requête

| Propriété | Type | Requis | Notes |
|---|---|---|---|
| `currency` | String | **oui** | `XOF`, `XAF`, `GNF`, `CDF` |
| `merchant_transaction_id` | String | **oui** | unique, max 30 caractères |
| `amount` | Integer | **oui** | entier — cohérent avec XOF sans décimale |
| `lang` | String | **oui** | `fr` ou `en` |
| `designation` | String | **oui** | libellé du paiement |
| `client_email` | String | **oui** | adresse valide |
| `client_first_name` | String | **oui** | 2 à 255 caractères |
| `client_last_name` | String | **oui** | 2 à 255 caractères |
| `success_url` | String | **oui** | max 120 caractères |
| `failed_url` | String | **oui** | max 120 caractères |
| `notify_url` | String | **oui** | max 120 caractères |
| `payment_method` | String | non | ex. `OM_CI` — voir codes de paiement |
| `client_phone_number` | String | non | obligatoire en paiement direct |
| `direct_pay` | Boolean | non | `true` = sans redirection |
| `otp_code` | String | non | 4 à 6 chiffres, Orange uniquement |

Contraintes signalées par la documentation :

- `merchant_transaction_id` doit être **unique** dans le système.
- Le compte est lié à **une seule devise** ; envoyer celle du compte. Le
  compte SOTECHDI est en XOF.
- `client_phone_number` n'est pris en compte que si une option est activée sur
  le compte ; sans elle, le client peut modifier son numéro sur la passerelle.

### RÈGLE CARDINALE — deux niveaux, deux significations

Observé le 2026-09-22 sur des appels réels. Rien de tout cela n'est documenté,
et s'y tromper coûte de l'argent.

| Niveau | Ce qu'il décrit |
|---|---|
| `code` / `status` racine | le sort de la **requête HTTP** |
| `details.code` / `details.status` | le sort de la **transaction** |

Les deux appels suivants ont **tous deux** répondu `HTTP 200` avec
`"code": 200, "status": "OK"` à la racine :

- l'un avec `details.status = "INITIATED"` — demande acceptée ;
- l'autre avec `details.status = "INVALID_PARAMS"` — requête rejetée, rien
  n'a été créé côté paiement.

**Ne jamais conclure au succès depuis le niveau racine.** Toujours lire
`details.status`. Un test sur `status == "OK"` croira avoir encaissé de
l'argent qui n'a jamais bougé.

### Réponse d'initialisation réussie — observée le 2026-09-22

```json
{
  "code": 200,
  "status": "OK",
  "payment_token": "1f1b680fe7e26c8683d0910fa1926b4f01a0c915fd7670f582584c0cac407dc5",
  "notify_token": "9bfba2413af0403cb5227725371d5060",
  "transaction_id": "69fe371559c34c6f98971be5c8f4e4df",
  "merchant_transaction_id": "probe-6fdc5f42f74f",
  "payment_url": "https://secure.cinetpay.net/checkout/<payment_token>",
  "details": {
    "code": 2001,
    "status": "INITIATED",
    "message": "Veuillez cliquer sur le lien pour continuer le paiement",
    "payment_code": null,
    "must_be_redirected": true
  }
}
```

À retenir :

- `merchant_transaction_id` est **renvoyé tel qu'envoyé**. C'est la clé de
  rapprochement côté appelant.
- `payment_url` se termine par le **`payment_token`**, pas par le
  `transaction_id`.
- `expires_in` du jeton valait **86400 s** en réel, contre 5767 dans
  l'exemple de la documentation. Ne pas coder la durée en dur, lire le champ.

### Réponse d'erreur de validation — observée le 2026-09-22

Même endpoint, champs d'identité client envoyés vides. **`HTTP 200`.**

```json
{
  "code": 200,
  "status": "OK",
  "transaction_id": "ER-P-2339255-probe-6e14383b056b",
  "notify_token": "...",
  "payment_token": "...",
  "details": {
    "code": 1004,
    "status": "INVALID_PARAMS",
    "message": "Params you provides are invalid",
    "errors": {
      "client_first_name": ["Le champ client first name est obligatoire."],
      "client_last_name": ["Le champ client last name est obligatoire."],
      "client_email": ["Le champ client email est obligatoire."]
    }
  }
}
```

À retenir :

- `details.errors` est un objet **champ → liste de messages**, en français.
  C'est la source à relayer à l'appelant pour un message actionnable.
- `payment_url` est **absent** de cette réponse. Sa présence n'est donc pas
  garantie : ne pas y accéder sans vérifier.
- Le `transaction_id` valait ici `ER-P-2339255-probe-…`, alors qu'il vaut un
  hexadécimal de 32 caractères en cas de succès. **Le format n'est pas
  stable** : le traiter comme une chaîne opaque, ne jamais l'analyser.

### Table des statuts — section « Codes de statut », relevée le 2026-09-23

Source officielle et complète. Elle remplace les déductions partielles des
jours précédents, dont **deux étaient fausses** :

1. J'avais écrit que les statuts racine et ceux de `details` formaient deux
   vocabulaires disjoints. **Faux** : c'est une table unique. `OK` (200) et
   `NOT_ALLOWED` (2011) y côtoient `INITIATED` (2001).
2. J'avais classé `INVALID_PARAMS` comme final. **Faux** : la documentation le
   marque non final.

| `code` | `status` | Sens | Final |
|---|---|---|---|
| 200 | `OK` | Opération réussie | non |
| 100 | `SUCCESS` | Transaction traitée avec succès | **oui** |
| -1 | `OPERATION_ERROR` | Une erreur s'est produite | non |
| 404 | `NOT_FOUND` | Introuvable | non |
| 1005 | `INVALID_CREDENTIALS` | Identifiants invalides | non |
| 1004 | `INVALID_PARAMS` | Paramètres invalides | non |
| 1003 | `EXPIRED_TOKEN` | Jeton expiré | non |
| 1002 | `INVALID_TOKEN` | Jeton invalide | non |
| 1200 | `TRANSACTION_EXIST` | La transaction existe déjà | **oui** |
| 2001 | `INITIATED` | Initiée, en attente du client | non |
| 2002 | `PENDING` | Le client a commencé le paiement | non |
| 2003 | `EXPIRED` | Expirée, le client n'a pas confirmé | non |
| 2004 | `OTP_ERROR` | Code OTP incorrect | non |
| 2008 | `OTP_EXPIRED` | Code OTP expiré | non |
| 2005 | `INSUFFICIENT_BALANCE` | Solde marchand insuffisant | **oui** |
| 2006 | `USER_NOT_FOUND` | L'utilisateur n'existe pas | non |
| 2007 | `USER_IS_BLOCKED` | L'utilisateur est bloqué | non |
| 2010 | `FAILED` | Le paiement a échoué | **oui** |
| 2011 | `NOT_ALLOWED` | IP non autorisée | non |

**Quatre statuts finaux seulement**, et la liste surprend : `EXPIRED` n'est pas
final alors qu'on l'attendrait, `INSUFFICIENT_BALANCE` l'est. C'est exactement
pourquoi cette colonne se recopie et ne se devine pas. La table vit dans
`src/momo_xof_mcp/statuses.py`, avec la traduction vers le vocabulaire stable.

Deux enseignements pour la suite :

- **`TRANSACTION_EXIST` (1200) est la réponse à l'idempotence.** Rejouer une
  `merchant_transaction_id` ne crée pas un second paiement, l'API la refuse.
  Reste à l'observer réellement avant de s'en prévaloir.
- **`INSUFFICIENT_BALANCE` parle du solde du MARCHAND**, pas du client. Sur
  une collecte, il ne devrait pas apparaître ; sur un décaissement, si.

### Réponse de succès — exemple de la documentation

```json
{
    "code": 200,
    "status": "OK",
    "merchant_transaction_id": "k0oqli6ns26xyrf",
    "notify_token": "382a2329ae0647f896fa70283fa087cc",
    "transaction_id": "4c9a7225819943fe9f1eab6ef5b573a5",
    "payment_token": "ksjksjd239232938238dj923",
    "payment_url": "https://secure.cinetpay.net/checkout/ksjksjd239232938238dj923",
    "details": {
        "code": 2001,
        "status": "INITIATED",
        "message": "Veuillez cliquer sur le lien pour continuer le paiement",
        "must_be_redirected": true,
        "payment_code": null
    }
}
```

Réponse d'erreur documentée : **`422`** (contenu non relevé).

### Statuts — les seules valeurs attestées

`details.status` prend l'une de ces quatre valeurs, et **aucune autre ne doit
être inventée** :

| Valeur | Sens documenté | Final ? |
|---|---|---|
| `SUCCESS` | l'utilisateur a été débité, paiement réussi | oui |
| `FAILED` | non finalisé, ou erreur opérateur | oui |
| `INITIATED` | paiement en cours de traitement par l'utilisateur | non |
| `PENDING` | paiement toujours en cours de traitement | non |

Codes `details.code` observés : `2001` avec `INITIATED`, `2010` avec `FAILED`.
La correspondance complète code ↔ statut n'est pas relevée.

### Paiement direct

`direct_pay: true` évite la redirection vers la passerelle : le client reste
dans l'application appelante. Exige `client_phone_number`, et `otp_code` pour
Orange. Après initialisation, se fier à `details.must_be_redirected` : si
`true`, rediriger vers `payment_url`.

---

## Conséquences pour `momo_initiate_payment`

À trancher avant d'écrire l'outil. Rien n'est décidé ici.

1. **Trois URL sont obligatoires** — `success_url`, `failed_url`, `notify_url`.
   La v0.1 n'a pas de serveur web. Il faut soit des URL de rebond fournies par
   l'exploitant via la configuration, soit renoncer. `.env.example` disait que
   l'URL de rappel pouvait rester vide : c'est faux, l'API la refuse.
2. **L'identité du client est obligatoire** — `client_email`,
   `client_first_name`, `client_last_name`. Le tour d'un paiement mobile money
   ne se résume donc pas à « un numéro et un montant ». Ces champs devront
   être des paramètres de l'outil, ce qui alourdit sa signature.
3. **Redirection ou paiement direct ?** Un agent MCP ne peut pas ouvrir un
   navigateur. `direct_pay: true` est le seul mode qui a du sens ici, mais il
   impose l'OTP pour Orange — donc un aller-retour supplémentaire avec
   l'utilisateur final, que le protocole MCP devra porter.
4. **`merchant_transaction_id` est la référence d'idempotence** exigée par
   CLAUDE.md. Fournie par l'appelant, jamais générée en silence. Max 30
   caractères : la validation doit le dire.
5. **`payment_method`** (`OM_CI`…) est la clé qui relierait le catalogue de
   `momo_list_operators` aux codes CinetPay. La liste des codes n'est pas
   encore relevée.

## Consultation du statut d'un paiement — **observé le 2026-09-23**

Trois appels réels, sur deux références réellement initiées la veille et une
référence inexistante.

### Paiement initié puis jamais réglé

```json
GET /v1/payment/e2e-16c3f19e37   ->   HTTP 200
{
    "code": 2010,
    "status": "FAILED",
    "merchant_transaction_id": "e2e-16c3f19e37",
    "transaction_id": "daa3dcf52578408f8093c6c55d792bb8",
    "user": null
}
```

Enseignements, aucun n'était devinable :

- Une demande acceptée que personne n'honore finit en **`FAILED` (2010)**,
  pas en `EXPIRED` (2003). Le statut `EXPIRED` existe dans la table mais ce
  n'est pas celui-ci qui sort après abandon du client. `FAILED` est **final**.
- La réponse est **plate** : ni `details`, ni `payment_method`, ni `amount`.
  Les champs de l'exemple de la documentation ne sont donc pas tous garantis.
- `user` vaut `null` hors succès, confirmé sur une transaction terminée.

### Référence inconnue

```json
GET /v1/payment/inexistant-xyz-123   ->   HTTP 422
{
    "code": 404,
    "status": "NOT_FOUND",
    "description": "Not found"
}
```

- **`HTTP 422` avec `code: 404`.** Les deux nombres se contredisent en
  apparence ; c'est `code` qui fait foi, comme partout dans cette API.
- Le champ est `description`, pas `message`, comme pour toutes les erreurs de
  haut niveau.

### Contrat retenu pour `momo_check_payment_status`

```
GET {{baseUrl}}/v1/payment/{merchant_transaction_id}
```

- Le segment d'URL accepte **soit** le `merchant_transaction_id`, soit le
  `transaction_id` rendu à l'initialisation. Deux clés pour la même
  ressource.
- Authentification : `Authorization: Bearer`, comme l'initialisation.

Réponse `200`, cas `SUCCESS` :

```json
{
    "code": 100,
    "status": "SUCCESS",
    "merchant_transaction_id": "MY-ORDER-ID-08082116",
    "transaction_id": "3de579e7ec43451a9463d45d21a4cf48",
    "user": {
        "name": "Doe John",
        "email": "john.doe@gmail.com",
        "phone_number": "+2250707000000"
    },
    "payment_method": "OM"
}
```

### Asymétrie à ne pas manquer

**Le statut est à la RACINE ici**, dans `code` et `status`. Il n'y a pas
d'objet `details`, alors que l'initialisation y loge tout. La même API
répond donc dans deux formes différentes selon l'endpoint, et un code qui
cherche `details` sur cette réponse ne trouvera rien.

Autres points relevés :

- La documentation annonce trois réponses, **toutes en `HTTP 200`** :
  `SUCCESS`, `ERROR`, et `INITIATED` avec `user` à `null`. Le code HTTP ne
  distingue donc rien, ici non plus.
- `user` est un objet, **`null` tant que le client n'a pas payé**. Y accéder
  sans vérifier lèvera.
- `user.phone_number` est en clair. Toute journalisation passe par
  `mask_msisdn`.
- `payment_method` vaut `"OM"` dans l'exemple — un code de méthode de
  paiement, à rapprocher de la page « Méthodes de paiement », pas encore
  relevée.
- Les corps exacts des réponses `ERROR` et `INITIATED` ne sont pas connus :
  seuls leurs intitulés le sont.

## Vérifications effectuées

- **2026-09-22 — `momo_initiate_payment`, chemin nominal, bout en bout.**
  Client MCP réel sur transport stdio, jusqu'à l'API sandbox. Enchaînement
  `/v1/oauth/login` puis `/v1/payment` avec jeton en cache. Réponse
  `details.status = "INITIATED"`, `payment_url` reçue, `merchant_transaction_id`
  renvoyé tel qu'envoyé. Montant 100 XOF, `direct_pay: false`, aucun téléphone
  sollicité, aucun débit.
- **2026-09-23 — `GET /v1/payment/{reference}`, trois cas.** Paiement abandonné
  (FAILED 2010, réponse plate, `user` null) et référence inconnue (HTTP 422,
  code 404, NOT_FOUND). Lecture seule, aucun paiement déclenché.
- **2026-09-22 — les six garde-fous de l'outil.** Plafond dépassé, montant nul,
  référence vide, référence de plus de 30 caractères, numéro invalide,
  argument mal orthographié : tous refusés avant tout appel réseau.

## Encore à relever

- [x] Endpoint d'authentification — `POST /v1/oauth/login`, relevé le 2026-09-21
- [x] Jeton en `Authorization: Bearer` — **confirmé** par la sonde le 2026-09-22
- [ ] Liste des codes de paiement (`payment_method`)
- [x] Corps d'une réponse `422` — relevé (code 2011, NOT_ALLOWED)
- [x] Endpoint de consultation de statut — `GET /v1/payment/{reference}`, **observé**
      le 2026-09-23 sur trois cas réels. Reste à écrire `momo_check_payment_status`.

- [ ] URL de base de production

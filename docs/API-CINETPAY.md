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

### Authentification — INCONNUE, bloquant

La page d'endpoint ne décrit pas l'en-tête d'authentification. Elle indique
seulement :

> Vous disposez d'un compte (`account_key`/`account_password`) dans chaque pays
> pour lequel vous souhaitez traiter. Nous utilisons donc le jeton généré à
> partir de votre `account_key` pour identifier le pays et le fixer sur le
> formulaire de paiement.

Il existe donc un endpoint d'authentification préalable qui rend un jeton, et
ce jeton porte aussi le **pays**. Restent à relever : le chemin de cet
endpoint, la forme de sa requête et de sa réponse, et la manière dont le jeton
est transmis à `/v1/payment` (en-tête `Authorization`, ou champ du corps).

Ne pas écrire `scripts/first_call.py` avant d'avoir cette page.

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

### Réponse de succès — `200`

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

## Encore à relever

- [ ] Endpoint d'authentification : chemin, requête, réponse, transmission du jeton
- [ ] Liste des codes de paiement (`payment_method`)
- [ ] Corps d'une réponse `422`
- [ ] Endpoint de consultation de statut, pour `momo_check_payment_status`
- [ ] URL de base de production

# CLAUDE.md — momo-xof-mcp

## Ce qu'est ce projet

Serveur MCP donnant à un agent l'accès aux paiements mobile money de la zone
franc CFA ouest-africaine (XOF) : Orange Money, Moov Money, Wave, via un
agrégateur.

Il n'existe aucun serveur MCP pour cette zone. `mpesa-mcp` couvre l'Afrique de
l'Est (M-Pesa) et sert de référence de qualité, pas de code à copier.

Mainteneur : SOTECHDI (Ouagadougou, Burkina Faso).

## Stack imposée — ne pas proposer d'alternative

- Python 3.11+
- `mcp` (SDK officiel) avec `FastMCP`
- `pydantic` v2 pour la validation des entrées
- `httpx` en asynchrone pour les appels HTTP
- `python-dotenv` pour la configuration
- Transport : **stdio** uniquement en v0.1
- Pas de base de données en v0.1. Pas de framework web. Pas de Docker.

Nom du serveur : `momo_xof_mcp`.

## Les trois outils de la v0.1 — liste figée

| Outil | Rôle | readOnly |
|---|---|---|
| `momo_list_operators` | Lister les opérateurs et pays supportés | oui |
| `momo_initiate_payment` | Déclencher une demande de paiement (collecte) | non |
| `momo_check_payment_status` | Consulter le statut d'une transaction | oui |

**RÈGLE ABSOLUE : n'ajoute jamais un quatrième outil sans que je le demande
explicitement.** Pas de décaissement, pas de solde, pas de remboursement, pas
d'outil « utilitaire » ou « helper » exposé. Si tu penses qu'un outil manque,
écris-le dans `docs/BACKLOG.md` et continue.

## Règles de travail

1. **Un outil à la fois, un commit par outil.** Jamais « implémente le serveur
   complet ». Si je demande un outil, tu ne touches pas aux autres.
2. **Aucun code d'appel API écrit à l'aveugle.** Avant d'implémenter un appel,
   demande-moi la réponse brute réelle de l'API en sandbox. Je la colle dans le
   contexte. Tu codes à partir de la réponse observée, jamais à partir d'une
   supposition sur la documentation.
3. **Zéro secret dans le dépôt.** Toute clé passe par `.env`, jamais en dur,
   jamais dans un test, jamais dans un exemple de README. Vérifie `.gitignore`
   avant tout commit.
4. **Ne jamais journaliser** un numéro de téléphone complet, une clé d'API ou un
   corps de réponse contenant l'un des deux. Masquer : `+226 76 ** ** 26`.
5. **Pas de dépendance ajoutée** sans me demander.
6. Si une étape te bloque, arrête-toi et pose la question. Ne contourne pas en
   inventant une valeur de test ou en simulant une réponse d'API.

## Conventions de code

- Noms d'outils en `snake_case`, toujours préfixés `momo_`.
- **Paramètres d'outil à plat** dans la signature de la fonction, un argument
  par champ, typés en `Annotated[T, Field(description=..., examples=[...])]`.
  Ne jamais passer un modèle Pydantic comme paramètre unique : FastMCP en fait
  un objet imbriqué et l'appelant doit alors envelopper ses arguments dans
  `{"params": {...}}`. Les modèles Pydantic servent à la validation interne et
  aux structures de sortie, pas de porte d'entrée.
- Description explicite et exemple sur chaque champ, portés par `Field`.
- Annotations MCP renseignées sur chaque outil : `title`, `readOnlyHint`,
  `destructiveHint`, `idempotentHint`, `openWorldHint`.
- Retour des outils : JSON sérialisé en `str`.
- Messages d'erreur **actionnables** : dire ce qui a échoué et quoi faire
  ensuite. `"Numéro invalide"` est insuffisant ; `"Numéro invalide : attendu au
  format E.164 (+226XXXXXXXX) pour le Burkina Faso"` convient.
- Toute fonction d'I/O est `async`.

## Spécificités mobile money à ne pas sous-estimer

- **Numéros** : normaliser en E.164. Chaque pays XOF a son indicatif et sa
  longueur. Écrire cette normalisation en premier, avec des tests.
- **Idempotence** : chaque demande de paiement porte une référence externe
  unique fournie par l'appelant. Ne jamais la générer silencieusement.
- **Asynchronisme** : un paiement n'est pas confirmé par la réponse HTTP. Le
  statut définitif arrive par callback ou par interrogation. `momo_initiate_payment`
  retourne « demande acceptée », jamais « paiement réussi ».
- **Montants** : XOF n'a pas de décimale. Entiers uniquement, jamais de float.
- **Statuts** : ne jamais inventer un statut. Mapper explicitement les valeurs
  réelles de l'agrégateur vers un vocabulaire stable et documenté.

## Sécurité — non négociable

Ce serveur peut déplacer de l'argent réel. En conséquence :

- `momo_initiate_payment` porte `destructiveHint: true` et `readOnlyHint: false`.
- Tant que `MOMO_ENV=sandbox`, refuser tout appel vers un endpoint de production.
- Prévoir un plafond de montant configurable (`MOMO_MAX_AMOUNT`) appliqué côté
  serveur, qui refuse au-delà avec un message clair.
- Aucun test automatisé ne doit déclencher un paiement réel.

## Définition du « terminé » pour la v0.1

- [ ] Les trois outils répondent correctement en sandbox
- [ ] `python -m py_compile` passe sur tout le paquet
- [ ] Test manuel réussi via MCP Inspector
- [ ] `evals/questions.xml` contient 10 questions de test réelles
- [ ] README en anglais, avec GIF de démonstration
- [ ] `.env.example` à jour, `.env` absent du dépôt
- [ ] Licence MIT présente

## Hors périmètre v0.1

Décaissements, remboursements, webhooks entrants, historisation SQLite,
multi-agrégateurs, transport HTTP, interface web. Tout cela va dans
`docs/BACKLOG.md`.

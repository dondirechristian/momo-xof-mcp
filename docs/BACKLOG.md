# Backlog

Tout ce qui est hors périmètre v0.1. Claude Code écrit ici au lieu de coder.

## Décidé, plus tard

- Décaissements (`momo_disburse`) — v0.2
- Second agrégateur en secours — v0.2
- Webhooks entrants pour statut en temps réel — v0.3
- Historisation SQLite des transactions — v0.3
- Transport HTTP pour déploiement distant — v0.3

## Proposé par l'agent, à arbitrer

<!-- Format : date — outil ou fonctionnalité — justification en une ligne -->

- 2026-09-18 — ~~élargir le catalogue aux opérateurs hors périmètre~~ —
  **tranché** : `payment_services` liste désormais les services réellement
  présents dans chaque pays (MTN MoMo, Celtiis Cash, T-Money, Free Money,
  E-Money, Airtel Money inclus). Le périmètre des trois outils reste figé.
- 2026-09-18 — normalisation E.164 des numéros — prévue par CLAUDE.md « écrire
  en premier, avec des tests », mais hors du périmètre demandé pour cet outil ;
  à écrire avant `momo_initiate_payment`, en s'appuyant sur les longueurs
  nationales déjà présentes dans `operators.py`.

## Dette technique — à traiter avant `momo_initiate_payment`

- ~~**Migration SDK 2.x.**~~ **Faite le 2026-09-19**, sur `mcp` 2.2.0.
  `pyproject.toml` déclare désormais `mcp>=2.2,<3` — la borne basse est celle
  réellement testée, pas `>=2.0` dont l'API n'a pas été vérifiée. Changements
  appliqués : `FastMCP` → `MCPServer` (`mcp.server.mcpserver`), `inputSchema`
  → `input_schema`, `call_tool` prend un `context` et rend un `CallToolResult`.
  Le piège non évident : **une exception quelconque est maintenant traitée
  comme un crash et son message est retiré de la réponse.** Tous les messages
  actionnables passent donc par `ToolError` — consigne ajoutée aux conventions
  de CLAUDE.md. `mcp.server.fastmcp` subsiste en 2.x comme un module qui lève
  un `ModuleNotFoundError` explicite pointant vers le guide de migration.

- **MCP Inspector en échec.** Timeout de 30 s au handshake, alors que le serveur
  répond correctement en JSON-RPC direct sur stdin. Cause probable : l'espace
  dans le chemin `C:\dev\Projet MCP`. À revérifier une fois le projet déplacé
  dans un dossier `momo-xof-mcp`. Sans gravité : les tests passent en ligne de
  commande.

- ~~**`extra='forbid'` perdu.**~~ **Réglé le 2026-09-19.** Le modèle
  d'arguments généré par le SDK hérite d'`ArgModelBase`, dont la config
  Pydantic laisse `extra` à « ignore » : `{"pays": "BF"}` renvoyait le
  catalogue complet avec `isError=False`. `_StrictArgsMCPServer` dans
  `server.py` refuse désormais tout argument inconnu avant exécution, et
  annonce `additionalProperties: false` dans le schéma publié. Vaut pour tous
  les outils, y compris ceux à venir.

## Compte CinetPay — à durcir avant la mise en production

Constaté sur le tableau de bord sandbox le 2026-09-21. Sans urgence tant
qu'on reste en sandbox, bloquant avant tout passage en production.

- **IP dynamique contre liste blanche — bloquant à l'usage.** Mesuré le
  2026-09-22 : l'adresse publique du poste est passée de `105.235.191.52` à
  `197.239.96.186` **en une vingtaine de minutes**. Chaque changement
  réintroduit le `2011 / NOT_ALLOWED`. Développer depuis cette connexion
  suppose de remettre l'IP à jour sans cesse. Trois sorties possibles :
  demander à CinetPay si la liste blanche peut être désactivée en sandbox ;
  déployer depuis une machine à IP fixe, VPS ou serveur de l'entreprise ;
  passer par un tunnel sortant à adresse stable. À trancher avant d'aller
  plus loin dans les tests d'intégration, sinon chaque séance commencera par
  dix minutes de tableau de bord.

- ~~**Liste blanche IP vide.**~~ **Corrigé par l'observation le 2026-09-22.**
  Le tableau de bord affirme « Aucune IP configurée. L'API est accessible
  depuis n'importe quelle IP ». C'est faux : le premier appel réel a été
  refusé par un `422` / `code 2011` / `NOT_ALLOWED`. Une liste vide refuse
  tout. La liste blanche n'est donc pas un durcissement optionnel à prévoir
  pour la production, c'est un **prérequis de fonctionnement**, dès la
  sandbox. Point de vigilance : sur une connexion à IP dynamique, l'entrée
  devient caduque au changement d'adresse et l'erreur réapparaît.
- **Mot de passe API non configuré.** Sans effet si l'initialisation de
  paiement n'en a pas besoin. À vérifier lors de l'écriture de la sonde : si
  le flux de collecte passe par un jeton OAuth, c'est un prérequis.
- **Plafonds du compte** : 1 000 000 F CFA/jour, 5 000 000 F CFA/mois.
  `MOMO_MAX_AMOUNT` vaut 50 000 dans `.env.example`, soit un garde-fou serveur
  vingt fois plus strict que celui de l'agrégateur. Valeur finale à arbitrer.

## Questions ouvertes

- ~~Quel agrégateur en défaut : CinetPay ou PayDunya ?~~ **Tranché le
  2026-09-21 : CinetPay.** Compte sandbox SOTECHDI (Burkina Faso) créé et
  actif, 0 transaction à ce stade. `MOMO_PROVIDER=cinetpay` était déjà la
  valeur par défaut de `.env.example`. PayDunya reste le candidat pour le
  second agrégateur de secours prévu en v0.2.
- Wave passe-t-il par l'agrégateur ou nécessite-t-il une intégration directe ?
- ~~**Quelle API CinetPay exactement ?**~~ **Hôte tranché le 2026-09-21** par
  le tableau de bord : `https://api.cinetpay.net`, sandbox, version
  **« 1.0 Aurore »**. Ce n'est donc pas `api-checkout.cinetpay.com/v2`.
  Endpoint de collecte, champs et réponse **relevés le 2026-09-21** et
  consignés dans `docs/API-CINETPAY.md` : `POST /v1/payment`.
  **Reste bloquant : l'authentification.** La page d'endpoint n'en dit rien,
  sinon qu'un jeton est « généré à partir de votre `account_key` » et qu'il
  porte aussi le pays. Il existe donc un endpoint d'authentification non
  relevé. Ne pas écrire `scripts/first_call.py` avant de l'avoir lu.
- **URL de production inconnue.** Seule la base sandbox est connue. À relever
  avant tout passage en production, et à croiser avec la règle « refuser un
  endpoint de production tant que `MOMO_ENV=sandbox` ».
- Les numéros de test sandbox sont-ils les mêmes pour les huit pays ?
- Plans de numérotation encore à récupérer auprès des régulateurs : Bénin,
  Guinée-Bissau, Mali, Niger, Togo. `prefix_hints.confidence` vaut `none` et la
  table est vide pour ces cinq pays — on n'invente rien. Seuls le Burkina
  (ARCEP, plan du 4 mai 2023) et la Côte d'Ivoire (plan du 31 janvier 2021)
  sont renseignés en `high`.
- Sénégal : volontairement laissé sans préfixes. L'ARTP alloue par tranches de
  3 à 4 chiffres et la portabilité existe depuis 2015 ; un mapping à 2 chiffres
  produirait des faux positifs. À ne rouvrir qu'avec les tranches complètes.


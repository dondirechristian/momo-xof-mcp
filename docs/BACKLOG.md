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

- **Liste blanche IP vide.** Le tableau de bord indique « L'API est accessible
  depuis n'importe quelle IP ». Acceptable en sandbox depuis un poste de
  développement à IP dynamique. En production, la clé seule devient le seul
  facteur : restreindre aux IP du serveur.
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
  Reste inconnu, et toujours bloquant pour `scripts/first_call.py` :
  - le chemin exact de l'endpoint de collecte ;
  - le schéma d'authentification — la page « API & sécurité » expose une clé
    API **et** un mot de passe API, ce qui laisse ouverte l'hypothèse d'un
    jeton OAuth préalable ;
  - les noms exacts des champs du corps et la forme de la réponse.
  « 1.0 Aurore » est une génération récente : aucune source publique fiable
  ne la décrit. Ne rien écrire tant que la page d'endpoint n'a pas été lue.
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


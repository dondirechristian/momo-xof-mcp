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

## Questions ouvertes

- Quel agrégateur en défaut : CinetPay ou PayDunya ?
- Wave passe-t-il par l'agrégateur ou nécessite-t-il une intégration directe ?
- Les numéros de test sandbox sont-ils les mêmes pour les huit pays ?
- Plans de numérotation encore à récupérer auprès des régulateurs : Bénin,
  Guinée-Bissau, Mali, Niger, Togo. `prefix_hints.confidence` vaut `none` et la
  table est vide pour ces cinq pays — on n'invente rien. Seuls le Burkina
  (ARCEP, plan du 4 mai 2023) et la Côte d'Ivoire (plan du 31 janvier 2021)
  sont renseignés en `high`.
- Sénégal : volontairement laissé sans préfixes. L'ARTP alloue par tranches de
  3 à 4 chiffres et la portabilité existe depuis 2015 ; un mapping à 2 chiffres
  produirait des faux positifs. À ne rouvrir qu'avec les tranches complètes.


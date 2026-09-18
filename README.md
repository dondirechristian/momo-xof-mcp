# momo-xof-mcp

**MCP server for West African mobile money (XOF zone).**
Give your AI agent the ability to initiate and track mobile money payments
across Orange Money, Moov Money and Wave in the eight UEMOA countries.

> Status: v0.1 in development. Sandbox only. Do not use against production
> credentials yet.

<!-- TODO: insérer ici le GIF de démonstration avant la première publication -->

## Why this exists

Mobile money is how most of West Africa pays. Dozens of SDKs exist for these
APIs in PHP, Node, Python and Flutter — but no MCP server. An agent built today
cannot request a payment in XOF without custom integration work.

`momo-xof-mcp` closes that gap for the franc CFA zone. (For East Africa,
see `mpesa-mcp`, which covers M-Pesa and Africa's Talking.)

Countries in scope: Benin, Burkina Faso, Côte d'Ivoire, Guinea-Bissau, Mali,
Niger, Senegal, Togo.

## Tools

| Tool | Description |
|---|---|
| `momo_list_operators` | List supported operators and countries |
| `momo_initiate_payment` | Request a payment from a customer's mobile wallet |
| `momo_check_payment_status` | Check the status of a payment request |

`momo_initiate_payment` requests a payment; it does not confirm one. Final
status arrives asynchronously — always poll with `momo_check_payment_status`.

## Install

```bash
pip install momo-xof-mcp
```

Claude Desktop / Claude Code configuration:

```json
{
  "mcpServers": {
    "momo-xof": {
      "command": "python",
      "args": ["-m", "momo_xof_mcp"],
      "env": {
        "MOMO_ENV": "sandbox",
        "MOMO_PROVIDER": "cinetpay"
      }
    }
  }
}
```

Credentials go in `.env`. See `.env.example`.

## Safety

This server can move real money. It ships with:

- a server-side amount ceiling (`MOMO_MAX_AMOUNT`)
- a sandbox lock that refuses production endpoints while `MOMO_ENV=sandbox`
- caller-supplied idempotency references on every payment request
- masked logging: no full phone numbers, no keys

## Roadmap

v0.2 — disbursements, additional aggregators.
v0.3 — inbound webhooks, transaction history.

## Licence

MIT. Built by [SOTECHDI](https://sotechdi.bf), Ouagadougou, Burkina Faso.

---

## Français

Serveur MCP pour le mobile money en zone franc CFA (XOF) : Orange Money, Moov
Money et Wave dans les huit pays de l'UEMOA. Trois outils — lister les
opérateurs, initier un paiement, consulter un statut. Version 0.1 en sandbox
uniquement. Documentation complète en anglais ci-dessus.

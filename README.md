# momo-xof-mcp

**MCP server for West African mobile money (XOF zone).**
Give your AI agent the ability to initiate and track mobile money payments
across the major mobile money operators in the eight UEMOA countries.

> Status: v0.1. All three tools work against the CinetPay sandbox. Sandbox
> only — the production base URL has not been established yet, and the server
> refuses any non-sandbox endpoint while `MOMO_ENV=sandbox`.

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

## Usage

Ask for a payment. The response below is a real sandbox response, trimmed:

```json
{
  "status": "accepted",
  "is_final": false,
  "provider_status": "INITIATED",
  "merchant_reference": "CMD-2026-0042",
  "transaction_id": "69fe371559c34c6f98971be5c8f4e4df",
  "payment_url": "https://secure.cinetpay.net/checkout/1f1b6850f7e1...",
  "what_this_means": "The payment has been REQUESTED, not completed.
                      No money has moved yet."
}
```

Send the customer to `payment_url`. Later, check what became of it — with
your own reference or the returned `transaction_id`, both work:

```json
{
  "status": "failed",
  "is_final": true,
  "provider_status": "FAILED",
  "merchant_reference": "CMD-2026-0042",
  "customer": null,
  "what_this_means": "This payment will not complete. The outcome is final."
}
```

## Four things that will bite you

These are not hypothetical. Each one cost us a debugging session against the
live sandbox, and each is now enforced in code.

**A successful call is not a successful payment.** `momo_initiate_payment`
returning `"accepted"` means the aggregator took the request. The customer has
not paid. Nothing has moved. Treat `payment_url` as an invitation, not a
receipt.

**An abandoned payment ends up `failed`, and that is final.** It does not
linger in a pending state waiting for the customer to come back. An agent that
polls until it sees something other than "pending" will poll forever. Read
`is_final`.

**Retrying with the same reference is safe.** The aggregator refuses to create
a second payment for a reference it already knows, so a retry after a network
timeout cannot double-charge. You will get an error, not a duplicate — call
`momo_check_payment_status` with that reference to learn what happened to the
first attempt.

**Number prefixes do not identify a payment service.** Wave runs on any
national number and owns no prefix range at all. Portability breaks
prefix-to-operator mapping anyway. `momo_list_operators` returns prefix hints
for input validation only; the aggregator decides the real routing.

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
        "MOMO_ENV": "sandbox"
      }
    }
  }
}
```

Credentials go in `.env`. See `.env.example`.

Installing the package also provides a `momo-xof-mcp` console script, which
starts the same stdio server with no arguments.

## Testing with MCP Inspector

Use the **console script**, not `python -m momo_xof_mcp`:

```bash
npx @modelcontextprotocol/inspector --cli /path/to/venv/bin/momo-xof-mcp \
  --method tools/list
```

The Inspector does not forward arguments to the program it launches. Point it
at `python` with `-m momo_xof_mcp` and Python starts with no script, drops into
REPL mode, reads the JSON-RPC handshake from stdin and tries to evaluate it as
Python — you get `NameError: name 'true' is not defined` and then a handshake
timeout. The console script takes no arguments, so the problem disappears.

MCP clients such as Claude Desktop pass arguments correctly, so the
`python -m momo_xof_mcp` form above is fine for them.

## Configuration

| Variable | Required | Notes |
|---|---|---|
| `MOMO_API_KEY` | yes | CinetPay API key |
| `MOMO_API_PASSWORD` | yes | Set it on the dashboard first — it is unset by default |
| `MOMO_CALLBACK_URL` | yes | The aggregator rejects a payment without it |
| `MOMO_SUCCESS_URL` | yes | Max 120 characters |
| `MOMO_FAILED_URL` | yes | Max 120 characters |
| `MOMO_ENV` | no | `sandbox` (default) or `production` |
| `MOMO_BASE_URL` | no | Defaults to the sandbox host |
| `MOMO_MAX_AMOUNT` | no | Server-side ceiling in whole XOF, default 50000 |
| `MOMO_TIMEOUT` | no | Seconds, default 30 |

**Whitelist your server's public IP** on the CinetPay dashboard, under
*API & sécurité → Liste Blanche IP*. The dashboard claims an empty whitelist
means "accessible from any IP". It does not: an empty whitelist rejects every
call. If you develop from a dynamic IP, expect to update this often, or ask
CinetPay support to lift it for your sandbox account.

## Safety

This server can move real money. It ships with:

- a server-side amount ceiling (`MOMO_MAX_AMOUNT`), enforced before any
  network call
- a sandbox lock that refuses any non-sandbox endpoint while `MOMO_ENV=sandbox`
- caller-supplied idempotency references, never generated for you
- unknown arguments rejected rather than silently ignored, so a mistyped field
  on a payment request fails loudly instead of falling back to a default
- explicit status mapping: an aggregator status this server does not recognise
  raises, rather than being rounded to the nearest plausible one
- masked phone numbers, in logs and in tool output alike
- amounts as whole integers only — the CFA franc has no decimal subunit

## Roadmap

v0.2 — disbursements, additional aggregators.
v0.3 — inbound webhooks, transaction history.

## Licence

MIT. Built by [SOTECHDI](https://sotechdi.bf), Ouagadougou, Burkina Faso.

---

## Français

Serveur MCP pour le mobile money en zone franc CFA (XOF) : les principaux
opérateurs des huit pays de l'UEMOA. Trois outils — lister les
opérateurs, initier un paiement, consulter un statut. Version 0.1, les trois
outils répondent en sandbox. Documentation complète en anglais ci-dessus.

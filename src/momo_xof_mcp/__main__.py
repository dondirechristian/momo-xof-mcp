"""Point d'entrée : démarre le serveur MCP sur le transport stdio.

    python -m momo_xof_mcp

Le transport stdio réserve stdout au protocole MCP. Ne rien y écrire : tout
message de diagnostic doit partir sur stderr.
"""

from __future__ import annotations

from dotenv import load_dotenv

from .server import mcp


def main() -> None:
    """Charge la configuration depuis .env puis sert sur stdio."""
    # override=False : les variables déjà présentes dans l'environnement du
    # client MCP (bloc "env" de la configuration) l'emportent sur le .env local.
    load_dotenv(override=False)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

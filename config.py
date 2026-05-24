"""Credentials Plex partagés (~/.config/plex-tools/config.toml) et helpers API."""

import sys
import tomllib
from pathlib import Path

SHARED_CONFIG_PATH = Path.home() / ".config" / "plex-tools" / "config.toml"


def load_credentials() -> tuple[str, str]:
    """Retourne (base_url, token) depuis le fichier de config partagé."""
    if not SHARED_CONFIG_PATH.exists():
        print(
            f"Fichier de configuration introuvable : {SHARED_CONFIG_PATH}\n"
            f"Créez-le avec :\n\n"
            f"  mkdir -p ~/.config/plex-tools\n"
            f"  cat > ~/.config/plex-tools/config.toml << 'EOF'\n"
            f"  [plex]\n"
            f'  url = "http://localhost:32400"\n'
            f'  token = "votre-token-ici"\n'
            f"  EOF\n"
            f"  chmod 600 ~/.config/plex-tools/config.toml",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(SHARED_CONFIG_PATH, "rb") as f:
        data = tomllib.load(f)

    plex = data.get("plex", {})
    url = plex.get("url")
    token = plex.get("token")

    if not url or not token:
        print(
            f"Clés 'url' et 'token' requises dans [plex] de {SHARED_CONFIG_PATH}",
            file=sys.stderr,
        )
        sys.exit(1)

    return url.rstrip("/"), token


def plex_headers(token: str) -> dict:
    """Headers standard pour les requêtes API Plex."""
    return {
        "Accept": "application/json",
        "X-Plex-Token": token,
    }

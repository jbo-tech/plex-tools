"""Credentials Plex partagés (~/.config/plex-tools/config.toml) et helpers API."""

import re
import sys
import unicodedata
import tomllib
from pathlib import Path

import requests

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


def normalize_text(text: str | None) -> str:
    """Normalise pour le matching : NFC, lowercase, espaces condensés, strip."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def plex_headers(token: str) -> dict:
    """Headers standard pour les requêtes API Plex."""
    return {
        "Accept": "application/json",
        "X-Plex-Token": token,
    }


def resolve_playlist(base_url: str, token: str, identifier: str) -> dict | None:
    """Résout une playlist par ratingKey (si numérique) ou par nom exact. Retourne le dict ou None."""
    headers = plex_headers(token)
    resp = requests.get(f"{base_url}/playlists", headers=headers)
    resp.raise_for_status()
    playlists = resp.json()["MediaContainer"].get("Metadata", [])

    if identifier.isdigit():
        for pl in playlists:
            if str(pl.get("ratingKey")) == identifier:
                return pl

    for pl in playlists:
        if pl.get("title") == identifier:
            return pl
    return None


def get_all_playlists(base_url: str, token: str) -> list[dict]:
    """Récupère toutes les playlists audio du serveur."""
    headers = plex_headers(token)
    resp = requests.get(f"{base_url}/playlists", headers=headers)
    resp.raise_for_status()
    playlists = resp.json()["MediaContainer"].get("Metadata", [])
    return [pl for pl in playlists if pl.get("playlistType") == "audio"]


def get_playlist_items(base_url: str, token: str, playlist_key: str) -> list[dict]:
    """Récupère les tracks d'une playlist par sa ratingKey."""
    headers = plex_headers(token)
    resp = requests.get(f"{base_url}/playlists/{playlist_key}/items", headers=headers)
    resp.raise_for_status()
    return resp.json()["MediaContainer"].get("Metadata", [])


# --- Helpers d'écriture Plex (partagés par rebuild et adder) ---


def get_machine_id(base_url: str, token: str) -> str:
    """Récupère le machineIdentifier du serveur Plex."""
    headers = plex_headers(token)
    resp = requests.get(f"{base_url}/", headers=headers)
    resp.raise_for_status()
    return resp.json()["MediaContainer"]["machineIdentifier"]


def build_playlist_uri(machine_id: str, rating_keys) -> str:
    """Construit l'URI Plex pour ajouter des tracks à une playlist."""
    if isinstance(rating_keys, set):
        keys_csv = ",".join(sorted(rating_keys))
    else:
        keys_csv = ",".join(rating_keys)
    return f"server://{machine_id}/com.plexapp.plugins.library/library/metadata/{keys_csv}"


def create_playlist(base_url: str, token: str, title: str, machine_id: str, rating_keys) -> None:
    """Crée une nouvelle playlist audio."""
    headers = plex_headers(token)
    uri = build_playlist_uri(machine_id, rating_keys)
    resp = requests.post(
        f"{base_url}/playlists",
        headers=headers,
        params={"type": "audio", "title": title, "smart": 0, "uri": uri},
    )
    resp.raise_for_status()


def add_tracks_to_playlist(base_url: str, token: str, playlist_key: str, machine_id: str, rating_keys) -> None:
    """Ajoute des tracks à une playlist existante."""
    headers = plex_headers(token)
    uri = build_playlist_uri(machine_id, rating_keys)
    resp = requests.put(
        f"{base_url}/playlists/{playlist_key}/items",
        headers=headers,
        params={"uri": uri},
    )
    resp.raise_for_status()

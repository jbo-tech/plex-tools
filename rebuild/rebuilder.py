"""Reconstruction des playlists via l'API HTTP Plex (mode incrémental)."""

import requests
from config import plex_headers
from .reconciler import MatchResult


def rebuild_playlist(
    base_url: str,
    token: str,
    title: str,
    matches: list[MatchResult],
    dry_run: bool = True,
) -> dict:
    """Reconstruit une playlist. Mode incrémental : n'ajoute que les tracks manquantes."""
    headers = plex_headers(token)
    resolved = [m for m in matches if m.matched_track is not None]
    unresolved = [m for m in matches if m.matched_track is None]
    resolved_keys = {str(m.matched_track["ratingKey"]) for m in resolved}

    existing = _find_playlist(base_url, headers, title)
    if existing:
        existing_keys = _get_playlist_track_keys(base_url, headers, existing["ratingKey"])
    else:
        existing_keys = set()

    already_present = resolved_keys & existing_keys
    to_add = resolved_keys - existing_keys

    result = {
        "title": title,
        "total": len(matches),
        "resolved": len(resolved),
        "unresolved": len(unresolved),
        "already_present": len(already_present),
        "to_add": len(to_add),
        "created": False,
        "updated": False,
    }

    if not resolved:
        result["skipped"] = True
        result["reason"] = "aucune track résolue"
        return result

    if existing and not to_add:
        result["skipped"] = True
        result["reason"] = "toutes les tracks sont déjà présentes"
        return result

    if dry_run:
        return result

    machine_id = _get_machine_id(base_url, headers)

    if existing:
        _add_tracks_to_playlist(base_url, headers, existing["ratingKey"], machine_id, to_add)
        result["updated"] = True
    else:
        _create_playlist(base_url, headers, title, machine_id, resolved_keys)
        result["created"] = True

    return result


def _find_playlist(base_url: str, headers: dict, title: str) -> dict | None:
    """Cherche une playlist par titre exact."""
    resp = requests.get(f"{base_url}/playlists", headers=headers)
    resp.raise_for_status()
    playlists = resp.json()["MediaContainer"].get("Metadata", [])
    for pl in playlists:
        if pl.get("title") == title:
            return pl
    return None


def _get_playlist_track_keys(base_url: str, headers: dict, playlist_key: str) -> set[str]:
    """Récupère les ratingKeys des tracks d'une playlist existante."""
    resp = requests.get(f"{base_url}/playlists/{playlist_key}/items", headers=headers)
    resp.raise_for_status()
    items = resp.json()["MediaContainer"].get("Metadata", [])
    return {str(item["ratingKey"]) for item in items}


def _create_playlist(
    base_url: str, headers: dict, title: str, machine_id: str, rating_keys: set[str],
) -> None:
    """Crée une nouvelle playlist."""
    uri = _build_uri(machine_id, rating_keys)
    resp = requests.post(
        f"{base_url}/playlists",
        headers=headers,
        params={"type": "audio", "title": title, "smart": 0, "uri": uri},
    )
    resp.raise_for_status()


def _add_tracks_to_playlist(
    base_url: str, headers: dict, playlist_key: str, machine_id: str, rating_keys: set[str],
) -> None:
    """Ajoute des tracks manquantes à une playlist existante."""
    uri = _build_uri(machine_id, rating_keys)
    resp = requests.put(
        f"{base_url}/playlists/{playlist_key}/items",
        headers=headers,
        params={"uri": uri},
    )
    resp.raise_for_status()


def _build_uri(machine_id: str, rating_keys: set[str]) -> str:
    keys_csv = ",".join(sorted(rating_keys))
    return f"server://{machine_id}/com.plexapp.plugins.library/library/metadata/{keys_csv}"


def _get_machine_id(base_url: str, headers: dict) -> str:
    """Récupère le machineIdentifier du serveur Plex."""
    resp = requests.get(f"{base_url}/", headers=headers)
    resp.raise_for_status()
    return resp.json()["MediaContainer"]["machineIdentifier"]

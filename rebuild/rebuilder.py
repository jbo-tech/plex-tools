"""Reconstruction des playlists via l'API HTTP Plex (mode incrémental)."""

from config import (
    plex_headers,
    get_playlist_items,
    get_machine_id,
    build_playlist_uri,
    create_playlist,
    add_tracks_to_playlist,
)
from .reconciler import MatchResult


def rebuild_playlist(
    base_url: str,
    token: str,
    title: str,
    matches: list[MatchResult],
    dry_run: bool = True,
) -> dict:
    """Reconstruit une playlist. Mode incrémental : n'ajoute que les tracks manquantes."""
    resolved = [m for m in matches if m.matched_track is not None]
    unresolved = [m for m in matches if m.matched_track is None]
    resolved_keys = {str(m.matched_track["ratingKey"]) for m in resolved}

    existing = _find_playlist(base_url, token, title)
    if existing:
        items = get_playlist_items(base_url, token, str(existing["ratingKey"]))
        existing_keys = {str(item["ratingKey"]) for item in items}
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

    machine_id = get_machine_id(base_url, token)

    if existing:
        add_tracks_to_playlist(base_url, token, str(existing["ratingKey"]), machine_id, to_add)
        result["updated"] = True
    else:
        create_playlist(base_url, token, title, machine_id, resolved_keys)
        result["created"] = True

    return result


def _find_playlist(base_url: str, token: str, title: str) -> dict | None:
    """Cherche une playlist par titre exact."""
    import requests

    headers = plex_headers(token)
    resp = requests.get(f"{base_url}/playlists", headers=headers)
    resp.raise_for_status()
    playlists = resp.json()["MediaContainer"].get("Metadata", [])
    for pl in playlists:
        if pl.get("title") == title:
            return pl
    return None

"""Reconstruction des playlists via l'API HTTP Plex."""

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
    """Recrée une playlist. En dry_run, retourne uniquement le rapport."""
    resolved = [m for m in matches if m.matched_track is not None]
    unresolved = [m for m in matches if m.matched_track is None]

    result = {
        "title": title,
        "total": len(matches),
        "resolved": len(resolved),
        "unresolved": len(unresolved),
        "created": False,
    }

    if not resolved:
        result["skipped"] = True
        result["reason"] = "aucune track résolue"
        return result

    if dry_run:
        return result

    headers = plex_headers(token)
    rating_keys = [m.matched_track["ratingKey"] for m in resolved]
    machine_id = _get_machine_id(base_url, headers)

    resp = requests.post(
        f"{base_url}/playlists",
        headers=headers,
        params={
            "type": "audio",
            "title": title,
            "smart": 0,
            "uri": f"server://{machine_id}/com.plexapp.plugins.library/library/metadata/{','.join(str(k) for k in rating_keys)}",
        },
    )
    resp.raise_for_status()
    result["created"] = True
    return result


def _get_machine_id(base_url: str, headers: dict) -> str:
    """Récupère le machineIdentifier du serveur Plex."""
    resp = requests.get(f"{base_url}/", headers=headers)
    resp.raise_for_status()
    return resp.json()["MediaContainer"]["machineIdentifier"]

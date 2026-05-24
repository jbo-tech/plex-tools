"""Application des corrections de métadonnées via l'API Plex."""

import sys
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from config import plex_headers

DELAY_BETWEEN_CALLS = 0.05  # 50ms


def _session_with_retry() -> requests.Session:
    """Session HTTP avec retry automatique sur erreurs transitoires."""
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def apply_fixes(base_url: str, token: str, fixes: dict, *, refresh: bool = True, delay: float = DELAY_BETWEEN_CALLS) -> dict:
    """Applique les corrections via PUT /library/metadata/{ratingKey}.

    Si refresh=True, déclenche un refresh metadata sur chaque album corrigé
    pour que Plex ré-enrichisse depuis ses sources en ligne.
    """
    headers = plex_headers(token)
    session = _session_with_retry()
    stats = {"albums_fixed": 0, "tracks_fixed": 0, "albums_refreshed": 0, "errors": 0}

    # --- Albums ---
    total_albums = len(fixes["albums"])
    for i, album in enumerate(fixes["albums"], 1):
        params = {"title.value": album["new_title"], "title.locked": "1"}
        try:
            resp = session.put(
                f"{base_url}/library/metadata/{album['ratingKey']}",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            stats["albums_fixed"] += 1

            if refresh:
                time.sleep(delay)
                session.put(
                    f"{base_url}/library/metadata/{album['ratingKey']}/refresh",
                    headers=headers,
                )
                stats["albums_refreshed"] += 1
        except requests.RequestException as e:
            print(f"  ERREUR album {album['ratingKey']}: {e}", file=sys.stderr)
            stats["errors"] += 1

        if i % 100 == 0 or i == total_albums:
            print(f"  Albums : {i}/{total_albums}")
        time.sleep(delay)

    # --- Tracks ---
    total_tracks = len(fixes["tracks"])
    refreshed_parents = set()
    for i, track in enumerate(fixes["tracks"], 1):
        params = {}
        if track["new_title"]:
            params["title.value"] = track["new_title"]
            params["title.locked"] = "1"
        if track["new_index"] is not None:
            params["index.value"] = str(track["new_index"])
            params["index.locked"] = "1"

        if not params:
            continue

        try:
            resp = session.put(
                f"{base_url}/library/metadata/{track['ratingKey']}",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            stats["tracks_fixed"] += 1

            parent_key = track.get("parent_ratingKey")
            if refresh and parent_key and parent_key not in refreshed_parents:
                time.sleep(delay)
                session.put(
                    f"{base_url}/library/metadata/{parent_key}/refresh",
                    headers=headers,
                )
                refreshed_parents.add(parent_key)
        except requests.RequestException as e:
            print(f"  ERREUR track {track['ratingKey']}: {e}", file=sys.stderr)
            stats["errors"] += 1

        if i % 500 == 0 or i == total_tracks:
            print(f"  Tracks : {i}/{total_tracks}")
        time.sleep(delay)

    if refresh:
        print(f"  Refresh déclenché sur {stats['albums_refreshed']} albums + {len(refreshed_parents)} albums parents de tracks")

    return stats

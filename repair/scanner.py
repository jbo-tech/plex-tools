"""Scan de la bibliothèque Plex pour détecter les métadonnées manquantes."""

import os
import re
from collections import defaultdict

import requests
from config import plex_headers


def _find_section_key(base_url: str, headers: dict, library_name: str) -> str:
    resp = requests.get(f"{base_url}/library/sections", headers=headers)
    resp.raise_for_status()
    for s in resp.json()["MediaContainer"]["Directory"]:
        if s["title"] == library_name:
            return s["key"]
    available = [s["title"] for s in resp.json()["MediaContainer"]["Directory"]]
    raise ValueError(f"Bibliothèque '{library_name}' introuvable. Disponibles : {available}")


def _get_filepath(track: dict) -> str:
    for media in track.get("Media", []):
        for part in media.get("Part", []):
            return part.get("file", "")
    return ""


def _extract_prefix(filepath: str) -> str | None:
    """Extrait le préfixe numérique du nom de fichier."""
    name = os.path.splitext(os.path.basename(filepath))[0]
    m = re.match(r"^(\d+)\b", name)
    return m.group(1) if m else None


def _is_disc_track(prefixes: list[str], n_digits: int) -> bool:
    """Détermine si les préfixes à n_digits suivent le pattern disc+track.

    Logique : grouper par "numéro de disque" (premier(s) chiffre(s)).
    Si plusieurs groupes existent et que les numéros de piste redémarrent
    près de 01 dans chaque groupe → disc+track.
    Si un seul groupe → disc+track (un seul disque).
    Si le "disque" est 0 ou 00 → index brut (pas de disque 0).
    """
    if not prefixes:
        return True

    if n_digits == 3:
        disc_len = 1
    elif n_digits == 4:
        disc_len = 2
    else:
        return True

    groups = defaultdict(list)
    for p in prefixes:
        disc = p[:disc_len]
        track = int(p[disc_len:])
        groups[disc].append(track)

    # Disc "0" ou "00" n'existe pas → c'est un index brut
    zero_disc = "0" * disc_len
    if zero_disc in groups:
        return False

    if len(groups) > 1:
        return all(min(tracks) <= 2 for tracks in groups.values())

    # Un seul groupe → disc+track par défaut
    return True


def _detect_overflow(by_len: dict[int, list[str]]) -> str | None:
    """Détecte le cas d'overflow : 3 chiffres → 4 chiffres dans le même album.

    Quand un disc a plus de 99 tracks, la numérotation déborde :
      disc 1 tracks 01-99 → '101'-'199' (3 chiffres)
      disc 1 tracks 100+  → '1100'-'1260' (4 chiffres, même préfixe disc)

    Retourne le chiffre de disc en overflow, ou None.
    """
    three = by_len.get(3, [])
    four = by_len.get(4, [])
    if not three or not four:
        return None

    groups_3 = defaultdict(list)
    for p in three:
        groups_3[p[0]].append(int(p[1:]))

    for disc, tracks in groups_3.items():
        if max(tracks) < 90:
            continue
        # Ce disc atteint 90+, vérifier si les 4-chiffres commencent par le même digit
        four_same_disc = [p for p in four if p[0] == disc]
        if four_same_disc:
            return disc

    return None


def _build_album_index_map(tracks_needing_index: list[dict]) -> dict[str, int | None]:
    """Analyse les noms de fichier par album pour extraire les bons index.

    Regroupe les tracks par album, détecte le pattern de numérotation
    (disc+track vs index brut vs overflow), puis extrait l'index approprié.
    """
    # Grouper les filepaths par album
    album_files: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for track in tracks_needing_index:
        parent_key = track.get("parentRatingKey", "unknown")
        filepath = _get_filepath(track)
        if not filepath:
            continue
        prefix = _extract_prefix(filepath)
        if prefix:
            album_files[parent_key].append((filepath, prefix))

    result: dict[str, int | None] = {}

    for _parent_key, entries in album_files.items():
        # Séparer par longueur de préfixe
        by_len: dict[int, list[str]] = defaultdict(list)
        for _fp, prefix in entries:
            by_len[len(prefix)].append(prefix)

        # Détecter l'overflow (3→4 chiffres dans le même album)
        overflow_disc = _detect_overflow(by_len)

        # Déterminer le pattern pour chaque longueur
        patterns: dict[int, bool] = {}
        for n, pfxs in by_len.items():
            if n in (3, 4):
                patterns[n] = _is_disc_track(pfxs, n)

        for filepath, prefix in entries:
            n = len(prefix)
            if n <= 2:
                result[filepath] = int(prefix)
            elif n == 4 and overflow_disc and prefix[0] == overflow_disc:
                # Overflow : '1100' → strip disc digit → '100' → track 100
                result[filepath] = int(prefix[1:])
            elif n in (3, 4) and patterns.get(n, True):
                # disc+track : les derniers 2 chiffres = numéro de piste
                result[filepath] = int(prefix[-2:])
            elif n in (3, 4):
                # index brut
                result[filepath] = int(prefix)
            else:
                result[filepath] = None

    return result


def scan_missing_metadata(
    base_url: str,
    token: str,
    library_name: str,
    *,
    fix_index: bool = True,
    artist_filter: str | None = None,
) -> dict:
    """Scanne et retourne les corrections à appliquer."""
    headers = plex_headers(token)
    section_key = _find_section_key(base_url, headers, library_name)

    album_fixes = []
    track_fixes = []
    unfixable_albums = []
    unfixable_tracks = []

    # --- Albums sans titre ---
    resp = requests.get(
        f"{base_url}/library/sections/{section_key}/all",
        params={"type": 9},
        headers=headers,
    )
    resp.raise_for_status()
    albums = resp.json()["MediaContainer"].get("Metadata", [])

    for album in albums:
        if artist_filter and artist_filter.lower() not in (album.get("parentTitle") or "").lower():
            continue
        title = (album.get("title") or "").strip()
        title_sort = (album.get("titleSort") or "").strip()
        if not title:
            if title_sort:
                album_fixes.append({
                    "ratingKey": album["ratingKey"],
                    "artist": album.get("parentTitle", "?"),
                    "current_title": title,
                    "new_title": title_sort,
                })
            else:
                unfixable_albums.append({
                    "ratingKey": album["ratingKey"],
                    "artist": album.get("parentTitle", "?"),
                    "reason": "title et titleSort vides",
                })

    # --- Tracks sans titre ou sans index ---
    resp = requests.get(
        f"{base_url}/library/sections/{section_key}/all",
        params={"type": 10},
        headers=headers,
    )
    resp.raise_for_status()
    tracks = resp.json()["MediaContainer"].get("Metadata", [])

    # Pré-filtrer les tracks candidates
    candidates = []
    for track in tracks:
        if artist_filter and artist_filter.lower() not in (track.get("grandparentTitle") or "").lower():
            continue

        title = (track.get("title") or "").strip()
        title_sort = (track.get("titleSort") or "").strip()
        index = track.get("index")

        needs_title = not title and bool(title_sort)
        needs_index = fix_index and index is None

        if not title and not title_sort:
            unfixable_tracks.append({
                "ratingKey": track["ratingKey"],
                "artist": track.get("grandparentTitle", "?"),
                "album": track.get("parentTitle", "?"),
                "filepath": _get_filepath(track),
                "reason": "title et titleSort vides",
            })
            if needs_index:
                candidates.append((track, False, True))
        elif needs_title or needs_index:
            candidates.append((track, needs_title, needs_index))

    # Construire la map d'index par analyse album
    index_map = {}
    if fix_index:
        tracks_needing_index = [t for t, _, ni in candidates if ni]
        index_map = _build_album_index_map(tracks_needing_index)

    for track, needs_title, needs_index in candidates:
        title_sort = (track.get("titleSort") or "").strip()

        new_index = None
        if needs_index:
            filepath = _get_filepath(track)
            new_index = index_map.get(filepath)

        if needs_title or new_index is not None:
            track_fixes.append({
                "ratingKey": track["ratingKey"],
                "parent_ratingKey": track.get("parentRatingKey"),
                "artist": track.get("grandparentTitle", "?"),
                "album": track.get("parentTitle", "?"),
                "current_title": (track.get("title") or "").strip(),
                "new_title": title_sort if needs_title else None,
                "current_index": track.get("index"),
                "new_index": new_index,
            })

    total_albums = len(albums)
    total_tracks = len(tracks)

    return {
        "albums": album_fixes,
        "tracks": track_fixes,
        "unfixable": {
            "albums": unfixable_albums,
            "tracks": unfixable_tracks,
        },
        "stats": {
            "total_albums": total_albums,
            "total_tracks": total_tracks,
            "albums_to_fix": len(album_fixes),
            "tracks_to_fix": len(track_fixes),
            "tracks_title_fix": sum(1 for t in track_fixes if t["new_title"]),
            "tracks_index_fix": sum(1 for t in track_fixes if t["new_index"] is not None),
        },
    }

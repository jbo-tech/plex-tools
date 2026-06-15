"""Analyse des doublons dans les playlists Plex."""

from collections import defaultdict

from .normalizer import version_stripped_key


def _get_bitrate(item: dict) -> int | None:
    """Extrait le bitrate audio d'un item de playlist Plex (bps).

    Retourne None si l'information n'est pas disponible.
    """
    media = item.get("Media", [])
    if media:
        br = media[0].get("bitrate")
        if br:
            return int(br)
    return None


def _pick_best_quality(playlist_items: list[dict], indices: list[int]) -> int:
    """Sélectionne l'index avec le meilleur bitrate parmi les doublons.

    Critères (par ordre de priorité) :
    1. Bitrate le plus élevé (moins de compression)
    2. Première occurrence dans la playlist (ordre actuel)

    Args:
        playlist_items: liste complète des items de la playlist.
        indices: indices des occurrences du même ratingKey.

    Returns:
        L'index de l'item à conserver.
    """
    best_idx = indices[0]
    best_bitrate = _get_bitrate(playlist_items[best_idx]) or 0

    for idx in indices[1:]:
        bitrate = _get_bitrate(playlist_items[idx]) or 0
        if bitrate > best_bitrate:
            best_bitrate = bitrate
            best_idx = idx

    return best_idx


def find_exact_duplicates(playlist_items: list[dict]) -> list[dict]:
    """Trouve les doublons exacts (même ratingKey) au sein d'une playlist.

    Pour chaque groupe, conserve l'entrée avec le bitrate le plus élevé
    (moins de compression). En cas d'égalité, conserve la première occurrence.

    Retourne la liste des groupes de doublons avec indices à supprimer.
    """
    # Grouper par ratingKey en conservant l'ordre d'apparition
    by_key: dict[str, list[int]] = defaultdict(list)
    for idx, item in enumerate(playlist_items):
        rk = str(item.get("ratingKey", ""))
        if rk:
            by_key[rk].append(idx)

    duplicates = []
    for rk, indices in by_key.items():
        if len(indices) < 2:
            continue

        # Sélectionner le meilleur : bitrate, puis première occurrence
        keep_index = _pick_best_quality(playlist_items, indices)
        remove_indices = [i for i in indices if i != keep_index]
        item = playlist_items[keep_index]

        duplicates.append({
            "ratingKey": rk,
            "title": item.get("title", ""),
            "artist": item.get("grandparentTitle", ""),
            "occurrences": len(indices),
            "bitrate": _get_bitrate(item),
            "keep_index": keep_index,
            "remove_indices": remove_indices,
        })

    return duplicates


def find_cross_playlist_overlap(
    all_playlists: dict[str, list[dict]],
) -> list[dict]:
    """Trouve les tracks présentes dans 2+ playlists (par ratingKey).

    Retourne la liste triée par nombre de playlists (décroissant).
    """
    track_playlists: dict[str, dict] = {}

    for playlist_name, items in all_playlists.items():
        for item in items:
            rk = str(item.get("ratingKey", ""))
            if not rk:
                continue
            if rk not in track_playlists:
                track_playlists[rk] = {
                    "ratingKey": rk,
                    "title": item.get("title", ""),
                    "artist": item.get("grandparentTitle", ""),
                    "playlists": set(),
                }
            track_playlists[rk]["playlists"].add(playlist_name)

    # Filtrer celles présentes dans 2+ playlists
    overlaps = [
        {**info, "playlists": sorted(info["playlists"])}
        for info in track_playlists.values()
        if len(info["playlists"]) >= 2
    ]

    # Trier par nombre de playlists décroissant
    overlaps.sort(key=lambda x: len(x["playlists"]), reverse=True)
    return overlaps


def find_near_duplicates(
    all_playlists: dict[str, list[dict]],
) -> dict:
    """Trouve les quasi-doublons (versions différentes du même morceau).

    Regroupe par version_stripped_key, signale les groupes avec 2+ ratingKeys distincts.
    Retourne {"intra": {playlist: [groupes]}, "cross": [groupes]}.
    """
    # Collecter toutes les tracks avec leur playlist d'origine
    all_tracks: list[tuple[str, dict]] = []
    for playlist_name, items in all_playlists.items():
        for item in items:
            all_tracks.append((playlist_name, item))

    # Grouper par version_stripped_key
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for playlist_name, item in all_tracks:
        artist = item.get("grandparentTitle", "")
        title = item.get("title", "")
        key = version_stripped_key(artist, title)
        groups[key].append({
            "ratingKey": str(item.get("ratingKey", "")),
            "title": title,
            "artist": artist,
            "playlist": playlist_name,
        })

    # Ne garder que les groupes avec 2+ ratingKeys distincts
    near_dup_groups = {}
    for key, tracks in groups.items():
        distinct_keys = {t["ratingKey"] for t in tracks}
        if len(distinct_keys) >= 2:
            near_dup_groups[key] = tracks

    # Séparer intra-playlist vs cross-playlist
    intra: dict[str, list] = defaultdict(list)
    cross: list[dict] = []

    for key, tracks in near_dup_groups.items():
        playlists_involved = {t["playlist"] for t in tracks}

        if len(playlists_involved) == 1:
            # Tous dans la même playlist → intra
            playlist_name = next(iter(playlists_involved))
            intra[playlist_name].append({"key": key, "tracks": tracks})
        else:
            # Réparti sur plusieurs playlists → cross
            cross.append({"key": key, "tracks": tracks})

            # Vérifier aussi s'il y a des doublons intra dans ce groupe
            by_playlist: dict[str, list] = defaultdict(list)
            for t in tracks:
                by_playlist[t["playlist"]].append(t)
            for pl_name, pl_tracks in by_playlist.items():
                distinct_in_pl = {t["ratingKey"] for t in pl_tracks}
                if len(distinct_in_pl) >= 2:
                    intra[pl_name].append({"key": key, "tracks": pl_tracks})

    return {"intra": dict(intra), "cross": cross}


def find_orphans(playlist_items: list[dict], playlist_name: str = "") -> list[dict]:
    """Détecte les tracks orphelines (fichier absent ou métadonnées manquantes).

    Heuristique : Media vide ou Part sans file.
    """
    orphans = []
    for item in playlist_items:
        rk = str(item.get("ratingKey", ""))
        title = item.get("title", "")
        artist = item.get("grandparentTitle", "")

        # Vérifier que Media et Part.file existent
        media = item.get("Media", [])
        is_orphan = False

        if not media:
            is_orphan = True
        else:
            parts = media[0].get("Part", [])
            if not parts or not parts[0].get("file"):
                is_orphan = True

        if is_orphan:
            orphans.append({
                "ratingKey": rk,
                "title": title,
                "artist": artist,
                "playlist": playlist_name,
            })

    return orphans

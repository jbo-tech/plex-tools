"""Moteur de réconciliation en cascade : GUID → filepath → filename → metadata → fuzzy."""

import os
import re
import unicodedata
from dataclasses import dataclass

from thefuzz import fuzz

from .indexer import PlexIndexes


def _normalize(text: str | None) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


@dataclass
class SourceTrack:
    """Track telle qu'exportée de l'ancienne BDD Plex."""

    guid: str | None
    filepath: str | None
    artist: str | None
    album: str | None
    title: str | None
    track_number: int | None
    disc_number: int | None
    duration_ms: int | None
    original_rating_key: str


@dataclass
class MatchResult:
    source: SourceTrack
    matched_track: dict | None
    method: str
    confidence: float
    notes: str


def _check_duration(source: SourceTrack, track: dict, tolerance_ms: int = 2000) -> bool:
    """Vérifie que la durée du match est cohérente avec la source."""
    if source.duration_ms is None:
        return True
    track_dur = track.get("duration")
    if track_dur is None:
        return True
    return abs(source.duration_ms - track_dur) <= tolerance_ms


def reconcile(
    source: SourceTrack,
    indexes: PlexIndexes,
    fuzzy_threshold: int = 80,
    skip_fuzzy: bool = False,
) -> MatchResult:
    """Réconciliation en cascade. S'arrête au premier match."""

    # 1. GUID
    if source.guid and source.guid in indexes.by_guid:
        return MatchResult(source, indexes.by_guid[source.guid], "guid", 1.0, "")

    # 2. Chemin fichier exact
    if source.filepath and source.filepath in indexes.by_filepath:
        return MatchResult(source, indexes.by_filepath[source.filepath], "filepath", 1.0, "")

    # 3. Nom de fichier
    if source.filepath:
        filename = os.path.basename(source.filepath)
        candidates = indexes.by_filename.get(filename, [])
        if len(candidates) == 1:
            return MatchResult(source, candidates[0], "filename", 1.0, "")
        if len(candidates) > 1:
            for c in candidates:
                if _check_duration(source, c):
                    return MatchResult(
                        source, c, "filename", 0.95,
                        f"doublon filename ({len(candidates)} candidats), sélectionné par durée",
                    )

    # 4. Métadonnées exactes
    artist = _normalize(source.artist)
    album = _normalize(source.album)
    title = _normalize(source.title)
    key = (artist, album, title, source.track_number)

    if artist and title and key in indexes.by_metadata:
        return MatchResult(source, indexes.by_metadata[key], "metadata", 1.0, "")

    # 5. Fuzzy (artiste + titre)
    if not skip_fuzzy and artist and title:
        best_score = 0
        best_track = None
        source_str = f"{artist} {title}"

        for meta_key, track in indexes.by_metadata.items():
            candidate_str = f"{meta_key[0]} {meta_key[2]}"
            score = fuzz.token_sort_ratio(source_str, candidate_str)
            if score > best_score:
                best_score = score
                best_track = track

        if best_score >= fuzzy_threshold and best_track is not None:
            if _check_duration(source, best_track):
                return MatchResult(
                    source, best_track, "fuzzy", best_score / 100,
                    f"score fuzzy : {best_score}",
                )

    # 6. Non résolu
    return MatchResult(source, None, "unresolved", 0.0, "")


def parse_source_track(metadata: dict) -> SourceTrack:
    """Extrait un SourceTrack depuis une entrée JSON Plex."""
    filepath = None
    media_list = metadata.get("Media", [])
    if media_list:
        parts = media_list[0].get("Part", [])
        if parts:
            filepath = parts[0].get("file")

    return SourceTrack(
        guid=metadata.get("guid"),
        filepath=filepath,
        artist=metadata.get("grandparentTitle"),
        album=metadata.get("parentTitle"),
        title=metadata.get("title"),
        track_number=metadata.get("index"),
        disc_number=metadata.get("parentIndex"),
        duration_ms=metadata.get("duration"),
        original_rating_key=metadata.get("ratingKey", ""),
    )

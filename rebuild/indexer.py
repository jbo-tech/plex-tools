"""Indexation de la bibliothèque Plex via API HTTP : construit 4 index pour la réconciliation."""

import os
import re
import unicodedata
from dataclasses import dataclass, field

import requests
from config import plex_headers


def _normalize(text: str | None) -> str:
    """Normalise pour le matching : NFC, lowercase, espaces condensés, strip."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


@dataclass
class PlexIndexes:
    """Les 4 index de réconciliation, construits en un seul scan."""

    by_guid: dict[str, dict] = field(default_factory=dict)
    by_filepath: dict[str, dict] = field(default_factory=dict)
    by_filename: dict[str, list[dict]] = field(default_factory=dict)
    by_metadata: dict[tuple, dict] = field(default_factory=dict)

    @property
    def track_count(self) -> int:
        return len(self.by_guid)


def _find_music_section_key(base_url: str, headers: dict, library_name: str) -> str:
    """Trouve la clé de section pour la bibliothèque musicale."""
    resp = requests.get(f"{base_url}/library/sections", headers=headers)
    resp.raise_for_status()
    sections = resp.json()["MediaContainer"]["Directory"]
    for s in sections:
        if s["title"] == library_name:
            return s["key"]
    available = [s["title"] for s in sections]
    raise ValueError(f"Bibliothèque '{library_name}' introuvable. Disponibles : {available}")


def build_indexes(base_url: str, token: str, library_name: str) -> PlexIndexes:
    """Scanne toutes les tracks via l'API HTTP et construit les 4 index."""
    headers = plex_headers(token)
    section_key = _find_music_section_key(base_url, headers, library_name)

    # type=10 = tracks dans l'API Plex
    resp = requests.get(
        f"{base_url}/library/sections/{section_key}/all",
        params={"type": 10},
        headers=headers,
    )
    resp.raise_for_status()
    all_tracks = resp.json()["MediaContainer"].get("Metadata", [])

    indexes = PlexIndexes()

    for track in all_tracks:
        guid = track.get("guid")
        if guid:
            indexes.by_guid[guid] = track

        for media in track.get("Media", []):
            for part in media.get("Part", []):
                filepath = part.get("file")
                if filepath:
                    indexes.by_filepath[filepath] = track
                    filename = os.path.basename(filepath)
                    indexes.by_filename.setdefault(filename, []).append(track)

        artist = _normalize(track.get("grandparentTitle"))
        album = _normalize(track.get("parentTitle"))
        title = _normalize(track.get("title"))
        track_num = track.get("index")

        if artist and title:
            key = (artist, album, title, track_num)
            indexes.by_metadata[key] = track

    return indexes

"""Parsing du fichier d'entrée : liste de tracks au format 'Artist – Title'."""

import unicodedata
from pathlib import Path


def parse_track_list(filepath: Path) -> list[tuple[str, str]]:
    """Lit un fichier texte et retourne les paires (artist, title).

    Format attendu :
        Artist – Title   (en-dash avec espaces)
        Artist - Title   (hyphen avec espaces)

    Les lignes vides et les commentaires (commençant par #) sont ignorés.
    Lève ValueError si une ligne non-vide n'a pas de séparateur reconnu.
    """
    entries: list[tuple[str, str]] = []

    with open(filepath, encoding="utf-8") as f:
        for line_num, raw_line in enumerate(f, start=1):
            line = raw_line.strip()

            # Ignorer lignes vides et commentaires
            if not line or line.startswith("#"):
                continue

            # Séparateur en-dash d'abord, fallback hyphen
            if " – " in line:
                parts = line.split(" – ", maxsplit=1)
            elif " - " in line:
                parts = line.split(" - ", maxsplit=1)
            else:
                raise ValueError(
                    f"Ligne {line_num} : séparateur introuvable "
                    f"(attendu ' – ' ou ' - ') : {line!r}"
                )

            artist = parts[0].strip()
            title = parts[1].strip()
            entries.append((artist, title))

    return entries


def deduplicate_entries(entries: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Supprime les doublons en comparant via NFC normalisé + lowercase.

    Conserve la première occurrence et l'ordre original.
    """
    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str]] = []

    for artist, title in entries:
        key = (
            unicodedata.normalize("NFC", artist).lower().strip(),
            unicodedata.normalize("NFC", title).lower().strip(),
        )
        if key not in seen:
            seen.add(key)
            result.append((artist, title))

    return result

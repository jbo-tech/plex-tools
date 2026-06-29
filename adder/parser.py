"""Parsing du fichier d'entrée : liste 'Artist – Title' ou CSV unresolved de rebuild."""

import csv
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


def parse_unresolved_csv(
    filepath: Path,
) -> list[tuple[str, str, str | None, str]]:
    """Lit un CSV 'unresolved' produit par rebuild.

    Colonnes attendues : Playlist, Artiste, Album, Titre (les autres sont ignorées).
    Retourne des tuples (playlist, artist, album, title) ; album vaut None si vide.
    Les lignes sans playlist ou sans titre sont ignorées.
    Lève ValueError si les colonnes obligatoires sont absentes.
    """
    entries: list[tuple[str, str, str | None, str]] = []

    with open(filepath, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = set(reader.fieldnames or [])
        required = {"Playlist", "Artiste", "Titre"}
        missing = required - fields
        if missing:
            raise ValueError(
                f"Colonnes manquantes dans le CSV : {sorted(missing)} "
                f"(trouvées : {sorted(fields)})"
            )

        for row in reader:
            playlist = (row.get("Playlist") or "").strip()
            artist = (row.get("Artiste") or "").strip()
            album = (row.get("Album") or "").strip() or None
            title = (row.get("Titre") or "").strip()

            # Une entrée sans playlist ou sans titre est inexploitable
            if not playlist or not title:
                continue

            entries.append((playlist, artist, album, title))

    return entries


def _norm_key(value: str) -> str:
    """Clé de comparaison : NFC normalisé, lowercase, trimé."""
    return unicodedata.normalize("NFC", value).lower().strip()


def deduplicate_entries(entries: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Supprime les doublons en comparant via NFC normalisé + lowercase.

    Conserve la première occurrence et l'ordre original.
    """
    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str]] = []

    for artist, title in entries:
        key = (_norm_key(artist), _norm_key(title))
        if key not in seen:
            seen.add(key)
            result.append((artist, title))

    return result


def deduplicate_csv_entries(
    entries: list[tuple[str, str, str | None, str]],
) -> list[tuple[str, str, str | None, str]]:
    """Dédup des lignes CSV par (playlist, artist, title), album ignoré pour la clé.

    Conserve la première occurrence (et donc son album) et l'ordre original.
    """
    seen: set[tuple[str, str, str]] = set()
    result: list[tuple[str, str, str | None, str]] = []

    for playlist, artist, album, title in entries:
        key = (_norm_key(playlist), _norm_key(artist), _norm_key(title))
        if key not in seen:
            seen.add(key)
            result.append((playlist, artist, album, title))

    return result

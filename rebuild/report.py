"""Génération du rapport de réconciliation (console + JSON + CSV non-résolus)."""

import csv
import json
from datetime import datetime
from pathlib import Path

from .reconciler import MatchResult


def print_playlist_report(title: str, matches: list[MatchResult]) -> None:
    """Affiche le rapport console d'une playlist."""
    resolved = [m for m in matches if m.matched_track is not None]

    print(f"\n=== {title} ({len(matches)} tracks) ===")
    for m in matches:
        artist = m.source.artist or "?"
        track_title = m.source.title or "?"
        label = f"{artist} – {track_title}"

        if m.matched_track:
            method = m.method
            if m.notes:
                method += f" ({m.notes})"
            print(f"  ✓ {label:<45} [{method}]")
        else:
            print(f"  ✗ {label:<45} [NON RÉSOLU]")

    pct = (len(resolved) / len(matches) * 100) if matches else 0
    print(f"\nRésultat : {len(resolved)}/{len(matches)} résolus ({pct:.0f}%)")


def _match_to_dict(m: MatchResult) -> dict:
    matched_info = None
    if m.matched_track:
        matched_info = {
            "ratingKey": m.matched_track.get("ratingKey"),
            "title": m.matched_track.get("title"),
            "artist": m.matched_track.get("grandparentTitle"),
            "album": m.matched_track.get("parentTitle"),
        }

    return {
        "source": {
            "guid": m.source.guid,
            "filepath": m.source.filepath,
            "artist": m.source.artist,
            "album": m.source.album,
            "title": m.source.title,
            "track_number": m.source.track_number,
            "duration_ms": m.source.duration_ms,
            "original_rating_key": m.source.original_rating_key,
        },
        "match": matched_info,
        "method": m.method,
        "confidence": m.confidence,
        "notes": m.notes,
    }


def save_json_report(all_results: dict[str, list[MatchResult]], output_dir: Path) -> Path:
    """Sauvegarde le rapport JSON global."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = output_dir / f"reconciliation_{timestamp}.json"

    report = {}
    for title, matches in all_results.items():
        resolved = [m for m in matches if m.matched_track is not None]
        report[title] = {
            "stats": {
                "total": len(matches),
                "resolved": len(resolved),
                "unresolved": len(matches) - len(resolved),
                "percent": round(len(resolved) / len(matches) * 100, 1) if matches else 0,
            },
            "tracks": [_match_to_dict(m) for m in matches],
        }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return filepath


def _safe_name(name: str) -> str:
    """Nettoie un nom pour usage dans un nom de fichier."""
    return "".join(c if c.isalnum() or c in " _-" else "_" for c in name).strip()


def _make_prefix(rating_key: str, playlist_title: str) -> str:
    """Construit le préfixe pour les noms de fichiers de rapport."""
    safe_title = _safe_name(playlist_title)
    if rating_key:
        return f"{rating_key}_{safe_title}"
    return safe_title


def save_playlist_json_report(matches: list[MatchResult], title: str, rating_key: str, output_dir: Path) -> Path:
    """Sauvegarde le rapport JSON d'une playlist."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = _make_prefix(rating_key, title)
    filepath = output_dir / f"reconciliation_{prefix}_{timestamp}.json"

    resolved = [m for m in matches if m.matched_track is not None]
    report = {
        "playlist": title,
        "ratingKey": rating_key,
        "stats": {
            "total": len(matches),
            "resolved": len(resolved),
            "unresolved": len(matches) - len(resolved),
            "percent": round(len(resolved) / len(matches) * 100, 1) if matches else 0,
        },
        "tracks": [_match_to_dict(m) for m in matches],
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return filepath


def save_playlist_unresolved_csv(matches: list[MatchResult], title: str, rating_key: str, output_dir: Path) -> Path | None:
    """Sauvegarde un CSV des tracks non résolues d'une playlist."""
    unresolved = [m for m in matches if m.matched_track is None]

    if not unresolved:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = _make_prefix(rating_key, title)
    filepath = output_dir / f"unresolved_{prefix}_{timestamp}.csv"

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Playlist", "Artiste", "Album", "Titre", "Fichier", "Méthode tentée", "Notes"])

        for m in unresolved:
            w.writerow([
                title,
                m.source.artist or "",
                m.source.album or "",
                m.source.title or "",
                m.source.filepath or "",
                m.method,
                m.notes,
            ])

    return filepath

"""CLI pour l'ajout de tracks à une playlist Plex depuis un fichier texte."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from thefuzz import fuzz

from config import (
    load_credentials,
    normalize_text,
    resolve_playlist,
    get_playlist_items,
    get_machine_id,
    create_playlist,
    add_tracks_to_playlist,
)
from rebuild.indexer import build_indexes, PlexIndexes
from rebuild.reconciler import SourceTrack, reconcile

from .parser import parse_track_list, deduplicate_entries


_BEST_CANDIDATE_MIN_SCORE = 30


def _find_best_fuzzy_candidate(
    artist: str, title: str, indexes: PlexIndexes
) -> tuple[str | None, str | None, int]:
    """Cherche le meilleur candidat fuzzy dans l'index, sans seuil.

    Retourne (candidate_artist, candidate_title, score).
    Abandon rapide si aucun candidat ne dépasse _BEST_CANDIDATE_MIN_SCORE.
    """
    source_str = f"{normalize_text(artist)} {normalize_text(title)}"
    best_score = 0
    best_artist: str | None = None
    best_title: str | None = None

    for meta_key, track in indexes.by_metadata.items():
        candidate_str = f"{meta_key[0]} {meta_key[2]}"
        score = fuzz.token_sort_ratio(source_str, candidate_str)
        if score > best_score:
            best_score = score
            best_artist = track.get("grandparentTitle")
            best_title = track.get("title")

    if best_score < _BEST_CANDIDATE_MIN_SCORE:
        return None, None, 0

    return best_artist, best_title, best_score


def _print_report(
    playlist_name: str,
    total_input: int,
    added: list[dict],
    already_present: list[dict],
    low_confidence: list[dict],
    missing: list[dict],
    dry_run: bool,
) -> None:
    """Affiche le rapport console."""
    print(f'\n=== Ajout à playlist "{playlist_name}" ({total_input} entrées) ===')

    for entry in added:
        label = f"{entry['artist']} – {entry['title']}"
        method = entry["method"]
        if method == "fuzzy":
            info = f"fuzzy (score: {int(entry['confidence'] * 100)})"
        else:
            info = method
        print(f"  ✓ {label:<50} [{info}]")

    for entry in already_present:
        label = f"{entry['artist']} – {entry['title']}"
        print(f"  = {label:<50} [DÉJÀ PRÉSENT]")

    for entry in low_confidence:
        label = f"{entry['artist']} – {entry['title']}"
        conf = f"{entry['confidence']:.2f}"
        print(f"  ~ {label:<50} [faible confiance: {conf}]")

    for entry in missing:
        label = f"{entry['artist']} – {entry['title']}"
        best = entry.get("best_candidate_title")
        score = entry.get("best_score", 0)
        if best:
            hint = f'NON TROUVÉ | meilleur: "{best}" ({score})'
        else:
            hint = "NON TROUVÉ"
        print(f"  ✗ {label:<50} [{hint}]")

    n_added = len(added)
    n_present = len(already_present)
    n_low = len(low_confidence)
    n_miss = len(missing)
    print(
        f"\nRésultat : {n_added} ajoutés, {n_present} déjà présents, "
        f"{n_low} faible confiance, {n_miss} non trouvés"
    )

    if dry_run:
        print("Mode DRY-RUN — relancez avec --execute pour appliquer.")
    else:
        print("Mode EXECUTE — modifications appliquées.")


def _save_report(
    playlist_name: str,
    input_file: str,
    total_input: int,
    deduplicated: int,
    added: list[dict],
    already_present: list[dict],
    low_confidence: list[dict],
    missing: list[dict],
    dry_run: bool,
) -> Path:
    """Sauvegarde le rapport JSON."""
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = reports_dir / f"add_{timestamp}.json"

    report = {
        "timestamp": datetime.now().isoformat(),
        "mode": "dry-run" if dry_run else "execute",
        "playlist": playlist_name,
        "input_file": input_file,
        "stats": {
            "total_input": total_input,
            "deduplicated": deduplicated,
            "added": len(added),
            "already_present": len(already_present),
            "low_confidence": len(low_confidence),
            "missing": len(missing),
        },
        "added": added,
        "already_present": already_present,
        "low_confidence": low_confidence,
        "missing": missing,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return filepath


def main() -> None:
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Ajouter des tracks à une playlist Plex depuis un fichier texte."
    )
    parser.add_argument("--file", required=True, type=Path, help="Fichier d'entrée (artist – title)")
    parser.add_argument("--playlist", required=True, help="Nom ou ratingKey de la playlist cible")
    parser.add_argument("--execute", action="store_true", help="Appliquer les modifications (dry-run par défaut)")
    parser.add_argument("--library", default="Music", help="Nom de la bibliothèque Plex (défaut: Music)")
    parser.add_argument("--min-confidence", type=float, default=0.85, help="Seuil de confiance minimum (défaut: 0.85)")
    parser.add_argument("--fuzzy-threshold", type=int, default=85, help="Seuil fuzzy pour le reconciler (défaut: 85)")

    args = parser.parse_args()

    if not args.file.exists():
        print(f"Fichier introuvable : {args.file}", file=sys.stderr)
        sys.exit(1)

    base_url, token = load_credentials()

    try:
        raw_entries = parse_track_list(args.file)
    except ValueError as e:
        print(f"Erreur de parsing : {e}", file=sys.stderr)
        sys.exit(1)

    total_input = len(raw_entries)
    entries = deduplicate_entries(raw_entries)
    deduplicated = total_input - len(entries)

    if not entries:
        print("Aucune entrée valide dans le fichier.", file=sys.stderr)
        sys.exit(1)

    print(f"Fichier : {args.file} ({total_input} entrées, {deduplicated} doublons supprimés)")

    print(f"Indexation de la bibliothèque '{args.library}'...")
    indexes = build_indexes(base_url, token, args.library)
    print(f"  {indexes.track_count} tracks indexées.")

    playlist_info = resolve_playlist(base_url, token, args.playlist)
    existing_keys: set[str] = set()

    if playlist_info:
        playlist_name = playlist_info["title"]
        items = get_playlist_items(base_url, token, str(playlist_info["ratingKey"]))
        existing_keys = {str(item["ratingKey"]) for item in items}
        print(f'Playlist "{playlist_name}" trouvée ({len(existing_keys)} tracks existantes).')
    else:
        playlist_name = args.playlist
        print(f'Playlist "{playlist_name}" inexistante — sera créée si --execute.')

    added: list[dict] = []
    already_present: list[dict] = []
    low_confidence: list[dict] = []
    missing: list[dict] = []

    for artist, title in entries:
        source = SourceTrack(
            guid=None,
            filepath=None,
            artist=artist,
            album=None,
            title=title,
            track_number=None,
            disc_number=None,
            duration_ms=None,
            original_rating_key="",
        )

        result = reconcile(source, indexes, fuzzy_threshold=args.fuzzy_threshold)

        if result.confidence >= args.min_confidence and result.matched_track:
            rating_key = str(result.matched_track["ratingKey"])
            entry_dict = {
                "artist": artist,
                "title": title,
                "matched_artist": result.matched_track.get("grandparentTitle", ""),
                "matched_title": result.matched_track.get("title", ""),
                "ratingKey": rating_key,
                "confidence": result.confidence,
                "method": result.method,
            }

            if rating_key in existing_keys:
                already_present.append(entry_dict)
            else:
                added.append(entry_dict)

        elif result.confidence > 0 and result.matched_track:
            low_confidence.append({
                "artist": artist,
                "title": title,
                "candidate_artist": result.matched_track.get("grandparentTitle", ""),
                "candidate_title": result.matched_track.get("title", ""),
                "ratingKey": str(result.matched_track["ratingKey"]),
                "confidence": result.confidence,
            })

        else:
            best_artist, best_title, best_score = _find_best_fuzzy_candidate(
                artist, title, indexes
            )
            entry_dict = {
                "artist": artist,
                "title": title,
            }
            if best_artist and best_score > 0:
                entry_dict["best_candidate_artist"] = best_artist
                entry_dict["best_candidate_title"] = best_title
                entry_dict["best_score"] = best_score
            missing.append(entry_dict)

    _print_report(playlist_name, len(entries), added, already_present, low_confidence, missing, not args.execute)

    report_path = _save_report(
        playlist_name, str(args.file), total_input, deduplicated,
        added, already_present, low_confidence, missing, not args.execute,
    )
    print(f"\nRapport sauvegardé : {report_path}")

    if args.execute and added:
        machine_id = get_machine_id(base_url, token)
        rating_keys = [entry["ratingKey"] for entry in added]

        if playlist_info:
            add_tracks_to_playlist(
                base_url, token, str(playlist_info["ratingKey"]), machine_id, rating_keys
            )
            print(f"\n{len(added)} tracks ajoutées à la playlist \"{playlist_name}\".")
        else:
            create_playlist(base_url, token, playlist_name, machine_id, rating_keys)
            print(f"\nPlaylist \"{playlist_name}\" créée avec {len(added)} tracks.")

    elif args.execute and not added:
        print("\nAucune track à ajouter.")


if __name__ == "__main__":
    main()

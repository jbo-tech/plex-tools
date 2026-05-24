"""CLI — réconciliation et reconstruction de playlists Plex après reset de BDD."""

import argparse
import json
import sys
from pathlib import Path

from config import load_credentials
from .indexer import build_indexes
from .reconciler import parse_source_track, reconcile
from .rebuilder import rebuild_playlist
from .report import print_playlist_report, save_json_report, save_unresolved_csv


def load_playlist(path: Path) -> tuple[str, list[dict]]:
    """Charge un JSON de playlist exporté et retourne (titre, métadonnées)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    container = data["MediaContainer"]
    title = container["title"]
    metadata = container.get("Metadata", [])
    return title, metadata


def discover_playlists(playlist_dir: Path, filter_name: str | None = None) -> list[Path]:
    """Trouve les fichiers JSON de playlists."""
    paths = sorted(playlist_dir.glob("*.json"))
    if filter_name:
        paths = [p for p in paths if filter_name.lower() in p.stem.lower()]
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconstruction de playlists Plex")
    parser.add_argument("--execute", action="store_true", help="Créer les playlists (sinon dry-run)")
    parser.add_argument("--library", default="Music", help="Nom de la bibliothèque Plex (défaut: Music)")
    parser.add_argument("--playlist-dir", default="./playlists", help="Répertoire des JSON exportés (défaut: ./playlists)")
    parser.add_argument("--playlist", type=str, help="Filtrer sur une playlist (recherche dans le nom)")
    parser.add_argument("--fuzzy-threshold", type=int, default=80, help="Seuil fuzzy 0-100 (défaut: 80)")
    parser.add_argument("--skip-fuzzy", action="store_true", help="Désactiver le matching fuzzy")
    parser.add_argument("--report-only", action="store_true", help="Rapport seul, pas de reconstruction")
    args = parser.parse_args()

    playlist_dir = Path(args.playlist_dir)
    playlist_files = discover_playlists(playlist_dir, args.playlist)
    if not playlist_files:
        print(f"Aucune playlist trouvée dans {playlist_dir}", file=sys.stderr)
        sys.exit(1)

    dry_run = not args.execute
    print(f"Playlists trouvées : {len(playlist_files)}")
    print(f"Mode : {'DRY-RUN' if dry_run else 'EXÉCUTION'}")

    base_url, token = load_credentials()

    print(f"\nConnexion à {base_url}...")
    print(f"Indexation de la bibliothèque '{args.library}'...")
    indexes = build_indexes(base_url, token, args.library)
    print(f"Index construits : {indexes.track_count} morceaux")

    all_results: dict[str, list] = {}
    total_resolved = 0
    total_tracks = 0

    for path in playlist_files:
        title, metadata = load_playlist(path)
        matches = [
            reconcile(
                parse_source_track(m),
                indexes,
                fuzzy_threshold=args.fuzzy_threshold,
                skip_fuzzy=args.skip_fuzzy,
            )
            for m in metadata
        ]

        all_results[title] = matches
        resolved = sum(1 for m in matches if m.matched_track is not None)
        total_resolved += resolved
        total_tracks += len(matches)

        print_playlist_report(title, matches)

        if not args.report_only:
            result = rebuild_playlist(base_url, token, title, matches, dry_run=dry_run)
            if result.get("created"):
                print("  → Playlist créée dans Plex")
            elif result.get("skipped"):
                print(f"  → Skippée : {result['reason']}")

    pct = (total_resolved / total_tracks * 100) if total_tracks else 0
    print(f"\n{'=' * 50}")
    print(f"Total : {total_resolved}/{total_tracks} résolus ({pct:.0f}%)")
    print(f"Playlists : {len(all_results)}")
    if dry_run and not args.report_only:
        print("Mode DRY-RUN — aucune playlist créée. Relancez avec --execute.")

    report_path = save_json_report(all_results, Path("reports"))
    print(f"Rapport : {report_path}")

    unresolved_path = save_unresolved_csv(all_results, Path("reports"))
    if unresolved_path:
        unresolved_count = sum(1 for ms in all_results.values() for m in ms if m.matched_track is None)
        print(f"Non résolus : {unresolved_count} tracks → {unresolved_path}")


if __name__ == "__main__":
    main()

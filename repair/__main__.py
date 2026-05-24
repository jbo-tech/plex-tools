"""CLI — réparation des métadonnées manquantes (title, index) dans la bibliothèque Plex."""

import argparse
import sys
from pathlib import Path

from config import load_credentials
from .scanner import scan_missing_metadata
from .fixer import apply_fixes
from .report import print_report, save_pre_run_report, save_post_run_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Réparation des métadonnées Plex manquantes")
    parser.add_argument("--execute", action="store_true", help="Appliquer les corrections (sinon dry-run)")
    parser.add_argument("--library", default="Music", help="Nom de la bibliothèque (défaut: Music)")
    parser.add_argument("--no-index", action="store_true", help="Ne pas corriger les numéros de piste")
    parser.add_argument("--no-refresh", action="store_true", help="Ne pas déclencher de refresh metadata après correction")
    parser.add_argument("--artist", type=str, help="Filtrer sur un artiste (recherche partielle)")
    parser.add_argument("--report-dir", default="./reports", help="Répertoire des rapports (défaut: ./reports)")
    args = parser.parse_args()

    base_url, token = load_credentials()
    dry_run = not args.execute

    print(f"Mode : {'DRY-RUN' if dry_run else 'EXÉCUTION'}")
    print(f"Scan de la bibliothèque '{args.library}'...")

    fixes = scan_missing_metadata(
        base_url, token, args.library,
        fix_index=not args.no_index,
        artist_filter=args.artist,
    )

    print_report(fixes)

    if not fixes["albums"] and not fixes["tracks"]:
        if fixes["unfixable"]["albums"] or fixes["unfixable"]["tracks"]:
            save_post_run_report(fixes, {"albums_fixed": 0, "tracks_fixed": 0, "errors": 0}, Path(args.report_dir))
        else:
            print("\nRien à corriger.")
        return

    report_dir = Path(args.report_dir)
    save_pre_run_report(fixes, report_dir)

    if dry_run:
        print(f"\nDRY-RUN — aucune modification. Relancez avec --execute pour appliquer.")
        return

    print(f"\nApplication des corrections...")
    stats = apply_fixes(base_url, token, fixes, refresh=not args.no_refresh)
    save_post_run_report(fixes, stats, report_dir)


if __name__ == "__main__":
    main()

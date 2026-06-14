"""CLI — détection de doublons dans les playlists Plex."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

from config import load_credentials, plex_headers, get_all_playlists, get_playlist_items, resolve_playlist
from .scanner import (
    find_exact_duplicates,
    find_cross_playlist_overlap,
    find_near_duplicates,
    find_orphans,
)


def _remove_playlist_item(
    base_url: str, token: str, playlist_key: str, playlist_item_id: str
) -> bool:
    """Supprime un item spécifique d'une playlist via son playlistItemID."""
    url = f"{base_url}/playlists/{playlist_key}/items/{playlist_item_id}"
    resp = requests.delete(url, headers=plex_headers(token))
    return resp.status_code == 200


def _print_report(
    exact_dups: dict[str, list],
    cross_overlap: list[dict],
    near_dups: dict,
    orphans: dict[str, list],
) -> None:
    """Affiche le rapport en console."""
    print("\n" + "=" * 60)
    print("RAPPORT DE DOUBLONS")
    print("=" * 60)

    # Doublons exacts
    total_exact = sum(len(dups) for dups in exact_dups.values())
    print(f"\n{'─' * 40}")
    print(f"DOUBLONS EXACTS (même track répétée) : {total_exact} groupes")
    print(f"{'─' * 40}")
    for pl_name, dups in exact_dups.items():
        if not dups:
            continue
        print(f"\n  [{pl_name}]")
        for d in dups:
            print(f"    • {d['artist']} — {d['title']} (×{d['occurrences']})")

    # Chevauchement cross-playlist
    print(f"\n{'─' * 40}")
    print(f"CHEVAUCHEMENT INTER-PLAYLISTS : {len(cross_overlap)} tracks")
    print(f"{'─' * 40}")
    for item in cross_overlap[:20]:
        pls = ", ".join(item["playlists"])
        print(f"  • {item['artist']} — {item['title']} → {pls}")
    if len(cross_overlap) > 20:
        print(f"  ... et {len(cross_overlap) - 20} autres")

    # Quasi-doublons
    intra_count = sum(len(groups) for groups in near_dups.get("intra", {}).values())
    cross_count = len(near_dups.get("cross", []))
    print(f"\n{'─' * 40}")
    print(f"QUASI-DOUBLONS (versions différentes) : {intra_count} intra + {cross_count} cross")
    print(f"{'─' * 40}")
    for pl_name, groups in near_dups.get("intra", {}).items():
        if not groups:
            continue
        print(f"\n  [{pl_name}]")
        for g in groups[:10]:
            tracks_str = " | ".join(
                f"{t['title']} (rk:{t['ratingKey']})" for t in g["tracks"]
            )
            print(f"    • {tracks_str}")
    for g in near_dups.get("cross", [])[:10]:
        tracks_str = " | ".join(
            f"{t['title']} [{t['playlist']}]" for t in g["tracks"]
        )
        print(f"  ✗ {tracks_str}")

    # Orphelins
    total_orphans = sum(len(o) for o in orphans.values())
    print(f"\n{'─' * 40}")
    print(f"ORPHELINS (fichier absent) : {total_orphans}")
    print(f"{'─' * 40}")
    for pl_name, items in orphans.items():
        if not items:
            continue
        print(f"\n  [{pl_name}]")
        for o in items:
            print(f"    • {o['artist']} — {o['title']} (rk:{o['ratingKey']})")


def _save_report(
    exact_dups: dict[str, list],
    cross_overlap: list[dict],
    near_dups: dict,
    orphans: dict[str, list],
    mode: str,
    execution_results: dict | None = None,
) -> Path:
    """Sauvegarde le rapport JSON (après exécution si applicable)."""
    report_dir = Path("reports")
    report_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"dedup_{timestamp}.json"

    serializable_near_dups = {
        "intra": {
            pl: [
                {"key": list(g["key"]), "tracks": g["tracks"]}
                for g in groups
            ]
            for pl, groups in near_dups.get("intra", {}).items()
        },
        "cross": [
            {"key": list(g["key"]), "tracks": g["tracks"]}
            for g in near_dups.get("cross", [])
        ],
    }

    report = {
        "timestamp": datetime.now().isoformat(),
        "mode": mode,
        "exact_duplicates": exact_dups,
        "cross_playlist_overlap": cross_overlap,
        "near_duplicates": serializable_near_dups,
        "orphans": orphans,
    }

    if execution_results is not None:
        report["execution_results"] = execution_results

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Détection de doublons dans les playlists Plex"
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="Supprimer les doublons exacts intra-playlist (sinon dry-run)"
    )
    parser.add_argument(
        "--library", default="Music",
        help="Nom de la bibliothèque Plex (défaut: Music)"
    )
    parser.add_argument(
        "--playlist", type=str,
        help="Filtrer sur une playlist (nom ou ratingKey)"
    )
    parser.add_argument(
        "--fuzzy-threshold", type=int, default=85,
        help="Seuil fuzzy pour les quasi-doublons 0-100 (défaut: 85)"
    )
    args = parser.parse_args()

    dry_run = not args.execute
    mode = "dry-run" if dry_run else "execute"
    print(f"Mode : {'DRY-RUN' if dry_run else 'EXÉCUTION'}")

    base_url, token = load_credentials()
    print(f"Connexion à {base_url}...")

    # Récupérer les playlists
    if args.playlist:
        pl = resolve_playlist(base_url, token, args.playlist)
        if not pl:
            print(f"Playlist introuvable : {args.playlist}", file=sys.stderr)
            sys.exit(1)
        playlists = [pl]
    else:
        playlists = get_all_playlists(base_url, token)

    if not playlists:
        print("Aucune playlist audio trouvée.", file=sys.stderr)
        sys.exit(1)

    print(f"Playlists à analyser : {len(playlists)}")

    # Récupérer les items de chaque playlist
    all_playlist_data: dict[str, list[dict]] = {}
    for pl in playlists:
        pl_name = pl["title"]
        pl_key = str(pl["ratingKey"])
        items = get_playlist_items(base_url, token, pl_key)
        all_playlist_data[pl_name] = items
        print(f"  • {pl_name} : {len(items)} tracks")

    # Analyses
    print("\nAnalyse en cours...")

    # 1. Doublons exacts par playlist
    exact_dups: dict[str, list] = {}
    for pl_name, items in all_playlist_data.items():
        dups = find_exact_duplicates(items)
        if dups:
            exact_dups[pl_name] = dups

    # 2. Chevauchement cross-playlist
    cross_overlap = find_cross_playlist_overlap(all_playlist_data)

    # 3. Quasi-doublons
    near_dups = find_near_duplicates(all_playlist_data)

    # 4. Orphelins
    orphans: dict[str, list] = {}
    for pl_name, items in all_playlist_data.items():
        orph = find_orphans(items, pl_name)
        if orph:
            orphans[pl_name] = orph

    # Affichage console
    _print_report(exact_dups, cross_overlap, near_dups, orphans)

    # Exécution : suppression des doublons exacts intra-playlist uniquement
    execution_results = None

    if not dry_run and exact_dups:
        print(f"\n{'─' * 40}")
        print("SUPPRESSION DES DOUBLONS EXACTS")
        print(f"{'─' * 40}")

        pl_key_by_name = {pl["title"]: str(pl["ratingKey"]) for pl in playlists}

        removed_count = 0
        error_count = 0
        for pl_name, dups in exact_dups.items():
            pl_key = pl_key_by_name[pl_name]
            items = all_playlist_data[pl_name]

            for dup in dups:
                for idx in dup["remove_indices"]:
                    item = items[idx]
                    playlist_item_id = str(item.get("playlistItemID", ""))
                    if not playlist_item_id:
                        print(
                            f"  ⚠ Pas de playlistItemID pour "
                            f"{dup['artist']} — {dup['title']} (index {idx})"
                        )
                        error_count += 1
                        continue

                    success = _remove_playlist_item(
                        base_url, token, pl_key, playlist_item_id
                    )
                    if success:
                        removed_count += 1
                        print(
                            f"  ✓ Supprimé : {dup['artist']} — {dup['title']} "
                            f"(playlist: {pl_name}, index: {idx})"
                        )
                    else:
                        error_count += 1
                        print(
                            f"  ✗ Échec : {dup['artist']} — {dup['title']} "
                            f"(playlist: {pl_name}, itemID: {playlist_item_id})"
                        )

        print(f"\nTotal supprimé : {removed_count} items")
        if error_count:
            print(f"Erreurs : {error_count}")

        execution_results = {"removed": removed_count, "errors": error_count}

    elif dry_run and exact_dups:
        total_removable = sum(
            len(idx) for dups in exact_dups.values() for d in dups for idx in [d["remove_indices"]]
        )
        print(f"\nMode DRY-RUN — {total_removable} doublons exacts supprimables.")
        print("Relancez avec --execute pour les supprimer.")

    # Sauvegarde JSON (après exécution pour refléter les résultats réels)
    report_path = _save_report(exact_dups, cross_overlap, near_dups, orphans, mode, execution_results)
    print(f"\nRapport sauvegardé : {report_path}")


if __name__ == "__main__":
    main()

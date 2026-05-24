"""Affichage du rapport de diagnostic et post-exécution."""

import csv
from pathlib import Path


def print_report(fixes: dict) -> None:
    stats = fixes["stats"]

    print(f"\n{'=' * 60}")
    print(f"DIAGNOSTIC MÉTADONNÉES")
    print(f"{'=' * 60}")
    print(f"Albums : {stats['albums_to_fix']} à corriger / {stats['total_albums']} total")
    print(f"Tracks : {stats['tracks_to_fix']} à corriger / {stats['total_tracks']} total")
    print(f"  - titres manquants : {stats['tracks_title_fix']}")
    print(f"  - index manquants :  {stats['tracks_index_fix']}")

    unfixable = fixes.get("unfixable", {})
    if unfixable.get("albums") or unfixable.get("tracks"):
        n_albums = len(unfixable.get("albums", []))
        n_tracks = len(unfixable.get("tracks", []))
        print(f"\n  ⚠ Non traitables (titleSort aussi vide) :")
        print(f"    Albums : {n_albums}")
        print(f"    Tracks : {n_tracks}")

    if fixes["albums"]:
        print(f"\n--- Albums sans titre (échantillon) ---")
        for a in fixes["albums"][:15]:
            print(f"  {a['artist']} → \"{a['new_title']}\"")
        if len(fixes["albums"]) > 15:
            print(f"  ... et {len(fixes['albums']) - 15} de plus")

    if fixes["tracks"]:
        print(f"\n--- Tracks à corriger (échantillon) ---")
        for t in fixes["tracks"][:15]:
            parts = []
            if t["new_title"]:
                parts.append(f"titre: \"{t['new_title']}\"")
            if t["new_index"] is not None:
                parts.append(f"index: {t['new_index']}")
            print(f"  {t['artist']} / {t['album']} → {', '.join(parts)}")
        if len(fixes["tracks"]) > 15:
            print(f"  ... et {len(fixes['tracks']) - 15} de plus")

    print(f"{'=' * 60}")


def save_pre_run_report(fixes: dict, report_dir: Path) -> Path:
    """Sauvegarde l'inventaire complet avant exécution."""
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "repair_pre_run.csv"

    with open(report_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Type", "Statut", "RatingKey", "Artiste", "Album", "Titre actuel", "Correction prévue", "Détail"])

        for a in fixes["albums"]:
            w.writerow(["album", "à_corriger", a["ratingKey"], a["artist"], "", a["current_title"], a["new_title"], ""])

        for t in fixes["tracks"]:
            parts = []
            if t["new_title"]:
                parts.append(f"titre={t['new_title']}")
            if t["new_index"] is not None:
                parts.append(f"index={t['new_index']}")
            w.writerow([
                "track", "à_corriger", t["ratingKey"], t["artist"], t["album"],
                t["current_title"], ", ".join(parts), "",
            ])

        unfixable = fixes.get("unfixable", {})
        for a in unfixable.get("albums", []):
            w.writerow(["album", "non_traitable", a["ratingKey"], a["artist"], "", "", "", a["reason"]])
        for t in unfixable.get("tracks", []):
            w.writerow(["track", "non_traitable", t["ratingKey"], t["artist"], t["album"], "", "", t["reason"]])

    stats = fixes["stats"]
    print(f"\nRapport pré-exécution sauvegardé : {report_path}")
    print(f"  {stats['albums_to_fix']} albums + {stats['tracks_to_fix']} tracks à corriger")
    print(f"  {len(unfixable.get('albums', []))} albums + {len(unfixable.get('tracks', []))} tracks non traitables")

    return report_path


def save_post_run_report(fixes: dict, stats: dict, report_dir: Path) -> Path:
    """Sauvegarde le rapport post-exécution avec les cas non traitables."""
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "repair_report.csv"

    with open(report_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Type", "Statut", "RatingKey", "Artiste", "Album", "Titre actuel", "Correction", "Détail"])

        for a in fixes["albums"]:
            w.writerow(["album", "corrigé", a["ratingKey"], a["artist"], "", "", a["new_title"], ""])

        for t in fixes["tracks"]:
            parts = []
            if t["new_title"]:
                parts.append(f"titre={t['new_title']}")
            if t["new_index"] is not None:
                parts.append(f"index={t['new_index']}")
            w.writerow([
                "track", "corrigé", t["ratingKey"], t["artist"], t["album"],
                t["current_title"], ", ".join(parts), "",
            ])

        unfixable = fixes.get("unfixable", {})
        for a in unfixable.get("albums", []):
            w.writerow([
                "album", "non_traitable", a["ratingKey"], a["artist"], "",
                "", "", a["reason"],
            ])
        for t in unfixable.get("tracks", []):
            w.writerow([
                "track", "non_traitable", t["ratingKey"], t["artist"], t["album"],
                "", "", t["reason"],
            ])

    # Résumé console
    unfixable_albums = len(unfixable.get("albums", []))
    unfixable_tracks = len(unfixable.get("tracks", []))
    print(f"\n{'=' * 60}")
    print(f"RAPPORT POST-EXÉCUTION")
    print(f"{'=' * 60}")
    print(f"Albums corrigés :  {stats['albums_fixed']}")
    print(f"Tracks corrigées : {stats['tracks_fixed']}")
    if stats.get("albums_refreshed") or stats.get("errors"):
        print(f"Refreshs :         {stats.get('albums_refreshed', 0)}")
    if stats["errors"]:
        print(f"Erreurs :          {stats['errors']}")
    if unfixable_albums or unfixable_tracks:
        print(f"\nNon traitables :")
        print(f"  Albums : {unfixable_albums}")
        print(f"  Tracks : {unfixable_tracks}")
    print(f"\nRapport : {report_path}")
    print(f"{'=' * 60}")

    return report_path

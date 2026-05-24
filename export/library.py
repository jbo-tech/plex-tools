"""Export de la configuration des bibliothèques Plex vers JSON."""

import argparse
import json
import os

import requests
from config import load_credentials, plex_headers


def main() -> None:
    parser = argparse.ArgumentParser(description="Export de la configuration des bibliothèques Plex")
    parser.add_argument("--type", type=str, help="Filtrer par type : movie, show, artist, photo")
    parser.add_argument("--output-dir", default="config", help="Répertoire de sortie (défaut : config)")
    args = parser.parse_args()

    base_url, token = load_credentials()
    headers = plex_headers(token)

    os.makedirs(args.output_dir, exist_ok=True)

    response = requests.get(f"{base_url}/library/sections", headers=headers)
    if response.status_code != 200:
        print(f"Erreur {response.status_code} : {response.text}")
        raise SystemExit(1)

    data = response.json()
    directories = data["MediaContainer"]["Directory"]

    if args.type:
        directories = [d for d in directories if d.get("type") == args.type]
        if not directories:
            print(f"Aucune section de type '{args.type}' trouvée.")
            raise SystemExit(0)

    full_file = os.path.join(args.output_dir, "plex_library_full.json")
    full_data = {**data, "MediaContainer": {**data["MediaContainer"], "Directory": directories}}
    with open(full_file, "w", encoding="utf-8") as f:
        json.dump(full_data, f, indent=4, ensure_ascii=False)
    print(f"Version complète sauvegardée dans {full_file}")

    simplified = [
        {
            "title": d.get("title"),
            "type": d.get("type"),
            "agent": d.get("agent"),
            "scanner": d.get("scanner"),
            "language": d.get("language"),
            "paths": [loc["path"] for loc in d.get("Location", [])],
        }
        for d in directories
    ]

    simple_file = os.path.join(args.output_dir, "plex_library_simplified.json")
    with open(simple_file, "w", encoding="utf-8") as f:
        json.dump(simplified, f, indent=4, ensure_ascii=False)
    print(f"Version simplifiée sauvegardée dans {simple_file} ({len(directories)} section(s))")


if __name__ == "__main__":
    main()

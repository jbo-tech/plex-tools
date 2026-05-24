"""Export des playlists Plex vers JSON."""

import argparse
import json
import os
from datetime import datetime

import requests
from config import load_credentials, plex_headers


def main() -> None:
    parser = argparse.ArgumentParser(description="Export des playlists Plex vers JSON")
    parser.add_argument("--id", type=str, help="ID (ratingKey) d'une playlist à exporter")
    parser.add_argument("--name", type=str, help="Filtrer par nom (recherche partielle, insensible à la casse)")
    parser.add_argument("--type", type=str, default="audio", help="Type : audio, video, photo (défaut : audio)")
    parser.add_argument("--output-dir", default="playlists", help="Répertoire de sortie (défaut : playlists)")
    args = parser.parse_args()

    base_url, token = load_credentials()
    headers = plex_headers(token)

    os.makedirs(args.output_dir, exist_ok=True)

    response = requests.get(f"{base_url}/playlists/all?playlistType={args.type}&smart=0", headers=headers)
    if response.status_code != 200:
        print(f"Erreur {response.status_code} : {response.text}")
        raise SystemExit(1)

    playlists_data = response.json()

    playlists = [
        (p["ratingKey"], p["title"])
        for p in playlists_data["MediaContainer"]["Metadata"]
    ]

    if args.id:
        playlists = [(rid, title) for rid, title in playlists if rid == args.id]
    if args.name:
        pattern = args.name.lower()
        playlists = [(rid, title) for rid, title in playlists if pattern in title.lower()]

    if not playlists:
        print("Aucune playlist trouvée avec ces critères.")
        raise SystemExit(0)

    for playlist_id, playlist_title in playlists:
        response = requests.get(f"{base_url}/playlists/{playlist_id}/items", headers=headers)
        playlist_content = response.json()

        json_file_path = os.path.join(args.output_dir, f"{playlist_id}_{playlist_title}.json")
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(playlist_content, f, indent=4, ensure_ascii=False)

        print(f"{datetime.now()}: Playlist '{playlist_title}' (ID: {playlist_id}) exportée.")

    print(f"Export terminé. {len(playlists)} playlist(s) exportée(s).")


if __name__ == "__main__":
    main()

"""Téléchargement de fichiers audio depuis Mega à partir des playlists exportées."""

import argparse
import json
import logging
import subprocess
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("mega_download.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def extract_file_paths(json_file: Path) -> list[str]:
    """Extrait les chemins de fichiers audio depuis un JSON de playlist."""
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)

    paths = []
    for metadata in data.get("MediaContainer", {}).get("Metadata", []):
        for media in metadata.get("Media", []):
            for part in media.get("Part", []):
                if file_path := part.get("file"):
                    paths.append(file_path)
    return paths


def download_file(mega_path: str, dest_file: Path, timeout: int = 600) -> bool:
    """Télécharge un fichier depuis Mega via mega-get."""
    dest_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            ["mega-get", "-q", mega_path, str(dest_file)],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode == 0:
            logger.info(f"  ✓ {dest_file.name}")
            return True
        logger.error(f"  ✗ {dest_file.name} — {result.stderr.strip()}")
        return False

    except subprocess.TimeoutExpired:
        logger.error(f"  ✗ {dest_file.name} — timeout ({timeout}s)")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Télécharge les fichiers audio depuis Mega")
    parser.add_argument("--playlist-dir", default="playlists", help="Répertoire des JSON exportés (défaut : playlists)")
    parser.add_argument("--output-dir", default="downloads", help="Répertoire de téléchargement (défaut : downloads)")
    parser.add_argument("--name", type=str, help="Filtrer les playlists par nom")
    parser.add_argument("--media-prefix", default="/Media", help="Préfixe des chemins dans Plex (défaut : /Media)")
    parser.add_argument("--mega-prefix", default="/Mini me cloud", help="Préfixe correspondant sur Mega (défaut : /Mini me cloud)")
    args = parser.parse_args()

    # Vérification de mega-cmd
    try:
        subprocess.run(["mega-get", "--help"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.error("mega-cmd n'est pas installé. https://mega.nz/cmd")
        raise SystemExit(1)

    playlist_dir = Path(args.playlist_dir)
    output_dir = Path(args.output_dir)
    json_files = sorted(playlist_dir.glob("*.json"))

    if args.name:
        pattern = args.name.lower()
        json_files = [f for f in json_files if pattern in f.stem.lower()]

    if not json_files:
        logger.warning("Aucune playlist trouvée.")
        raise SystemExit(0)

    total = downloaded = failed = 0

    for json_file in json_files:
        file_paths = extract_file_paths(json_file)
        if not file_paths:
            continue

        playlist_name = json_file.stem
        logger.info(f"\n=== {playlist_name} ({len(file_paths)} fichiers) ===")

        for file_path in file_paths:
            total += 1
            mega_path = file_path.replace(args.media_prefix, args.mega_prefix)
            dest_file = output_dir / playlist_name / Path(file_path).name

            if download_file(mega_path, dest_file):
                downloaded += 1
            else:
                failed += 1

    logger.info(f"\nTotal : {downloaded}/{total} téléchargés, {failed} échecs")


if __name__ == "__main__":
    main()

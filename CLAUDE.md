# plex-tools

Outils CLI pour Plex : export, téléchargement, reconstruction de playlists, réparation de métadonnées, déduplication et ajout de tracks.

## Commands

```bash
uv run python check.py                  # Vérifier la connexion
uv run python -m export.playlists       # Exporter les playlists
uv run python -m export.library         # Exporter la config bibliothèques
uv run python -m export.download        # Télécharger depuis Mega
uv run python -m rebuild                # Reconstruire les playlists (dry-run)
uv run python -m repair                 # Diagnostiquer les métadonnées manquantes (dry-run)
uv run python -m repair --execute       # Appliquer les corrections
uv run python -m dedup                  # Détecter les doublons (dry-run)
uv run python -m dedup --execute        # Supprimer les doublons exacts intra-playlist
uv run python -m adder --file list.txt --playlist "Name"  # Ajouter des tracks (dry-run)
uv run python -m adder --file list.txt --playlist "Name" --execute  # Appliquer
uv run pytest tests/ -v                 # Tests
```

## Stack

- Python ≥3.12, uv
- `requests` — API HTTP Plex directe
- `thefuzz` — fuzzy matching
- Credentials partagés : `~/.config/plex-tools/config.toml`

## Architecture

- `config.py` — chargement credentials + helpers API (partagé)
- `export/` — playlists, library, download (scripts autonomes)
- `rebuild/` — pipeline complet (indexer → reconciler → rebuilder → report)
- `repair/` — diagnostic et réparation des métadonnées manquantes (scanner → fixer → report)
- `dedup/` — détection de doublons (exacts, cross-playlist, near-duplicates, orphelins)
- `adder/` — ajout de tracks depuis un fichier texte (parser → reconciler → API)
- `check.py` — utilitaire simple (reste à la racine)

## Conventions

- Commentaires et docstrings en **français**
- Noms de variables et fonctions en **anglais**
- Commits en anglais, format conventional commits
- Pas de `.env` : réglages projet en arguments CLI avec défauts sensibles
- API Plex via `requests` (pas de `plexapi`)

## Context

Quand pertinent, lire :
- Travail en cours : `.claude/context/status.md`
- Erreurs passées : `.claude/context/anti-patterns.md`
- Décisions techniques : `.claude/context/decisions.md`

## End of session

Lancer `/retro` avant de s'arrêter pour mettre à jour les fichiers de contexte.

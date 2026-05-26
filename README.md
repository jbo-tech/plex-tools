# plex-tools

Outils CLI pour un serveur Plex : export de playlists, export de bibliothèque, téléchargement Mega, reconstruction de playlists après reset de BDD, réparation de métadonnées manquantes.

## Prérequis

Credentials Plex dans `~/.config/plex-tools/config.toml` :

```toml
[plex]
url = "http://localhost:32400"
token = "votre-token-ici"
```

```bash
mkdir -p ~/.config/plex-tools
chmod 600 ~/.config/plex-tools/config.toml
```

Le token se récupère via Plex Web → Inspecter → Network → `X-Plex-Token`.

## Installation

```bash
uv sync
```

## Commandes

### Vérifier la connexion

```bash
uv run python check.py
```

### Export — Playlists

```bash
uv run python -m export.playlists                     # Toutes les playlists audio
uv run python -m export.playlists --name "Soul"        # Filtrer par nom
uv run python -m export.playlists --id 169772          # Par ID
uv run python -m export.playlists --output-dir exports
```

### Export — Bibliothèques

```bash
uv run python -m export.library                        # Toutes les sections
uv run python -m export.library --type artist           # Filtrer par type
uv run python -m export.library --output-dir exports
```

### Export — Téléchargement Mega

```bash
uv run python -m export.download                           # Toutes les playlists
uv run python -m export.download --name "Cricri"           # Filtrer par nom
uv run python -m export.download --output-dir downloads
uv run python -m export.download --media-prefix /Media --mega-prefix "/Mini me cloud"
```

Nécessite `mega-cmd` installé (`mega-get`).

### Rebuild — Reconstruire les playlists

```bash
uv run python -m rebuild                              # Dry-run
uv run python -m rebuild --execute                    # Création effective
uv run python -m rebuild --playlist "Douceur"         # Filtrer par nom
uv run python -m rebuild --library "Musique"          # Bibliothèque (défaut: Music)
uv run python -m rebuild --fuzzy-threshold 85         # Seuil fuzzy (défaut: 80)
uv run python -m rebuild --skip-fuzzy                 # Désactiver le fuzzy
uv run python -m rebuild --report-only                # Rapport seul
```

Algorithme de réconciliation en cascade :
1. **GUID Plex** — identifiant global, le plus fiable
2. **Chemin fichier exact** — fonctionne si les fichiers n'ont pas bougé
3. **Nom de fichier** — résiste aux déplacements de dossiers
4. **Métadonnées exactes** — artiste + album + titre + n° piste
5. **Métadonnées fuzzy** — rattrape les variations de nommage

Chaque exécution produit un rapport JSON par playlist dans `reports/` (`reconciliation_{ratingKey}_{nom}_{timestamp}.json`), un rapport global, et un CSV des tracks non résolues par playlist (`unresolved_{ratingKey}_{nom}_{timestamp}.csv`).

### Repair — Réparation des métadonnées

```bash
uv run python -m repair                                # Dry-run (diagnostic)
uv run python -m repair --execute                      # Appliquer les corrections
uv run python -m repair --artist "Earth, Wind"         # Filtrer sur un artiste
uv run python -m repair --no-index                     # Ne pas corriger les index
uv run python -m repair --no-refresh                   # Ne pas déclencher de refresh
uv run python -m repair --report-dir ./reports         # Répertoire des rapports
```

Corrige les métadonnées manquantes dans la bibliothèque Plex :
- **Titres** : copie `titleSort` → `title` quand le titre est vide
- **Index de piste** : extraction depuis les noms de fichier (détection disc+track, overflow)
- **Refresh** : déclenche un refresh metadata sur chaque album corrigé

Produit un rapport pré-exécution (`repair_pre_run.csv`) et post-exécution (`repair_report.csv`) dans `reports/`.

## Structure

```
plex-tools/
├── config.py              # Credentials partagés + helpers API
├── check.py               # Vérification connexion
├── export/
│   ├── playlists.py       # Export playlists → JSON
│   ├── library.py         # Export config bibliothèques → JSON
│   └── download.py        # Téléchargement depuis Mega
├── rebuild/
│   ├── __main__.py        # CLI reconstruction
│   ├── indexer.py         # Indexation bibliothèque (4 index)
│   ├── reconciler.py      # Cascade de matching
│   ├── rebuilder.py       # Création playlists via API
│   └── report.py          # Rapport console + JSON + CSV non-résolus
├── repair/
│   ├── __main__.py        # CLI réparation
│   ├── scanner.py         # Scan métadonnées manquantes
│   ├── fixer.py           # Corrections via API PUT
│   └── report.py          # Rapports pré/post-exécution
├── tests/
├── playlists/             # JSON exportés
└── reports/               # Rapports de réconciliation
```

# Status

## Objectif
Monorepo d'outils CLI Plex : export playlists, export bibliothèque, téléchargement Mega, reconstruction de playlists après reset de BDD, réparation de métadonnées manquantes.

## Focus actuel
Module `rebuild/` : mode incrémental implémenté. Le rebuilder détecte les playlists existantes et n'ajoute que les tracks manquantes. Prêt pour dry-run complet puis exécution.

## Log

### 2026-06-01
- Done :
  - Mode incrémental dans `rebuild/rebuilder.py` : détection playlist existante par titre, diff des ratingKeys, ajout sélectif via `PUT /playlists/{id}/items`
  - Nouvelles fonctions : `_find_playlist()`, `_get_playlist_track_keys()`, `_add_tracks_to_playlist()`, `_create_playlist()`
  - Rapport enrichi dans `__main__.py` : affiche `already_present` / `to_add` par playlist
  - 7 tests unitaires dans `tests/test_rebuilder.py` (dry-run + exécution, création + mise à jour + skip)
  - 19 tests passent (12 reconciler existants + 7 rebuilder nouveaux)
- Next :
  1. Dry-run complet rebuild sur les 31 playlists (vérifier les compteurs incrémentaux)
  2. Exécution réelle rebuild (`--execute`)
  3. Relancer pour vérifier que le 2ᵉ run détecte 0 tracks à ajouter

### 2026-05-26
- Done :
  - `load_playlist()` retourne aussi le `ratingKey` de la playlist (en plus du titre et metadata)
  - Ajout `save_playlist_json_report()` et `save_playlist_unresolved_csv()` dans `report.py`
  - Noms de fichiers formatés : `reconciliation_{ratingKey}_{nom}_{timestamp}.json` / `unresolved_{ratingKey}_{nom}_{timestamp}.csv`
  - Rapports globaux conservés en parallèle des rapports par playlist
- Next :
  1. Dry-run complet rebuild sur les 31 playlists
  2. Analyser rapport + CSV non-résolus, ajuster seuils fuzzy si besoin
  3. Exécution réelle rebuild (`--execute`)

### 2026-05-24
- Done :
  - Module `repair/` complet : scanner, fixer, report (pré-run + post-run)
  - Scan détecte albums/tracks sans titre (copie titleSort → title) et tracks sans index (extraction depuis noms de fichier)
  - Détection intelligente des patterns de numérotation : disc+track (3-4 chiffres), index brut, overflow (3→4 chiffres)
  - Temporisation (50ms entre appels) + retry automatique (3 tentatives, backoff exponentiel)
  - Rapport pré-exécution CSV sauvegardé avant chaque run
  - Tests réussis sur Jerry Lee Lewis et Jungle Brothers (0 erreur)
  - **Run complet exécuté** : 1 album + 11 374 tracks corrigés, 891 albums rafraîchis, 0 erreur
  - Vérification post-run : il reste 9 albums + 1 track (résidu minimal)
  - Ajout export CSV des tracks non résolues dans `rebuild/report.py`
- Problèmes rencontrés :
  - DNS transitoire (`zimaboard2.local` non résolu) → résolu par retry
  - Deux processus lancés en parallèle par accident → tués et relancé proprement
- Next :
  1. Dry-run complet rebuild sur les 31 playlists
  2. Analyser rapport + CSV non-résolus, ajuster seuils fuzzy si besoin
  3. Exécution réelle rebuild (`--execute`)
  4. Initial commit + repo GitHub

### 2026-05-15
- Done :
  - Fusion de 3 projets en monorepo `plex-tools`
  - Remplacement de `plexapi` par `requests`
  - Restructuration : `export/` + `rebuild/`
  - 12 tests passent, dry-run vérifié
- Next :
  1. Dry-run complet sur les 31 playlists exportées
  2. Exécution réelle rebuild

### 2026-05-14
- Code initial dans plex-playlist-rebuild (supersédé par le monorepo)
- Découverte du timeout plexapi sur grosse bibliothèque

### 2026-05-13
- Bootstrap du projet plex-playlist-rebuild
- Spec rédigée, données source en place

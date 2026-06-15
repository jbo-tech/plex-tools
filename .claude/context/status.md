# Status

## Objectif
Monorepo d'outils CLI Plex : export playlists, export bibliothèque, téléchargement Mega, reconstruction de playlists après reset de BDD, réparation de métadonnées manquantes, détection de doublons, ajout de tracks depuis listes texte.

## Focus actuel
Amélioration continue — critère de sélection bitrate pour le dédoublonnage, commits en attente.

## Log

### 2026-06-15
- Done :
  - `find_exact_duplicates()` modifié : sélection par bitrate (meilleur = conservé) au lieu de "première occurrence"
  - Helpers `_get_bitrate()` et `_pick_best_quality()` dans `dedup/scanner.py`
  - Fallback première occurrence si bitrates égaux ou absents
  - Fixture `_make_track` enrichie (paramètre `bitrate`)
  - 5 nouveaux tests (keep_highest_bitrate, tie→first, missing→first, mixed, multi-group)
  - 69/69 tests passent
- Next :
  1. Commit du changement bitrate
  2. Test live dry-run dedup sur les playlists réelles
  3. Exécution réelle dedup (--execute)

### 2026-06-14
- Done :
  - Module `dedup/` complet : normalizer (version-stripped), scanner (4 analyses), CLI avec dry-run/execute
  - Module `adder/` complet : parser (`Artist – Title`), matching via reconciler, 4 buckets, fuzzy best-candidate
  - Refactoring `config.py` : centralisation de `resolve_playlist`, `get_all_playlists`, `get_playlist_items`, `get_machine_id`, `build_playlist_uri`, `create_playlist`, `add_tracks_to_playlist`
  - `normalize_text` partagé depuis config.py (suppression des duplications dans indexer/reconciler)
  - `rebuild/rebuilder.py` nettoyé : utilise les helpers de config.py, plus de `import requests` local
  - Tests rewriten pour `test_rebuilder.py` (patch sur fonctions importées, plus sur requests)
  - 24 tests dedup + 21 tests adder + tests existants = 64/64 passent
  - `thefuzz[speedup]` pour C-accelerated Levenshtein + cutoff score 30 sur best-candidate
  - Seuils alignés : fuzzy_threshold=85, min_confidence=0.85 (pas de dead-zone)
  - Audit complété : tous les "must fix" et "consider" adressés
  - Documentation orientation régénérée (architecture.md + reference.md)
  - `additions.example.txt` documenting input format
- Next :
  1. Commit de l'ensemble
  2. Test live dry-run sur les playlists réelles
  3. Exécution réelle dedup puis adder

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
  3. Relancer pour vérifier que le 2e run détecte 0 tracks à ajouter

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
  - Scan détecte albums/tracks sans titre (copie titleSort -> title) et tracks sans index (extraction depuis noms de fichier)
  - **Run complet exécuté** : 1 album + 11 374 tracks corrigés, 891 albums rafraîchis, 0 erreur
- Next :
  1. Dry-run complet rebuild sur les 31 playlists

### 2026-05-15
- Done :
  - Fusion de 3 projets en monorepo `plex-tools`
  - Remplacement de `plexapi` par `requests`
  - Restructuration : `export/` + `rebuild/`
  - 12 tests passent, dry-run vérifié

### 2026-05-14
- Code initial dans plex-playlist-rebuild (superseded par le monorepo)

### 2026-05-13
- Bootstrap du projet plex-playlist-rebuild

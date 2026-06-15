---
generated_from_commit: a7c0d23
generated_on: 2026-06-15
---

# Référence — plex-tools

## Drift — à arbitrer

### Décisions non appliquées

Aucune — toutes les décisions enregistrées dans `decisions.md` sont en vigueur dans le code. La décision « Sélection par bitrate pour la déduplication exacte » (2026-06-15) est implémentée dans `dedup/scanner.py`.

### Divergences

Aucune divergence identifiée entre les décisions et le code.

### Drift silencieux (choix sans décision tracée)

| # | Fichier | Question à résoudre |
|---|---------|---------------------|
| 1 | `dedup/normalizer.py` | [⚠ drift: logique de normalisation isolée](#d1-normalisation-version-stripped-sans-décision) — La liste des qualificatifs à retirer (Remastered, Original Mix, Extended, etc.) est codée en dur. Aucune décision ne documente cette liste ni le choix de préserver `feat.` mais pas `Live`. |

### Dette connue

| # | Localisation | Coût si on ne traite pas |
|---|-------------|--------------------------|
| D1 | `check.py` | [⚠ debt: script non-modulaire](#d2-check-py-non-modulaire) — Pas de `main()`, le code s'exécute à l'import. Empêche la réutilisation. |
| D2 | `rebuild/rebuilder.py:72` | [⚠ debt: _find_playlist isolé](#d3-find-playlist-non-partagé) — `_find_playlist` fait un `import requests` local et duplique la logique de `resolve_playlist` (sans le support ratingKey). Devrait utiliser `resolve_playlist` de `config.py`. |

### Docs existants — verdicts

| Fichier | Verdict |
|----------|---------|
| `docs/architecture.md` | Complémentaire — carte pédagogique du système |
| `docs/reference.md` | Ce fichier |

Aucun autre fichier `docs/` à évaluer.

---

## config.py — Socle partagé

### Fonctions publiques

| Fonction | Entrée | Sortie | Comportement |
|----------|--------|--------|-------------|
| `load_credentials()` | — | `(base_url, token)` | Lit `~/.config/plex-tools/config.toml`, `sys.exit(1)` si absent |
| `normalize_text(text)` | `str \| None` | `str` | NFC + lowercase + espaces condensés + strip |
| `plex_headers(token)` | token str | dict | `{"Accept": "application/json", "X-Plex-Token": ...}` |
| `resolve_playlist(base_url, token, identifier)` | nom ou ratingKey | `dict \| None` | Si `identifier.isdigit()` → cherche par ratingKey d'abord, sinon par titre |
| `get_all_playlists(base_url, token)` | — | `list[dict]` | Filtre `playlistType == "audio"` |
| `get_playlist_items(base_url, token, playlist_key)` | ratingKey str | `list[dict]` | GET `/playlists/{key}/items` |
| `get_machine_id(base_url, token)` | — | `str` | machineIdentifier du serveur |
| `build_playlist_uri(machine_id, rating_keys)` | machine_id, `set\|list` | `str` | URI pour créer/ajouter. `set` → sorted, `list` → préserve l'ordre |
| `create_playlist(base_url, token, title, machine_id, rating_keys)` | — | None | POST `/playlists` |
| `add_tracks_to_playlist(base_url, token, playlist_key, machine_id, rating_keys)` | — | None | PUT `/playlists/{key}/items` |

### Config

| Clé (config.toml) | Rôle |
|--------------------|------|
| `[plex].url` | URL du serveur (ex: `http://192.168.1.50:32400`) |
| `[plex].token` | Token d'authentification Plex |

---

## rebuild/ — Reconstruction de playlists

### Commande

```
uv run python -m rebuild [--execute] [--library Music] [--playlist FILTER]
                         [--fuzzy-threshold 80] [--skip-fuzzy] [--report-only]
```

### Pipeline

1. Charge les JSON de playlists depuis `./playlists/`
2. Indexe la bibliothèque live → `PlexIndexes`
3. Réconcilie chaque track source via la cascade
4. Rapport + reconstruction incrémentale

### PlexIndexes (indexer.py)

| Index | Clé | Valeur | Usage |
|-------|-----|--------|-------|
| `by_guid` | GUID Plex | track dict | Match exact |
| `by_filepath` | chemin absolu | track dict | Match exact après déplacement |
| `by_filename` | nom fichier seul | `list[track]` | Match après réorganisation |
| `by_metadata` | `(artist, album, title, track_num)` | track dict | Match sémantique |

### Cascade de réconciliation (reconciler.py)

GUID → filepath → filename (+ durée si ambigu) → metadata exacte → fuzzy (`token_sort_ratio`). S'arrête au premier hit. Retourne `MatchResult(source, matched_track, method, confidence, notes)`.

### Gotchas

- Le fuzzy scan est **O(n)** sur `by_metadata` (scan linéaire). Acceptable pour rebuild (one-shot).
- L'ajout incrémental ne modifie pas l'ordre de la playlist existante — il ajoute en fin.

⚠ debt: <a id="d3-find-playlist-non-partagé"></a> `rebuilder._find_playlist` duplique partiellement `resolve_playlist` (recherche par titre uniquement, sans support ratingKey). Mineur — le rebuilder opère toujours par titre (source = JSON exporté).

---

## dedup/ — Détection de doublons

### Commande

```
uv run python -m dedup [--execute] [--library Music] [--playlist NAME_OR_ID]
                       [--fuzzy-threshold 85]
```

### Analyses

| Analyse | Détection | Action possible |
|---------|-----------|-----------------|
| Doublons exacts (intra) | Même `ratingKey` ×N dans une playlist | `--execute` supprime les doublons, conserve celui avec le meilleur bitrate (fallback 1re occurrence) |
| Overlap cross-playlist | Même `ratingKey` dans 2+ playlists | Jamais supprimé (report only) |
| Near-duplicates | `version_stripped_key` identique, `ratingKey` différents | Jamais supprimé (report only) |
| Orphelins | `Media` vide ou `Part[0].file` absent | Report only |

### Sélection du gagnant (scanner.py)

Fonctions privées qui déterminent quel doublon conserver :

| Fonction | Rôle |
|----------|------|
| `_get_bitrate(item)` | Extrait le bitrate audio depuis `Media[0].bitrate` (bps). Retourne `None` si absent. |
| `_pick_best_quality(items, indices)` | Parcourt les occurrences, retourne l'index avec le bitrate le plus élevé. Fallback première occurrence si égalité ou absence. |

La sélection est appliquée dans `find_exact_duplicates()` — le champ `bitrate` (en bps) est inclus dans chaque dict retourné (visible dans le rapport JSON).

### Normalisation (normalizer.py)

`version_stripped_key(artist, title)` → `(str, str)` :
- NFC + lowercase
- Retire du titre : `(Remastered 2011)`, `(Original Mix)`, `[Radio Edit]`, `(Deluxe)`, trailing ` - Remastered`
- Préserve : `(feat. X)`, `(ft. X)`

⚠ drift: <a id="d1-normalisation-version-stripped-sans-décision"></a> La liste de qualificatifs supprimés n'est documentée dans aucune décision. Le choix de préserver `feat.` mais de supprimer `Live` et `Acoustic` n'est tracé nulle part.

### Rapport JSON

Sauvegardé **après** exécution. En mode `execute`, contient un champ `execution_results: {"removed": N, "errors": N}`.

### Suppression (--execute)

Cible un item spécifique via `DELETE /playlists/{ratingKey}/items/{playlistItemID}`. Utilise `remove_indices` calculé par `find_exact_duplicates()` — tous les indices sauf `keep_index` (le gagnant bitrate).

---

## adder/ — Ajout de tracks

### Commande

```
uv run python -m adder --file INPUT.txt --playlist "Nom ou ID"
                       [--execute] [--library Music]
                       [--min-confidence 0.85] [--fuzzy-threshold 85]
```

### Format d'entrée

```
# Commentaire (ignoré)
Artist – Title
Artist - Title
```

Séparateurs : ` – ` (en-dash) prioritaire, fallback ` - ` (hyphen). ValueError si aucun séparateur sur une ligne non-vide non-commentée.

### Flux

1. Parse fichier → `list[(artist, title)]`
2. Déduplique (NFC + lowercase)
3. Indexe la bibliothèque → `PlexIndexes`
4. Résout la playlist cible (nom ou ratingKey)
5. Réconcilie via `rebuild.reconciler.reconcile()`
6. Catégorise en 4 buckets selon `confidence` vs `min_confidence`
7. Pour les "missing" : 2e passe fuzzy sans seuil → meilleur candidat (score minimum 30 pour être affiché)

### Buckets

| Bucket | Condition | En sortie |
|--------|-----------|-----------|
| added | `confidence >= min_confidence` et absent de playlist | Ajouté avec `--execute` |
| already_present | `confidence >= min_confidence` et déjà dans playlist | Ignoré |
| low_confidence | `0 < confidence < min_confidence` | Report : candidat + score |
| missing | `confidence == 0` | Report : meilleur candidat fuzzy + score |

### Gotchas

- Les seuils `fuzzy_threshold` et `min_confidence` sont **alignés à 85** par défaut. Un match fuzzy à 85 est considéré confiant. Abaisser `fuzzy_threshold` sans abaisser `min_confidence` crée une dead-zone.
- `_find_best_fuzzy_candidate` est O(n) sur la bibliothèque, appelé pour chaque track manquante. Atténué par `thefuzz[speedup]` (binding C).

---

## repair/ — Réparation de métadonnées

### Commande

```
uv run python -m repair [--execute] [--library Music] [--no-index]
                        [--no-refresh] [--artist FILTER] [--report-dir DIR]
```

### Comportement

- Scanne les tracks avec `title` vide (copie `titleSort` → `title`) et index manquant (extrait depuis le nom de fichier)
- Throttle 50ms entre appels + retry exponentiel (3 tentatives)
- Rapport CSV pré-exécution systématique

---

## export/ — Exports

| Commande | Sortie | Flags |
|----------|--------|-------|
| `python -m export.playlists` | `playlists/*.json` | `--id`, `--name`, `--type` |
| `python -m export.library` | `config/*.json` | `--type` |
| `python -m export.download` | fichiers audio | utilise `megadownload` CLI |

---

## check.py — Vérification connexion

Script one-shot. Affiche : nom serveur, version, plateforme, bibliothèques, playlists.

⚠ debt: <a id="d2-check-py-non-modulaire"></a> Pas de guard `if __name__ == "__main__"`. Le code s'exécute à l'import.

---

## Tests

| Fichier | Couverture | Nombre |
|---------|-----------|--------|
| `tests/test_reconciler.py` | Cascade complète + `parse_source_track` | 12 |
| `tests/test_rebuilder.py` | Dry-run incrémental + exécution (create/update/skip) | 7 |
| `tests/test_dedup.py` | `version_stripped_key`, `are_near_duplicates`, `find_exact_duplicates` + sélection bitrate | 29 |
| `tests/test_adder.py` | `parse_track_list`, `deduplicate_entries` | 21 |

Total : 69 tests. Exécution : `uv run pytest tests/ -v`

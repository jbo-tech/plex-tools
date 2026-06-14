## Playlist Hygiene Tooling — Dedup & Adder

### Vision

Deux nouveaux modules CLI pour maintenir les playlists DJ dans Plex : détecter les doublons (exacts et near-duplicates) et ajouter des tracks depuis une liste texte pré-structurée. Extension naturelle du projet existant, réutilisant l'indexer et le reconciler.

### Problem

Après des années de curation manuelle, les playlists DJ accumulent :
- Des doublons exacts (même track ajoutée 2 fois)
- Des versions multiples du même morceau (radio edit, remaster, extended)
- Des entrées orphelines (tracks déplacées/supprimées de la bibliothèque)

Et quand on veut ajouter des tracks depuis une recommandation (blog, ami, LLM), il faut les chercher une par une dans Plex.

### User

DJ amateur avec ~30 playlists Plex, bibliothèque musicale conséquente.

### Success criteria

- [ ] `uv run python -m dedup` produit un rapport 4 sections (doublons exacts, overlap, near-duplicates, orphelins) sans rien muter
- [ ] `uv run python -m dedup --execute` supprime uniquement les doublons exacts intra-playlist (garde la 1re occurrence)
- [ ] Cross-playlist overlap et near-duplicates ne sont JAMAIS supprimés, quel que soit le flag
- [ ] Near-duplicates détectés via version-stripped normalization (retire "(Remastered 2011)", "(Original Mix)", etc.)
- [ ] `uv run python -m adder --file list.txt --playlist "Peak Time"` en dry-run liste ce qui serait ajouté
- [ ] `uv run python -m adder --file list.txt --playlist 12345 --execute` ajoute les tracks confiantes
- [ ] Identification des playlists par nom OU par ratingKey (appliqué aussi à dedup avec `--playlist`)
- [ ] Format d'entrée adder documenté, simple : `Artist – Title` (une par ligne, `#` = commentaire, blanks ignorés)
- [ ] Rapport adder avec 4 buckets : added, already present, low-confidence, missing (+ meilleur candidat fuzzy)
- [ ] Aucune logique de matching dupliquée — le reconciler existant est réutilisé
- [ ] Rapports JSON sous `reports/`
- [ ] Tests unitaires pour le normaliseur version-stripped et le parser de liste

### Scope

**In** :
- Module `dedup/` — 4 analyses, rapport, suppression doublons exacts
- Module `adder/` — parser, matching via reconciler, ajout à playlist
- Helper partagé d'identification playlist (nom ou ratingKey)
- Normaliseur version-stripped (nouvelle logique)
- Tests unitaires ciblés
- Documentation du format d'entrée adder

**Out** :
- Pas de LLM intégré (la structuration de la liste est faite en amont, hors outil)
- Pas d'optimisation performance du fuzzy (acceptable pour l'usage)
- Pas de `--check-dj-metadata` (BPM/key) — itération future si besoin
- Pas de modification du module `rebuild/` ou `repair/`

### Constraints

- Tech : `requests` direct (pas de `plexapi`), `thefuzz`, pas de nouvelle dépendance
- Config : `~/.config/plex-tools/config.toml` via `load_credentials()`
- Pattern CLI : `python -m <module>` avec `__main__.py`
- Dry-run par défaut, `--execute` pour muter
- Commentaires/docstrings en français, noms en anglais

### Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Faux positifs near-duplicates | Rapport pollué | Seuil fuzzy sur base_title + liste d'exclusion pour qualificatifs pertinents (feat., Live) |
| Fuzzy scan lent sur grosse bibliothèque | UX dégradée pour adder | Acceptable pour v1, skip étapes 1-3 du reconciler quand guid/path absents |
| API Plex : suppression de doublons sans perdre l'ordre | Corruption playlist | Supprimer par index inversé (du dernier au premier) pour préserver les positions |

### Architecture

#### Overview

Deux modules autonomes suivant le pattern `rebuild/`. Extraction d'un helper partagé pour la résolution playlist (nom/ID). Ajout d'un normaliseur version-stripped dans `dedup/` pour la détection de near-duplicates.

#### Key decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Identification playlist | Nom ou ratingKey, helper partagé | Cohérence projet, UX flexible |
| Format entrée adder | `Artist – Title` strict, LLM en amont | Pas de parsing heuristique fragile |
| Near-duplicate key | `(normalized_artist, base_title)` | Regroupe versions d'un même morceau |
| Suppression doublons | API DELETE sur items spécifiques | Préserve l'ordre de la playlist |

#### Components

- **`dedup/scanner.py`** : lit les playlists live, construit les structures de détection
- **`dedup/normalizer.py`** : version-stripped normalization (retire qualificatifs)
- **`dedup/__main__.py`** : CLI + orchestration + rapport
- **`adder/parser.py`** : parse le fichier texte structuré
- **`adder/__main__.py`** : CLI + matching via reconciler + ajout
- **`config.py`** (extension) : helper `resolve_playlist(base_url, token, identifier)` → playlist dict

#### Data flow

```
DEDUP:
  API Plex → playlists live → scanner → 4 analyses → rapport + (execute → API DELETE)

ADDER:
  fichier texte → parser → [SourceTrack(artist, title)] → reconcile() → filtre confiance
    → rapport + (execute → API PUT playlist/items)
```

### Open questions

Aucun — prêt pour implémentation.

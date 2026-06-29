# Décisions

Décisions techniques et leur contexte. Alimenté via `/retro`.

### Monorepo plex-tools
**Décision** : Fusionner plex-playlist-to-json, plex-playlist-rebuild et plex-playlist-download en un seul repo `plex-tools`.
**Contexte** : Même domaine, mêmes credentials, workflow naturel export → rebuild. Repos séparés = friction inutile.
**Alternatives envisagées** : Garder des repos séparés avec pratiques alignées — rejeté pour la friction.
**Date** : 2026-05-15

### Structure export/ + rebuild/ (groupé par fonction)
**Décision** : Scripts d'export dans `export/` (playlists, library, download), pipeline rebuild dans `rebuild/` (indexer, reconciler, rebuilder, report), utilitaires simples à la racine (check.py, config.py).
**Contexte** : Tous les scripts à la racine créait confusion et manque de lisibilité (9 fichiers .py au même niveau).
**Alternatives envisagées** : Structure flat avec convention de nommage (export_*, rebuild_*) — rejeté car ne scale pas.
**Date** : 2026-05-15

### requests au lieu de plexapi
**Décision** : API HTTP Plex directe via `requests` plutôt que le wrapper `plexapi`.
**Contexte** : `plexapi` provoquait des timeouts sur une bibliothèque de 453k tracks. `requests` avec `Accept: application/json` est plus léger et on contrôle les champs demandés. L'autre projet (export) utilisait déjà `requests` avec succès.
**Alternatives envisagées** : Garder plexapi avec pagination — complexe et non documenté pour ce cas.
**Date** : 2026-05-15

### Cascade de matching à 5 niveaux
**Décision** : GUID → filepath → filename → metadata exactes → fuzzy. On s'arrête au premier match.
**Contexte** : Déduit de la spec (2026-05-12). Chaque niveau est plus permissif et moins fiable.
**Date** : 2026-05-12

### Credentials partagés ~/.config/plex-tools/config.toml
**Décision** : URL + token dans un TOML partagé, réglages projet en args CLI.
**Contexte** : Plusieurs outils Plex, pas de duplication de credentials.
**Alternatives envisagées** : Package partagé (prématuré), keyring (trop lourd).
**Date** : 2026-05-14

### uv + pyproject.toml
**Décision** : `uv` plutôt que pip + requirements.txt.
**Contexte** : Préférence utilisateur, rapide, lockfile reproductible.
**Date** : 2026-05-14

### Pas de .env, args CLI avec défauts
**Décision** : Réglages projet en arguments CLI (--library, --playlist, --output-dir).
**Contexte** : Peu de réglages, défauts sensibles. Évite une dépendance inutile (python-dotenv).
**Date** : 2026-05-14

### Module repair/ — titleSort → title + index depuis filename
**Décision** : Copier `titleSort` dans `title` via PUT API Plex pour les items où `title` est vide. Extraire les index de piste depuis les préfixes numériques des noms de fichier avec analyse au niveau album.
**Contexte** : ~10% de la bibliothèque (3 116 albums, 47K tracks) avait `title` vide alors que `titleSort` était peuplé. Les index manquaient aussi sur ~48K tracks. L'analyse album-level permet de distinguer disc+track (101=disc1 track01) vs index brut (101=piste 101).
**Alternatives envisagées** : Scan Plex natif (ne corrige pas ce type de problème), plexapi (timeout sur 471K tracks).
**Date** : 2026-05-23

### Throttle + retry sur les appels API Plex en masse
**Décision** : 50ms de délai entre chaque appel API + retry automatique (3 tentatives, backoff exponentiel 2s/4s/8s) via `urllib3.Retry`.
**Contexte** : Le serveur Plex tourne sur un ZimaBoard (SBC basse consommation). Un premier run sans throttle a provoqué des erreurs DNS transitoires. ~109K appels API nécessaires.
**Alternatives envisagées** : Pas de throttle (crash DNS), batch API (non supporté par Plex).
**Date** : 2026-05-24

### Rapport pré-exécution systématique
**Décision** : Sauvegarder un CSV complet de l'état "avant" (tous les items à corriger + non traitables) avant d'appliquer les corrections.
**Contexte** : Opération irréversible sur ~109K items. Le rapport permet de vérifier et de rollback manuellement si nécessaire.
**Date** : 2026-05-24

### Rapports par playlist avec ratingKey dans le nom de fichier
**Décision** : Produire un rapport JSON et un CSV par playlist (en plus du rapport global), avec `ratingKey` et nom de la playlist dans le nom de fichier.
**Contexte** : Faciliter l'identification des rapports quand on traite plusieurs playlists. Le format `reconciliation_{ratingKey}_{nom}_{timestamp}.json` permet de retrouver immédiatement de quelle playlist il s'agit, même hors contexte.
**Alternatives envisagées** : Rapport global seul avec timestamp (actuel) — pas assez identifiable. Ajout console dans les tracks (rejeté par l'utilisateur, c'est le nom de fichier qui compte).
**Date** : 2026-05-26

### Dry-run par défaut
**Décision** : `--execute` requis pour créer les playlists. Sans flag, dry-run + rapport.
**Contexte** : Reconstruction destructive si faux positifs ; le rapport doit être validé d'abord.
**Date** : 2026-05-12

### Rebuild incrémental (approche A : diff + ajout)
**Décision** : Avant de créer une playlist, chercher par titre exact sur le serveur. Si elle existe, comparer les ratingKeys présents et n'ajouter que les manquants via `PUT /playlists/{id}/items`.
**Contexte** : Relancer `rebuild --execute` dupliquait les playlists. L'approche incrémentale permet de relancer sans risque et de ne traiter que le delta.
**Alternatives envisagées** : Approche B (supprimer + recréer) — plus simple mais perd l'ordre et les modifications manuelles de l'utilisateur.
**Date** : 2026-06-01

### Helpers Plex centralisés dans config.py
**Décision** : Fonctions d'écriture Plex (`get_machine_id`, `build_playlist_uri`, `create_playlist`, `add_tracks_to_playlist`) et de lecture (`get_all_playlists`, `get_playlist_items`, `resolve_playlist`) dans `config.py` plutôt que dupliquées dans chaque module.
**Contexte** : Le rebuilder avait ses propres helpers privés (`_find_playlist`, `_create_playlist`, etc.) qui dupliquaient la logique. `adder/` et `dedup/` ont besoin des mêmes opérations. Centraliser évite la divergence.
**Alternatives envisagées** : Module `plex_api.py` séparé — prématuré, `config.py` fait office de couche d'accès partagée et la cohésion est suffisante.
**Date** : 2026-06-14

### resolve_playlist : ratingKey prioritaire si identifier est numérique
**Décision** : Si `identifier.isdigit()`, chercher d'abord par `ratingKey`, puis fallback par titre. Sinon, recherche par titre uniquement.
**Contexte** : Les ratingKeys sont numériques. Un utilisateur passant "12345" veut probablement l'ID, pas une playlist nommée "12345". Le fallback par titre permet de traiter les rares cas où un nombre est un vrai nom de playlist.
**Date** : 2026-06-14

### Seuils fuzzy alignés à 85
**Décision** : `fuzzy_threshold=85` et `min_confidence=0.85` par défaut dans `adder/`. Un match fuzzy à 85+ est considéré confiant.
**Contexte** : Si `fuzzy_threshold < min_confidence`, les matches entre les deux seuils tombent dans une dead-zone (acceptés par le reconciler mais rejetés par l'adder). Aligner évite ce piège.
**Alternatives envisagées** : fuzzy_threshold=80 + min_confidence=85 (proposé initialement dans le scope, créait la dead-zone).
**Date** : 2026-06-14

### thefuzz[speedup] + cutoff score 30
**Décision** : Dépendre de `thefuzz[speedup]` (python-Levenshtein binding C) et couper la recherche best-candidate en dessous d'un score de 30.
**Contexte** : `_find_best_fuzzy_candidate` est O(n) sur la bibliothèque entière. Le binding C accélère le calcul de distance (~10x). Le cutoff 30 évite d'afficher des candidats absurdes.
**Date** : 2026-06-14

### Sélection par bitrate pour la déduplication exacte
**Décision** : Dans `find_exact_duplicates()`, conserver la track avec le bitrate le plus élevé (moins de compression) plutôt que la première occurrence dans la playlist.
**Contexte** : Quand un même morceau apparaît plusieurs fois dans une playlist (même `ratingKey`), le premier ajouté n'est pas nécessairement la meilleure version. Le bitrate est un critère objectif de qualité audio. En cas d'égalité, fallback sur la première occurrence.
**Alternatives envisagées** : Première occurrence seulement (comportement précédent) — simple mais peut conserver un MP3 128kbps alors qu'un FLAC est présent. Codec ou canaux comme critère secondaire — pas nécessaire, le bitrate suffit comme proxy de qualité.
**Date** : 2026-06-15

### Dedup : rapport JSON sauvegardé après exécution
**Décision** : Le rapport JSON est écrit après l'éventuelle suppression, et contient un champ `execution_results` avec les compteurs réels.
**Contexte** : Sauvegarder avant exécution puis récrire après serait confus. Un seul rapport post-hoc reflète l'état final.
**Date** : 2026-06-14

### Adder consomme directement le CSV `unresolved` de rebuild
**Décision** : Étendre `adder` pour lire le CSV `unresolved` (auto-détection par extension `.csv`) plutôt qu'un convertisseur séparé. La playlist est lue dans la colonne `Playlist` (groupement par playlist, index construit une seule fois) ; `--playlist` devient optionnel et sert d'override.
**Contexte** : Le CSV porte déjà la playlist par ligne et l'album — un convertisseur vers le format texte perdrait ces infos et imposerait de retaper le nom. Boucler rebuild → adder permet de réinjecter les non-résolues après ajout en bibliothèque.
**Alternatives envisagées** : Script convertisseur CSV → texte (perd playlist + album) ; nouveau sous-module dédié (duplique toute la logique de matching/ajout).
**Date** : 2026-06-29

### Adder : pas de création de playlist par défaut (--create opt-in)
**Décision** : Par défaut, l'adder n'ajoute que dans des playlists **existantes**. Une playlist introuvable est ignorée avec avertissement. La création nécessite `--create` explicite.
**Contexte** : Directive utilisateur explicite (« il ne faut pas que cela crée une nouvelle playlist »). Le risque : `resolve_playlist` (match exact) échoue sur un nom légèrement différent → duplication silencieuse. Le défaut sûr protège aussi l'import texte.
**Alternatives envisagées** : Garder la création auto (comportement précédent) ; flag `--no-create` (mais le défaut resterait dangereux).
**Date** : 2026-06-29

### Album du CSV passé au reconciler, fallback intrinsèque
**Décision** : Passer l'album du CSV au reconciler (était `None`), sans second passage « sans album ».
**Contexte** : La cascade fournit déjà le fallback : l'étape « metadata exacte » utilise la clé `(artist, album, title, track_number)` ; le CSV n'ayant pas de numéro de piste (`None`), cette étape matche rarement, et la recherche tombe sur le fuzzy qui ne compare que `artist + title` (album ignoré). Passer l'album est donc strictement additif — il peut ajouter un match exact, jamais en bloquer un.
**Alternatives envisagées** : Double passage explicite (avec puis sans album) — redondant vu la cascade ; modifier le reconciler pour ignorer `track_number` quand absent — changement plus large, non retenu pour l'instant.
**Date** : 2026-06-29

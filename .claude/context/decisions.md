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
**Décision** : Réglages projet en arguments CLI (--library, --playlist-dir, --output-dir).
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

### Dry-run par défaut
**Décision** : `--execute` requis pour créer les playlists. Sans flag, dry-run + rapport.
**Contexte** : Reconstruction destructive si faux positifs ; le rapport doit être validé d'abord.
**Date** : 2026-05-12

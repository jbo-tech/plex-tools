# Anti-patterns

Erreurs rencontrées et comment les éviter. Alimenté via `/retro`.

### plexapi timeout sur grosses bibliothèques
**Problème** : `plexapi.searchTracks()` et `section.all(libtype='track')` bloquent indéfiniment sur une bibliothèque de 453k morceaux.
**Cause** : `plexapi` charge tous les attributs de chaque objet Track (médias, parts, guids, etc.) via des requêtes XML lourdes, sans pagination efficace.
**Solution** : Utiliser `requests` en direct sur l'API HTTP Plex (`/library/sections/{key}/all?type=10` avec `Accept: application/json`). Réponse JSON plus légère, une seule requête, temps acceptable même pour 453k tracks.
**Date** : 2026-05-15

### Processus background non terminés qui s'accumulent
**Problème** : Deux runs `repair --execute` tournaient simultanément, doublant la charge sur le serveur Plex et causant des conflits.
**Cause** : Le premier run (lancé en background) n'avait pas été explicitement tué après son échec DNS. Le second run a été lancé sans vérifier que le premier était arrêté.
**Solution** : Toujours vérifier `ps aux | grep` qu'aucun processus précédent ne tourne avant de relancer une commande longue en background.
**Date** : 2026-05-24

### Regex 3 chiffres ne couvre pas les préfixes 4 chiffres (DDTT)
**Problème** : Les numéros de piste n'étaient pas extraits pour les fichiers avec préfixes 4 chiffres (ex: `0101`, `0201`).
**Cause** : Le pattern regex `^(\d)(\d{2})\b` ne matchait que 3 chiffres. Le format DDTT (2 chiffres disc + 2 chiffres track) n'était pas géré.
**Solution** : Analyser les préfixes par longueur, puis déterminer le pattern (disc+track vs index brut) au niveau de l'album entier, pas track par track.
**Date** : 2026-05-23

### section.all() retourne artistes + albums + tracks
**Problème** : `section.all()` sans filtre retourne tous les objets de la bibliothèque, pas seulement les tracks → `AttributeError: 'Artist' object has no attribute 'media'`.
**Cause** : Dans plexapi, `all()` retourne le type par défaut de la section (artistes pour une bibliothèque musicale).
**Solution** : Spécifier `libtype='track'` ou, mieux, utiliser l'API HTTP avec `type=10`.
**Date** : 2026-05-15

### Tests qui patchent des imports supprimés
**Problème** : Après refactoring de `rebuild/rebuilder.py` (suppression de `import requests`, remplacement par helpers de config.py), les tests échouaient avec `AttributeError: <module 'rebuild.rebuilder'> does not have the attribute 'requests'`.
**Cause** : Les tests patchaient `rebuild.rebuilder.requests.get` etc., mais le module n'importait plus `requests` directement.
**Solution** : Patcher les fonctions telles qu'elles sont importées dans le module sous test (`rebuild.rebuilder._find_playlist`, `rebuild.rebuilder.get_playlist_items`, etc.). Règle : toujours patcher "where it's used", pas "where it's defined".
**Date** : 2026-06-14

### Dead-zone entre fuzzy_threshold et min_confidence
**Problème** : Avec `fuzzy_threshold=80` et `min_confidence=0.85`, les matches fuzzy entre 80 et 84 étaient acceptés par le reconciler mais rejetés par l'adder — ils tombaient dans "low_confidence" au lieu d'être soit confiants soit refusés.
**Cause** : Deux seuils indépendants configurés à des valeurs divergentes créent une bande morte.
**Solution** : Aligner les deux seuils (tous deux à 85 par défaut). Documenter le piège : abaisser `fuzzy_threshold` sans abaisser `min_confidence` crée une dead-zone.
**Date** : 2026-06-14

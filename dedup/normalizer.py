"""Normalisation de titres pour détecter les variantes d'un même morceau."""

import re
import unicodedata

from thefuzz import fuzz


# Suffixes à retirer après un tiret (insensible à la casse)
_TRAILING_DASH_PATTERNS = re.compile(
    r"\s*-\s*(remaster(ed)?|radio edit|single version|album version|"
    r"original mix|extended mix|bonus track|live|acoustic|remix|edit|"
    r"mono|stereo|deluxe|explicit|clean)(\s+\d{4})?\s*$",
    re.IGNORECASE,
)

# Contenu entre parenthèses/crochets à retirer, SAUF feat./ft.
_PAREN_CONTENT = re.compile(r"[\(\[][^\)\]]*[\)\]]")
_FEAT_PATTERN = re.compile(r"fe?a?t\.?\s+", re.IGNORECASE)


def _remove_version_markers(title: str) -> str:
    """Retire les marqueurs de version (parenthèses, crochets, suffixes tiret)."""
    # Retirer les suffixes après tiret
    title = _TRAILING_DASH_PATTERNS.sub("", title)

    # Retirer le contenu entre parenthèses/crochets sauf feat./ft.
    def _keep_feat(match: re.Match) -> str:
        content = match.group(0)
        if _FEAT_PATTERN.search(content):
            return content
        return ""

    title = _PAREN_CONTENT.sub(_keep_feat, title)
    return title


def version_stripped_key(artist: str, title: str) -> tuple[str, str]:
    """Normalise artiste et titre pour comparaison version-agnostique.

    Retourne (artiste_normalisé, titre_strippé).
    """
    # NFC normalize, lowercase, strip
    artist = unicodedata.normalize("NFC", artist).lower().strip()
    title = unicodedata.normalize("NFC", title).lower().strip()

    # Retirer les marqueurs de version du titre
    title = _remove_version_markers(title)

    # Condenser les espaces multiples
    artist = re.sub(r"\s+", " ", artist).strip()
    title = re.sub(r"\s+", " ", title).strip()

    return (artist, title)


def are_near_duplicates(
    track_a: dict, track_b: dict, fuzzy_threshold: int = 85
) -> bool:
    """Détermine si deux tracks sont des quasi-doublons (versions différentes du même morceau)."""
    artist_a = track_a.get("grandparentTitle", "")
    title_a = track_a.get("title", "")
    artist_b = track_b.get("grandparentTitle", "")
    title_b = track_b.get("title", "")

    norm_artist_a, norm_title_a = version_stripped_key(artist_a, title_a)
    norm_artist_b, norm_title_b = version_stripped_key(artist_b, title_b)

    # Artistes trop différents → pas un doublon
    if fuzz.ratio(norm_artist_a, norm_artist_b) < 80:
        return False

    # Titres identiques après normalisation
    if norm_title_a == norm_title_b:
        return True

    # Matching fuzzy sur les titres strippés
    if fuzz.ratio(norm_title_a, norm_title_b) >= fuzzy_threshold:
        return True

    return False

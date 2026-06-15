"""Tests unitaires pour le module dedup."""

import pytest

from dedup.normalizer import version_stripped_key, are_near_duplicates
from dedup.scanner import find_exact_duplicates


# --- Fixtures ---


def _make_track(rating_key, title, artist="Artist", playlist_item_id=None, media=None, bitrate=None):
    """Crée un dict track simulant la réponse API Plex.

    Args:
        rating_key: identifiant unique de la track.
        title: titre.
        artist: artiste.
        playlist_item_id: identifiant dans la playlist.
        media: dict Media complet (prioritaire sur bitrate).
        bitrate: bitrate audio en bps (raccourci, ignoré si media est fourni).
    """
    track = {
        "ratingKey": str(rating_key),
        "title": title,
        "grandparentTitle": artist,
        "parentTitle": "Album",
        "duration": 240000,
        "index": 1,
    }
    if playlist_item_id is not None:
        track["playlistItemID"] = playlist_item_id
    if media is not None:
        track["Media"] = media
    elif bitrate is not None:
        track["Media"] = [{"bitrate": bitrate, "Part": [{"file": f"/music/{title}.flac"}]}]
    else:
        track["Media"] = [{"Part": [{"file": f"/music/{title}.flac"}]}]
    return track


# --- Tests version_stripped_key ---


class TestVersionStrippedKey:
    def test_clean_title_unchanged(self):
        artist, title = version_stripped_key("Radiohead", "Karma Police")
        assert artist == "radiohead"
        assert title == "karma police"

    def test_remastered_parentheses_removed(self):
        _, title = version_stripped_key("Pink Floyd", "Comfortably Numb (Remastered 2011)")
        assert title == "comfortably numb"

    def test_remastered_no_year(self):
        _, title = version_stripped_key("Pink Floyd", "Comfortably Numb (Remastered)")
        assert title == "comfortably numb"

    def test_original_mix_removed(self):
        _, title = version_stripped_key("Depeche Mode", "Enjoy the Silence (Original Mix)")
        assert title == "enjoy the silence"

    def test_extended_mix_removed(self):
        _, title = version_stripped_key("Daft Punk", "Around the World (Extended Mix)")
        assert title == "around the world"

    def test_radio_edit_brackets_removed(self):
        _, title = version_stripped_key("Oasis", "Wonderwall [Radio Edit]")
        assert title == "wonderwall"

    def test_deluxe_removed(self):
        _, title = version_stripped_key("Adele", "Hello (Deluxe)")
        assert title == "hello"

    def test_feat_preserved(self):
        _, title = version_stripped_key("Drake", "Sicko Mode (feat. Travis Scott)")
        assert "feat. travis scott" in title

    def test_ft_preserved(self):
        _, title = version_stripped_key("Rihanna", "Monster (ft. Eminem)")
        assert "ft. eminem" in title

    def test_trailing_dash_remaster(self):
        _, title = version_stripped_key("Led Zeppelin", "Stairway to Heaven - Remastered")
        assert title == "stairway to heaven"

    def test_trailing_dash_radio_edit(self):
        _, title = version_stripped_key("Muse", "Supermassive Black Hole - Radio Edit")
        assert title == "supermassive black hole"

    def test_trailing_dash_remaster_with_year(self):
        _, title = version_stripped_key("The Beatles", "Let It Be - Remastered 2009")
        assert title == "let it be"

    def test_whitespace_condensed(self):
        artist, title = version_stripped_key("  The   Beatles  ", "  Hey   Jude  ")
        assert artist == "the beatles"
        assert title == "hey jude"

    def test_unicode_nfc(self):
        artist, title = version_stripped_key("Björk", "Hyper-Ballad")
        assert artist == "björk"


# --- Tests are_near_duplicates ---


class TestAreNearDuplicates:
    def test_same_track_different_versions(self):
        track_a = _make_track(100, "Comfortably Numb (Remastered 2011)", "Pink Floyd")
        track_b = _make_track(200, "Comfortably Numb", "Pink Floyd")
        assert are_near_duplicates(track_a, track_b) is True

    def test_same_track_dash_variant(self):
        track_a = _make_track(100, "Stairway to Heaven - Remastered", "Led Zeppelin")
        track_b = _make_track(200, "Stairway to Heaven", "Led Zeppelin")
        assert are_near_duplicates(track_a, track_b) is True

    def test_different_artists_not_duplicates(self):
        track_a = _make_track(100, "Dreams", "Fleetwood Mac")
        track_b = _make_track(200, "Dreams", "The Cranberries")
        assert are_near_duplicates(track_a, track_b) is False

    def test_completely_different_tracks(self):
        track_a = _make_track(100, "Bohemian Rhapsody", "Queen")
        track_b = _make_track(200, "Stairway to Heaven", "Led Zeppelin")
        assert are_near_duplicates(track_a, track_b) is False

    def test_similar_titles_fuzzy_match(self):
        track_a = _make_track(100, "Dont Stop Me Now", "Queen")
        track_b = _make_track(200, "Don't Stop Me Now", "Queen")
        assert are_near_duplicates(track_a, track_b) is True

    def test_feat_variants_still_match(self):
        track_a = _make_track(100, "Monster (feat. Eminem)", "Rihanna")
        track_b = _make_track(200, "Monster (ft. Eminem)", "Rihanna")
        assert are_near_duplicates(track_a, track_b) is True


# --- Tests find_exact_duplicates ---


class TestFindExactDuplicates:
    def test_no_duplicates(self):
        items = [
            _make_track(1, "Track A", playlist_item_id=10),
            _make_track(2, "Track B", playlist_item_id=11),
            _make_track(3, "Track C", playlist_item_id=12),
        ]
        result = find_exact_duplicates(items)
        assert result == []

    def test_single_duplicate(self):
        items = [
            _make_track(1, "Track A", playlist_item_id=10),
            _make_track(2, "Track B", playlist_item_id=11),
            _make_track(1, "Track A", playlist_item_id=12),
        ]
        result = find_exact_duplicates(items)
        assert len(result) == 1
        assert result[0]["ratingKey"] == "1"
        assert result[0]["occurrences"] == 2
        assert result[0]["keep_index"] == 0
        assert result[0]["remove_indices"] == [2]

    def test_triple_duplicate(self):
        items = [
            _make_track(1, "Track A", playlist_item_id=10),
            _make_track(1, "Track A", playlist_item_id=11),
            _make_track(2, "Track B", playlist_item_id=12),
            _make_track(1, "Track A", playlist_item_id=13),
        ]
        result = find_exact_duplicates(items)
        assert len(result) == 1
        assert result[0]["ratingKey"] == "1"
        assert result[0]["occurrences"] == 3
        assert result[0]["keep_index"] == 0
        assert result[0]["remove_indices"] == [1, 3]

    def test_multiple_different_duplicates(self):
        items = [
            _make_track(1, "Track A", playlist_item_id=10),
            _make_track(2, "Track B", playlist_item_id=11),
            _make_track(1, "Track A", playlist_item_id=12),
            _make_track(2, "Track B", playlist_item_id=13),
        ]
        result = find_exact_duplicates(items)
        assert len(result) == 2
        keys = {r["ratingKey"] for r in result}
        assert keys == {"1", "2"}

    def test_keep_highest_bitrate(self):
        """Conserve la track avec le bitrate le plus élevé."""
        items = [
            _make_track(1, "Track A", playlist_item_id=10, bitrate=128000),
            _make_track(1, "Track A", playlist_item_id=11, bitrate=320000),
            _make_track(1, "Track A", playlist_item_id=12, bitrate=256000),
        ]
        result = find_exact_duplicates(items)
        assert len(result) == 1
        # La 2e occurrence (index 1) a le meilleur bitrate
        assert result[0]["keep_index"] == 1
        assert result[0]["remove_indices"] == [0, 2]
        assert result[0]["bitrate"] == 320000

    def test_bitrate_tie_falls_back_to_first(self):
        """En cas d'égalité de bitrate, conserve la première occurrence."""
        items = [
            _make_track(1, "Track A", playlist_item_id=10, bitrate=320000),
            _make_track(1, "Track A", playlist_item_id=11, bitrate=320000),
        ]
        result = find_exact_duplicates(items)
        assert len(result) == 1
        assert result[0]["keep_index"] == 0
        assert result[0]["remove_indices"] == [1]

    def test_missing_bitrate_falls_back_to_first(self):
        """Si le bitrate est absent, conserve la première occurrence."""
        items = [
            _make_track(1, "Track A", playlist_item_id=10),
            _make_track(1, "Track A", playlist_item_id=11),
        ]
        result = find_exact_duplicates(items)
        assert len(result) == 1
        assert result[0]["keep_index"] == 0
        assert result[0]["remove_indices"] == [1]

    def test_mixed_bitrate_some_missing(self):
        """Certaines tracks ont un bitrate, d'autres non — garde le bitrate max."""
        items = [
            _make_track(1, "Track A", playlist_item_id=10),             # pas de bitrate → 0
            _make_track(1, "Track A", playlist_item_id=11, bitrate=192000),
        ]
        result = find_exact_duplicates(items)
        assert len(result) == 1
        # La 2e (index 1) a le bitrate le plus élevé
        assert result[0]["keep_index"] == 1
        assert result[0]["remove_indices"] == [0]

    def test_keep_highest_bitrate_with_different_tracks(self):
        """Deux groupes de doublons, chacun avec son propre gagnant bitrate."""
        items = [
            _make_track(1, "Track A", playlist_item_id=10, bitrate=128000),
            _make_track(2, "Track B", playlist_item_id=11, bitrate=320000),
            _make_track(1, "Track A", playlist_item_id=12, bitrate=320000),
            _make_track(2, "Track B", playlist_item_id=13, bitrate=192000),
        ]
        result = find_exact_duplicates(items)
        assert len(result) == 2

        dup_a = next(r for r in result if r["ratingKey"] == "1")
        dup_b = next(r for r in result if r["ratingKey"] == "2")

        # Track A : bitrate 128000 (idx 0) vs 320000 (idx 2) → garde idx 2
        assert dup_a["keep_index"] == 2
        assert dup_a["remove_indices"] == [0]
        assert dup_a["bitrate"] == 320000

        # Track B : bitrate 320000 (idx 1) vs 192000 (idx 3) → garde idx 1
        assert dup_b["keep_index"] == 1
        assert dup_b["remove_indices"] == [3]
        assert dup_b["bitrate"] == 320000

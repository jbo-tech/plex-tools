"""Tests du rebuilder incrémental."""

from unittest.mock import patch, MagicMock

from rebuild.rebuilder import rebuild_playlist
from rebuild.reconciler import MatchResult, SourceTrack


def _source(rk="100"):
    return SourceTrack(
        guid=None, filepath=None, artist="A", album="B", title="T",
        track_number=1, disc_number=1, duration_ms=200000,
        original_rating_key=rk,
    )


def _match(rk="200", resolved=True):
    track = {"ratingKey": rk, "title": "T"} if resolved else None
    return MatchResult(
        source=_source(), matched_track=track,
        method="guid" if resolved else "unresolved",
        confidence=1.0 if resolved else 0.0, notes="",
    )


def _patch_find_playlist(existing_playlist=None):
    """Mock pour _find_playlist interne au rebuilder."""
    def mock_find(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        metadata = [existing_playlist] if existing_playlist else []
        resp.json.return_value = {"MediaContainer": {"Metadata": metadata}}
        return resp
    return mock_find


class TestDryRunIncremental:
    def test_no_existing_playlist_shows_all_to_add(self):
        matches = [_match("200"), _match("201")]

        with (
            patch("rebuild.rebuilder._find_playlist", return_value=None),
        ):
            result = rebuild_playlist("http://plex", "token", "Ma Playlist", matches, dry_run=True)

        assert result["already_present"] == 0
        assert result["to_add"] == 2
        assert not result["created"]
        assert not result["updated"]

    def test_existing_playlist_all_present_skipped(self):
        matches = [_match("200"), _match("201")]
        playlist = {"ratingKey": "PL1", "title": "Ma Playlist"}

        with (
            patch("rebuild.rebuilder._find_playlist", return_value=playlist),
            patch("rebuild.rebuilder.get_playlist_items", return_value=[
                {"ratingKey": "200"}, {"ratingKey": "201"},
            ]),
        ):
            result = rebuild_playlist("http://plex", "token", "Ma Playlist", matches, dry_run=True)

        assert result["already_present"] == 2
        assert result["to_add"] == 0
        assert result["skipped"] is True
        assert "déjà présentes" in result["reason"]

    def test_existing_playlist_partial_shows_diff(self):
        matches = [_match("200"), _match("201"), _match("202")]
        playlist = {"ratingKey": "PL1", "title": "Ma Playlist"}

        with (
            patch("rebuild.rebuilder._find_playlist", return_value=playlist),
            patch("rebuild.rebuilder.get_playlist_items", return_value=[
                {"ratingKey": "200"},
            ]),
        ):
            result = rebuild_playlist("http://plex", "token", "Ma Playlist", matches, dry_run=True)

        assert result["already_present"] == 1
        assert result["to_add"] == 2

    def test_no_resolved_tracks_skipped(self):
        matches = [_match(resolved=False)]

        with (
            patch("rebuild.rebuilder._find_playlist", return_value=None),
        ):
            result = rebuild_playlist("http://plex", "token", "Ma Playlist", matches, dry_run=True)

        assert result["skipped"] is True
        assert "aucune track" in result["reason"]


class TestExecuteIncremental:
    def test_creates_new_playlist(self):
        matches = [_match("200")]

        with (
            patch("rebuild.rebuilder._find_playlist", return_value=None),
            patch("rebuild.rebuilder.get_machine_id", return_value="abc123"),
            patch("rebuild.rebuilder.create_playlist") as create_mock,
        ):
            result = rebuild_playlist("http://plex", "token", "Ma Playlist", matches, dry_run=False)

        assert result["created"] is True
        assert not result["updated"]
        create_mock.assert_called_once()

    def test_updates_existing_playlist(self):
        matches = [_match("200"), _match("201")]
        playlist = {"ratingKey": "PL1", "title": "Ma Playlist"}

        with (
            patch("rebuild.rebuilder._find_playlist", return_value=playlist),
            patch("rebuild.rebuilder.get_playlist_items", return_value=[
                {"ratingKey": "200"},
            ]),
            patch("rebuild.rebuilder.get_machine_id", return_value="abc123"),
            patch("rebuild.rebuilder.create_playlist") as create_mock,
            patch("rebuild.rebuilder.add_tracks_to_playlist") as add_mock,
        ):
            result = rebuild_playlist("http://plex", "token", "Ma Playlist", matches, dry_run=False)

        assert result["updated"] is True
        assert not result["created"]
        add_mock.assert_called_once()
        create_mock.assert_not_called()

    def test_skips_when_all_present(self):
        matches = [_match("200")]
        playlist = {"ratingKey": "PL1", "title": "Ma Playlist"}

        with (
            patch("rebuild.rebuilder._find_playlist", return_value=playlist),
            patch("rebuild.rebuilder.get_playlist_items", return_value=[
                {"ratingKey": "200"},
            ]),
            patch("rebuild.rebuilder.get_machine_id", return_value="abc123") as machine_mock,
            patch("rebuild.rebuilder.create_playlist") as create_mock,
            patch("rebuild.rebuilder.add_tracks_to_playlist") as add_mock,
        ):
            result = rebuild_playlist("http://plex", "token", "Ma Playlist", matches, dry_run=False)

        assert result["skipped"] is True
        create_mock.assert_not_called()
        add_mock.assert_not_called()
        machine_mock.assert_not_called()

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


def _mock_plex_responses(existing_playlist=None, existing_keys=None):
    """Configure les mocks pour les appels API Plex."""
    existing_keys = existing_keys or set()

    def mock_get(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if url.endswith("/playlists"):
            metadata = [existing_playlist] if existing_playlist else []
            resp.json.return_value = {"MediaContainer": {"Metadata": metadata}}
        elif "/playlists/" in url and "/items" in url:
            items = [{"ratingKey": k} for k in existing_keys]
            resp.json.return_value = {"MediaContainer": {"Metadata": items}}
        elif url.endswith("/"):
            resp.json.return_value = {"MediaContainer": {"machineIdentifier": "abc123"}}
        return resp

    def mock_post(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        return resp

    def mock_put(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        return resp

    return mock_get, mock_post, mock_put


class TestDryRunIncremental:
    def test_no_existing_playlist_shows_all_to_add(self):
        matches = [_match("200"), _match("201")]
        mock_get, _, _ = _mock_plex_responses()

        with patch("rebuild.rebuilder.requests.get", side_effect=mock_get):
            result = rebuild_playlist("http://plex", "token", "Ma Playlist", matches, dry_run=True)

        assert result["already_present"] == 0
        assert result["to_add"] == 2
        assert not result["created"]
        assert not result["updated"]

    def test_existing_playlist_all_present_skipped(self):
        matches = [_match("200"), _match("201")]
        playlist = {"ratingKey": "PL1", "title": "Ma Playlist"}
        mock_get, _, _ = _mock_plex_responses(
            existing_playlist=playlist, existing_keys={"200", "201"},
        )

        with patch("rebuild.rebuilder.requests.get", side_effect=mock_get):
            result = rebuild_playlist("http://plex", "token", "Ma Playlist", matches, dry_run=True)

        assert result["already_present"] == 2
        assert result["to_add"] == 0
        assert result["skipped"] is True
        assert "déjà présentes" in result["reason"]

    def test_existing_playlist_partial_shows_diff(self):
        matches = [_match("200"), _match("201"), _match("202")]
        playlist = {"ratingKey": "PL1", "title": "Ma Playlist"}
        mock_get, _, _ = _mock_plex_responses(
            existing_playlist=playlist, existing_keys={"200"},
        )

        with patch("rebuild.rebuilder.requests.get", side_effect=mock_get):
            result = rebuild_playlist("http://plex", "token", "Ma Playlist", matches, dry_run=True)

        assert result["already_present"] == 1
        assert result["to_add"] == 2

    def test_no_resolved_tracks_skipped(self):
        matches = [_match(resolved=False)]
        mock_get, _, _ = _mock_plex_responses()

        with patch("rebuild.rebuilder.requests.get", side_effect=mock_get):
            result = rebuild_playlist("http://plex", "token", "Ma Playlist", matches, dry_run=True)

        assert result["skipped"] is True
        assert "aucune track" in result["reason"]


class TestExecuteIncremental:
    def test_creates_new_playlist(self):
        matches = [_match("200")]
        mock_get, mock_post, _ = _mock_plex_responses()

        with (
            patch("rebuild.rebuilder.requests.get", side_effect=mock_get),
            patch("rebuild.rebuilder.requests.post", side_effect=mock_post) as post_mock,
        ):
            result = rebuild_playlist("http://plex", "token", "Ma Playlist", matches, dry_run=False)

        assert result["created"] is True
        assert not result["updated"]
        post_mock.assert_called_once()

    def test_updates_existing_playlist(self):
        matches = [_match("200"), _match("201")]
        playlist = {"ratingKey": "PL1", "title": "Ma Playlist"}
        mock_get, mock_post, mock_put = _mock_plex_responses(
            existing_playlist=playlist, existing_keys={"200"},
        )

        with (
            patch("rebuild.rebuilder.requests.get", side_effect=mock_get),
            patch("rebuild.rebuilder.requests.post", side_effect=mock_post) as post_mock,
            patch("rebuild.rebuilder.requests.put", side_effect=mock_put) as put_mock,
        ):
            result = rebuild_playlist("http://plex", "token", "Ma Playlist", matches, dry_run=False)

        assert result["updated"] is True
        assert not result["created"]
        put_mock.assert_called_once()
        post_mock.assert_not_called()
        params = put_mock.call_args[1]["params"]
        assert "201" in params["uri"]

    def test_skips_when_all_present(self):
        matches = [_match("200")]
        playlist = {"ratingKey": "PL1", "title": "Ma Playlist"}
        mock_get, mock_post, mock_put = _mock_plex_responses(
            existing_playlist=playlist, existing_keys={"200"},
        )

        with (
            patch("rebuild.rebuilder.requests.get", side_effect=mock_get),
            patch("rebuild.rebuilder.requests.post", side_effect=mock_post) as post_mock,
            patch("rebuild.rebuilder.requests.put", side_effect=mock_put) as put_mock,
        ):
            result = rebuild_playlist("http://plex", "token", "Ma Playlist", matches, dry_run=False)

        assert result["skipped"] is True
        post_mock.assert_not_called()
        put_mock.assert_not_called()

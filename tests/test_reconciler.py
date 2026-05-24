"""Tests du moteur de réconciliation."""

import os

from rebuild.reconciler import SourceTrack, parse_source_track, reconcile
from rebuild.indexer import PlexIndexes


def _make_source(**overrides) -> SourceTrack:
    defaults = {
        "guid": None,
        "filepath": None,
        "artist": None,
        "album": None,
        "title": None,
        "track_number": None,
        "disc_number": None,
        "duration_ms": None,
        "original_rating_key": "12345",
    }
    defaults.update(overrides)
    return SourceTrack(**defaults)


def _make_track(title="Smile", artist="Lily Allen", album="Alright, Still",
                index=1, duration=197000, file="/Media/Music/test.flac") -> dict:
    """Crée un dict track simulant la réponse API Plex."""
    return {
        "ratingKey": "99999",
        "guid": "plex://track/abc123",
        "title": title,
        "grandparentTitle": artist,
        "parentTitle": album,
        "index": index,
        "duration": duration,
        "Media": [{"Part": [{"file": file}]}],
    }


def _make_indexes(track: dict) -> PlexIndexes:
    indexes = PlexIndexes()

    guid = track.get("guid")
    if guid:
        indexes.by_guid[guid] = track

    for media in track.get("Media", []):
        for part in media.get("Part", []):
            filepath = part.get("file")
            if filepath:
                indexes.by_filepath[filepath] = track
                indexes.by_filename.setdefault(os.path.basename(filepath), []).append(track)

    artist = track["grandparentTitle"].lower().strip()
    album = track["parentTitle"].lower().strip()
    title = track["title"].lower().strip()
    indexes.by_metadata[(artist, album, title, track["index"])] = track
    return indexes


class TestMatchByGuid:
    def test_exact_guid_match(self):
        track = _make_track()
        indexes = _make_indexes(track)
        source = _make_source(guid="plex://track/abc123")

        result = reconcile(source, indexes)
        assert result.method == "guid"
        assert result.matched_track is track
        assert result.confidence == 1.0

    def test_guid_miss_falls_through(self):
        track = _make_track()
        indexes = _make_indexes(track)
        source = _make_source(guid="plex://track/unknown")

        result = reconcile(source, indexes)
        assert result.method != "guid"


class TestMatchByFilepath:
    def test_exact_filepath_match(self):
        track = _make_track()
        indexes = _make_indexes(track)
        source = _make_source(filepath="/Media/Music/test.flac")

        result = reconcile(source, indexes)
        assert result.method == "filepath"
        assert result.confidence == 1.0


class TestMatchByFilename:
    def test_filename_match_after_move(self):
        track = _make_track(file="/Media/Music/Artist/Album/test.flac")
        indexes = _make_indexes(track)
        source = _make_source(filepath="/old/path/test.flac")

        result = reconcile(source, indexes)
        assert result.method == "filename"

    def test_filename_duplicate_resolved_by_duration(self):
        track1 = _make_track(file="/path1/song.flac", duration=180000)
        track2 = _make_track(file="/path2/song.flac", duration=240000)
        indexes = PlexIndexes()
        indexes.by_filename["song.flac"] = [track1, track2]

        source = _make_source(filepath="/old/song.flac", duration_ms=180000)
        result = reconcile(source, indexes)
        assert result.method == "filename"
        assert result.matched_track is track1
        assert result.confidence == 0.95


class TestMatchByMetadata:
    def test_exact_metadata_match(self):
        track = _make_track()
        indexes = _make_indexes(track)
        source = _make_source(artist="Lily Allen", album="Alright, Still", title="Smile", track_number=1)

        result = reconcile(source, indexes)
        assert result.method == "metadata"
        assert result.confidence == 1.0

    def test_metadata_case_insensitive(self):
        track = _make_track()
        indexes = _make_indexes(track)
        source = _make_source(artist="LILY ALLEN", album="ALRIGHT, STILL", title="SMILE", track_number=1)

        result = reconcile(source, indexes)
        assert result.method == "metadata"


class TestMatchFuzzy:
    def test_fuzzy_match(self):
        track = _make_track(artist="Lily Allen", title="Smile")
        indexes = _make_indexes(track)
        source = _make_source(artist="Lilly Allen", title="Smile", duration_ms=197000)

        result = reconcile(source, indexes)
        assert result.method == "fuzzy"
        assert result.confidence > 0.8

    def test_fuzzy_skipped_when_disabled(self):
        track = _make_track(artist="Lily Allen", title="Smile")
        indexes = _make_indexes(track)
        source = _make_source(artist="Lilly Allen", title="Smile")

        result = reconcile(source, indexes, skip_fuzzy=True)
        assert result.method == "unresolved"


class TestUnresolved:
    def test_no_match(self):
        indexes = PlexIndexes()
        source = _make_source(artist="Nobody", title="Nothing")

        result = reconcile(source, indexes)
        assert result.method == "unresolved"
        assert result.matched_track is None
        assert result.confidence == 0.0


class TestParseSourceTrack:
    def test_parse_full_metadata(self):
        metadata = {
            "guid": "plex://track/abc",
            "grandparentTitle": "Artist",
            "parentTitle": "Album",
            "title": "Song",
            "index": 3,
            "parentIndex": 1,
            "duration": 200000,
            "ratingKey": "555",
            "Media": [{"Part": [{"file": "/path/song.flac"}]}],
        }
        st = parse_source_track(metadata)
        assert st.guid == "plex://track/abc"
        assert st.filepath == "/path/song.flac"
        assert st.artist == "Artist"
        assert st.title == "Song"
        assert st.track_number == 3
        assert st.duration_ms == 200000

    def test_parse_minimal_metadata(self):
        metadata = {"ratingKey": "1", "title": "X"}
        st = parse_source_track(metadata)
        assert st.title == "X"
        assert st.filepath is None
        assert st.guid is None

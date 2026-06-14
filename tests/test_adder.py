"""Tests unitaires pour le module adder (parser)."""

import pytest

from adder.parser import parse_track_list, deduplicate_entries


class TestParseTrackList:
    """Tests pour parse_track_list."""

    def test_en_dash_separator(self, tmp_path):
        """Parse correctement le séparateur en-dash."""
        f = tmp_path / "tracks.txt"
        f.write_text("Purple Disco Machine – Hypnotized\n", encoding="utf-8")

        result = parse_track_list(f)

        assert result == [("Purple Disco Machine", "Hypnotized")]

    def test_hyphen_separator(self, tmp_path):
        """Parse correctement le séparateur hyphen."""
        f = tmp_path / "tracks.txt"
        f.write_text("Shakedown - At Night\n", encoding="utf-8")

        result = parse_track_list(f)

        assert result == [("Shakedown", "At Night")]

    def test_en_dash_priority_over_hyphen(self, tmp_path):
        """Le en-dash a priorité si les deux sont présents."""
        f = tmp_path / "tracks.txt"
        f.write_text("Mark-Anthony – Something Good\n", encoding="utf-8")

        result = parse_track_list(f)

        assert result == [("Mark-Anthony", "Something Good")]

    def test_skip_comments(self, tmp_path):
        """Les lignes commençant par # sont ignorées."""
        f = tmp_path / "tracks.txt"
        f.write_text("# Ceci est un commentaire\nArtist – Title\n", encoding="utf-8")

        result = parse_track_list(f)

        assert result == [("Artist", "Title")]

    def test_skip_blank_lines(self, tmp_path):
        """Les lignes vides sont ignorées."""
        f = tmp_path / "tracks.txt"
        f.write_text("\nArtist – Title\n\n  \nOther – Song\n", encoding="utf-8")

        result = parse_track_list(f)

        assert result == [("Artist", "Title"), ("Other", "Song")]

    def test_comment_after_whitespace(self, tmp_path):
        """Les commentaires avec espaces avant # sont aussi ignorés."""
        f = tmp_path / "tracks.txt"
        f.write_text("  # indented comment\nArtist – Title\n", encoding="utf-8")

        result = parse_track_list(f)

        assert result == [("Artist", "Title")]

    def test_multiple_entries(self, tmp_path):
        """Parse plusieurs entrées mixtes."""
        content = (
            "# Peak Time tracks\n"
            "\n"
            "Purple Disco Machine – Hypnotized\n"
            "Shakedown - At Night\n"
            "LCD Soundsystem – Someone Great\n"
        )
        f = tmp_path / "tracks.txt"
        f.write_text(content, encoding="utf-8")

        result = parse_track_list(f)

        assert len(result) == 3
        assert result[0] == ("Purple Disco Machine", "Hypnotized")
        assert result[1] == ("Shakedown", "At Night")
        assert result[2] == ("LCD Soundsystem", "Someone Great")

    def test_strips_whitespace(self, tmp_path):
        """Les espaces autour de l'artiste et du titre sont supprimés."""
        f = tmp_path / "tracks.txt"
        f.write_text("  Artist  –  Title  \n", encoding="utf-8")

        result = parse_track_list(f)

        assert result == [("Artist", "Title")]

    def test_invalid_line_raises_valueerror(self, tmp_path):
        """Une ligne sans séparateur lève ValueError."""
        f = tmp_path / "tracks.txt"
        f.write_text("This has no separator\n", encoding="utf-8")

        with pytest.raises(ValueError, match="Ligne 1"):
            parse_track_list(f)

    def test_invalid_line_reports_correct_line_number(self, tmp_path):
        """ValueError contient le bon numéro de ligne."""
        content = "# comment\nArtist – Title\nBad line here\n"
        f = tmp_path / "tracks.txt"
        f.write_text(content, encoding="utf-8")

        with pytest.raises(ValueError, match="Ligne 3"):
            parse_track_list(f)

    def test_empty_file(self, tmp_path):
        """Un fichier vide retourne une liste vide."""
        f = tmp_path / "tracks.txt"
        f.write_text("", encoding="utf-8")

        result = parse_track_list(f)

        assert result == []

    def test_only_comments_and_blanks(self, tmp_path):
        """Un fichier avec seulement des commentaires et blancs retourne une liste vide."""
        f = tmp_path / "tracks.txt"
        f.write_text("# comment\n\n# another\n  \n", encoding="utf-8")

        result = parse_track_list(f)

        assert result == []

    def test_title_with_hyphen(self, tmp_path):
        """Un titre contenant un hyphen est correctement parsé (split maxsplit=1)."""
        f = tmp_path / "tracks.txt"
        f.write_text("Artist - Title - With Extra Hyphens\n", encoding="utf-8")

        result = parse_track_list(f)

        assert result == [("Artist", "Title - With Extra Hyphens")]


class TestDeduplicateEntries:
    """Tests pour deduplicate_entries."""

    def test_no_duplicates(self):
        """Pas de doublons, retourne tel quel."""
        entries = [("Artist A", "Song 1"), ("Artist B", "Song 2")]

        result = deduplicate_entries(entries)

        assert result == entries

    def test_exact_duplicates(self):
        """Supprime les doublons exacts."""
        entries = [("Artist", "Song"), ("Artist", "Song")]

        result = deduplicate_entries(entries)

        assert result == [("Artist", "Song")]

    def test_case_insensitive(self):
        """Les doublons sont détectés indépendamment de la casse."""
        entries = [("ARTIST", "SONG"), ("artist", "song")]

        result = deduplicate_entries(entries)

        assert result == [("ARTIST", "SONG")]

    def test_preserves_first_occurrence(self):
        """Conserve la première occurrence (casse originale)."""
        entries = [
            ("Purple Disco Machine", "Hypnotized"),
            ("purple disco machine", "hypnotized"),
            ("PURPLE DISCO MACHINE", "HYPNOTIZED"),
        ]

        result = deduplicate_entries(entries)

        assert result == [("Purple Disco Machine", "Hypnotized")]

    def test_preserves_order(self):
        """L'ordre des premières occurrences est préservé."""
        entries = [
            ("B", "Song B"),
            ("A", "Song A"),
            ("B", "Song B"),
            ("C", "Song C"),
            ("A", "Song A"),
        ]

        result = deduplicate_entries(entries)

        assert result == [("B", "Song B"), ("A", "Song A"), ("C", "Song C")]

    def test_unicode_normalization(self):
        """Les variantes Unicode NFC/NFD sont détectées comme doublons."""
        import unicodedata

        nfd = unicodedata.normalize("NFD", "Bénabar")
        nfc = unicodedata.normalize("NFC", "Bénabar")
        entries = [(nfd, "Song"), (nfc, "Song")]

        result = deduplicate_entries(entries)

        assert len(result) == 1

    def test_empty_list(self):
        """Liste vide retourne liste vide."""
        assert deduplicate_entries([]) == []

    def test_whitespace_stripping(self):
        """Les espaces autour sont ignorés dans la comparaison."""
        entries = [("Artist", "Song"), (" Artist ", " Song ")]

        result = deduplicate_entries(entries)

        assert len(result) == 1

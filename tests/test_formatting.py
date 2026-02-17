"""Tests for filename sanitization and Plex naming functions."""


from organize import format_episode, format_movie, sanitize


class TestSanitize:
    def test_removes_colons(self):
        assert sanitize("Doctor Strange: Multiverse") == "Doctor Strange Multiverse"

    def test_removes_slashes(self):
        assert sanitize("AC/DC") == "ACDC"

    def test_removes_backslashes(self):
        assert sanitize("foo\\bar") == "foobar"

    def test_strips_trailing_dots(self):
        assert sanitize("Mr. Robot.") == "Mr. Robot"

    def test_removes_question_marks(self):
        # ? is removed, then trailing dots are stripped by rstrip(".")
        assert sanitize("What If...?") == "What If"

    def test_removes_asterisks(self):
        assert sanitize("M*A*S*H") == "MASH"

    def test_removes_quotes(self):
        assert sanitize('He said "hello"') == "He said hello"

    def test_removes_angle_brackets(self):
        assert sanitize("Test <value>") == "Test value"

    def test_removes_pipes(self):
        assert sanitize("A | B") == "A  B"

    def test_empty_string(self):
        assert sanitize("") == ""

    def test_preserves_hyphens(self):
        assert sanitize("Spider-Man") == "Spider-Man"

    def test_preserves_parentheses(self):
        assert sanitize("Movie (2024)") == "Movie (2024)"

    def test_strips_whitespace(self):
        assert sanitize("  Hello  ") == "Hello"


class TestFormatMovie:
    def test_with_year(self):
        dirname, filename = format_movie("Inception", 2010, ".mkv")
        assert dirname == "Inception (2010)"
        assert filename == "Inception (2010).mkv"

    def test_without_year(self):
        dirname, filename = format_movie("The Matrix", None, ".mkv")
        assert dirname == "The Matrix"
        assert filename == "The Matrix.mkv"

    def test_mp4_extension(self):
        dirname, filename = format_movie("Test", 2020, ".mp4")
        assert filename == "Test (2020).mp4"

    def test_sanitizes_title(self):
        dirname, filename = format_movie("What If...?", 2021, ".mkv")
        assert "?" not in dirname
        assert "?" not in filename

    def test_colon_in_title(self):
        dirname, filename = format_movie("Batman: The Dark Knight", 2008, ".mkv")
        assert ":" not in dirname
        assert dirname == "Batman The Dark Knight (2008)"


class TestFormatEpisode:
    def test_standard_episode(self):
        series_dir, season_dir, filename = format_episode("Breaking Bad", 5, 16, ".mkv")
        assert series_dir == "Breaking Bad"
        assert season_dir == "Season 05"
        assert filename == "Breaking Bad - S05E16.mkv"

    def test_multi_episode(self):
        _, _, filename = format_episode("Friends", 1, [23, 24], ".mkv")
        assert filename == "Friends - S01E23E24.mkv"

    def test_single_digit_padding(self):
        _, season_dir, filename = format_episode("Lost", 1, 1, ".mkv")
        assert season_dir == "Season 01"
        assert filename == "Lost - S01E01.mkv"

    def test_high_season_number(self):
        _, season_dir, filename = format_episode("Simpsons", 35, 1, ".mkv")
        assert season_dir == "Season 35"
        assert filename == "Simpsons - S35E01.mkv"

    def test_sanitizes_series_name(self):
        series_dir, _, _ = format_episode("Marvel's: Agents", 1, 1, ".mkv")
        assert "/" not in series_dir
        assert ":" not in series_dir

    def test_mp4_extension(self):
        _, _, filename = format_episode("Test", 1, 1, ".mp4")
        assert filename == "Test - S01E01.mp4"

    def test_three_episode_multi(self):
        _, _, filename = format_episode("Show", 1, [1, 2, 3], ".mkv")
        assert filename == "Show - S01E01E02E03.mkv"

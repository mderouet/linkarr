"""Tests for title normalization logic (_word_overlap + normalize_title).

TMDb is disabled via conftest.py. Tests that need TMDb use a mock.
"""

import urllib.error
from unittest.mock import patch

import organize
from organize import _tmdb_search, _word_overlap, normalize_title

# =============================================================================
# _word_overlap — Jaccard similarity with hyphen/colon normalization
# =============================================================================


class TestWordOverlap:
    def test_exact_match(self):
        assert _word_overlap("Breaking Bad", "Breaking Bad") == 1.0

    def test_no_overlap(self):
        assert _word_overlap("Breaking Bad", "Inception") == 0.0

    def test_partial_overlap(self):
        # {"breaking", "bad"} & {"breaking", "bad", "season", "five"} = 2
        # union = 4, so 2/4 = 0.5
        assert _word_overlap("Breaking Bad", "Breaking Bad Season Five") == 0.5

    def test_hyphen_normalization(self):
        # "Spider-Man" → {"spider", "man"}, "Spider Man" → {"spider", "man"}
        assert _word_overlap("Spider-Man", "Spider Man") == 1.0

    def test_colon_normalization(self):
        assert _word_overlap("Spider-Man: No Way Home", "Spider-Man No Way Home") == 1.0

    def test_empty_string_a(self):
        assert _word_overlap("", "Something") == 0.0

    def test_empty_string_b(self):
        assert _word_overlap("Something", "") == 0.0

    def test_both_empty(self):
        assert _word_overlap("", "") == 0.0

    def test_none_a(self):
        assert _word_overlap(None, "Something") == 0.0

    def test_case_insensitive(self):
        assert _word_overlap("JUJUTSU KAISEN", "jujutsu kaisen") == 1.0


# =============================================================================
# normalize_title — picks the best title from guessit/aniparse via TMDb
# =============================================================================


class TestNormalizeTitle:
    def _mock_search(self, mapping):
        """Return a mock _tmdb_search that uses a dict for controlled responses."""
        def search(query, media_type="tv", year=None):
            key = query.lower().replace(".", " ").strip()
            return mapping.get(key, (None, None))
        return search

    def test_guessit_wins_higher_overlap(self):
        mock = self._mock_search({
            "breaking bad": ("Breaking Bad", 1),
            "bad breaking": ("Bad Breaking Show", 2),
        })
        with patch("organize._tmdb_search", side_effect=mock):
            result = normalize_title("Breaking Bad", "Bad Breaking", media_type="tv")
        assert result == "Breaking Bad"

    def test_aniparse_wins_higher_overlap(self):
        mock = self._mock_search({
            "dandadan": ("Dan Da Dan Official", 1),  # low overlap with "dandadan"
            "dan da dan": ("Dan Da Dan", 2),          # perfect overlap
        })
        with patch("organize._tmdb_search", side_effect=mock):
            result = normalize_title("Dandadan", "Dan Da Dan", media_type="tv")
        assert result == "Dan Da Dan"

    def test_both_tmdb_fail_falls_back_to_guessit(self):
        mock = self._mock_search({})  # everything returns (None, None)
        with patch("organize._tmdb_search", side_effect=mock):
            result = normalize_title("Breaking Bad", "Bad Show", media_type="tv")
        assert result == "Breaking Bad"

    def test_guessit_empty_falls_back_to_aniparse(self):
        mock = self._mock_search({})
        with patch("organize._tmdb_search", side_effect=mock):
            result = normalize_title("", "Dandadan", media_type="tv")
        assert result == "Dandadan"

    def test_same_title_skips_second_search(self):
        """When aniparse and guessit produce the same title, only one TMDb search happens."""
        call_count = 0

        def counting_search(query, media_type="tv", year=None):
            nonlocal call_count
            call_count += 1
            return ("Breaking Bad", 1)

        with patch("organize._tmdb_search", side_effect=counting_search):
            result = normalize_title("Breaking Bad", "Breaking Bad", media_type="tv")
        assert result == "Breaking Bad"
        assert call_count == 1  # only searched once

    def test_aniparse_none_uses_guessit_only(self):
        mock = self._mock_search({"inception": ("Inception", 1)})
        with patch("organize._tmdb_search", side_effect=mock):
            result = normalize_title("Inception", None, media_type="movie", year=2010)
        assert result == "Inception"


# =============================================================================
# _tmdb_search — network error handling
# =============================================================================


class TestTmdbSearchErrors:
    def test_network_error_returns_none(self, monkeypatch):
        """URLError during TMDb lookup must return (None, None), not crash."""
        monkeypatch.setenv("TMDB_API_KEY", "fake-key")
        organize._tmdb_cache.clear()
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("DNS failed")):
            name, tmdb_id = _tmdb_search("Inception", "movie", 2010)
        assert name is None
        assert tmdb_id is None

    def test_network_error_not_cached(self, monkeypatch):
        """Network errors must NOT be cached — a temporary outage shouldn't poison the cache."""
        monkeypatch.setenv("TMDB_API_KEY", "fake-key")
        organize._tmdb_cache.clear()
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
            _tmdb_search("Inception", "movie", 2010)
        assert "movie:inception:2010" not in organize._tmdb_cache

"""Integration tests that call the real TMDb API.

These tests validate the full parsing + TMDb normalization pipeline for
filenames that guessit alone cannot resolve correctly. They require a
TMDB_API_KEY environment variable and are skipped when it's not set
or when the TMDb API is unreachable.

Run locally:
    TMDB_API_KEY=xxx pytest -v -m integration
"""

import os

import pytest

from organize import _parse_movie, _parse_series, _tmdb_search

_REAL_KEY = os.environ.get("TMDB_API_KEY", "")

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _enable_tmdb(monkeypatch):
    """Override the global _disable_tmdb fixture with the real API key."""
    if not _REAL_KEY:
        pytest.skip("TMDB_API_KEY not set")
    monkeypatch.setenv("TMDB_API_KEY", _REAL_KEY)
    # Verify TMDb is actually reachable (skip on SSL errors, etc.)
    name, _ = _tmdb_search("Inception", "movie", 2010)
    if name is None:
        pytest.skip("TMDb API unreachable")


# --- Movies that need TMDb normalization ---


def test_wall_e():
    title, year = _parse_movie("WALL-E.2008.1080p.BluRay.x264-GROUP.mkv")
    assert year == 2008
    assert "WALL" in title and "E" in title  # "WALL·E" or "WALL-E"


def test_spider_man_no_way_home():
    title, year = _parse_movie("Spider-Man.No.Way.Home.2021.1080p.BluRay.mkv")
    assert year == 2021
    assert "Spider-Man" in title


def test_amelie_accent():
    title, year = _parse_movie("Amelie.2001.1080p.BluRay.mkv")
    assert year == 2001
    assert "Amélie" in title


def test_dune_part_two():
    title, year = _parse_movie("Dune.Part.Two.2024.1080p.BluRay.mkv")
    assert year == 2024
    assert "Dune" in title
    assert "Part Two" in title


def test_les_miserables():
    title, year = _parse_movie("Les.Miserables.2012.1080p.BluRay.mkv")
    assert year == 2012
    assert "Misérables" in title


# --- Series that need TMDb normalization ---


def test_oshi_no_ko():
    title, season, episode = _parse_series("[SubsPlease] Oshi no Ko - 01 (1080p).mkv")
    assert episode == 1
    assert "Oshi" in title


def test_dandadan():
    title, season, episode = _parse_series("[SubsPlease] Dandadan - 03 (1080p) [ABC12345].mkv")
    assert episode == 3
    assert season == 1
    assert "Dandadan" in title or "DAN DA DAN" in title


def test_dr_stone():
    title, season, episode = _parse_series("Dr.Stone.S01E05.720p.mkv")
    assert season == 1
    assert episode == 5
    assert "Dr." in title or "Dr " in title or "Stone" in title

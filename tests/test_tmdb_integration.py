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


# --- Movies: TMDb normalization ---


def test_spider_man_no_way_home():
    title, year = _parse_movie("Spider-Man.No.Way.Home.2021.1080p.BluRay.mkv")
    assert year == 2021
    assert "spider" in title.lower()


def test_amelie_accent():
    title, year = _parse_movie("Amelie.2001.1080p.BluRay.mkv")
    assert year == 2001
    assert "mélie" in title  # Amélie or Le Fabuleux Destin d'Amélie Poulain


def test_les_miserables():
    title, year = _parse_movie("Les.Miserables.2012.1080p.BluRay.mkv")
    assert year == 2012
    assert "rables" in title  # Misérables — accent normalized by TMDb


def test_inception_basic():
    title, year = _parse_movie("Inception.2010.1080p.BluRay.x264-GROUP.mkv")
    assert year == 2010
    assert title == "Inception"


def test_the_batman():
    title, year = _parse_movie("The.Batman.2022.1080p.WEB-DL.mkv")
    assert year == 2022
    assert "batman" in title.lower()


# --- Series: TMDb normalization ---


def test_dandadan():
    title, season, episode = _parse_series("[SubsPlease] Dandadan - 03 (1080p) [ABC12345].mkv")
    assert episode == 3
    assert season == 1
    # TMDb returns "Dan Da Dan" (official title)
    assert "dan" in title.lower()


def test_breaking_bad():
    title, season, episode = _parse_series("Breaking.Bad.S05E16.720p.BluRay.x264-DEMAND.mkv")
    assert season == 5
    assert episode == 16
    assert "breaking bad" in title.lower()


def test_jujutsu_kaisen():
    title, season, episode = _parse_series("[SubsPlease] Jujutsu Kaisen S2 - 15 (1080p).mkv")
    assert season == 2
    assert episode == 15
    assert "jujutsu kaisen" in title.lower()


def test_dr_stone():
    title, season, episode = _parse_series("Dr.Stone.S01E05.720p.mkv")
    assert season == 1
    assert episode == 5
    assert "stone" in title.lower()

"""Integration tests for the organizer pipeline: ledger, hardlinks, cleanup, dry-run."""

import os

import pytest

import organize


@pytest.fixture
def media_dirs(tmp_path, monkeypatch):
    """Set up a temporary media directory structure and patch organize module globals."""
    dl_movies = tmp_path / "downloads" / "movies"
    dl_series = tmp_path / "downloads" / "series"
    lib_movies = tmp_path / "movies"
    lib_series = tmp_path / "series"
    data_dir = tmp_path / "data"

    for d in [dl_movies, dl_series, lib_movies, lib_series, data_dir]:
        d.mkdir(parents=True)

    monkeypatch.setattr(organize, "DOWNLOADS_MOVIES", dl_movies)
    monkeypatch.setattr(organize, "DOWNLOADS_SERIES", dl_series)
    monkeypatch.setattr(organize, "LIBRARY_MOVIES", lib_movies)
    monkeypatch.setattr(organize, "LIBRARY_SERIES", lib_series)
    monkeypatch.setattr(organize, "LEDGER_FILE", data_dir / "processed.json")
    monkeypatch.setattr(organize, "TMDB_CACHE_FILE", data_dir / "tmdb_cache.json")
    monkeypatch.setattr(organize, "LOG_FILE", data_dir / "organize.log")
    monkeypatch.setattr(organize, "DRY_RUN", False)

    return {
        "dl_movies": dl_movies,
        "dl_series": dl_series,
        "lib_movies": lib_movies,
        "lib_series": lib_series,
        "data_dir": data_dir,
    }


def _create_fake_video(directory, filename, size=1024):
    """Create a small file to serve as a fake video."""
    path = directory / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(os.urandom(size))
    return path


class TestLedger:
    def test_load_empty(self, media_dirs):
        ledger = organize.load_ledger()
        assert ledger == {}

    def test_save_and_load_roundtrip(self, media_dirs):
        ledger = {"/src/test.mkv": "/dest/Test/Test.mkv"}
        organize.save_ledger(ledger)
        loaded = organize.load_ledger()
        assert loaded == ledger

    def test_corrupt_json_returns_empty(self, media_dirs):
        organize.LEDGER_FILE.write_text("not json{{{")
        ledger = organize.load_ledger()
        assert ledger == {}

    def test_atomic_write(self, media_dirs):
        """Verify no .tmp file remains after save."""
        organize.save_ledger({"a": "b"})
        assert not organize.LEDGER_FILE.with_suffix(".tmp").exists()
        assert organize.LEDGER_FILE.exists()


class TestHardlinks:
    def test_creates_hardlink(self, media_dirs):
        src = _create_fake_video(media_dirs["dl_movies"], "test.mkv")
        dest = media_dirs["lib_movies"] / "test.mkv"
        assert organize.create_hardlink(src, dest)
        assert dest.exists()
        assert src.stat().st_ino == dest.stat().st_ino

    def test_creates_parent_directories(self, media_dirs):
        src = _create_fake_video(media_dirs["dl_movies"], "test.mkv")
        dest = media_dirs["lib_movies"] / "Movie (2024)" / "Movie (2024).mkv"
        assert organize.create_hardlink(src, dest)
        assert dest.exists()

    def test_skips_existing_same_inode(self, media_dirs):
        src = _create_fake_video(media_dirs["dl_movies"], "test.mkv")
        dest = media_dirs["lib_movies"] / "test.mkv"
        organize.create_hardlink(src, dest)
        assert organize.create_hardlink(src, dest)

    def test_skips_existing_different_inode(self, media_dirs):
        src = _create_fake_video(media_dirs["dl_movies"], "test.mkv")
        dest = media_dirs["lib_movies"] / "test.mkv"
        dest.write_bytes(b"different content")
        assert not organize.create_hardlink(src, dest)

    def test_dry_run_does_not_create(self, media_dirs):
        src = _create_fake_video(media_dirs["dl_movies"], "test.mkv")
        dest = media_dirs["lib_movies"] / "test.mkv"
        assert organize.create_hardlink(src, dest, dry_run=True)
        assert not dest.exists()


class TestProcessMovies:
    def test_processes_new_movie(self, media_dirs):
        _create_fake_video(media_dirs["dl_movies"], "Inception.2010.1080p.BluRay.mkv")
        ledger = {}
        count = organize.process_movies(ledger)
        assert count == 1
        assert len(ledger) == 1
        lib_files = list(media_dirs["lib_movies"].rglob("*.mkv"))
        assert len(lib_files) == 1

    def test_skips_already_processed(self, media_dirs):
        src = _create_fake_video(media_dirs["dl_movies"], "Inception.2010.1080p.mkv")
        ledger = {str(src): "/some/dest.mkv"}
        count = organize.process_movies(ledger)
        assert count == 0

    def test_processes_multiple_movies(self, media_dirs):
        _create_fake_video(media_dirs["dl_movies"], "Inception.2010.1080p.mkv")
        _create_fake_video(media_dirs["dl_movies"], "The.Batman.2022.1080p.mkv")
        ledger = {}
        count = organize.process_movies(ledger)
        assert count == 2
        assert len(ledger) == 2

    def test_handles_nested_directories(self, media_dirs):
        _create_fake_video(media_dirs["dl_movies"] / "subfolder", "Inception.2010.1080p.mkv")
        ledger = {}
        count = organize.process_movies(ledger)
        assert count == 1

    def test_ignores_non_video_files(self, media_dirs):
        (media_dirs["dl_movies"] / "readme.txt").write_text("hello")
        (media_dirs["dl_movies"] / "cover.jpg").write_bytes(b"\xff\xd8")
        ledger = {}
        count = organize.process_movies(ledger)
        assert count == 0


class TestProcessSeries:
    def test_processes_new_episode(self, media_dirs):
        _create_fake_video(media_dirs["dl_series"], "Breaking.Bad.S05E16.720p.mkv")
        ledger = {}
        count = organize.process_series(ledger)
        assert count == 1
        lib_files = list(media_dirs["lib_series"].rglob("*.mkv"))
        assert len(lib_files) == 1

    def test_creates_season_directory(self, media_dirs):
        _create_fake_video(media_dirs["dl_series"], "Breaking.Bad.S05E16.720p.mkv")
        ledger = {}
        organize.process_series(ledger)
        season_dirs = list(media_dirs["lib_series"].rglob("Season *"))
        assert len(season_dirs) == 1
        assert season_dirs[0].name == "Season 05"


class TestCleanup:
    def test_removes_stale_entries(self, media_dirs):
        src = _create_fake_video(media_dirs["dl_movies"], "test.mkv")
        dest = media_dirs["lib_movies"] / "Test" / "test.mkv"
        organize.create_hardlink(src, dest)
        ledger = {str(src): str(dest)}

        src.unlink()

        stale = organize.cleanup_stale_entries(ledger)
        assert stale == 1
        assert not dest.exists()
        assert len(ledger) == 0

    def test_removes_empty_parent_dirs(self, media_dirs):
        src = _create_fake_video(media_dirs["dl_movies"], "test.mkv")
        dest = media_dirs["lib_movies"] / "Movie (2020)" / "Movie (2020).mkv"
        organize.create_hardlink(src, dest)
        ledger = {str(src): str(dest)}

        src.unlink()
        organize.cleanup_stale_entries(ledger)
        assert not (media_dirs["lib_movies"] / "Movie (2020)").exists()

    def test_keeps_non_empty_parent_dirs(self, media_dirs):
        src1 = _create_fake_video(media_dirs["dl_movies"], "test1.mkv")
        src2 = _create_fake_video(media_dirs["dl_movies"], "test2.mkv")
        dest1 = media_dirs["lib_movies"] / "Shared" / "file1.mkv"
        dest2 = media_dirs["lib_movies"] / "Shared" / "file2.mkv"
        organize.create_hardlink(src1, dest1)
        organize.create_hardlink(src2, dest2)
        ledger = {str(src1): str(dest1), str(src2): str(dest2)}

        # Remove only one source
        src1.unlink()
        organize.cleanup_stale_entries(ledger)
        # Parent dir still has file2
        assert (media_dirs["lib_movies"] / "Shared").exists()
        assert dest2.exists()

    def test_no_stale_entries(self, media_dirs):
        src = _create_fake_video(media_dirs["dl_movies"], "test.mkv")
        ledger = {str(src): "/some/dest.mkv"}
        stale = organize.cleanup_stale_entries(ledger)
        assert stale == 0

    def test_dry_run_does_not_delete(self, media_dirs, monkeypatch):
        monkeypatch.setattr(organize, "DRY_RUN", True)
        src = _create_fake_video(media_dirs["dl_movies"], "test.mkv")
        dest = media_dirs["lib_movies"] / "Test" / "test.mkv"
        organize.create_hardlink(src, dest)
        ledger = {str(src): str(dest)}

        src.unlink()
        stale = organize.cleanup_stale_entries(ledger)
        assert stale == 1
        # File should still exist in dry-run
        assert dest.exists()


class TestUnparseableFallback:
    """When parsing fails, files should be hardlinked with their original name."""

    def test_unparseable_movie_uses_original_name(self, media_dirs):
        # guessit extracts no title from pure-metadata filenames like "1080p.mkv"
        _create_fake_video(media_dirs["dl_movies"], "1080p.mkv")
        ledger = {}
        count = organize.process_movies(ledger)
        assert count == 1
        # Should land directly in library root with original name
        assert (media_dirs["lib_movies"] / "1080p.mkv").exists()

    def test_unparseable_series_uses_original_name(self, media_dirs):
        _create_fake_video(media_dirs["dl_series"], "720p.x264.mkv")
        ledger = {}
        count = organize.process_series(ledger)
        assert count == 1
        assert (media_dirs["lib_series"] / "720p.x264.mkv").exists()


class TestDryRun:
    def test_process_movies_dry_run(self, media_dirs, monkeypatch):
        monkeypatch.setattr(organize, "DRY_RUN", True)
        _create_fake_video(media_dirs["dl_movies"], "Inception.2010.1080p.mkv")
        ledger = {}
        count = organize.process_movies(ledger)
        assert count == 1
        assert len(ledger) == 1
        # No actual files created in library
        lib_files = list(media_dirs["lib_movies"].rglob("*.mkv"))
        assert len(lib_files) == 0

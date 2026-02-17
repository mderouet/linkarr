#!/usr/bin/env python3
"""
Media organizer: creates hardlinks from scene-named downloads into
Plex-compatible library directories.

Scans download directories for video files, parses metadata with
guessit + aniparse, normalizes titles via TMDb API, and creates
hardlinks with clean Plex naming in the library directories.

Tracks processed files in a JSON ledger to avoid re-processing.
"""

import json
import logging
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import aniparse
from guessit import guessit

# --- Configuration (all overridable via environment variables) ---

DOWNLOADS_MOVIES = Path(os.environ.get("DOWNLOADS_MOVIES", "/media/downloads/movies"))
DOWNLOADS_SERIES = Path(os.environ.get("DOWNLOADS_SERIES", "/media/downloads/series"))
LIBRARY_MOVIES = Path(os.environ.get("LIBRARY_MOVIES", "/media/movies"))
LIBRARY_SERIES = Path(os.environ.get("LIBRARY_SERIES", "/media/series"))
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))

LEDGER_FILE = DATA_DIR / "processed.json"
TMDB_CACHE_FILE = DATA_DIR / "tmdb_cache.json"
LOG_FILE = DATA_DIR / "organize.log"

DRY_RUN = os.environ.get("DRY_RUN", "false").lower() in ("true", "1", "yes")

VIDEO_EXTENSIONS = {
    ".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm",
    ".m4v", ".mpg", ".mpeg", ".ts", ".vob",
}

log = logging.getLogger("linkarr")


def setup_logging():
    """Configure logging. Must be called from main() before any log usage."""
    level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG_FILE),
        ],
    )


# --- Ledger (idempotency) ---


def load_ledger():
    """Load the processed files ledger. Returns {source_path: dest_path}."""
    if LEDGER_FILE.exists():
        try:
            return json.loads(LEDGER_FILE.read_text())
        except (json.JSONDecodeError, OSError) as e:
            log.warning("Failed to load ledger, starting fresh: %s", e)
    return {}


def save_ledger(ledger):
    """Persist the ledger to disk atomically."""
    LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = LEDGER_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, indent=2))
    tmp.rename(LEDGER_FILE)


# --- TMDb Cache ---

_tmdb_cache = {}


def load_tmdb_cache():
    global _tmdb_cache
    if TMDB_CACHE_FILE.exists():
        try:
            _tmdb_cache = json.loads(TMDB_CACHE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            _tmdb_cache = {}


def save_tmdb_cache():
    if not _tmdb_cache:
        return
    tmp = TMDB_CACHE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(_tmdb_cache, indent=2))
    tmp.rename(TMDB_CACHE_FILE)


# --- TMDb API ---


def _word_overlap(a, b):
    """Jaccard similarity on word sets, normalizing hyphens and colons."""
    if not a or not b:
        return 0.0
    wa = set(a.lower().replace("-", " ").replace(":", " ").split())
    wb = set(b.lower().replace("-", " ").replace(":", " ").split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def _tmdb_search(query, media_type="tv", year=None):
    """Search TMDb for a title. Returns (canonical_name, tmdb_id) or (None, None)."""
    tmdb_api_key = os.environ.get("TMDB_API_KEY", "")
    query = query.replace(".", " ").strip()
    if not query or len(query) < 2 or not tmdb_api_key:
        return None, None

    cache_key = f"{media_type}:{query.lower()}"
    if media_type == "movie" and year:
        cache_key += f":{year}"
    if cache_key in _tmdb_cache:
        val = _tmdb_cache[cache_key]
        if val is None:
            return None, None
        return val.get("name"), val.get("id")

    endpoint = "search/tv" if media_type == "tv" else "search/movie"
    p = {"api_key": tmdb_api_key, "query": query, "language": "en-US"}
    if year:
        p["year" if media_type == "movie" else "first_air_date_year"] = str(year)

    params = urllib.parse.urlencode(p)
    url = f"https://api.themoviedb.org/3/{endpoint}?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        results = data.get("results", [])
        if not results:
            _tmdb_cache[cache_key] = None
            return None, None

        name_key = "name" if media_type == "tv" else "title"
        query_norm = query.lower().replace(":", "").replace("-", " ")

        # Prefer exact match among top 5
        for r in results[:5]:
            rn = r.get(name_key, "").lower().replace(":", "").replace("-", " ")
            if rn == query_norm:
                _tmdb_cache[cache_key] = {"name": r[name_key], "id": r["id"]}
                return r[name_key], r["id"]

        # Otherwise take first result
        best = results[0]
        _tmdb_cache[cache_key] = {"name": best[name_key], "id": best["id"]}
        return best[name_key], best["id"]

    except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError) as e:
        log.warning("TMDb lookup failed for '%s': %s", query, e)
        return None, None  # don't cache network errors


def normalize_title(guessit_title, aniparse_title, media_type="tv", year=None):
    """Try both parser titles with TMDb, return the best canonical name."""
    # Try guessit title
    tmdb_name, tmdb_id = _tmdb_search(guessit_title, media_type, year)
    score_g = _word_overlap(guessit_title, tmdb_name) if tmdb_name else 0

    # Try aniparse title if different
    if aniparse_title and aniparse_title != guessit_title:
        tmdb_name2, tmdb_id2 = _tmdb_search(aniparse_title, media_type, year)
        score_a = _word_overlap(aniparse_title, tmdb_name2) if tmdb_name2 else 0
        if score_a > score_g:
            return tmdb_name2

    if tmdb_name:
        return tmdb_name

    # Fallback: prefer guessit (cleaner for scene releases), aniparse as last resort
    return guessit_title or aniparse_title


# --- Naming ---


def sanitize(name):
    """Remove characters that are problematic in filenames."""
    for ch in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
        name = name.replace(ch, "")
    return name.strip().rstrip(".")


def format_movie(title, year, ext):
    """
    Return (directory_name, filename) for a movie.
    Plex format: Movie Name (Year)/Movie Name (Year).ext
    """
    title = sanitize(title)
    if year:
        dirname = f"{title} ({year})"
    else:
        dirname = title
    filename = f"{dirname}{ext}"
    return dirname, filename


def format_episode(title, season, episode, ext):
    """
    Return (series_dir, season_dir, filename) for a TV episode.
    Plex format: Series Name/Season 01/Series Name - S01E05.ext
    """
    series_name = sanitize(title)
    season_dir = f"Season {season:02d}"

    if isinstance(episode, list):
        ep_str = "".join(f"E{e:02d}" for e in episode)
    else:
        ep_str = f"E{episode:02d}"

    episode_code = f"S{season:02d}{ep_str}"
    filename = f"{series_name} - {episode_code}{ext}"
    return series_name, season_dir, filename


# --- Core Logic ---


def find_video_files(directory):
    """Recursively find all video files in a directory."""
    if not directory.exists():
        return []
    files = []
    for path in directory.rglob("*"):
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
            files.append(path)
    return sorted(files)


def create_hardlink(source, dest, dry_run=False):
    """Create a hardlink. Returns True on success."""
    try:
        if dry_run:
            log.info("[DRY RUN] Would hardlink: %s -> %s", source.name, dest)
            return True
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            if dest.stat().st_ino == source.stat().st_ino:
                return True
            log.warning("Destination exists but different inode, skipping: %s", dest)
            return False
        os.link(source, dest)
        log.info("Hardlinked: %s -> %s", source.name, dest)
        return True
    except OSError as e:
        log.error("Failed to hardlink %s -> %s: %s", source, dest, e)
        return False


def _parse_series(filename):
    """
    Parse a series filename using guessit + aniparse.
    Returns (title, season, episode) or (None, None, None).
    """
    g = dict(guessit(filename, {"type": "episode"}))
    a = aniparse.parse(filename)

    gt = g.get("title", "")
    at = a.get("anime_title", "")

    # Episode: guessit -> rescue from episode_title -> aniparse
    episode = g.get("episode")
    if episode is None:
        ep_title = g.get("episode_title", "")
        if isinstance(ep_title, str) and ep_title.strip().isdigit():
            episode = int(ep_title.strip())
    if episode is None:
        ani_ep = a.get("episode_number")
        if isinstance(ani_ep, int):
            episode = ani_ep
        elif isinstance(ani_ep, str) and ani_ep.isdigit():
            episode = int(ani_ep)

    # Season: guessit (>100 = year) -> aniparse -> default 1
    season = g.get("season")
    if season is not None and season > 100:
        season = None
    if season is None:
        ani_s = a.get("anime_season")
        if isinstance(ani_s, int) and ani_s <= 100:
            season = ani_s
    if season is None and episode is not None:
        season = 1

    if not gt and not at:
        return None, None, None
    if episode is None:
        return gt or at, None, None

    # Normalize title via TMDb (try both parser titles)
    canonical = normalize_title(gt, at, media_type="tv")
    return canonical, season, episode


def _parse_movie(filename):
    """
    Parse a movie filename using guessit + aniparse.
    Returns (title, year) or (None, None).
    """
    g = dict(guessit(filename, {"type": "movie"}))
    a = aniparse.parse(filename)

    gt = g.get("title", "")
    at = a.get("anime_title", "")
    year = g.get("year")

    if not gt and not at:
        return None, None

    canonical = normalize_title(gt, at, media_type="movie", year=year)
    return canonical, year


def process_movies(ledger):
    """Process movie downloads. Returns count of newly processed files."""
    count = 0
    for source in find_video_files(DOWNLOADS_MOVIES):
        source_str = str(source)
        if source_str in ledger:
            continue

        title, year = _parse_movie(source.name)

        if title:
            dirname, filename = format_movie(title, year, source.suffix)
            dest = LIBRARY_MOVIES / dirname / filename
        else:
            log.warning("Could not parse, hardlinking with original name: %s", source.name)
            dest = LIBRARY_MOVIES / source.name

        if create_hardlink(source, dest, dry_run=DRY_RUN):
            ledger[source_str] = str(dest)
            count += 1

    return count


def process_series(ledger):
    """Process series downloads. Returns count of newly processed files."""
    count = 0
    for source in find_video_files(DOWNLOADS_SERIES):
        source_str = str(source)
        if source_str in ledger:
            continue

        title, season, episode = _parse_series(source.name)

        if title and season is not None and episode is not None:
            series_dir, season_dir, filename = format_episode(title, season, episode, source.suffix)
            dest = LIBRARY_SERIES / series_dir / season_dir / filename
        else:
            log.warning("Could not parse, hardlinking with original name: %s", source.name)
            dest = LIBRARY_SERIES / source.name

        if create_hardlink(source, dest, dry_run=DRY_RUN):
            ledger[source_str] = str(dest)
            count += 1

    return count


def cleanup_stale_entries(ledger):
    """Remove ledger entries where the source file no longer exists."""
    stale = [k for k in ledger if not Path(k).exists()]
    for key in stale:
        dest = Path(ledger[key])
        if dest.exists():
            if DRY_RUN:
                log.info("[DRY RUN] Would clean up stale hardlink: %s", dest)
            else:
                try:
                    dest.unlink()
                    log.info("Cleaned up stale hardlink: %s", dest)
                    # Remove empty parent directories up to the library root
                    parent = dest.parent
                    while parent not in (LIBRARY_MOVIES, LIBRARY_SERIES):
                        if parent == parent.parent:
                            break  # safety: reached filesystem root
                        try:
                            parent.rmdir()
                            parent = parent.parent
                        except OSError:
                            break
                except OSError as e:
                    log.warning("Failed to clean up %s: %s", dest, e)
        del ledger[key]
    return len(stale)


def main():
    setup_logging()

    start = time.time()
    ledger = load_ledger()
    load_tmdb_cache()

    movies = process_movies(ledger)
    series = process_series(ledger)
    stale = cleanup_stale_entries(ledger)

    if not DRY_RUN:
        save_ledger(ledger)
        save_tmdb_cache()

    elapsed = time.time() - start

    if movies or series or stale:
        log.info(
            "Done in %.1fs: %d movies, %d episodes processed, %d stale cleaned, %d total tracked",
            elapsed, movies, series, stale, len(ledger),
        )


if __name__ == "__main__":
    main()

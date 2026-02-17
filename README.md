# Linkarr

Hardlink media organizer for Plex, Jellyfin, and Emby.

Scans scene-named torrent downloads, parses filenames with [guessit](https://github.com/guessit-io/guessit) + [aniparse](https://github.com/igorcmoura/aniparse), normalizes titles via [TMDb](https://www.themoviedb.org/), and creates hardlinks in a clean library structure. Zero extra disk usage. Seeding continues uninterrupted.

## The problem

Torrent clients and media servers want opposite things:

```
 qBittorrent / ruTorrent              Plex / Jellyfin / Emby

 Needs the ORIGINAL filename          Needs CLEAN names in a
 to keep seeding                      structured library

 Inception.2010.1080p.BluRay.         Movies/
   x264-GROUP.mkv                       Inception (2010)/
                                          Inception (2010).mkv

 Breaking.Bad.S05E16.720p.            TV Shows/
   BluRay.x264-DEMAND.mkv               Breaking Bad/
                                           Season 05/
                                             Breaking Bad - S05E16.mkv
```

- Renaming breaks seeding
- Copying doubles disk usage
- Symlinks aren't followed by all media servers

**Hardlinks**: two filenames, one block of data on disk. Torrent client sees the original. Plex sees the clean name. Zero extra bytes.

## How it works

```
┌──────────────┐         ┌──────────────────────────┐         ┌──────────────┐
│   Torrent    │         │         linkarr          │         │ Media Server │
│   Client     │         │                          │         │              │
│              │  scan   │  1. Find new files       │  read   │              │
│ /downloads/  │ ──────> │  2. Parse with guessit   │ <────── │  /movies/    │
│   movies/    │         │     + aniparse fallback   │         │  /series/    │
│   series/    │         │  3. Normalize via TMDb   │         │              │
│              │         │  4. Hardlink to library   │         │              │
│              │         │  5. Clean stale links    │         │              │
└──────────────┘         └──────────────────────────┘         └──────────────┘
      │                              │                               │
      │         same filesystem, same inode                          │
      └──────────────────────────────┴───────────────────────────────┘
                        zero extra disk space
```

When a torrent is removed, linkarr detects the missing source and cleans up the hardlink + empty directories automatically.

## Quick start

```yaml
services:
  linkarr:
    image: ghcr.io/mderouet/linkarr:latest
    container_name: linkarr
    restart: unless-stopped
    environment:
      - TMDB_API_KEY=your_tmdb_api_key  # optional, for title normalization
      - SCAN_INTERVAL=60                # seconds between scans
    volumes:
      - /path/to/media:/media
      - linkarr-data:/data

volumes:
  linkarr-data:
```

### With qBittorrent + Plex

```yaml
services:
  qbittorrent:
    image: lscr.io/linuxserver/qbittorrent:latest
    volumes:
      - /mnt/media:/media
    # ... your config

  plex:
    image: lscr.io/linuxserver/plex:latest
    volumes:
      - /mnt/media:/media
    # ... your config

  linkarr:
    image: ghcr.io/mderouet/linkarr:latest
    environment:
      - TMDB_API_KEY=${TMDB_API_KEY}
    volumes:
      - /mnt/media:/media            # same mount as qbittorrent and plex
      - linkarr-data:/data

volumes:
  linkarr-data:
```

> **Important**: All three containers must share the exact same `/media` mount from the host. Hardlinks only work within the same filesystem.

### Directory structure

```
/media/                          <- shared mount
├── downloads/
│   ├── movies/                  <- qBittorrent "movies" category
│   │   └── Inception.2010.1080p.BluRay.x264-GROUP.mkv
│   └── series/                  <- qBittorrent "series" category
│       └── Breaking.Bad.S05E16.720p.BluRay.x264-DEMAND.mkv
├── movies/                      <- Plex movie library
│   └── Inception (2010)/
│       └── Inception (2010).mkv          <- hardlink (same inode)
└── series/                      <- Plex TV library
    └── Breaking Bad/
        └── Season 05/
            └── Breaking Bad - S05E16.mkv  <- hardlink (same inode)
```

## Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TMDB_API_KEY` | *(empty)* | [TMDb API key](https://www.themoviedb.org/settings/api) for title normalization |
| `SCAN_INTERVAL` | `60` | Seconds between scans (0 = run once and exit) |
| `DRY_RUN` | `false` | Log what would happen without creating hardlinks |
| `LOG_LEVEL` | `INFO` | Logging verbosity (DEBUG, INFO, WARNING, ERROR) |
| `DOWNLOADS_MOVIES` | `/media/downloads/movies` | Source directory for movie downloads |
| `DOWNLOADS_SERIES` | `/media/downloads/series` | Source directory for series downloads |
| `LIBRARY_MOVIES` | `/media/movies` | Plex movie library destination |
| `LIBRARY_SERIES` | `/media/series` | Plex TV library destination |
| `DATA_DIR` | `/data` | Directory for state files (ledger, cache, log) |

## TMDb integration

When `TMDB_API_KEY` is set, linkarr normalizes parsed titles against TMDb:

- `Amelie` -> `Amelie` (accent normalization)
- `Spiderman` -> `Spider-Man` (canonical naming)
- Scene variants -> consistent official titles

Get a free API key at https://www.themoviedb.org/settings/api

Without TMDb, linkarr uses the raw parsed title — still works well for standard scene releases.

## One-shot mode

Run once and exit (useful for cron or testing):

```bash
docker run --rm \
  -e TMDB_API_KEY=xxx \
  -v /mnt/media:/media \
  -v linkarr-data:/data \
  ghcr.io/mderouet/linkarr:latest once
```

Or set `SCAN_INTERVAL=0`.

## What it parses

Handles all common torrent naming patterns:

| Format | Example | Result |
|--------|---------|--------|
| Scene | `Inception.2010.1080p.BluRay.x264-GROUP.mkv` | `Inception (2010)/Inception (2010).mkv` |
| YTS | `The Batman (2022) [1080p] [WEBRip] [YTS.MX].mkv` | `The Batman (2022)/The Batman (2022).mkv` |
| Anime fansub | `[SubsPlease] Dandadan - 03 (1080p).mkv` | `Dandadan/Season 01/Dandadan - S01E03.mkv` |
| Anime season | `[SubsPlease] Jujutsu Kaisen S2 - 15.mkv` | `Jujutsu Kaisen/Season 02/... - S02E15.mkv` |
| Absolute | `[SubsPlease] One Piece - 1122 (1080p).mkv` | `One Piece/Season 01/... - S01E1122.mkv` |
| Multi-ep | `Avatar.S01E01E02.1080p.mkv` | `Avatar .../Season 01/... - S01E01E02.mkv` |
| No year | `The.Matrix.1080p.BluRay.mkv` | `The Matrix/The Matrix.mkv` |

Supported video extensions: `.mkv`, `.mp4`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`, `.m4v`, `.mpg`, `.mpeg`, `.ts`, `.vob`

## Why not Sonarr/Radarr?

| | Sonarr/Radarr | Linkarr |
|---|---|---|
| Auto-grab from indexers | Yes | No |
| Quality upgrades | Yes | No |
| Web UI | Yes | No |
| Database | SQLite | JSON file |
| RAM usage | ~200-500 MB each | < 50 MB |
| Docker image | ~200 MB each | ~60 MB |
| Setup | Hours | 30 seconds |

Linkarr is for users who manage their torrents manually and just need the **renaming + hardlinking** part.

## Logs and state

```bash
docker logs linkarr                    # recent output
```

Persistent state files (in `DATA_DIR` volume):
- `processed.json` — tracked source-to-destination mappings
- `tmdb_cache.json` — TMDb API response cache
- `organize.log` — full log file

### Re-process all files

Delete the ledger and restart:

```bash
# If using a named volume:
docker exec linkarr rm /data/processed.json
docker restart linkarr
```

## License

MIT

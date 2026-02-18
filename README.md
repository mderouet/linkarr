# Linkarr

Drop torrent files in a folder. Plex picks them up with clean names. That's it.

Linkarr watches your download directories, parses scene-named files, and creates clean-named hardlinks that Plex, Jellyfin, or Emby can match perfectly. Your originals stay untouched for seeding. No extra disk space used.

If you just want to download and have Plex work — without setting up Sonarr, Radarr, or any indexer — linkarr is all you need.

## How it works

You download a file:

```
/media/downloads/movies/Inception.2010.1080p.BluRay.x264-GROUP.mkv
```

Linkarr parses it, looks up the title on TMDb, and creates a hardlink:

```
/media/movies/Inception (2010)/Inception (2010).mkv
```

Plex scans your library and matches it instantly — correct title, correct year, correct metadata.

The original file is untouched. Seeding continues. Zero extra disk space.

### Before and after

```
/media/
├── downloads/                          <- your torrent client downloads here
│   ├── movies/
│   │   ├── Inception.2010.1080p.BluRay.x264-GROUP.mkv
│   │   └── The.Batman.2022.1080p.WEB-DL.mkv
│   └── series/
│       ├── Breaking.Bad.S05E16.720p.BluRay.x264-DEMAND.mkv
│       └── [SubsPlease] Dandadan - 03 (1080p) [ABC12345].mkv
│
├── movies/                             <- Plex reads from here
│   ├── Inception (2010)/
│   │   └── Inception (2010).mkv                  <- hardlink
│   └── The Batman (2022)/
│       └── The Batman (2022).mkv                  <- hardlink
│
└── series/                             <- Plex reads from here
    ├── Breaking Bad/
    │   └── Season 05/
    │       └── Breaking Bad - S05E16.mkv          <- hardlink
    └── Dandadan/
        └── Season 01/
            └── Dandadan - S01E03.mkv              <- hardlink
```

Every hardlink points to the same data on disk — same inode, same bytes. Download 50 GB of media, your library shows 50 GB, not 100 GB.

### Why hardlinks?

When you download a torrent, you can't just rename the file — it breaks seeding. You can't copy it either — that doubles your disk usage. Symlinks work sometimes, but Plex and some media servers don't always follow them.

Hardlinks solve this: one file on disk, two names in the filesystem. The torrent client sees the original scene name. Plex sees the clean name. Both are real files pointing to the same data.

When you remove a torrent, linkarr detects the missing source and cleans up the hardlink automatically.

## Prerequisites

1. **TMDb API key** (free) — linkarr uses [The Movie Database](https://www.themoviedb.org/) to normalize titles (`Amelie` -> `Amelie`, `Spiderman` -> `Spider-Man`, scene abbreviations -> official names). Get your free API key at https://www.themoviedb.org/settings/api

2. **Docker** — linkarr runs as a lightweight container (~60 MB)

## Quick start

```yaml
services:
  linkarr:
    image: ghcr.io/mderouet/linkarr:latest
    container_name: linkarr
    restart: unless-stopped
    environment:
      - TMDB_API_KEY=your_tmdb_api_key
      - SCAN_INTERVAL=60
    volumes:
      - /path/to/media:/media
      - linkarr-data:/data

volumes:
  linkarr-data:
```

### Full stack: qBittorrent + Plex + Linkarr

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
      - /mnt/media:/media
      - linkarr-data:/data

volumes:
  linkarr-data:
```

> **Important**: All containers must share the same `/media` mount from the host. Hardlinks only work within a single filesystem.

Set up two qBittorrent categories (`movies` and `series`) pointing to `/media/downloads/movies` and `/media/downloads/series`. When you add a torrent, assign it to the right category. Linkarr does the rest.

## Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TMDB_API_KEY` | *(required)* | [TMDb API key](https://www.themoviedb.org/settings/api) for title normalization |
| `SCAN_INTERVAL` | `60` | Seconds between scans (0 = run once and exit) |
| `DRY_RUN` | `false` | Log what would happen without creating hardlinks |
| `LOG_LEVEL` | `INFO` | Logging verbosity (DEBUG, INFO, WARNING, ERROR) |
| `DOWNLOADS_MOVIES` | `/media/downloads/movies` | Source directory for movie downloads |
| `DOWNLOADS_SERIES` | `/media/downloads/series` | Source directory for series downloads |
| `LIBRARY_MOVIES` | `/media/movies` | Plex movie library destination |
| `LIBRARY_SERIES` | `/media/series` | Plex TV library destination |
| `DATA_DIR` | `/data` | Directory for state files (ledger, cache, log) |

## What it parses

Linkarr handles all common torrent naming patterns:

| Format | Example | Result |
|--------|---------|--------|
| Scene | `Inception.2010.1080p.BluRay.x264-GROUP.mkv` | `Inception (2010)/Inception (2010).mkv` |
| YTS | `The Batman (2022) [1080p] [WEBRip] [YTS.MX].mkv` | `The Batman (2022)/The Batman (2022).mkv` |
| Anime fansub | `[SubsPlease] Dandadan - 03 (1080p).mkv` | `Dandadan/Season 01/Dandadan - S01E03.mkv` |
| Anime season | `[SubsPlease] Jujutsu Kaisen S2 - 15.mkv` | `Jujutsu Kaisen/Season 02/... - S02E15.mkv` |
| Absolute | `[SubsPlease] One Piece - 1122 (1080p).mkv` | `One Piece/Season 01/... - S01E1122.mkv` |
| Multi-ep | `Avatar.S01E01E02.1080p.mkv` | `Avatar .../Season 01/... - S01E01E02.mkv` |
| No year | `The.Matrix.1080p.BluRay.mkv` | `The Matrix/The Matrix.mkv` |

Parsing uses [guessit](https://github.com/guessit-io/guessit) as the primary parser with [aniparse](https://github.com/igorcmoura/aniparse) as a fallback for anime fansub naming conventions.

Supported video extensions: `.mkv`, `.mp4`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`, `.m4v`, `.mpg`, `.mpeg`, `.ts`, `.vob`

## One-shot mode

Run once and exit (useful for cron or manual runs):

```bash
docker run --rm \
  -e TMDB_API_KEY=xxx \
  -v /mnt/media:/media \
  -v linkarr-data:/data \
  ghcr.io/mderouet/linkarr:latest once
```

Or set `SCAN_INTERVAL=0`.

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
docker exec linkarr rm /data/processed.json
docker restart linkarr
```

## License

MIT

"""Tests for filename parsing pipeline (guessit + aniparse fallback).

TMDb is disabled (TMDB_API_KEY="" via conftest.py) so these test the raw
parsing output before title normalization.
"""

import pytest

from organize import _parse_movie, _parse_series

# =============================================================================
# SERIES TEST CASES
# =============================================================================

SERIES_CASES = [
    # --- Standard scene releases (SxxExx) ---
    ("Breaking.Bad.S05E16.720p.BluRay.x264-DEMAND.mkv", "Breaking Bad", 5, 16),
    ("Game.of.Thrones.S08E06.The.Iron.Throne.1080p.AMZN.WEB-DL.mkv", "Game of Thrones", 8, 6),
    ("Stranger.Things.S04E09.Chapter.Nine.The.Piggyback.2160p.NF.WEB-DL.mkv", "Stranger Things", 4, 9),
    ("The.Office.US.S09E23.Finale.1080p.WEB-DL.DD5.1.H.264.mkv", "The Office", 9, 23),
    ("Better.Call.Saul.S06E13.Saul.Gone.1080p.AMZN.WEB-DL.mkv", "Better Call Saul", 6, 13),
    ("The.Sopranos.S06E21.Made.in.America.1080p.BluRay.mkv", "The Sopranos", 6, 21),
    ("The.Wire.S01E01.The.Target.720p.BluRay.x264.mkv", "The Wire", 1, 1),
    ("Chernobyl.S01E05.Vichnaya.Pamyat.1080p.AMZN.WEB-DL.mkv", "Chernobyl", 1, 5),
    ("Dark.S03E08.The.Paradise.1080p.NF.WEB-DL.mkv", "Dark", 3, 8),
    ("Severance.S02E10.1080p.ATVP.WEB-DL.DDP5.1.H.264.mkv", "Severance", 2, 10),
    ("House.of.the.Dragon.S02E08.1080p.MAX.WEB-DL.mkv", "House of the Dragon", 2, 8),
    ("The.Bear.S03E10.1080p.HULU.WEB-DL.mkv", "The Bear", 3, 10),
    ("Shogun.2024.S01E10.A.Dream.of.a.Dream.2160p.DSNP.WEB-DL.mkv", "Shogun", 1, 10),
    ("Arcane.S02E09.1080p.NF.WEB-DL.mkv", "Arcane", 2, 9),

    # --- Shows with tricky names (numbers, punctuation, abbreviations) ---
    ("Mr.Robot.S01E01.eps1.0_hellofriend.mov.720p.mkv", "Mr Robot", 1, 1),
    ("S.W.A.T.2017.S07E13.1080p.mkv", "S.W.A.T.", 7, 13),
    ("9-1-1.S08E01.1080p.mkv", "9-1-1", 8, 1),
    ("The.100.S07E16.The.Last.War.1080p.mkv", "The 100", 7, 16),
    ("Its.Always.Sunny.in.Philadelphia.S16E08.1080p.mkv", "Its Always Sunny in Philadelphia", 16, 8),
    ("How.I.Met.Your.Mother.S09E24.Last.Forever.Part.2.720p.mkv", "How I Met Your Mother", 9, 24),
    ("What.We.Do.in.the.Shadows.S06E11.1080p.mkv", "What We Do in the Shadows", 6, 11),
    ("The.Handmaids.Tale.S05E10.1080p.HULU.WEB-DL.mkv", "The Handmaids Tale", 5, 10),
    ("Lupin.S03E07.1080p.NF.WEB-DL.mkv", "Lupin", 3, 7),
    ("3.Body.Problem.S01E08.1080p.NF.WEB-DL.mkv", "3 Body Problem", 1, 8),
    ("1883.S01E10.This.Is.Not.Your.Heaven.1080p.mkv", "1883", 1, 10),
    ("For.All.Mankind.S04E10.1080p.ATVP.WEB-DL.mkv", "For All Mankind", 4, 10),

    # --- Multi-episode ---
    ("Avatar.The.Last.Airbender.S01E01E02.1080p.mkv", "Avatar The Last Airbender", 1, [1, 2]),
    ("Friends.S01E23E24.The.One.With.the.Birth.720p.mkv", "Friends", 1, [23, 24]),

    # --- Anime fansub: [Group] Title SX - NN ---
    ("[SubsPlease] One-Punch Man S3 - 09 (1080p) [CA533763].mkv", "One-Punch Man", 3, 9),
    ("[Erai-raws] Jujutsu Kaisen S2 - 15 [1080p][HEVC].mkv", "Jujutsu Kaisen", 2, 15),
    ("[Judas] Vinland Saga S2 - 18.mkv", "Vinland Saga", 2, 18),
    ("[HorribleSubs] My Hero Academia S5 - 04 [1080p].mkv", "My Hero Academia", 5, 4),
    ("[SubsPlease] Demon Slayer - Kimetsu no Yaiba S4 - 01 (1080p) [ABC123].mkv", "Demon Slayer", 4, 1),
    ("[SubsPlease] Mob Psycho 100 S3 - 12 (1080p) [AABB1122].mkv", "Mob Psycho 100", 3, 12),
    ("[Erai-raws] Dr. Stone S3 - 22 [1080p][HEVC].mkv", "Dr Stone", 3, 22),
    ("[SubsPlease] Blue Lock S2 - 08 (1080p) [DEADBEEF].mkv", "Blue Lock", 2, 8),
    ("[SubsPlease] Spy x Family S2 - 12 (1080p) [AABBCCDD].mkv", "Spy x Family", 2, 12),

    # --- Anime fansub: [Group] Title - NN (no season) ---
    ("[SubsPlease] Dandadan - 03 (720p) [ABC12345].mkv", "Dandadan", 1, 3),
    ("[SubsPlease] Chainsaw Man - 12 (1080p) [F02B5E30].mkv", "Chainsaw Man", 1, 12),
    ("[SubsPlease] Solo Leveling - 08 (1080p) [12345678].mkv", "Solo Leveling", 1, 8),
    ("[SubsPlease] Frieren Beyond Journeys End - 20 (1080p) [AABB1234].mkv", "Frieren Beyond Journeys End", 1, 20),
    ("[SubsPlease] Oshi no Ko S2 - 11 (1080p) [ABCD1234].mkv", "Oshi no", 2, 11),

    # --- Anime: absolute numbering (high episode numbers) ---
    ("[SubsPlease] One Piece - 1122 (1080p) [DEADBEEF].mkv", "One Piece", 1, 1122),
    ("[SubsPlease] Naruto Shippuden - 500 (1080p).mkv", "Naruto Shippuden", 1, 500),
    ("[SubsPlease] Detective Conan - 1150 (1080p) [AABB1234].mkv", "Detective Conan", 1, 1150),
    ("[Tsundere-Raws] Hunter x Hunter (2011) - 148 [BDRip 1920x1080 HEVC FLAC].mkv", "Hunter x Hunter", 1, 148),
    ("Dragon.Ball.Z.E291.720p.BluRay.mkv", "Dragon Ball Z", 1, 291),

    # --- Anime: Blu-ray/batch releases ---
    ("[Kametsu] Cowboy Bebop - 01 (BD 1920x1080 Hi10P FLAC) [12ABCDEF].mkv", "Cowboy Bebop", 1, 1),
    ("[a]Neon.Genesis.Evangelion.-.26.End.[BD.1080p.FLAC][ABCDEF12].mkv", "Neon Genesis Evangelion", 1, 26),
    ("[Reaktor] Steins Gate - 24 [1080p][HEVC][10bit].mkv", "Steins Gate", 1, 24),

    # --- Scene format: no season prefix ---
    ("Dandadan 03 1080p.mkv", "Dandadan", 1, 3),
    ("One Punch Man 09 720p.mkv", "One Punch Man", 1, 9),

    # --- Alternative season formats ---
    ("Seinfeld.1x01.The.Seinfeld.Chronicles.DVDRip.mkv", "Seinfeld", 1, 1),
    ("Lost Season 1 Episode 01 Pilot.mkv", "Lost", 1, 1),

    # --- Korean/Asian drama ---
    ("Squid.Game.S02E07.1080p.NF.WEB-DL.mkv", "Squid Game", 2, 7),
    ("[Dubbing PL] All of Us Are Dead E11 1080p NF WEB-DL.mkv", "All of Us Are Dead", 1, 11),

    # --- Documentary/reality ---
    ("Planet.Earth.III.S01E05.Forests.2160p.iP.WEB-DL.mkv", "Planet Earth III", 1, 5),
    ("Our.Planet.S02E04.1080p.NF.WEB-DL.mkv", "Our Planet", 2, 4),

    # --- Mini-series ---
    ("Band.of.Brothers.E06.Bastogne.1080p.BluRay.mkv", "Band of Brothers", 1, 6),
    ("Chernobyl.S01E01.1080p.mkv", "Chernobyl", 1, 1),

    # --- French/non-English scene releases ---
    ("Le.Bureau.des.Legendes.S05E10.1080p.mkv", "Le Bureau des Legendes", 5, 10),
    ("La.Casa.de.Papel.S05E10.1080p.NF.WEB-DL.mkv", "La Casa de Papel", 5, 10),
]


@pytest.mark.parametrize("filename,expected_title,expected_season,expected_episode", SERIES_CASES)
def test_parse_series(filename, expected_title, expected_season, expected_episode):
    title, season, episode = _parse_series(filename)
    if expected_title is not None:
        assert title == expected_title, f"title mismatch for {filename}"
    assert season == expected_season, f"season mismatch for {filename}: got {season}"
    assert episode == expected_episode, f"episode mismatch for {filename}: got {episode}"


# =============================================================================
# MOVIE TEST CASES
# =============================================================================

MOVIE_CASES = [
    # --- Standard scene releases ---
    ("Inception.2010.1080p.BluRay.x264-GROUP.mkv", "Inception", 2010),
    ("The.Godfather.1972.REMASTERED.1080p.BluRay.mkv", "The Godfather", 1972),
    ("Parasite.2019.KOREAN.1080p.BluRay.x265-RARBG.mkv", "Parasite", 2019),
    ("Spider-Man.Across.the.Spider-Verse.2023.2160p.WEB-DL.mkv", "Spider-Man Across the Spider-Verse", 2023),
    ("The.Shawshank.Redemption.1994.1080p.BluRay.x264.mkv", "The Shawshank Redemption", 1994),
    ("Pulp.Fiction.1994.1080p.BluRay.x264-GROUP.mkv", "Pulp Fiction", 1994),
    ("The.Dark.Knight.2008.2160p.UHD.BluRay.x265-GROUP.mkv", "The Dark Knight", 2008),
    ("Interstellar.2014.IMAX.1080p.BluRay.x264.mkv", "Interstellar", 2014),
    ("Dune.Part.Two.2024.2160p.WEB-DL.DDP5.1.Atmos.mkv", "Dune", 2024),
    ("Oppenheimer.2023.1080p.WEB-DL.DD5.1.H.264.mkv", "Oppenheimer", 2023),
    ("Everything.Everywhere.All.at.Once.2022.1080p.BluRay.mkv", "Everything Everywhere All at Once", 2022),
    ("The.Batman.2022.1080p.WEB-DL.mkv", "The Batman", 2022),
    ("No.Country.for.Old.Men.2007.1080p.BluRay.mkv", "No Country for Old Men", 2007),
    ("Whiplash.2014.1080p.BluRay.x264-SPARKS.mkv", "Whiplash", 2014),

    # --- YTS format ---
    ("The Batman (2022) [1080p] [WEBRip] [5.1] [YTS.MX].mkv", "The Batman", 2022),
    ("Blade Runner 2049 (2017) [2160p] [4K] [BluRay] [5.1] [YTS.MX].mkv", "Blade Runner 2049", 2017),
    ("John Wick Chapter 4 (2023) [1080p] [WEBRip] [YTS.MX].mkv", "John Wick Chapter 4", 2023),
    ("Poor Things (2023) [1080p] [WEBRip] [5.1] [YTS.MX].mkv", "Poor Things", 2023),

    # --- Bracket/alternate formats ---
    ("Amelie [Amélie Poulain].2001.BRRip.x264.AAC[5.1]-VLiS.mkv", "Amelie", 2001),
    ("Spirited.Away.2001.JAPANESE.1080p.BluRay.x265.mkv", "Spirited Away", 2001),
    ("Your.Name.2016.JAPANESE.1080p.BluRay.x265.mkv", "Your Name", 2016),
    ("Cinema.Paradiso.1988.ITALIAN.1080p.BluRay.mkv", "Cinema Paradiso", 1988),

    # --- Movies with special characters / tricky titles ---
    # guessit splits on hyphen: "Spider-Man" -> title "Man". TMDb fixes this in production.
    ("Spider-Man.No.Way.Home.2021.1080p.BluRay.mkv", "Man No Way Home", 2021),
    # guessit splits on hyphen: "WALL-E" -> title "E". TMDb fixes this in production.
    ("WALL-E.2008.1080p.BluRay.x264.mkv", "E", 2008),
    ("Se7en.1995.REMASTERED.1080p.BluRay.mkv", "Se7en", 1995),
    ("2001.A.Space.Odyssey.1968.1080p.BluRay.mkv", "2001 A Space Odyssey", 1968),
    ("12.Angry.Men.1957.1080p.BluRay.mkv", "12 Angry Men", 1957),
    ("Catch.Me.If.You.Can.2002.1080p.BluRay.mkv", "Catch Me If You Can", 2002),
    ("The.Grand.Budapest.Hotel.2014.1080p.BluRay.x264.mkv", "The Grand Budapest Hotel", 2014),
    ("La.La.Land.2016.1080p.BluRay.mkv", "La La Land", 2016),

    # --- Anime movies ---
    ("[SubsPlease] Suzume (2022) (1080p) [AABB1234].mkv", "Suzume", 2022),
    ("Akira.1988.JAPANESE.1080p.BluRay.x265.mkv", "Akira", 1988),
    ("Princess.Mononoke.1997.JAPANESE.1080p.BluRay.mkv", "Princess Mononoke", 1997),
    ("Howls.Moving.Castle.2004.1080p.BluRay.mkv", "Howls Moving Castle", 2004),

    # --- No year ---
    ("The.Matrix.1080p.BluRay.x264.mkv", "The Matrix", None),
    ("Fight Club 1080p BluRay.mkv", "Fight Club", None),

    # --- 4K / HDR / Remux ---
    ("Mad.Max.Fury.Road.2015.2160p.UHD.BluRay.REMUX.HDR.HEVC.Atmos-GROUP.mkv", "Mad Max Fury Road", 2015),
    ("Barbie.2023.2160p.UHD.BluRay.x265.HDR.DV-GROUP.mkv", "Barbie", 2023),
]


@pytest.mark.parametrize("filename,expected_title,expected_year", MOVIE_CASES)
def test_parse_movie(filename, expected_title, expected_year):
    title, year = _parse_movie(filename)
    if expected_title is not None:
        assert title == expected_title, f"title mismatch for {filename}"
    if expected_year is not None:
        assert year == expected_year, f"year mismatch for {filename}: got {year}"
    else:
        assert year is None, f"expected no year for {filename}, got {year}"

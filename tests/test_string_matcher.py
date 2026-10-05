"""Unit tests for Flow Launcher-style StringMatcher acronym and fuzzy matching."""

from devtoolkit.core.search.matcher import extract_acronym, score_match


def test_extract_acronym():
    assert extract_acronym("Visual Studio Code") == "vsc"
    assert extract_acronym("Windows Terminal") == "wt"
    assert extract_acronym("Google Chrome") == "gc"
    assert extract_acronym("DevToolkit") == "dt"
    assert extract_acronym("PowerShell 7") == "ps7"
    assert extract_acronym("command-prompt") == "cp"
    assert extract_acronym("Firefox Developer Edition.lnk") == "fde"


def test_score_match_exact():
    score = score_match("code", "code")
    assert score == 1000


def test_score_match_acronym():
    score_vsc = score_match("vsc", "Visual Studio Code", "vsc")
    assert score_vsc >= 800

    score_wt = score_match("wt", "Windows Terminal", "wt")
    assert score_wt >= 800

    # Prefix acronym
    score_vs = score_match("vs", "Visual Studio Code", "vsc")
    assert score_vs >= 600


def test_score_match_word_boundary():
    score = score_match("code", "Visual Studio Code", "vsc")
    assert score >= 400


def test_score_match_mismatch():
    assert score_match("xyz123", "Visual Studio Code", "vsc") == 0


"""2026-11-12: Muse の投資・マネーの記事に「投資助言ではありません」が付く（門で落ちないように）"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import genre_focus  # noqa: E402
import muse_articles  # noqa: E402


def test_investment_gets_advice_disclaimer():
    text = muse_articles.muse_disclaimer("investment")
    assert genre_focus.ADVICE_DISCLAIMER_RE.search(text)
    assert not genre_focus.advice_problems({"genreSlug": "investment", "disclaimer": text, "body": "", "title": ""})


def test_other_genres_unchanged():
    assert "投資助言" not in muse_articles.muse_disclaimer("lifestyle")
    assert muse_articles.muse_disclaimer() == muse_articles.muse_disclaimer("")

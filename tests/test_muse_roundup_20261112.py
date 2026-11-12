"""2026-11-12: 毎月の「〜月から変わること」のまとめは、同じ出典URLでも重複にしない（題名がほぼ同じ出し直しだけ止める）"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import muse_articles  # noqa: E402


def test_roundup_detected():
    assert muse_articles.is_roundup({"title": "2026年12月から変わること　年金・児童手当・料金の一覧"}, "")
    assert muse_articles.is_roundup({"title": "x"}, "20261112-早見表-2026年12月から変わること.md")
    assert not muse_articles.is_roundup({"title": "児童手当の支給日はいつ"}, "20261112-早見表-児童手当の支給日はいつ.md")
    assert not muse_articles.is_roundup({"title": "ドコモの料金が変わる"}, "")


def test_roundup_skips_same_source_url(monkeypatch):
    import dedupe

    class Recent:
        entries = [{"bigrams": dedupe.bigrams("年金の支給日は12月15日"), "label": "年金の支給日は12月15日"}]

        def find(self, title, url):
            return "同じ出典URL"

    monkeypatch.setattr(dedupe, "load_recent", lambda days: Recent())
    data = {"title": "2026年12月から変わること　年金・ボーナス・料金", "sources": [{"url": "https://www.nenkin.go.jp/x"}]}
    assert muse_articles.duplicate_of(data, "20261112-早見表-2026年12月から変わること.md") is None


def test_roundup_resubmission_still_duplicate(monkeypatch):
    import dedupe

    title = "2026年12月から変わること　年金・ボーナス・料金"

    class Recent:
        entries = [{"bigrams": dedupe.bigrams(title), "label": title}]

        def find(self, title, url):
            return "同じ出典URL"

    monkeypatch.setattr(dedupe, "load_recent", lambda days: Recent())
    data = {"title": title, "sources": [{"url": "https://www.nenkin.go.jp/x"}]}
    assert muse_articles.duplicate_of(data, "20261112-早見表-2026年12月から変わること.md")

"""2026-11-09: Muse の続報は同じ出典でも通す / 出典が多くても落とさない"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import muse_articles  # noqa: E402
import muse_format  # noqa: E402


def test_followup_detected():
    assert muse_articles.is_followup({"title": "ドコモ流出の続報、対象の確かめ方"}, "")
    assert muse_articles.is_followup({"title": "x"}, "20261109-速報解説-地震2日目の確認.md")
    assert not muse_articles.is_followup({"title": "平均給与が過去最高"}, "20261109-お金-平均給与.md")


def test_many_sources_trimmed_not_rejected():
    data = {"title": "ドコモ流出の続報で分かった対象の確かめ方", "genre": muse_format.GENRES[0], "notes": "", "body": "本文",
            "sources": [{"url": f"https://www.docomo.ne.jp/info/{i}", "name": "ドコモ", "facts": "f"} for i in range(12)]}
    problems = muse_format.problems(data, "20261109-お金-ドコモ続報.md")
    if problems is not None:
        assert not any("件まで" in p for p in problems)
        assert len(data["sources"]) == muse_format.MAX_SOURCES

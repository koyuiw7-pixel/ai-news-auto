"""ニュース → 比較記事の導線（2026-11-09 オーナー「収益考えて」）: Muse のジャンル「比較」の記事に kind と話題を付ける。
話題の決め方は lib/comparison.ts の comparisonTopicOf と同じ（lib/comparison.test.ts と同じ題名で同じ答え）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import muse_articles as m  # noqa: E402
import a8_import  # noqa: E402

CASES = [
    ("ふるさと納税の申込先、2025年10月にポイント付与が終わり選び方は手続きで比べる時代に", "furusato"),
    ("12月に料金が変わるahamoとソフトバンク光、スマホと光回線の月額を公式料金で比較", "mobile"),
    ("情報流出が不安な人へ セキュリティソフト3製品を価格と台数で比べた", "leak"),
    ("防災の備えの選び方 ポータブル電源と非常食、セットの中身と価格を比べる", "disaster"),
    ("電気代の見直しは単価だけでは決まらない、東京エリア4プランの基本料金と従量単価", "energy"),
]


def test_topic_from_title():
    for title, key in CASES:
        assert m.comparison_topic(title, "") == key, title


def test_topic_keys_are_action_ads():
    keys = {rule["key"] for rule in a8_import.ACTION_ADS}
    for _, key in CASES:
        assert key in keys


def test_override_and_body_only():
    assert m.comparison_topic("防災の備え", "", "leak") == "leak"
    assert m.comparison_topic("防災の備え", "", "nope") == "disaster"
    # 題名に当たらない話題は、本文で3語以上当たったときだけ
    assert m.comparison_topic("選び方のまとめ", "電気代と電気料金") is None
    assert m.comparison_topic("選び方のまとめ", "電気代と電気料金、新電力の比べ方") == "energy"


def test_mark_comparison_only_for_comparison_genre():
    record = {"title": CASES[2][0], "body": "ノートンとESETを比べる"}
    m.mark_comparison(record, {"genre": "比較", "title": CASES[2][0]})
    assert record["kind"] == "comparison" and record["comparisonTopic"] == "leak"
    news = {"title": "ドコモ情報流出、最大約30万件"}
    m.mark_comparison(news, {"genre": "速報解説"})
    assert "kind" not in news and "comparisonTopic" not in news


def test_comparison_genre_is_allowed():
    import muse_format

    assert m.COMPARISON_GENRE in muse_format.GENRES
    assert m.LANE_BY_GENRE[m.COMPARISON_GENRE] == "lifestyle"

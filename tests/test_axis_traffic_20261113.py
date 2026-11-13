"""交通ルール・免許・取り締まり・身近な乗り物の話題は、サイトの軸（暮らしとお金の「自分ごと」ニュース）の上（2026-11-13）。
題名「モペットは2026年も原付扱い、免許なしで乗れば無免許運転に」が、どの語にも当たらず「主題外」で誤って止まったのを直した。
実コンテンツ・ネットワーク・LLM は使わない。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import indexnow  # noqa: E402

MOPED = "モペットは2026年も原付扱い、免許なしで乗れば無免許運転に"
BODY = "## 概要\n" + "あ" * 1600 + "\n## 日本で使える？\n使えます。"

TRAFFIC_TITLES = (
    MOPED,
    "自転車の青切符、反則金はいくら",
    "電動キックボードの違反で摘発が増加",
    "ペダル付き電動バイクはナンバープレートと自賠責が必要",
    "歩道を走れるのはどんなとき、ヘルメットは努力義務",
    "道路交通法の改正で取り締まりを強化",
)
GOSSIP_TITLES = (
    "人気俳優の熱愛が発覚",
    "人気歌手が結婚を報告",
    "レイカーズが開幕戦に勝利",
    "『新作RPG』の新キャラクターを紹介",
)


def article(title: str, **extra) -> dict:
    # 今までの主題（is_focus）に当たらない分野・配信元にして、題名の語（life_link）だけで軸の上かを見る
    base = {
        "slug": "axis-traffic", "title": title, "genreSlug": "lifestyle", "channelSlug": "suntory",
        "body": BODY, "sourceUrl": "https://example.test/axis-traffic", "generatedAt": "2026-11-13T00:00:00+00:00",
    }
    base.update(extra)
    return base


class AxisTraffic(unittest.TestCase):
    def test_moped_title_is_on_axis(self):
        self.assertTrue(indexnow.life_link(MOPED))
        a = article(MOPED)
        self.assertTrue(indexnow.on_axis(a))
        self.assertNotEqual(indexnow.publish_block_reason(a), "off-focus")
        self.assertIsNone(indexnow.publish_block_reason(a))
        self.assertIsNone(indexnow.noindex_reason(a))
        self.assertFalse(indexnow.candidate_off_focus("lifestyle", MOPED))

    def test_gate_would_have_blocked_without_the_title_words(self):
        # この記事の形（分野・配信元）は、題名が軸の語に当たらないと「主題外」で止まる＝上の確認が題名の語で通っている証拠
        a = article("サンゴリアス 新ジャージーデザイン決定のお知らせ")
        self.assertEqual(indexnow.publish_block_reason(a), "off-focus")

    def test_traffic_titles_pass(self):
        for title in TRAFFIC_TITLES:
            with self.subTest(title=title):
                self.assertTrue(indexnow.life_link(title))
                self.assertNotEqual(indexnow.publish_block_reason(article(title)), "off-focus")
                self.assertIsNone(indexnow.noindex_reason(article(title)))

    def test_fine_words_are_money_words(self):
        for word in ("罰金", "反則金", "自賠責"):
            with self.subTest(word=word):
                self.assertTrue(indexnow.LIFE_MONEY_RE.search(word))

    def test_gossip_titles_still_fail(self):
        for title in GOSSIP_TITLES:
            with self.subTest(title=title):
                self.assertFalse(indexnow.life_link(title))
                self.assertEqual(indexnow.publish_block_reason(article(title)), "off-focus")
                self.assertEqual(indexnow.noindex_reason(article(title)), "no-life-link")

    def test_gossip_word_beats_traffic_word(self):
        # ゴシップ・物語・試合結果の語は、暮らしの語より先に見る（順番は変えない）
        self.assertFalse(indexnow.life_link("人気俳優がバイクで熱愛デート"))
        self.assertFalse(indexnow.life_link("自転車ロードレースで日本人選手が優勝"))


if __name__ == "__main__":
    unittest.main()

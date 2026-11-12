"""「すぐにできること」のそばの PR（ACTION_ADS）と、11/8 追加の A8 提携の設定を、通信なしで確かめる。"""
import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import a8_import  # noqa: E402
import aff_stats  # noqa: E402

A8MAT = re.compile(r"^[0-9A-Z]+(?:\+[0-9A-Z]+){3}$")
# 公式の名前と中立な1行だけにする（根拠のない売り文句を入れない）
HYPE = re.compile(r"最安|最強|No\.?1|ナンバーワン|一番|業界初|必ず|絶対|今だけ|お得|激安|｜")


class ActionAdsTest(unittest.TestCase):
    def setUp(self):
        self.offers = json.loads((ROOT / "content/offers.json").read_text(encoding="utf-8"))
        self.links = json.loads((ROOT / "affiliate_links.json").read_text(encoding="utf-8"))
        self.keys = {meta["key"] for meta in a8_import.PARTNERS.values()}
        # 楽天アフィリエイトの楽天ページへのリンク（rpx.a8.net。a8_import.RAKUTEN_DEEPLINKS）
        self.rakuten = set(a8_import.RAKUTEN_DEEPLINKS)

    def test_offers_json_matches_importer(self):
        self.assertEqual(self.offers["actionAds"], a8_import.ACTION_ADS)

    def test_every_action_partner_has_a_live_affiliate_link(self):
        for rule in a8_import.ACTION_ADS:
            for key in rule["partners"]:
                with self.subTest(rule=rule["key"], key=key):
                    partner = self.offers["partners"][key]
                    self.assertFalse(partner.get("hidden"))
                    self.assertIn(partner["program"], self.links)
                    if key in self.rakuten:
                        meta = a8_import.RAKUTEN_DEEPLINKS[key]
                        self.assertEqual(partner["link"], a8_import.rakuten_page_url(meta["page"]))
                        self.assertEqual(self.links[partner["program"]]["url"], partner["link"])
                        self.assertTrue(partner["link"].startswith("https://rpx.a8.net/svt/ejp?a8mat=4BELTP+50ED2Q+2HOM+BWGDT&rakuten=y&a8ejpredirect="))
                        continue
                    self.assertIn(key, self.keys)
                    self.assertTrue(partner["link"].startswith("https://px.a8.net/svt/ejp?a8mat="))
                    self.assertRegex(partner["link"].split("a8mat=")[1], A8MAT)

    def test_copy_is_neutral(self):
        for rule in a8_import.ACTION_ADS:
            self.assertNotRegex(rule["title"], HYPE)
            for key in rule["partners"]:
                partner = self.offers["partners"][key]
                with self.subTest(key=key):
                    self.assertNotRegex(partner["name"], HYPE)
                    self.assertNotRegex(partner["note"], HYPE)
                    self.assertLessEqual(len(partner["note"]), 70)

    def test_rules_are_valid_regex_and_ordered(self):
        order = [rule["key"] for rule in a8_import.ACTION_ADS]
        # 情報流出（ドコモなど通信会社の名前が出る）を、スマホ回線の見直しより先に当てる
        self.assertLess(order.index("leak"), order.index("mobile"))
        # ふるさと納税の記事は「確定申告」の語も出るので、ふるさと納税を先に当てる
        self.assertLess(order.index("furusato"), order.index("tax"))
        for rule in a8_import.ACTION_ADS:
            re.compile(rule["match"])
            self.assertGreaterEqual(rule.get("max", 2), 1)

    def test_new_programs_from_20261108_are_registered(self):
        ids = {
            "s00000025743001", "s00000020080001", "s00000025626001", "s00000027418001", "s00000023371001",
            "s00000022499001", "s00000000979014", "s00000017718057", "s00000015110002", "s00000004657003",
            "s00000023934001", "s00000021712001", "s00000021185002", "s00000014765001", "s00000019543001",
            # 11/8 夜の追加
            "s00000013511010", "s00000007476001", "s00000010789007", "s00000000040018", "s00000000489041",
            "s00000005230001", "s00000000218001", "s00000010685001",
        }
        self.assertLessEqual(ids, set(a8_import.PARTNERS))
        for pid in ids:
            meta = a8_import.PARTNERS[pid]
            if "a8" in meta:
                with self.subTest(pid=pid):
                    self.assertRegex(meta["a8"][0], A8MAT)
                    self.assertTrue(meta["a8"][1].isdigit())
                    self.assertEqual(self.offers["partners"][meta["key"]]["programId"], pid)

    def test_import_uses_inline_material_without_tsv(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            links, offers = root / "links.json", root / "offers.json"
            links.write_text("{}", encoding="utf-8")
            offers.write_text(json.dumps({"topics": [], "partners": {}}), encoding="utf-8")
            with patch.multiple(a8_import, TSV=root / "missing.tsv", LINKS=links, OFFERS=offers), redirect_stdout(io.StringIO()):
                self.assertEqual(a8_import.main(), 0)
            got = json.loads(offers.read_text(encoding="utf-8"))
            got_links = json.loads(links.read_text(encoding="utf-8"))
        self.assertEqual(got["partners"]["elpio"]["link"], "https://px.a8.net/svt/ejp?a8mat=4BGGBL+C9RNN6+4AXS+5Z6WY")
        self.assertEqual(got_links["エルピオでんき"]["pixel"], "https://www19.a8.net/0.gif?a8mat=4BGGBL+C9RNN6+4AXS+5Z6WY")
        # 弥生は既存の program 名（affiliate_links.json のキー）のまま、表示名だけ変える
        self.assertEqual(got["partners"]["yayoi-kakutei"]["program"], "弥生シリーズ")
        self.assertIsNone(got["partners"]["epos"]["image"])
        self.assertEqual(got["actionAds"], a8_import.ACTION_ADS)


class PositionStatsTest(unittest.TestCase):
    def test_action_ad_clicks_are_reported_separately(self):
        rows = [{"pos": "action-ad-1", "clicks": 2}, {"pos": "action-ad-2", "clicks": 1}, {"pos": "ranking-inline-1", "clicks": 4}]
        summary = dict(aff_stats.positions_summary(rows))
        self.assertEqual(summary["すぐにできることの下（本文中のPR）"], 3)
        self.assertEqual(summary["本文中の商品枠"], 4)
        self.assertEqual(aff_stats.position_group("action-ad"), "action-ad")
        self.assertEqual(aff_stats.position_group("other"), "other")

    def test_clicks_per_placement_and_partner(self):
        rows = [{"pos": "action-ad", "program": "X", "clicks": 1}, {"pos": "ranking-end", "program": "Y", "clicks": 3}]
        got = aff_stats.placement_summary(rows, {"Y": "Jackery"})
        self.assertEqual(got[0], ("記事末の商品枠（スマホ）", "Jackery", 3))
        self.assertEqual(got[1], ("すぐにできることの下（本文中のPR）", "X", 1))


class PitchTest(unittest.TestCase):
    """2026-11-09: 停電の記事の先頭が防災セット・「中身と価格は公式サイトで確認できます」だけだった件"""

    def test_pitch_is_short_neutral_and_has_no_numbers_beyond_the_note(self):
        offers = json.loads((ROOT / "content/offers.json").read_text(encoding="utf-8"))["partners"]
        for key, pitch in a8_import.PITCH.items():
            with self.subTest(key=key):
                self.assertIn(key, offers)
                merged = {**pitch, **({"gain": a8_import.GAIN[key]} if key in a8_import.GAIN else {}), **({"merits": a8_import.MERITS[key]} if a8_import.MERITS.get(key) else {})}
                self.assertEqual(offers[key]["pitch"], merged)
                for field in ("fit", "point", "cta"):
                    self.assertTrue(pitch[field])
                    self.assertNotRegex(pitch[field], HYPE)
                self.assertNotEqual(pitch["cta"], "公式サイトで見る")
                self.assertLessEqual(len(pitch["fit"]), 24)
                # 数字は note（公式の情報）にあるものだけ（例: 44点・1ギガ・10ギガ）
                for number in re.findall(r"\d+", pitch["point"] + pitch["fit"]):
                    self.assertIn(number, offers[key]["note"])

    def test_gain_and_merits_are_plain_and_merits_only_hold_the_numbers(self):
        # 2026-11-10 オーナー「広告が魅力的じゃない」: 見出しは読者が確かめられること（GAIN）、良いところは公式の事実（MERITS）
        banned = re.compile(r"[→›▶｜]|ざっくり")
        for key, gain in a8_import.GAIN.items():
            with self.subTest(gain=key):
                self.assertIn(key, a8_import.PITCH)
                self.assertNotRegex(gain, HYPE)
                self.assertNotRegex(gain, banned)
                self.assertNotRegex(gain, r"\d")  # 数字の約束は見出しに書かない（MERITS だけ）
                self.assertLessEqual(len(gain), 30)
        for key, merits in a8_import.MERITS.items():
            with self.subTest(merits=key):
                self.assertIn(key, a8_import.PITCH)
                self.assertTrue(1 <= len(merits) <= 3)
                for merit in merits:
                    self.assertNotRegex(merit, HYPE)
                    self.assertNotRegex(merit, banned)
                    self.assertLessEqual(len(merit), 24)
                    # 金額は税込・税抜を書く
                    if re.search(r"\d円", merit) and not re.search(r"0円|手数料|違約金", merit):
                        self.assertRegex(merit, r"税込|税抜")

    def test_every_action_rule_has_a_lead_and_valid_intents(self):
        for rule in a8_import.ACTION_ADS:
            with self.subTest(rule=rule["key"]):
                self.assertTrue(rule.get("lead"))
                # スマホの囲みで2行まで（2026-11-09 オーナー承認時の条件）。「〜しましょう」は使わない（A17）
                for lead in [rule["lead"], *[i["lead"] for i in rule.get("intents", []) if i.get("lead")]]:
                    self.assertLessEqual(len(lead), 36)
                    self.assertNotIn("しましょう", lead)
                self.assertNotRegex(rule["lead"], HYPE)
                for intent in rule.get("intents", []):
                    re.compile(intent["match"])
                    self.assertTrue(set(intent["partners"]) <= set(rule["partners"]))

    def test_outage_puts_portable_power_first(self):
        disaster = next(r for r in a8_import.ACTION_ADS if r["key"] == "disaster")
        outage = next(i for i in disaster["intents"] if re.search(i["match"], "停電したらまずブレーカーを確認"))
        self.assertEqual(outage["key"], "outage")
        self.assertIn(outage["partners"][0], ("jackery", "bluetti"))


class ComponentWiringTest(unittest.TestCase):
    def test_action_ad_block_is_labelled_and_tracked(self):
        src = (ROOT / "components/ActionAd.tsx").read_text(encoding="utf-8")
        # 置き場所の名前は記事では "action-ad"（手続きガイド・計算ツールは pos で渡す。lib/guide-ads.ts）
        self.assertIn('pos = "action-ad"', src)
        self.assertIn("data-aff-pos={pos}", src)
        # リンクの部品は右側の枠と同じ（components/rail/parts.tsx の PrFeature・PrRow）
        self.assertIn("PrFeature", src)
        self.assertIn("AFFILIATE_REL", (ROOT / "components/rail/parts.tsx").read_text(encoding="utf-8"))
        self.assertIn("PR", src)
        self.assertIn("広告", src)
        rel = (ROOT / "lib/affiliate.ts").read_text(encoding="utf-8")
        self.assertIn('AFFILIATE_REL = "sponsored nofollow', rel)
        # クリックの受け口が置き場所の名前を受け付ける形のまま
        aff = (ROOT / "cloudflare/aff.ts").read_text(encoding="utf-8")
        pos = re.search(r"const POS = /(.+)/;", aff).group(1)
        self.assertRegex("action-ad-2", pos)

    def test_both_article_layouts_render_it_after_today_actions(self):
        src = (ROOT / "app/articles/[slug]/page.tsx").read_text(encoding="utf-8")
        today = src.index("<TodayActions actions={todayActions} />}")
        self.assertLess(today, src.index("<ActionAd ad={actionAd}"))
        self.assertLess(src.index("<ActionAd ad={actionAd}") - today, 300)
        # ノワール（2026-11-09 オーナー「広告が一番下だけ」・2026-11-10 オーナー「合う広告は上のほうに」・
        # 2026-11-11 オーナー「答えを先に。1つ目の広告は答えの直後」）:
        # 要点 → 答えの表 → すぐにできること のすぐ下が1つ目の PR（本文より前）。この話の続き・イメージ写真はその後ろ
        noir = (ROOT / "components/noir/NoirArticle.tsx").read_text(encoding="utf-8")
        self.assertLess(noir.index('className="nr-sum"'), noir.index("{slots.answer}"))
        self.assertLess(noir.index("{slots.answer}"), noir.index("{slots.quick}"))
        self.assertLess(noir.index("{slots.quick}"), noir.index("{slots.adEarly"))
        self.assertLess(noir.index("{slots.adEarly"), noir.index("{slots.story}"))
        self.assertLess(noir.index("{slots.story}"), noir.index("{!coverOnTop && <CoverFigure"))
        self.assertLess(noir.index("{slots.adEarly"), noir.index('id="nr-body"'))
        page = (ROOT / "components/noir/noirArticlePage.tsx").read_text(encoding="utf-8")
        self.assertIn("if (actionAd) adBlocks.push(<ActionAd", page)
        # 2026-11-12: AdSense の審査の期間は1つだけ・本文の後ろ（lib/ad-review.ts）。期間のあとは元の3つ
        self.assertIn("const [adEarly, adMidPr, adEnd] = adReview ? [null, null, adBlocks[0] ?? null] : adBlocks.slice(0, 3);", page)

class AdPlacementUpgradeTest(unittest.TestCase):
    """2026-11-09: ドコモの情報流出の記事（いちばん読まれた記事）に、ほとんど広告が出ていなかった件の再発防止"""

    def setUp(self):
        self.offers = json.loads((ROOT / "content/offers.json").read_text(encoding="utf-8"))
        self.topics = {t["key"]: t for t in self.offers["topics"]}

    def test_every_action_rule_has_a_short_reason(self):
        for rule in a8_import.ACTION_ADS:
            with self.subTest(rule=rule["key"]):
                self.assertTrue(rule.get("reason"))
                self.assertLessEqual(len(rule["reason"]), 40)
                self.assertNotRegex(rule["reason"], HYPE)

    def test_life_topics_mirror_action_rules(self):
        for topic in a8_import.life_topics():
            with self.subTest(topic=topic["key"]):
                self.assertEqual(self.topics[topic["key"]], topic)
                # genres が無いと AI の記事にしか出ない（話題の既定は ai）
                self.assertTrue(topic["genres"])
                self.assertGreaterEqual(topic["min"], 5)

    def test_security_topic_matches_data_leak_headlines(self):
        security = self.topics["security"]
        pattern = re.compile(f"{security['match']}|{security['alsoMatch']}")
        self.assertIn("business", security["genres"])
        for title in ("ドコモ情報流出、最大約30万件", "顧客の個人情報が流出の恐れ", "不正ログインで乗っ取り被害"):
            self.assertRegex(title, pattern)

    def test_mobile_switch_needs_a_carrier_and_a_reason_to_switch(self):
        pattern = re.compile(self.topics["mobile-switch"]["match"])
        # 2026-11-10 チームの点検（Grok）: 流出の記事で、流出への対策のすぐ後に格安SIMが出ていた → 流出の記事はセキュリティの話題だけ
        self.assertNotRegex("ドコモ情報流出、最大約30万件", pattern)
        self.assertRegex("ドコモ情報流出、最大約30万件", re.compile(self.topics["mobile-switch"]["articleExclude"]))
        self.assertRegex("楽天モバイルのMNP手続きの不具合", pattern)
        self.assertNotRegex("ドコモ、新型iPad miniを予約開始", pattern)
        self.assertNotRegex("NTTドコモグループ、被災地で社員ボランティア", pattern)
        self.assertRegex("ソフトバンクが料金プランを改定", pattern)
        self.assertNotRegex("ソフトバンクグループの決算", pattern)

    def test_programs_in_new_topics_exist_in_importer(self):
        keys = {meta["key"] for meta in a8_import.PARTNERS.values()} | set(a8_import.RAKUTEN_DEEPLINKS)
        for key in ("mobile-switch", *[t["key"] for t in a8_import.life_topics()]):
            for partner in self.topics[key]["partners"]:
                with self.subTest(topic=key, partner=partner):
                    self.assertIn(partner, keys)
                    self.assertFalse(self.offers["partners"][partner].get("hidden"))

    def test_apply_topics_is_idempotent(self):
        once = json.loads(json.dumps(self.offers))
        a8_import.apply_topics(once)
        self.assertEqual(once["topics"], self.offers["topics"])
        self.assertEqual(once["actionAds"], self.offers["actionAds"])

    def test_action_ad_shows_banner_without_layout_shift(self):
        src = (ROOT / "components/ActionAd.tsx").read_text(encoding="utf-8")
        parts = (ROOT / "components/rail/parts.tsx").read_text(encoding="utf-8")
        # バナーは 6:5 の枠（AdThumb）に小さく。幅・高さを先に取る
        self.assertIn("width={300}", parts)
        self.assertIn("height={250}", parts)
        self.assertIn("aspect-[6/5]", parts)
        # 2026-11-11 オーナー「文字ばっか」（台帳 W39）: 記事から商品へつなぐ一文（ad.lead / ad.reason）は囲みに出さない
        self.assertNotIn("{lead", src)
        self.assertIn("<Pixels", src)

    def test_kids_ads_stay_on_kids_learning(self):
        # 2026-11-10 チームの点検（Grok）: 児童手当の記事の「子どもの学び」の枠にふるさと本舗、出産手当金の記事にプログラミング教室
        kids = next(rule for rule in a8_import.ACTION_ADS if rule["key"] == "kids")
        self.assertNotIn("furusato-honpo", kids["partners"])
        for title in ("出産手当金は産前42日から産後56日まで", "育児休業給付金の手続き"):
            self.assertRegex(title, kids["exclude"])
        self.assertNotRegex("児童手当、第3子以降は月3万円", kids["exclude"])

    def test_ad_cards_have_no_arrow_marks(self):
        # 2026-11-09 オーナー「→みたいな印はいらない」
        for path in ("components/ActionAd.tsx", "components/rail/RankingBody.tsx", "components/rail/RailRanking.tsx", "components/CompareOffers.tsx",
                     # 2026-11-11: 得のカード（parts.tsx）・サイト内の案内の行・小さなバナー・得のカードの読み込み
                     "components/rail/parts.tsx", "components/rail/RowThumb.tsx", "components/InternalMoneyCard.tsx", "lib/ad-benefits.ts"):
            src = (ROOT / path).read_text(encoding="utf-8")
            code = "\n".join(line for line in src.splitlines() if not line.strip().startswith(("*", "//", "{/*", "/**")))
            with self.subTest(path=path):
                self.assertNotRegex(code, "[→›]")

    def test_benefit_data_has_no_arrow_marks(self):
        # 得のカードの文言（content/ad_benefits.json の _README 以外）にも矢印は入れない
        import json
        data = json.loads((ROOT / "content/ad_benefits.json").read_text(encoding="utf-8"))
        data.pop("_README", None)
        self.assertNotRegex(json.dumps(data, ensure_ascii=False), "[→›]")

    def test_rows_without_image_hide_the_image_box(self):
        # 2026-11-11 オーナー指摘: 画像の無い・読み込めない行に空の白い枠を出さない
        parts = (ROOT / "components/rail/parts.tsx").read_text(encoding="utf-8")
        self.assertIn("{item.image && <RowThumb", parts)
        thumb = (ROOT / "components/rail/RowThumb.tsx").read_text(encoding="utf-8")
        self.assertIn("onError", thumb)
        self.assertIn("return null", thumb)

    def test_pages_keep_inline_offer_next_to_action_ad(self):
        # 行動欄そばの PR がある記事でも、本文の途中の商品枠を出す（以前は記事末に回して、多くの記事で消えていた）
        for path in ("app/articles/[slug]/page.tsx", "components/noir/noirArticlePage.tsx"):
            src = (ROOT / path).read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertNotIn("bottomOffer", src)
                self.assertNotIn("actionAd ? undefined : plannedInlineOffer", src)
        page = (ROOT / "app/articles/[slug]/page.tsx").read_text(encoding="utf-8")
        # 2026-11-09: 比較記事の提携先の一覧（lib/comparison.ts）の商品も、ほかの枠に重ねない
        self.assertIn("[...(actionAd?.items ?? []), ...(compareOffers?.items ?? [])].map((x) => x.item.key)", page)
        # スマホは記事の終わりに1〜3位の枠。PC は右側（記事末の「関連記事」は 2026-11-11 にやめ、本文の直後の「よく読まれている記事」にまとめた。枠の位置は変えない）
        self.assertIn('pos="ranking-end"', page)
        self.assertNotIn('aria-labelledby="related-heading"', page)
        self.assertIn('"ranking-end"', (ROOT / "scripts/aff_stats.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

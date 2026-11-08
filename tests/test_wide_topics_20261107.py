"""2026-11-07 オーナー承認「広めていいよ」（台帳 A56）。拾うテーマを広げる（交通・天気・暮らし・障害・自治体）。
事件〔犯罪〕・不祥事・芸能のゴシップは対象外のまま（2026-11-08 A23 で事故・災害は扱うことにした）。生成前の足切り（indexnow.candidate_off_focus）と検索に出す主題（indexnow.is_focus・
lib/indexing.ts）の両方で同じ判定になることを確かめる。外部への通信なし。"""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import feeds  # noqa: E402
import indexnow  # noqa: E402
import public_interest  # noqa: E402
import web_articles  # noqa: E402

# (題名, レーン, 発信元, 種類)
WIDE = [
    ("東北支社 【E6】常磐自動車道 上下線 広野IC～南相馬IC 夜間通行止めのお知らせ", "lifestyle", "e-nexco", "transport"),
    ("冬季期間の臨時列車運転に関するお知らせ 冬の九州新幹線運転日決定", "lifestyle", "jrkyushu", "transport"),
    ("2027年3月ダイヤ改正について", "lifestyle", "jrwest", "transport"),
    ("台風の接近に伴う計画運休の実施について", "lifestyle", "jrcentral", "transport"),
    ("国内線の一部便の欠航について", "lifestyle", "", "transport"),
    ("大雪に関する早期天候情報（北陸地方）", "public", "jma-press", "weather"),
    ("2027年春の花粉飛散予測", "public", "jma-press", "weather"),
    ("製品価格一部改定のお知らせ", "lifestyle", "yamazaki", "price"),
    ("2026年12月分電気料金の燃料費調整について", "lifestyle", "yonden", "price"),
    ("「うみやまむすび」運行終了のお知らせ", "lifestyle", "jrwest", "service-end"),
    ("旧アプリのサービス終了について", "tech-gadget", "", "service-end"),
    ("一部のお客さまで通信障害が発生しています", "tech-gadget", "rakuten-mobile-info", "outage"),
    ("【復旧】乗り換え手続き（MNP）が一部できない事象について", "tech-gadget", "rakuten-mobile-info", "outage"),
    ("インターネットバンキングのシステム障害のお詫び", "business", "smbc", "outage"),
    ("物価高騰対策 子育て世帯への給付金の申請受付を開始します", "public", "city-yokohama", "benefit"),
    ("2026年度技能五輪全国大会に出場する愛知県選手の出場費用を助成します", "public", "pref-aichi", "benefit"),
    ("寒くなる季節に濃厚な味わいを ラーメンにチーズ、おにぎりにバターなど 15品発売", "lifestyle", "lawson", "launch"),
    ("ファミリーマート限定で新商品を発売", "lifestyle", "", "launch"),
    ("ドラム式洗濯機の新製品を発売", "lifestyle", "", "launch"),
    # 2026-11-07 オーナー承認の追加: 食品メーカーの単品の新商品・新フレーバー、感染症の流行・鳥インフルエンザ
    ("湖池屋 「湖池屋くじ」(11月28日発売開始)", "lifestyle", "nissin", "launch"),
    ("「ピノ ぜんぶアーモンド」 11月9日（月）より全国にて数量限定発売", "lifestyle", "morinaga-milk", "launch"),
    ("ハイチュウ歯みがき粉に新フレーバー登場", "lifestyle", "morinaga", "launch"),
    ("インフルエンザの発生状況を更新しました", "public", "mhlw", "health"),
    ("感染性胃腸炎にご注意ください！ノロウイルス等による集団感染が多く発生する時期です", "public", "tokyo-metro", "health"),
    ("秋田県における野鳥の高病原性鳥インフルエンザウイルスの検出事例について", "lifestyle", "maff", "health"),
]
# 広げても扱わない（事件〔犯罪〕・不祥事・芸能のゴシップ・医療効果）。交通・天気・障害の語があっても入れない
EXCLUDED = [
    ("社員の逮捕に伴う運休のお詫び", "lifestyle", ""),
    ("当社社員による不祥事と料金の返金について", "lifestyle", ""),
    ("元社員の横領と料金の返還について", "lifestyle", ""),
    ("人気俳優が結婚を発表 新商品のCMにも出演", "lifestyle", "familymart"),
    ("社内のパワハラに関する懲戒処分について", "public", ""),
    ("この食品でインフルエンザが治る？", "lifestyle", ""),
]
# 2026-11-08 オーナー決定（台帳 A23）: 事故・災害は暮らしの安全として扱う（交通・停電・感染症の知らせ）
ACCIDENTS = [
    ("人身事故による運転見合わせについて", "lifestyle", "jrwest", "transport"),
    ("踏切事故の影響で一部列車が運休", "lifestyle", "jrkyushu", "transport"),
    ("工事現場での火災の発生について（停電）", "lifestyle", "rikuden", "outage"),
    ("インフルエンザによる死亡者数について", "public", "", "health"),
]
# 前から主題外のまま（広げた話題でもなく、お金にも暮らしにもつながらない）
STILL_OFF = [
    ("令和8年11月6日(金)午後-内閣官房長官記者会見", "public", "gov-online"),
    ("超伝導を特徴づける2つの長さを計算可能に", "science", "riken"),
    ("ちょいたしおでんの具 コーン肉団子", "lifestyle", "nipponham"),  # 発売の語が無い商品名だけの題名は入れない
]
# 広げた話題ではないが、題名がお金か暮らしにつながる（life_link）ので主題外にしない（2026-11-08 の台帳の見直し・A61 の最後の一文を外した）
ON_AXIS = [
    ("日本郵便と北海道テレビ放送による防災に関する連携協定の締結", "lifestyle", "japanpost"),
    ("障害福祉分野における人材確保に関する検討会", "public", "mhlw"),
]


def article(title, genre, channel=""):
    return {"title": title, "genreSlug": genre, "channelSlug": channel, "tags": []}


class WideTopicsTest(unittest.TestCase):
    def test_new_categories_pass_both_gates(self):
        for title, lane, src, cat in WIDE:
            with self.subTest(title=title):
                self.assertEqual(public_interest.wide_category(title, src), cat)
                self.assertFalse(indexnow.candidate_off_focus(lane, title, "", src))
                self.assertTrue(indexnow.is_focus(article(title, lane, src)))

    def test_crime_accident_celebrity_scandal_stay_out(self):
        for title, lane, src in EXCLUDED:
            with self.subTest(title=title):
                self.assertIsNone(public_interest.wide_category(title, src))
                # 料金・値上げの語（前からの読者像の話題）があっても、事件・事故・不祥事は生成前の足切りで落ちる
                dropped = web_articles.broad_prefilter({"title": title, "summary": "", "section": lane, "source_slug": src})
                self.assertIsNotNone(dropped, title)

    def test_accidents_are_covered(self):
        for title, lane, src, cat in ACCIDENTS:
            with self.subTest(title=title):
                self.assertEqual(public_interest.wide_category(title, src), cat)
                self.assertIsNone(web_articles.broad_prefilter({"title": title, "summary": "", "section": lane, "source_slug": src}))

    def test_life_linked_titles_are_on_axis(self):
        for title, lane, src in ON_AXIS:
            with self.subTest(title=title):
                self.assertFalse(indexnow.candidate_off_focus(lane, title, "", src))
                self.assertIsNone(indexnow.publish_block_reason({**article(title, lane, src), "body": "あ" * 900}))

    def test_unrelated_topics_still_off_focus(self):
        for title, lane, src in STILL_OFF:
            with self.subTest(title=title):
                self.assertIsNone(public_interest.wide_category(title, src))
                self.assertTrue(indexnow.candidate_off_focus(lane, title, "", src))
                self.assertFalse(indexnow.is_focus(article(title, lane, src)))

    def test_hard_exclude_still_drops_before_topic_check(self):
        # 2026-11-08 オーナー決定（台帳 A23）: 事件（犯罪）は今までどおり扱わない。事故・災害は暮らしの安全として扱う
        item = {"title": "駅で強盗事件 男を逮捕", "summary": "", "section": "lifestyle", "source_slug": "jrwest"}
        self.assertIn("扱わない話題", web_articles.broad_prefilter(item) or "")
        accident = {"title": "列車事故で負傷者 運転見合わせ続く", "summary": "", "section": "lifestyle", "source_slug": "jrwest"}
        self.assertNotIn("扱わない話題", web_articles.broad_prefilter(accident) or "")
        self.assertEqual(public_interest.wide_category(accident["title"], "jrwest"), "transport")

    def test_launch_needs_a_store_device_or_food_maker(self):
        # 発売の語だけでは入れない（コンビニ・外食・家電・スマホ・食品の語か、その会社の公式の発表に限る）
        self.assertIsNone(public_interest.wide_category("新フレーバー登場", ""))
        self.assertIsNone(public_interest.wide_category("新作フィギュアを発売", "cyberagent"))
        self.assertEqual(public_interest.wide_category("新フレーバー登場", "nipponham"), "launch")
        self.assertEqual(public_interest.wide_category("ローソン限定 無印良品「ボディフレグランスミスト」を発売", ""), "launch")

    def test_cosmetics_and_health_foods_are_not_launches(self):
        # 化粧品・健康食品・サプリは発売の話題に入れない（2026-11-07 11:30 オーナー決定。薬機法・AdSense の心配）
        for title, src in (("エイジングスキンケアブランド「F.A.G.E.（エファージュ）」2アイテム新発売", "suntory"),
                           ("サントリーの薬膳ブランド「薬膳好日」から新商品を発売", "suntory"),
                           ("「ビヒダス Wのビフィズス菌 腸からRe：Body」新発売", "morinaga-milk"),
                           ("機能性表示食品の新しいサプリメントを発売", "kirin"),
                           ("ファミリーマート限定のコスメを発売", "familymart")):
            with self.subTest(title=title):
                self.assertIsNone(public_interest.wide_category(title, src))
        self.assertEqual(public_interest.wide_category("「ピノ ぜんぶアーモンド」数量限定発売", "morinaga-milk"), "launch")

    def test_alcohol_launch_needs_the_note(self):
        rec = {"title": "『アサヒスーパードライ ドライクリスタル 生ジョッキ缶』 11月10日数量限定発売", "tags": [],
               "body": "## 発売日と価格\n11月10日から全国で数量限定で発売する。"}
        self.assertEqual(public_interest.wide_category(rec["title"], "asahi"), "launch")
        self.assertTrue(public_interest.is_alcohol(rec))
        self.assertTrue(any("注意書き" in p for p in public_interest.sensitive_problems(rec)))
        notes = public_interest.autofix(rec)
        self.assertTrue(notes)
        self.assertIn(public_interest.ALCOHOL_NOTE, rec["body"])
        self.assertEqual(public_interest.sensitive_problems(rec), [])
        self.assertEqual(public_interest.autofix(rec), [])  # 2回目は何もしない
        # 飲むことをすすめる言い方は不合格
        pushy = {**rec, "body": rec["body"] + "\nたくさん飲もう。"}
        self.assertTrue(any("すすめない" in p for p in public_interest.sensitive_problems(pushy)))
        # 作るときの指示にも入る
        self.assertIn(public_interest.ALCOHOL_NOTE, public_interest.alcohol_prompt_note(rec["title"]))

    def test_non_alcohol_and_other_products_need_no_note(self):
        for title in ("「のんある酒場 グレフルサワー ノンアルコール」新発売", "キリン 氷ゼロ スパークリング（ノンアルコール）新発売",
                      "新しいエンジンを搭載した車を発売", "サワークリームオニオン味のポテトチップスを発売", "ローソン 15品発売"):
            with self.subTest(title=title):
                self.assertFalse(public_interest.is_alcohol({"title": title}))
                self.assertEqual(public_interest.alcohol_problems({"title": title, "body": "本文"}), [])

    def test_election_only_in_summary_does_not_drop(self):
        item = {"title": "ガソリン補助金が縮小開始へ～価格上昇はどこまで？", "summary": "選挙を前に補助の扱いが議論になった。",
                "section": "business", "source_slug": "nli-research"}
        self.assertNotIn("扱わない話題", web_articles.broad_prefilter(item) or "")
        for title in ("衆議院議員選挙の候補者が決定", "政党の公約に電気代の補助"):
            dropped = web_articles.broad_prefilter({**item, "title": title, "summary": ""})
            self.assertIn("扱わない話題", dropped or "", title)

    def test_outage_notice_is_not_low_value(self):
        base = {"summary": "", "section": "tech-gadget", "source_slug": "rakuten-mobile-info"}
        self.assertIsNone(web_articles.broad_prefilter({**base, "title": "一部地域でのシステム障害の発生について（復旧済み）"}))
        self.assertIsNone(web_articles.broad_prefilter({**base, "title": "通信がつながりにくい事象のお詫び"}))
        # 定期のメンテナンス・訂正は今までどおり見送る
        self.assertIn("価値の薄い", web_articles.broad_prefilter({**base, "title": "システムメンテナンスのお知らせ（11月10日）"}) or "")
        self.assertIn("価値の薄い", web_articles.broad_prefilter({**base, "title": "【訂正とお詫び】料金プランの案内について"}) or "")

    def test_recall_site_plain_kaishu(self):
        self.assertEqual(public_interest.category("保健衛生品 興研「防毒マスクR-5-08型、ほか3商品」 - 回収"), "recall")

    def test_rules_exported_for_site(self):
        rules = json.loads((ROOT / "lib" / "index-rules.json").read_text("utf-8"))
        self.assertEqual([t["name"] for t in rules["wideTopics"]], list(public_interest.WIDE_TOPIC_RES))
        self.assertFalse(indexnow.rules_drift())
        ts = (ROOT / "lib" / "indexing.ts").read_text("utf-8")
        self.assertIn("wideCategory", ts)
        self.assertIn("rules.wideExclude", ts)
        # JavaScript でも読める正規表現（Python だけの書き方を使わない）
        for pat in [t["source"] for t in rules["wideTopics"]] + [rules[k]["source"] for k in ("wideExclude", "wideNotOutage", "launchTopic", "launchContext")]:
            self.assertNotRegex(pat, r"\(\?P<|\(\?<!|\\A|\\Z")

    def test_new_sources_registered(self):
        by_slug = {f["slug"]: f for f in feeds.BROAD_FEEDS}
        for slug in ("jrkyushu", "energia", "yonden", "rikuden", "smbc", "yamazaki", "city-yokohama",
                     "asahi", "morinaga-milk", "megmilk", "fujiya", "maff-tori", "jihs"):
            with self.subTest(slug=slug):
                f = by_slug[slug]
                self.assertIn(f["kind"], ("gov", "company"))
                re.compile(f.get("include_re") or "")
                self.assertFalse(public_interest.is_press_url(f["url"]))

    def test_ledger_row(self):
        rules = (ROOT / "docs" / "owner_rules.md").read_text("utf-8")
        row = next((line for line in rules.splitlines() if line.startswith("| A56 |")), "")
        self.assertIn("拾うテーマを広げる", row)
        self.assertIn("事件・事故・芸能・不祥事は対象外のまま", row)


if __name__ == "__main__":
    unittest.main()

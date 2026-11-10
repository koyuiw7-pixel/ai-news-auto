"""検索結果の題名 searchTitle（2026-11-10 オーナー承認・台帳 A29 の変更）の決まりを、全記事で確かめる。

- <title> だけに使う題名。見出し（h1）・og:title・SNS・画像は title のまま（lib/headline.ts の searchResultTitle）
- 記事の本文にある事実だけ（rewrite_titles.check_title〔reviewed〕と check_seo を通る）・32字以内・「｜」なし・「ざっくり」なし
- 最初に入れたのは見本の10本（out/strategy_20261110/title_samples_ja.md）。2026-11-10 20:45 オーナー「広げていきたい」で
  暮らしとお金の80本に1本ずつ手で足した（第2弾。out/strategy_20261110/search_titles_wave2_ja.md）
- 新しい暮らしとお金の記事には scripts/main.py の write_article が案を作り、決まりを通ったときだけ付ける（scripts/search_title.py）
ネットワーク・LLM は使わない。
"""
import json
import sys
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import article_style  # noqa: E402
import rewrite_titles  # noqa: E402
import search_title  # noqa: E402

MAX = 32  # lib/headline.ts の SEARCH_TITLE_MAX と同じ
SAMPLES = {
    "child-allowance-december-payment": "児童手当の12月はいくら？　2か月分の振込額を人数別に",
    "pension-child-allowance-payment-calendar": "年金の支払日はいつ？　偶数月15日、12月は10月・11月分",
    "furusato-nozei-deadline-2026": "ふるさと納税の期限は12月31日　ワンストップ特例は1月10日",
    "electricity-bill-nov-2026-subsidy-ends": "電気代の値引きはいつ戻る？　11月分から終了、再開は1月分",
    "nitori-member-data-leak-2026": "ニトリの個人情報が流出の恐れ、対象は？　最大3,762万件",
    "docomo-data-leak-what-to-do": "ドコモ情報流出、対象かはまだ調べられない　今やる確認",
    "yokohama-rubber-tire-recall-lt151r": "横浜ゴムのタイヤリコール　LT151Rなど対象の見分け方",
    "zaishoku-rourei-nenkin-65man-2026": "在職老齢年金は2026年4月から月65万円　減る額の出し方",
    "nencho-2026-changes": "年末調整2026の変更点　基礎控除104万円、扶養は62万円以下",
    "pension-support-benefit-old-age-eligibility": "年金生活者支援給付金の対象は？　はがきが届かないとき",
}


def _with_search_title() -> list[dict]:
    out = []
    for path in sorted((ROOT / "content" / "articles").glob("*.json")):
        try:
            record = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(record, dict) and "searchTitle" in record:
            out.append(record)
    return out


class SearchTitleRulesTest(unittest.TestCase):
    def test_every_search_title_follows_the_rules(self):
        bad = []
        for record in _with_search_title():
            value = record["searchTitle"]
            problems = []
            if not isinstance(value, str) or not value.strip():
                problems.append("空")
            else:
                if len(value) > MAX:
                    problems.append(f"{len(value)}字（{MAX}字まで）")
                if "｜" in value or "|" in value:
                    problems.append("縦棒")
                if article_style.ZAKKURI_RE.search(value):
                    problems.append("ざっくり")
                problems += rewrite_titles.check_title(record, value, reviewed=True)
                problems += rewrite_titles.check_seo(record, value)
            if problems:
                bad.append((record.get("slug"), value, problems))
        self.assertEqual(bad, [])

    def test_owner_approved_samples_are_applied_exactly(self):
        for slug, title in SAMPLES.items():
            record = json.loads((ROOT / "content" / "articles" / f"{slug}.json").read_text("utf-8"))
            self.assertEqual(record.get("searchTitle"), title, slug)
            # 見出し（title）はそのまま（別の題名）
            self.assertNotEqual(record.get("title"), title, slug)

    def test_search_titles_are_distinct(self):
        # 2026-11-10 20:45 オーナー「広げていきたい」で本数の上限（試しの30本）は外した。同じ題名を2本の記事に付けない
        values = [r["searchTitle"] for r in _with_search_title()]
        self.assertEqual(len(values), len(set(values)))
        self.assertGreaterEqual(len(values), 90)

    def test_pipeline_rules_are_the_same(self):
        # 自動で付ける経路（scripts/search_title.py）も、このテストと同じ決まりで確かめる
        self.assertEqual(search_title.MAX, MAX)
        record = json.loads((ROOT / "content" / "articles" / "child-allowance-december-payment.json").read_text("utf-8"))
        self.assertEqual(search_title.problems(record, record["searchTitle"]), [])
        for bad in ("児童手当｜12月はいくら？", "あ" * 33, "", record["title"], "衝撃！児童手当の12月はいくら？"):
            self.assertTrue(search_title.problems(record, bad), bad)


class PipelineTest(unittest.TestCase):
    """新しい記事に自動で付ける経路（scripts/search_title.py・scripts/main.py の write_article）"""

    RECORD = {
        "slug": "child-allowance-sample", "genre": "社会・行政",
        "title": "12月の児童手当は10月分・11月分の2か月分",
        "description": "児童手当は偶数月に前月までの2か月分が支払われます。12月は10月分と11月分です。",
        "lede": "児童手当の12月の支払いは10月分と11月分の2か月分です。",
        "highlights": ["12月は10月分と11月分の2か月分が支払われる"],
        "body": "児童手当は偶数月に前月までの2か月分を支払います。12月の振込額は10月分と11月分です。",
    }

    def test_targets_are_life_and_money_only(self):
        self.assertTrue(search_title.is_target(self.RECORD))
        self.assertTrue(search_title.is_target({"genre": "ビジネス・経済", "title": "ロータス「エリーゼ」611台をリコール"}))
        self.assertFalse(search_title.is_target({"genre": "ビジネス・経済", "title": "トヨタの中間決算、営業利益2兆1,911億円"}))
        self.assertFalse(search_title.is_target({"genre": "AI・テクノロジー", "title": "Gemini、ファイルを直接編集"}))
        self.assertFalse(search_title.is_target({"genre": "社会・行政", "title": "児童手当の新しい案内", "breaking": True}))

    def test_good_proposal_is_attached(self):
        record = dict(self.RECORD)
        with mock.patch.object(search_title.llm, "generate_json", return_value=({"search_title": "児童手当の12月はいくら？　10月分・11月分の2か月分"}, "m")), \
                mock.patch.object(search_title.rewrite_titles, "llm_grounding_problems", return_value=[]):
            note = search_title.attach(record)
        self.assertEqual(record.get("searchTitle"), "児童手当の12月はいくら？　10月分・11月分の2か月分", note)

    def test_bad_proposal_or_error_leaves_it_empty_and_never_raises(self):
        for side in ({"search_title": "児童手当｜衝撃の12月！"}, {"search_title": "児童手当の12月は5万円"}):
            record = dict(self.RECORD)
            with mock.patch.object(search_title.llm, "generate_json", return_value=(side, "m")):
                search_title.attach(record)
            self.assertNotIn("searchTitle", record)
        record = dict(self.RECORD)
        with mock.patch.object(search_title.llm, "generate_json", side_effect=RuntimeError("down")):
            self.assertIn("作れなかった", search_title.attach(record))
        self.assertNotIn("searchTitle", record)
        # 事実の確認に落ちたら付けない
        record = dict(self.RECORD)
        with mock.patch.object(search_title.llm, "generate_json", return_value=({"search_title": "児童手当の12月はいくら？　10月分・11月分の2か月分"}, "m")), \
                mock.patch.object(search_title.rewrite_titles, "llm_grounding_problems", return_value=["記事に無い主張"]):
            search_title.attach(record)
        self.assertNotIn("searchTitle", record)

    def test_stale_value_is_removed(self):
        record = {**self.RECORD, "searchTitle": "児童手当の12月は5万円　振込はいつ？"}
        self.assertTrue(search_title.revalidate(record))
        self.assertNotIn("searchTitle", record)

    def test_write_article_attaches_only_to_new_files(self):
        import main as m  # noqa: PLC0415
        src = (ROOT / "scripts" / "main.py").read_text("utf-8")
        body = src[src.index("def write_article"):src.index("def write_sample")]
        self.assertIn("search_title.revalidate(record)", body)
        self.assertIn("not path.exists() and (note := search_title.attach(record))", body)
        self.assertTrue(callable(m.write_article))

if __name__ == "__main__":
    unittest.main()

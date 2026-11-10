"""検索結果の題名 searchTitle（2026-11-10 オーナー承認・台帳 A29 の変更）の決まりを、全記事で確かめる。

- <title> だけに使う題名。見出し（h1）・og:title・SNS・画像は title のまま（lib/headline.ts の searchResultTitle）
- 記事の本文にある事実だけ（rewrite_titles.check_title〔reviewed〕と check_seo を通る）・32字以内・「｜」なし・「ざっくり」なし
- 最初に入れるのは見本の10本（out/strategy_20261110/title_samples_ja.md）。まとめての書き直しはしない
ネットワーク・LLM は使わない。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import article_style  # noqa: E402
import rewrite_titles  # noqa: E402

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

    def test_no_mass_rewrite(self):
        # まとめての書き直しはしない（2026-11-10 は見本の10本だけ。増やすときは1本ずつ手で、オーナーの試しの30本まで）
        self.assertLessEqual(len(_with_search_title()), 30)


if __name__ == "__main__":
    unittest.main()

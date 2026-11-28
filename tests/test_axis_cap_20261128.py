"""2026-11-28 オーナー承認（台帳 A79）: 軸の記事で中身の門（scripts/your_number.py の a〜d）を全部通ったものは1日30本に数えない。
軸の外は30本のまま。30本のあとに出すのは安全・お金の急ぎの話と axisPass の記事だけ。門に落ちた記事は出さない。
1日の公開の合計の安全上限 AXIS_DAILY_CEILING（既定 80）。外部への通信なし。"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import pacing  # noqa: E402
import web_articles as w  # noqa: E402

NOW = datetime(2026, 11, 28, 12, tzinfo=pacing.JST)
AT = NOW.isoformat()

PASS_BODY = """## 対象かどうかの確かめ方

| 項目 | 内容 |
|---|---|
| 商品名 | テストのクッキー |
| 賞味期限 | 2027年1月10日 |

対象の商品は賞味期限で確かめられます（[消費者庁のリコール情報](https://www.recall.caa.go.jp/result/detail.php?rcl=00000036299)）。

## 窓口

回収は11月24日から受け付けています。問い合わせはテスト食品のお客様相談室（電話 0120-000-000）へ。
"""


def record(title="テスト食品「テストのクッキー」を自主回収　賞味期限で対象を確認", body=PASS_BODY):
    return {"title": title, "seoTitle": title, "body": body, "genreSlug": "lifestyle",
            "sourceUrl": "https://www.recall.caa.go.jp/result/detail.php?rcl=00000036299", "sourceName": "消費者庁 リコール情報サイト",
            "sources": [{"url": "https://www.recall.caa.go.jp/result/detail.php?rcl=00000036299", "title": "消費者庁"}]}


class AxisCapTest(unittest.TestCase):
    def _state(self, folder: Path, entries: list[dict]) -> dict:
        state = {"processed_web": {}}
        for n, entry in enumerate(entries):
            slug = f"s{n}"
            (folder / f"{slug}.json").write_text(json.dumps({"title": "x"}), "utf-8")
            state["processed_web"][slug] = {"slug": slug, "at": AT, **entry}
        return state

    def test_axis_pass_is_cap_exempt_but_counted_in_total(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            state = self._state(folder, [{"mix": "money"}, {"axisPass": True}, {"axisPass": True}, {"writer": "muse"}, {"safetyLane": True}])
            self.assertEqual(pacing.live_today(state, NOW, folder), 1)
            self.assertEqual(pacing.total_today(state, NOW, folder), 4)  # Muse は数えない

    def test_daily_ceiling(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            state = self._state(folder, [{"axisPass": True}] * 3)
            with patch.dict(os.environ, {"AXIS_DAILY_CEILING": "3"}):
                self.assertEqual(pacing.axis_ceiling(), 3)
                self.assertFalse(pacing.axis_room(state, NOW, folder))
            with patch.dict(os.environ, {"AXIS_DAILY_CEILING": ""}):
                self.assertEqual(pacing.axis_ceiling(), 80)
                self.assertTrue(pacing.axis_room(state, NOW, folder))

    def test_axis_pass_needs_all_four_elements(self):
        self.assertTrue(w.axis_pass(record()))
        self.assertFalse(w.axis_pass(record(body="テスト食品がクッキーを回収します。")))  # 表・窓口・日付・公式の URL が無い
        self.assertFalse(w.axis_pass(record(title="新社長の就任について", body=PASS_BODY)))  # 軸の外

    def test_axis_item(self):
        self.assertTrue(w.axis_item({"title": "児童手当の支給日が変わります", "summary": "", "section": "public"}))
        self.assertTrue(w.axis_item({"title": "電気ケトルの自主回収", "summary": "", "section": "lifestyle"}))
        self.assertFalse(w.axis_item({"title": "新社長の就任について", "summary": "", "section": "business"}))

    def test_wiring(self):
        web = (ROOT / "scripts" / "web_articles.py").read_text("utf-8")
        self.assertIn('**({"axisPass": True} if passed else {})', web)
        self.assertEqual(web.count("if hold := over_cap_hold("), 2)  # ふつうの記事と話題のレーンの報道の記事
        self.assertIn("axis_items = [i for i in broad_items if i not in safety_items and axis_item(i)]", web)
        self.assertIn('if created["trend"] >= trend_routine_slots and trend_lane.axis_rank(q) > 0:', web)
        self.assertIn('if entry.get("axisPass"):', (ROOT / "scripts" / "pacing.py").read_text("utf-8"))
        self.assertIn("AXIS_DAILY_CEILING: ${{ vars.AXIS_DAILY_CEILING }}", (ROOT / ".github" / "workflows" / "auto_run.yml").read_text("utf-8"))
        ledger = (ROOT / "docs" / "owner_rules.md").read_text("utf-8")
        self.assertIn("| A79 | **2026-11-28 オーナー承認", ledger)
        # 門に落ちた記事は出さない（止める切り替えは使わない）
        self.assertNotIn("AXIS_CONTENT_GATE: '0'", (ROOT / ".github" / "workflows" / "auto_run.yml").read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()

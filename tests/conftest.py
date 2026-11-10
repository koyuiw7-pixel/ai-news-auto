"""テスト全体の下ごしらえ。

2026-11-10 オーナー決定「今後は全て手投稿にしよう」で、本番の scripts/sns_plan.json の auto_post（Threads・X・Bluesky・Facebook への
記事の自動投稿のスイッチ）は false（止める）になった。今までのテストは「自動投稿が動いているときの決まり」（枠・門番・文面）を確かめるもの
なので、そのまま auto_post を true とみなして動かす（スイッチを戻したときに同じ決まりで動くことを確かめ続ける）。
止めている状態そのものは tests/test_auto_post_off_20261110.py が本物の設定（AUTO_POST_REAL）で確かめる。
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sns_plan  # noqa: E402

_REAL_PLAN = sns_plan.plan
AUTO_POST_REAL = {"on": False}  # True の間は本物の auto_post（本番の設定）を使う


def _plan_with_auto_post():
    data = _REAL_PLAN()
    if AUTO_POST_REAL["on"]:
        return data
    data = copy.copy(data)
    data["auto_post"] = {**(data.get("auto_post") or {}), "threads": True, "x": True, "bluesky": True, "facebook": True}
    return data


sns_plan.plan = _plan_with_auto_post

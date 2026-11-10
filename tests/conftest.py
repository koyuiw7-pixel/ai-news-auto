"""テスト全体の下ごしらえ。

2026-11-10 オーナー決定「今後は全て手投稿にしよう」で、本番の scripts/sns_plan.json の auto_post（Threads・X・Bluesky・Facebook・Instagram への
記事の自動投稿のスイッチ）は false（止める）になった。今までのテストは「自動投稿が動いているときの決まり」（枠・門番・文面）を確かめるもの
なので、そのまま auto_post を true とみなして動かす（スイッチを戻したときに同じ決まりで動くことを確かめ続ける）。
止めている状態そのものは tests/test_auto_post_off_20261110.py が本物の設定（AUTO_POST_REAL）で確かめる。

pytest はこのファイルを自動で読むが、python -m unittest（owner_rules.yml・sns_rules.yml など）は読まない。
自動投稿の決まりを確かめるテストのファイルは、頭で `import conftest` してこの下ごしらえを読む（2回読まれても包むのは1回だけ）。
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sns_plan  # noqa: E402

# 別の名前で2回読まれても（pytest の conftest と unittest の import conftest）、本物の plan と切り替えは1つだけにする
_REAL_PLAN = getattr(sns_plan.plan, "_real_plan", sns_plan.plan)
AUTO_POST_REAL = getattr(sns_plan.plan, "_auto_post_real", {"on": False})  # True の間は本物の auto_post（本番の設定）を使う


def _plan_with_auto_post():
    data = _REAL_PLAN()
    if AUTO_POST_REAL["on"]:
        return data
    data = copy.copy(data)
    data["auto_post"] = {**(data.get("auto_post") or {}), "threads": True, "x": True, "bluesky": True, "facebook": True, "instagram": True}
    return data


_plan_with_auto_post._real_plan = _REAL_PLAN
_plan_with_auto_post._auto_post_real = AUTO_POST_REAL
sns_plan.plan = _plan_with_auto_post

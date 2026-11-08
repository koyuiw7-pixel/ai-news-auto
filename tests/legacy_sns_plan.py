"""2026-11-08 より前の SNS の枠（Threads 4枠・上限5、Bluesky・X・Facebook 3枠・上限3）で動かすテスト用の差し替え。
2026-11-08 オーナー承認（台帳 S47）で本番は1日15本・およそ1時間おきの枠になった。枠の選び方・数え方そのもののテストは、
数の少ない前の枠のままでも意味があるので、この差し替えで前の数を使う（今の数は tests/test_sns_volume_20261108.py）。"""
import copy
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sns_plan  # noqa: E402

_REAL = sns_plan.plan
LEGACY = {
    "slots_jst": ["07:15", "12:15", "18:45", "20:30"], "daily_cap": 5, "per_day_max": 5,
    "bluesky": {"slots_jst": ["07:30", "13:00", "21:00"], "daily_cap": 3, "window_end": "23:00"},
    "x": {"slots_jst": ["07:30", "12:30", "21:00"], "daily_cap": 3, "window_end": "23:00"},
    "facebook": {"slots_jst": ["07:30", "12:30", "20:00"], "daily_cap": 3, "window_end": "23:00"},
}


def legacy_plan() -> dict:
    data = copy.deepcopy(_REAL())
    for key, value in LEGACY.items():
        if isinstance(value, dict):
            data[key] = {**(data.get(key) or {}), **value}
        else:
            data[key] = value
    return data


_patches: list = []


def start() -> None:
    """setUpModule から呼ぶ"""
    _patches.append(patch.object(sns_plan, "plan", legacy_plan))
    _patches.append(patch.dict("os.environ", {"SNS_PER_DAY": ""}))
    if "threads_post" in sys.modules:
        tp = sys.modules["threads_post"]
        old = [(7, 15), (12, 15), (18, 45), (20, 30)]
        _patches.extend([patch.object(tp, "SLOTS_JST", old), patch.object(tp, "SLOT_PRIORITY", old), patch.object(tp, "SNS_PER_DAY", 4)])
    if "bluesky_post" in sys.modules:
        _patches.append(patch.object(sys.modules["bluesky_post"], "PER_DAY", 3))
    for p in _patches:
        p.start()


def stop() -> None:
    """tearDownModule から呼ぶ"""
    while _patches:
        _patches.pop().stop()

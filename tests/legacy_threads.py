"""以前の Threads の書き方（台帳 S46 より前）の決まりを確かめるテスト用。
2026-11-07 夜からの Threads の記事の投稿は新しい書き方（sns_rules.reader_kind・threads_reader）で、承認までは止め（threads_gate.style_hold）。
リンクの位置・間隔・動画などの仕組みそのものを確かめる古いテストだけ、この2つを外して動かす（本番の経路は外さない）"""
from unittest.mock import patch

import sns_rules
import threads_gate

_PATCHES = [
    patch.object(sns_rules, "reader_kind", lambda platform, kind, article: kind),
    patch.object(threads_gate, "style_hold", lambda *a, **k: ""),
]


def start() -> None:
    for p in _PATCHES:
        p.start()


def stop() -> None:
    for p in _PATCHES:
        p.stop()

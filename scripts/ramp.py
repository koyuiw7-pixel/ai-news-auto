"""
本数を週ごとに少しずつ増やす（急に増やすと量産サイトと見なされやすく、SNSは凍結されやすいため）。

GitHub の変数（WEB_DAILY_CAP_BRAKE / SNS_PER_DAY）が設定されていればそちらを優先し、
無ければ下の予定表から今日の値を出す。予定表の日付は日本時間。
Search Console で評価が下がる兆しがあれば、変数 WEB_DAILY_CAP_BRAKE を設定して止める（予定表より優先される）。
2026-11-06 オーナー決定（台帳 A47）: 記事を1日100本へ。増やす分は検索される話題（使い方・料金・いつから・比較・手続き・対策）と
国内のニュース。海外 AI は増やさない（scripts/web_articles.py の FOREIGN_AI_DAILY_CAP）。品質の門はそのまま。
以前の変数 WEB_DAILY_CAP（80 のまま残っている）は読まない（100 の決定を古い値で抑えないため）。
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

# (この日から, 公式ブログ・プレスリリース・話題の1日の上限)。動画からの記事（最大8本/日）は別
# 2026-11-06 オーナー決定（台帳 A47）: この日から100本/日（目標は 11/26 に日本からの訪問 2,500/日）。それより上には増やさない
OWNER_DAILY_TARGET = 100
WEB_RAMP = [("2026-10-27", 45), ("2026-11-03", 95), ("2026-11-06", OWNER_DAILY_TARGET)]
# (この日から, SNS の1日の投稿本数)
SNS_RAMP = [("2026-10-27", 7), ("2026-11-03", 8), ("2026-11-10", 9), ("2026-11-17", 10)]


def pick(table: list[tuple[str, int]], today: str) -> int:
    value = table[0][1]
    for start, number in table:
        if today >= start:
            value = number
    return value


# AdSense 再審査のあいだは量より質（2026-11-03 オーナー決定）で40本に抑えていた。
# 2026-11-06 オーナー決定（台帳 A47）で 11/6 から100本に上げる（品質の門はそのまま）ので、40本の期間は 11/5 で終わり
REVIEW_PERIOD = ("2026-11-03", "2026-11-06", 40)


def review_cap(web: int, today: str) -> int:
    start, until, cap = REVIEW_PERIOD
    return min(web, cap) if start <= today < until else web


def broad_per_run(web: int) -> int:
    """幅広い話題（国内のニュース）の1回あたりの本数。AI のレーンは1回1本のまま（海外 AI は増やさない）。
    実際に回るのは1日50回ほど（1回が20分を超えると次は待つ）。100本/日なら AI と大きなニュースを除いた約75本を
    国内のレーンで作るので1回3本（作れる本数は pacing の配分と1日の上限で止まる）"""
    if web <= 45:
        return 1
    if web < OWNER_DAILY_TARGET:
        return 2
    return 3


def main() -> None:
    today = datetime.now(JST).strftime("%Y-%m-%d")
    web = str(review_cap(int(os.environ.get("WEB_DAILY_CAP_OVERRIDE") or pick(WEB_RAMP, today)), today))
    sns = os.environ.get("SNS_PER_DAY_OVERRIDE") or str(pick(SNS_RAMP, today))
    out = os.environ.get("GITHUB_OUTPUT")
    # 20分ごと（1日72回）に出すので、上限が大きい日は1回あたりの本数も増やす
    broad = os.environ.get("BROAD_MAX_PER_RUN_OVERRIDE") or str(broad_per_run(int(web)))
    lines = f"web_daily_cap={web}\nsns_per_day={sns}\nbroad_per_run={broad}\n"
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(lines)
    print(f"[ramp] {today}: 記事の上限 {web}本/日（動画は別）・SNS {sns}本/日")


if __name__ == "__main__":
    main()

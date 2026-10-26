"""
本数を週ごとに少しずつ増やす（急に増やすと量産サイトと見なされやすく、SNSは凍結されやすいため）。

GitHub の変数（WEB_DAILY_CAP / SNS_PER_DAY）が設定されていればそちらを優先し、
無ければ下の予定表から今日の値を出す。予定表の日付は日本時間。
Search Console で評価が下がる兆しがあれば、変数を設定して止める（予定表より優先される）。
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

# (この日から, 公式ブログ・プレスリリース・話題の1日の上限)。動画からの記事（最大8本/日）は別
WEB_RAMP = [("2026-10-27", 45), ("2026-11-03", 95), ("2026-11-10", 145), ("2026-11-17", 195), ("2026-11-24", 295)]
# (この日から, SNS の1日の投稿本数)
SNS_RAMP = [("2026-10-27", 7), ("2026-11-03", 8), ("2026-11-10", 9), ("2026-11-17", 10)]


def pick(table: list[tuple[str, int]], today: str) -> int:
    value = table[0][1]
    for start, number in table:
        if today >= start:
            value = number
    return value


def main() -> None:
    today = datetime.now(JST).strftime("%Y-%m-%d")
    web = os.environ.get("WEB_DAILY_CAP_OVERRIDE") or str(pick(WEB_RAMP, today))
    sns = os.environ.get("SNS_PER_DAY_OVERRIDE") or str(pick(SNS_RAMP, today))
    out = os.environ.get("GITHUB_OUTPUT")
    # 20分ごと（1日72回）に出すので、上限が大きい週は1回あたりの本数も増やす
    broad = os.environ.get("BROAD_MAX_PER_RUN_OVERRIDE") or ("1" if int(web) <= 145 else "2")
    lines = f"web_daily_cap={web}\nsns_per_day={sns}\nbroad_per_run={broad}\n"
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(lines)
    print(f"[ramp] {today}: 記事の上限 {web}本/日（動画は別）・SNS {sns}本/日")


if __name__ == "__main__":
    main()

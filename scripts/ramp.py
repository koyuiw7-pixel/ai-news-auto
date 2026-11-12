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
# 2026-11-09 オーナー「目標を妨げる可能性のあるルールは消そう」「達成してもそれ以上を目指す」:
# 100本は最低ライン。上限は 200 に広げる（品質の門はそのまま）
WEB_CEILING = 200
WEB_RAMP = [("2026-10-27", 45), ("2026-11-03", 95), ("2026-11-06", OWNER_DAILY_TARGET), ("2026-11-09", WEB_CEILING)]
# (この日から, SNS の1日の投稿本数)
# 2026-11-08 オーナー承認（台帳 S47）: 15本/日（Threads・X・Facebook・Bluesky のそれぞれ。変数 SNS_PER_DAY も15）
SNS_RAMP = [("2026-10-27", 7), ("2026-11-03", 8), ("2026-11-08", 15)]


def pick(table: list[tuple[str, int]], today: str) -> int:
    value = table[0][1]
    for start, number in table:
        if today >= start:
            value = number
    return value


# AdSense 再審査のあいだは量より質（2026-11-03 オーナー決定）で40本に抑えていた。
# 2026-11-06 オーナー決定（台帳 A47）で 11/6 から100本に上げる（品質の門はそのまま）ので、40本の期間は 11/5 で終わり
REVIEW_PERIOD = ("2026-11-03", "2026-11-06", 40)


# 2026-11-12 AdSense の2回目の不承認（有用性の低いコンテンツ）を受けたオーナー決定「両方やっていいよ。ただ量を超えることができるレベルの最高の記事にする」:
# 申し込み直し（11/26ごろ）までは、自動のニュース記事を1日30本までにし、暮らしとお金の記事だけにする（海外の AI の発表の自動の言い換えは止める）。
# 速報・大きなニュースのレーンはこの上限の外（台帳 S41）。Muse の記事は自動の本数に食われないよう別の上限（MUSE_DAILY_CAP）
ADSENSE_REVIEW = ("2026-11-12", "2026-11-27", 30)
MUSE_DAILY_CAP = 200


def in_adsense_review(today: str) -> bool:
    start, until, _ = ADSENSE_REVIEW
    return start <= today < until


def review_cap(web: int, today: str) -> int:
    start, until, cap = REVIEW_PERIOD
    web = min(web, cap) if start <= today < until else web
    if in_adsense_review(today):
        web = min(web, ADSENSE_REVIEW[2])
    return web


def broad_per_run(web: int) -> int:
    """幅広い話題（国内のニュース・暮らしとお金）の1回あたりの本数。
    2026-11-09 オーナー「100本/日は必須」: 実際に回るのは日中1時間に3回ほど（6〜24時で約54回）。
    11/9 の昼は候補が 18〜21 件あるのに1回2本で止まり、14時で23本しか出ていなかった。100本/日なら1回4本
    （遅れているときは scripts/pacing.py の needed_per_run でさらに増やす。1日の上限・時刻の配分では止まる）"""
    if web <= 45:
        return 1
    if web < 80:
        return 2
    if web < 100:
        return 3
    return 4


def ai_per_run(web: int) -> int:
    """AI のレーン（公式ブログ）の1回あたりの本数。海外の AI の発表は1日の上限（web_articles.FOREIGN_AI_DAILY_CAP・台帳 A47）で止まる。
    国内の企業の AI の発表・使い方は数えないので、1回2本まで（100本/日のとき）"""
    return 2 if web >= 80 else 1


# 2026-11-08 オーナー決定（台帳 A58）: 100本へは段階を踏んで上げる。40 → 60（3〜4日）→ 80（1週間）→ 100。
# 次の段に上げるのは (a) 門の合格率が安定し0本の回が無い (b) 新しい記事の7日のインデックス率がおよそ60%以上
# (c)「クロール済み・インデックス未登録」がインデックス済みより速く増えていない、がそろったときだけ（確かめるのはメインのセッション）。
# 悪ければ上げるのを止める（本数は減らさない）。段は GitHub の変数 WEB_STAGE_TARGET で上げる（2026-11-09 から未設定なら 100）。
# ニュースの記事の上限で、使い方・手続きのガイド（evergreen.yml・EVERGREEN_DAILY_CAP）は別に数える
# 2026-11-09 オーナー指示「100本/日は必須（訪問の目標のため）」: 段は今日から100（変数 WEB_STAGE_TARGET=100・未設定でも100）。
# インデックス率などの見張りは夜の報告で続けるが、上限を下げる理由にはしない
STAGES = (40, 60, 80, 100)
DEFAULT_STAGE = 200


def stage_target() -> int:
    try:
        value = int(os.environ.get("WEB_STAGE_TARGET") or DEFAULT_STAGE)
    except ValueError:
        value = DEFAULT_STAGE
    return max(OWNER_DAILY_TARGET, min(value, WEB_CEILING))


def main() -> None:
    today = datetime.now(JST).strftime("%Y-%m-%d")
    planned = min(pick(WEB_RAMP, today), stage_target())
    web = str(review_cap(int(os.environ.get("WEB_DAILY_CAP_OVERRIDE") or planned), today))
    sns = os.environ.get("SNS_PER_DAY_OVERRIDE") or str(pick(SNS_RAMP, today))
    out = os.environ.get("GITHUB_OUTPUT")
    # 20分ごと（1日72回）に出すので、上限が大きい日は1回あたりの本数も増やす
    broad = os.environ.get("BROAD_MAX_PER_RUN_OVERRIDE") or str(broad_per_run(int(web)))
    ai = os.environ.get("AI_MAX_PER_RUN_OVERRIDE") or str(ai_per_run(int(web)))
    foreign_ai = "1000"
    if in_adsense_review(today):
        # 審査の期間: 1回2本まで・AI のレーンは止める・海外の AI の発表は0本（暮らしとお金だけ）
        broad, ai, foreign_ai = str(min(int(broad), 2)), "0", "0"
    lines = (f"web_daily_cap={web}\nsns_per_day={sns}\nbroad_per_run={broad}\nai_per_run={ai}\n"
             f"foreign_ai_cap={foreign_ai}\nmuse_daily_cap={MUSE_DAILY_CAP}\n")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(lines)
    print(f"[ramp] {today}: 記事の上限 {web}本/日（動画は別）・SNS {sns}本/日・1回あたり 幅広い話題 {broad}本 / AI {ai}本")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
提携リンクのブラウザ操作由来のクリック数（自前計測・推定）を表示する。A8 などの管理画面と見比べる用。
既知の自動アクセスを除くが、実在人間・成約・承認を証明する数値ではない。

  python3 scripts/aff_stats.py                 # 今日（日本時間）
  python3 scripts/aff_stats.py --yesterday     # 昨日（毎晩・毎朝の報告用。A8 の前日分と並べる）
  python3 scripts/aff_stats.py --date 2026-10-27
  python3 scripts/aff_stats.py --days 7        # 7日分（週の報告用）
  python3 scripts/aff_stats.py --json          # 生の JSON

鍵 AFF_STATS_TOKEN は環境変数か .env.local（メインのフォルダ）から読む。中身は表示しない。
数えるのは Worker（cloudflare/aff.ts）。画面側は components/AffClickTracker.tsx（既知の機械・自動ブラウザを除外）
同じことを curl でするなら:
  curl -s -H "Authorization: Bearer $AFF_STATS_TOKEN" "https://ai-tech-express.jp/api/aff/stats?date=2026-10-27"
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = os.environ.get("SITE_URL", "https://ai-tech-express.jp").rstrip("/")
JST = timezone(timedelta(hours=9))


def env_files() -> list[Path]:
    """作業フォルダ（git worktree）から動かしたときもメインの .env.local を探す"""
    files = [ROOT / ".env.local"]
    git = ROOT / ".git"
    if git.is_file():
        match = re.match(r"gitdir:\s*(.+)", git.read_text("utf-8").strip())
        if match:
            files.append(Path(match.group(1)).resolve().parents[2] / ".env.local")
    return files


def load_token() -> str:
    token = os.environ.get("AFF_STATS_TOKEN", "").strip()
    if token:
        return token
    for path in env_files():
        if path.exists():
            for line in path.read_text("utf-8").splitlines():
                match = re.match(r"^AFF_STATS_TOKEN=(.+)$", line.strip())
                if match:
                    return match.group(1).strip().strip("\"'")
    return ""


def program_names() -> dict[str, str]:
    """a8mat → 提携先の名前（affiliate_links.json・content/offers.json・content/products.json から）"""
    # A8 以外はドメインで数えている（components/AffClickTracker.tsx の programOf）
    names: dict[str, str] = {"amazon": "Amazonアソシエイト", "rakuten": "楽天アフィリエイト"}

    def take(text: str, name: str) -> None:
        for code in re.findall(r"a8mat=([0-9A-Z+]+)", text or ""):
            names.setdefault(code, name)

    try:
        for name, entry in json.loads((ROOT / "affiliate_links.json").read_text("utf-8")).items():
            if isinstance(entry, dict):
                take(json.dumps(entry), name)
    except (OSError, ValueError):
        pass
    try:
        for key, partner in json.loads((ROOT / "content/offers.json").read_text("utf-8")).get("partners", {}).items():
            take(json.dumps(partner), partner.get("program") or partner.get("name") or key)
    except (OSError, ValueError, AttributeError):
        pass
    try:
        take((ROOT / "content/products.json").read_text("utf-8"), "楽天（A8経由。ブックス・市場検索）")
    except OSError:
        pass
    return names


def fetch(token: str, date: str) -> dict:
    req = urllib.request.Request(
        f"{SITE}/api/aff/stats?date={date}",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "SaisokuAffStats/1.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.loads(res.read())


def show(data: dict, names: dict[str, str]) -> None:
    print(f"■ {data['date']}（日本時間）自動アクセスを除いたクリック {data['clicks']} 回 / 推定 {data['visitors']} 訪問者")
    funnel = data.get("funnel")
    if funnel:
        labels = {"entry_view": "ガイド一覧表示", "guide_click": "Dify比較への遷移", "guide_view": "Dify比較ページ表示", "comparison_view": "比較表到達", "choice_click": "行き先クリック", "article_view": "対象Dify記事の可視閲覧"}
        print(f"  導線 {funnel['id']}（日内推定。売上・承認・通過順序ではありません）:")
        for row in funnel["stages"]:
            print(f"    {labels.get(row['stage'], row['stage'])}: {row['events']}回 / 推定{row['visitors']}訪問者")
        for row in funnel["byChoice"]:
            print(f"    行き先 {row['choice']}: {row['events']}回")
        article_measurement = funnel.get("articleMeasurement")
        if article_measurement:
            print("  記事別（新計測開始後のみ。日内推定の突合で、順序付きセッションCVRではありません）:")
            for row in article_measurement.get("byArticle", []):
                rate = row.get("observedReaderClickRate")
                rate_text = "分母なし・算出不可" if rate is None else f"{rate:.1%}"
                print(f"    {row['path']}: 可視閲覧{row['viewEvents']}回/推定{row['viewVisitors']}人、比較クリック{row['comparisonClickEvents']}回、双方観測{row['matchedReaderClickVisitors']}人（{rate_text}）")
                print(f"      閲覧未観測のクリック推定{row['clickVisitorsWithoutObservedView']}人、旧計測クリック{row['legacyClickEventsExcluded']}回は新分母と混ぜない")
            print("    注意: 導入日途中・送信欠測・日跨ぎの影響あり。観測0は全訪問0の証明ではありません。")
        if funnel.get("truncated"):
            print("    注意: 集計上限に達しました。全件集計ではありません。")
    if not data["clicks"]:
        return
    print("  提携先別:")
    for row in data["byProgram"]:
        label = names.get(row["program"], row["program"])
        code = f"（{row['program']}）" if label != row["program"] else ""
        print(f"    {label}{code}  {row['clicks']}回 / {row['visitors']}人")
    print("  ページ別（上位10）:")
    for row in data["byPage"][:10]:
        print(f"    {row['path']}  {row['clicks']}回")
    print("  置き場所別: " + "、".join(f"{row['pos']} {row['clicks']}" for row in data["byPosition"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--date", help="YYYY-MM-DD（日本時間）")
    parser.add_argument("--yesterday", action="store_true")
    parser.add_argument("--days", type=int, default=1, help="--date（既定は今日）までの日数")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    token = load_token()
    if not token:
        print("[aff] AFF_STATS_TOKEN が見つかりません（環境変数か .env.local に入れてください）", file=sys.stderr)
        return 1
    end = datetime.now(JST).date()
    if args.yesterday:
        end -= timedelta(days=1)
    if args.date:
        end = datetime.strptime(args.date, "%Y-%m-%d").date()
    dates = [(end - timedelta(days=i)).isoformat() for i in range(max(1, args.days) - 1, -1, -1)]

    try:
        results = [fetch(token, d) for d in dates]
    except urllib.error.HTTPError as error:
        print(f"[aff] 取得に失敗しました: HTTP {error.code}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError) as error:
        print(f"[aff] 取得に失敗しました: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(results[0] if len(results) == 1 else results, ensure_ascii=False, indent=2))
        return 0
    names = program_names()
    for data in results:
        show(data, names)
    if len(results) > 1:
        print(f"■ 合計 {sum(r['clicks'] for r in results)} 回（{dates[0]}〜{dates[-1]}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

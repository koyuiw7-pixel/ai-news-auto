#!/usr/bin/env python3
"""デプロイ直後の「1回目の表示」の速さを本番で確かめる（台帳 W29）。

  python3 scripts/cold_check.py version                 # 今の版（x-saisoku-ver）を出す（デプロイ前に控える）
  python3 scripts/cold_check.py check --previous <版>   # 新しい版に切り替わるのを待ってから測る（deploy_cloudflare.yml）
  python3 scripts/cold_check.py check --n 40            # 手元で測る
  python3 scripts/cold_check.py plain                   # 何も付けない URL で、新しい版・新しい記事が出ているか（報告だけ）

サイトマップから選んだページ（毎回入れる決まったページ＋無作為の n 本）を、エッジのキャッシュに無い
URL（?_cold=<乱数>）で開き、最初の1バイトが届くまでの時間（TTFB）を測る。デプロイ直後に読者・検索の
ロボットが初めて開いたときと同じ道を通る（Workers → OpenNext のキャッシュ → 無ければ描画）。

落とす条件（どれか1つで終了コード 1。GitHub Actions のデプロイが赤になり、オーナーに知らせが届く）:
  - x-nextjs-cache: MISS … ビルドで作っておくべきページを、アクセスが来てから作っている（遅さの根本の原因。2026-11-04）
  - 5xx・時間切れ
  - LIMIT 秒を超え、新しい乱数で開き直しても LIMIT 秒を超えた（1回目だけ遅いものは注意として出す）
計測は自社の確かめなので、X-Saisoku-Internal: 1 と ?_internal=1 を付けて計測から外す。標準ライブラリだけで動く。
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

LIMIT = 2.0  # 秒。オーナーの目安「どのページも2秒以内」
TIMEOUT = 30.0
# 2026-11-04 の点検で遅かったページ（約53秒・時間切れ）。毎回測る
ALWAYS = ["/", "/articles/openai-gpt-6-astra-comprehensive-guide-matome", "/products/chatgpt-voice"]
HEADERS = {"X-Saisoku-Internal": "1", "User-Agent": "saisoku-cold-check/1.0"}


def site_url() -> str:
    return (os.environ.get("NEXT_PUBLIC_SITE_URL") or "https://ai-tech-express.jp").rstrip("/")


def with_params(path: str, nonce: str | None = None) -> str:
    sep = "&" if "?" in path else "?"
    return f"{path}{sep}_internal=1" + (f"&_cold={nonce}" if nonce else "")


def fetch(base: str, path: str, nonce: str | None = None) -> dict:
    """1回開いて TTFB・状態・キャッシュの印を返す"""
    url = base + with_params(path, nonce)
    started = time.monotonic()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=TIMEOUT) as res:
            res.read(1)
            ttfb = time.monotonic() - started
            headers = {k.lower(): v for k, v in res.headers.items()}
            # Server-Timing は Cloudflare（cfEdge・cfWorker）とこちら（base・app）の2本が来る。両方つなぐ
            headers["server-timing"] = ", ".join(res.headers.get_all("server-timing") or [])
            res.read()
            status = res.status
    except urllib.error.HTTPError as error:
        ttfb = time.monotonic() - started
        headers = {k.lower(): v for k, v in error.headers.items()}
        status = error.code
    except Exception as error:  # 時間切れ・接続の失敗
        return {"path": path, "status": 0, "ttfb": round(time.monotonic() - started, 2), "cache": "", "ver": "", "error": type(error).__name__}
    return {
        "path": path,
        "status": status,
        "ttfb": round(ttfb, 2),
        "cache": headers.get("x-nextjs-cache", ""),
        "ver": headers.get("x-saisoku-ver", ""),
        "timing": timing_of(headers.get("server-timing", "")),
        "error": "",
    }


def timing_of(header: str) -> str:
    """Worker の内訳（cloudflare/worker.ts の Server-Timing。自社の確かめのときだけ付く。台帳 W43）を短い文字にする。
    例 'base-cold;dur=812, app;dur=95, total;dur=907' → 'base-cold 0.81・app 0.10'"""
    parts = []
    for item in header.split(","):
        match = re.match(r"\s*([A-Za-z-]+)\s*;\s*dur=([\d.]+)", item)
        if match and match.group(1) not in ("total", "cfOrigin"):
            parts.append(f"{match.group(1)} {float(match.group(2)) / 1000:.2f}")
    return "・".join(parts)


def sitemap_paths(xml: str, base: str) -> list[str]:
    """サイトマップの <loc> をサイト内のパスにする（分割されたサイトマップの目次なら子のサイトマップの URL を返す）"""
    out = []
    for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml):
        if not loc.startswith(base):
            continue
        out.append(loc[len(base):] or "/")
    return out


def load_sitemap(base: str) -> list[str]:
    def get(path: str) -> str:
        with urllib.request.urlopen(urllib.request.Request(base + with_params(path), headers=HEADERS), timeout=TIMEOUT) as res:
            return res.read().decode("utf-8", "replace")

    xml = get("/sitemap.xml")
    paths = sitemap_paths(xml, base)
    if "<sitemapindex" in xml:
        children = paths
        paths = []
        for child in children:
            paths += sitemap_paths(get(child), base)
    return paths


def choose(paths: list[str], n: int, seed: str | None = None) -> list[str]:
    """毎回入れる決まったページ＋サイトマップから無作為に n 本（重ならない）"""
    rest = [p for p in dict.fromkeys(paths) if p not in ALWAYS]
    rnd = random.Random(seed)
    return ALWAYS + rnd.sample(rest, min(n, len(rest)))


def judge(first: dict, again: dict | None, limit: float = LIMIT) -> tuple[str, str]:
    """('fail' | 'warn' | 'ok', 理由)"""
    if first["error"] or first["status"] == 0:
        return "fail", f"開けない（{first['error'] or '接続の失敗'}・{first['ttfb']}秒）"
    if first["status"] >= 400:
        # サイトマップに載るページは 200 で開くはず（404・410 を合格にしない。W3・W25。2026-11-04 一貫性の点検）
        return "fail", f"状態 {first['status']}"
    if first["cache"] == "MISS":
        return "fail", "ビルドで作っておらず、アクセスが来てから作った（x-nextjs-cache: MISS）"
    if first["ttfb"] > limit:
        if again is None or again["error"] or again["ttfb"] > limit:
            second = "" if again is None else f"・開き直しても {again['ttfb']}秒"
            return "fail", f"{first['ttfb']}秒（{limit}秒を超えた{second}）"
        return "warn", f"1回目だけ {first['ttfb']}秒（開き直すと {again['ttfb']}秒。通信の揺れの可能性）"
    return "ok", ""


def wait_for_new_version(base: str, previous: str, seconds: int = 120) -> str:
    deadline = time.monotonic() + seconds
    current = ""
    while time.monotonic() < deadline:
        current = fetch(base, "/", nonce=str(random.randrange(10**12)))["ver"]
        if current and current != previous:
            return current
        time.sleep(5)
    return current


PLAIN_PATHS = ["/", "/sitemap.xml"]
ARTICLE_LINK = re.compile(r"/articles/([A-Za-z0-9][A-Za-z0-9_-]*)")


def fetch_body(base: str, path: str, nonce: str | None = None, plain: bool = False) -> dict:
    """GET して版と本文を返す。plain=True のときは ?_internal も付けない（読者・検索のロボットと同じ URL。印は X-Saisoku-Internal だけ）"""
    url = base + (path if plain else with_params(path, nonce))
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=TIMEOUT) as res:
            headers = {k.lower(): v for k, v in res.headers.items()}
            return {"status": res.status, "ver": headers.get("x-saisoku-ver", ""), "edge": headers.get("x-saisoku-edge", ""), "body": res.read().decode("utf-8", "replace"), "error": ""}
    except urllib.error.HTTPError as error:
        return {"status": error.code, "ver": error.headers.get("x-saisoku-ver", ""), "edge": error.headers.get("x-saisoku-edge", ""), "body": "", "error": ""}
    except Exception as error:  # 時間切れ・接続の失敗
        return {"status": 0, "ver": "", "edge": "", "body": "", "error": type(error).__name__}


def top_slug(body: str) -> str:
    """描いたばかりのトップで最初に出てくる記事（いちばん上の記事）"""
    match = ARTICLE_LINK.search(body)
    return match.group(1) if match else ""


def judge_plain(path: str, version: str, newest: str, second: dict) -> tuple[bool, str]:
    """何も付けない URL の2回目が、今の版で、トップのいちばん上の記事を含むか（seo A1）"""
    if second["error"] or second["status"] != 200:
        return False, f"{path}: 開けない（{second['error'] or second['status']}）"
    if second["ver"] != version:
        return False, f"{path}: 古い版を返した（{second['ver'][:8] or '版の印なし'}・今は {version[:8]}・{second['edge'] or '-'}）"
    if newest and f"/articles/{newest}" not in second["body"]:
        return False, f"{path}: トップのいちばん上の記事（{newest}）が載っていない"
    return True, f"{path}: 今の版（{version[:8]}・{second['edge'] or '-'}）で、新しい記事も載っている"


def plain(args) -> int:
    """報告だけ（終了コードはいつも 0。デプロイを赤にしない）"""
    base = site_url()
    nonce = str(random.randrange(10**12))
    fresh_home = fetch_body(base, "/", nonce=nonce)
    version = fresh_home["ver"]
    newest = top_slug(fresh_home["body"])
    lines = ["## 何も付けない URL の確かめ（seo A1。報告だけ）", "", f"- 今の版: {version[:8] or '(不明)'}・トップのいちばん上の記事: {newest or '(不明)'}"]
    problems = []
    if not version:
        problems.append("今の版が分からない（描いたばかりのトップに x-saisoku-ver が無い）")
    else:
        for path in PLAIN_PATHS:
            fetch_body(base, path, plain=True)
            second = fetch_body(base, path, plain=True)
            ok, message = judge_plain(path, version, newest, second)
            lines.append(f"- {'✓' if ok else '✗'} {message}")
            if not ok:
                problems.append(message)
    report = "\n".join(lines)
    print(report, flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report + "\n")
    for message in problems:
        print(f"::warning::{message}", flush=True)
    return 0


def check(args) -> int:
    base = site_url()
    if args.previous:
        version = wait_for_new_version(base, args.previous)
        print(f"版: {args.previous[:8]} → {version[:8] or '(不明)'}", flush=True)
        if not version or version == args.previous:
            # 新しい版に切り替わっていない → 古い版を測って「合格」にしない（確かめられない検査は不合格）
            print("::error::デプロイのあとも新しい版に切り替わらない（古い版を測ることになるので不合格）", flush=True)
            return 1
    listed = load_sitemap(base)
    if len(listed) < 10:
        print(f"::error::サイトマップから測るページを選べない（{len(listed)} 本）", flush=True)
        return 1
    paths = choose(listed, args.n, args.seed)
    print(f"{len(paths)} ページを、エッジのキャッシュに無い URL で開きます（同時 {args.concurrency}・上限 {args.limit}秒）", flush=True)

    def one(path: str) -> dict:
        first = fetch(base, path, nonce=str(random.randrange(10**12)))
        again = fetch(base, path, nonce=str(random.randrange(10**12))) if first["ttfb"] > args.limit and not first["error"] else None
        verdict, reason = judge(first, again, args.limit)
        return {**first, "verdict": verdict, "reason": reason}

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(one, paths))

    times = sorted(r["ttfb"] for r in results)
    fails = [r for r in results if r["verdict"] == "fail"]
    warns = [r for r in results if r["verdict"] == "warn"]
    median = times[len(times) // 2] if times else 0
    lines = [
        "## デプロイ直後の1回目の表示（台帳 W29）",
        "",
        f"- {len(results)} ページ・最大 {times[-1] if times else 0}秒・中央値 {median}秒・{args.limit}秒超え {sum(t > args.limit for t in times)} 本",
        f"- 落ちた {len(fails)} 本・注意 {len(warns)} 本",
        "",
        "| ページ | 秒 | 状態 | キャッシュ | Worker の内訳（秒） | 判定 |",
        "|---|---|---|---|---|---|",
    ]
    for r in sorted(results, key=lambda r: -r["ttfb"]):
        mark = {"fail": "✗ " + r["reason"], "warn": "△ " + r["reason"], "ok": "✓"}[r["verdict"]]
        lines.append(f"| `{r['path']}` | {r['ttfb']} | {r['status'] or r['error']} | {r['cache'] or '-'} | {r.get('timing') or '-'} | {mark} |")
    report = "\n".join(lines)
    print(report, flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report + "\n")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=1)
    for r in warns:
        print(f"::warning::{r['path']} {r['reason']}", flush=True)
    for r in fails:
        print(f"::error::デプロイ直後の表示が遅い・作っていない: {r['path']} {r['reason']}", flush=True)
    return 1 if fails else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version")
    c = sub.add_parser("check")
    c.add_argument("--previous", default="", help="デプロイ前の版。違う版に切り替わるまで待ってから測る")
    c.add_argument("--n", type=int, default=30)
    c.add_argument("--concurrency", type=int, default=4)
    c.add_argument("--limit", type=float, default=LIMIT)
    c.add_argument("--seed", default=None)
    c.add_argument("--json", default="")
    sub.add_parser("plain")
    args = parser.parse_args()
    if args.command == "version":
        print(fetch(site_url(), "/", nonce=str(random.randrange(10**12)))["ver"])
        return 0
    if args.command == "plain":
        return plain(args)
    return check(args)


if __name__ == "__main__":
    sys.exit(main())

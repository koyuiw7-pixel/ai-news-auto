#!/usr/bin/env python3
"""AI検索の巡回が本番のページを読めるかの、毎日の確認（LLMO-A2。読み取りだけ。サイトの設定は変えない）。

確かめること（通信は最大 25 回。すべてヘッダー X-Saisoku-Internal: 1 と ?v=<時刻> を付ける＝訪問に数えない・古い控えを避ける）:
  (a) /robots.txt に Content-signal の行がなく、AI検索の巡回（app/robots.ts の SEARCH_AGENTS）に Disallow: / がない
  (b) OAI-SearchBot・ChatGPT-User・PerplexityBot・Claude-SearchBot・bingbot・Googlebot の名乗りで、いちばん新しい記事と
      ガイド1本を開くと 200 で、cf-mitigated（Cloudflare の門前払い）の印がなく、本文の最初の一文が入っている
      （大きさは比べない。Cloudflare の控えは名乗りごとに分かれていないため）
  (c) ページの meta robots に max-snippet:-1 があり、nosnippet・noarchive がない
  (d) IndexNow の鍵のファイルが 200 で開ける

注意: GitHub の実行環境の IP は本物の巡回の IP と違う。本物の巡回が通っているかは、Cloudflare の画面（AI Crawl Control）が正しい。

  python3 scripts/llmo_access_check.py                         # 本番を確かめて PASS / FAIL を出す（失敗があれば終了コード 1）
  python3 scripts/llmo_access_check.py --robots-file robots.txt  # 手元の robots.txt だけを確かめる（通信なし）
  python3 scripts/llmo_access_check.py --record                # 加えて、RECORD_FROM 以降は結果を state/pipeline_health.json に書く
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).resolve().parent.parent
ROBOTS_TS = ROOT / "app" / "robots.ts"
ARTICLES_DIR = ROOT / "content" / "articles"
GUIDES_DIR = ROOT / "content" / "guides"
PUBLIC_DIR = ROOT / "public"
BASE = "https://ai-tech-express.jp"
MAX_REQUESTS = 25
JST = timezone(timedelta(hours=9))
# はじめの3日（11/10〜11/12）は表示だけ。11/13 から失敗を state/pipeline_health.json に書く
RECORD_FROM = "2026-11-13"
# 公開の直後はまだ本番に出ていないことがあるので、この時間より前に公開された記事を選ぶ
ARTICLE_SETTLE = timedelta(minutes=60)
SOURCE_OF_TRUTH = ("この確認は GitHub の実行環境から行っていて、本物の巡回とは IP が違います。"
                   "本物の AI 巡回が通っているかは、Cloudflare の画面（AI Crawl Control）が正しい情報です。")
TAG = " (saisoku-llmo-check)"  # 自社の確認だと分かるよう、名乗りの最後に付ける
USER_AGENTS = {
    "OAI-SearchBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.3; +https://openai.com/searchbot",
    "ChatGPT-User": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot",
    "PerplexityBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
    "Claude-SearchBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-SearchBot/1.0; +https://www.anthropic.com)",
    "bingbot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm) Chrome/116.0.1938.76 Safari/537.36",
    "Googlebot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Googlebot/2.1; +http://www.google.com/bot.html) Chrome/130.0.0.0 Safari/537.36",
}


class Budget:
    def __init__(self, limit: int = MAX_REQUESTS):
        self.limit = limit
        self.used = 0

    def fetch(self, url: str, user_agent: str = "SaisokuLLMOCheck/1.0") -> tuple[int, dict, str]:
        if self.used >= self.limit:
            raise RuntimeError(f"通信の上限（{self.limit} 回）を超えます")
        self.used += 1
        sep = "&" if "?" in url else "?"
        req = request.Request(f"{url}{sep}v={int(time.time())}", headers={
            "User-Agent": user_agent + (TAG if user_agent in USER_AGENTS.values() else ""),
            "X-Saisoku-Internal": "1", "Accept-Encoding": "identity"})
        try:
            with request.urlopen(req, timeout=20) as resp:
                return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read().decode("utf-8", "replace")
        except error.HTTPError as exc:
            return exc.code, {k.lower(): v for k, v in (exc.headers or {}).items()}, exc.read().decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001
            return 0, {}, f"{type(exc).__name__}: {exc}"


def search_agents(source: str | None = None) -> list[str]:
    """app/robots.ts の SEARCH_AGENTS（AI検索の巡回の名前）を読む"""
    text = source if source is not None else ROBOTS_TS.read_text("utf-8")
    block = re.search(r"const SEARCH_AGENTS\s*=\s*\[(.*?)\]", text, re.S)
    return re.findall(r'"([^"]+)"', block.group(1)) if block else []


def robots_groups(text: str) -> list[tuple[list[str], list[tuple[str, str]]]]:
    """robots.txt を (名前の並び, [(allow|disallow, パス)]) のグループに分ける（RFC 9309）"""
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    agents: list[str] = []
    rules: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if rules:
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(value.lower())
        elif key in ("allow", "disallow") and agents:
            rules.append((key, value))
    if agents:
        groups.append((agents, rules))
    return groups


def check_robots(text: str, agents: list[str]) -> list[str]:
    failures = []
    for raw in text.splitlines():
        if re.match(r"\s*content-signal\s*:", raw, re.I):
            failures.append(f"robots.txt に Content-signal の行があります（{raw.strip()}）。"
                            "Cloudflare の管理された robots.txt が足したものなら、Cloudflare の画面でオーナーが止めます")
            break
    groups = robots_groups(text)
    for agent in agents:
        named = [rules for names, rules in groups if agent.lower() in names]
        rules = [r for group in named for r in group] if named else [r for names, group in groups if "*" in names for r in group]
        if ("disallow", "/") in rules:
            failures.append(f"robots.txt で {agent}（AI検索の巡回）に Disallow: / があります。AIの回答に引用されなくなります")
    return failures


def _strip_markdown(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return re.sub(r"[*_`~>#]", "", text).strip()


def first_sentence(text: str, limit: int = 30) -> str:
    """本文の最初の一文（見出し・空行を飛ばし、Markdown の記号を外し、長ければ頭の limit 文字）"""
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "|", "-", "!", "<")):
            continue
        plain = _strip_markdown(line)
        sentence = plain.split("。", 1)[0]
        if sentence:
            return re.sub(r"\s+", "", sentence)[:limit]
    return ""


def page_text(body: str) -> str:
    body = re.sub(r"<(script|style)\b.*?</\1>", "", body, flags=re.S | re.I)
    return re.sub(r"\s+", "", html.unescape(re.sub(r"<[^>]+>", "", body)))


def meta_robots_problem(body: str) -> str | None:
    metas = [html.unescape(m.group(1)).lower().replace(" ", "") for m in
             re.finditer(r'<meta[^>]+name="robots"[^>]+content="([^"]*)"', body, re.I)]
    metas += [html.unescape(m.group(1)).lower().replace(" ", "") for m in
              re.finditer(r'<meta[^>]+content="([^"]*)"[^>]+name="robots"', body, re.I)]
    if not metas:
        return "meta robots がありません"
    joined = ",".join(metas)
    bad = [word for word in ("nosnippet", "noarchive") if word in joined.split(",")]
    if bad:
        return f"meta robots に {'・'.join(bad)} があります（AIの回答に抜き出されません）: {joined}"
    if "max-snippet:-1" not in joined:
        return f"meta robots に max-snippet:-1 がありません: {joined}"
    return None


def pick_article(now: datetime | None = None, articles_dir: Path | None = None) -> tuple[str, str] | None:
    """公開から ARTICLE_SETTLE 以上たった、いちばん新しい記事の (slug, 本文の最初の一文)"""
    limit = (now or datetime.now(timezone.utc)) - ARTICLE_SETTLE
    best: tuple[datetime, str, str] | None = None
    for path in (articles_dir or ARTICLES_DIR).glob("*.json"):
        try:
            data = json.loads(path.read_text("utf-8"))
            published = datetime.fromisoformat(str(data.get("publishedAt")).replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(data, dict) or data.get("duplicateOf") or not published.tzinfo or published > limit:
            continue
        sentence = first_sentence(data.get("body") or "")
        if sentence and (best is None or published > best[0]):
            best = (published, str(data.get("slug") or path.stem), sentence)
    return (best[1], best[2]) if best else None


def moved_guides(root: Path | None = None) -> set[str]:
    """next.config.ts が別のページへ 308 で転送するガイド（製品のまとめページへ移ったもの・まとめたもの）"""
    base = root or ROOT
    moved: set[str] = set()
    try:
        linked = json.loads((base / "content" / "product_sources.json").read_text("utf-8")).get("items") or {}
        products = {p.stem for p in (base / "content" / "products").glob("*.json")}
        moved |= {slug for slug in products if isinstance(linked.get(slug), dict) and linked[slug].get("pricing")}
    except Exception:  # noqa: BLE001
        pass
    try:
        block = re.search(r"MERGED_GUIDES[^=]*=\s*\{(.*?)\}", (base / "next.config.ts").read_text("utf-8"), re.S)
        moved |= set(re.findall(r'"([^"]+)"\s*:', block.group(1))) if block else set()
    except Exception:  # noqa: BLE001
        pass
    return moved


def pick_guide(guides_dir: Path | None = None, moved: set[str] | None = None) -> tuple[str, str] | None:
    """転送されない（そのまま開ける）ガイド1本の (slug, 紹介文の最初の一文)"""
    skip = moved_guides() if moved is None else moved
    for path in sorted((guides_dir or GUIDES_DIR).glob("*.json")):
        if path.stem in skip:
            continue
        try:
            data = json.loads(path.read_text("utf-8"))
        except Exception:  # noqa: BLE001
            continue
        sentence = first_sentence(data.get("intro") or "") if isinstance(data, dict) else ""
        if sentence:
            return str(data.get("slug") or path.stem), sentence
    return None


def indexnow_key(public_dir: Path | None = None) -> str | None:
    for path in (public_dir or PUBLIC_DIR).glob("*.txt"):
        if re.fullmatch(r"[0-9a-f]{32,128}", path.stem) and path.read_text().strip() == path.stem:
            return path.stem
    return None


def check_live(base: str = BASE, budget: Budget | None = None) -> tuple[list[str], list[str]]:
    budget = budget or Budget()
    passes: list[str] = []
    failures: list[str] = []
    agents = search_agents()
    status, _, text = budget.fetch(f"{base}/robots.txt")
    if status != 200:
        failures.append(f"/robots.txt が開けません（HTTP {status}）")
    else:
        problems = check_robots(text, agents)
        failures += problems
        if not problems:
            passes.append(f"(a) robots.txt: Content-signal なし、AI検索の巡回 {len(agents)} 種に Disallow: / なし")
    pages = [("記事", pick_article()), ("ガイド", pick_guide())]
    for label, picked in pages:
        if not picked:
            failures.append(f"確かめる{label}が見つかりません")
            continue
        slug, sentence = picked
        path = f"/articles/{slug}" if label == "記事" else f"/guides/{slug}"
        meta_checked = False
        for name, ua in USER_AGENTS.items():
            status, headers, body = budget.fetch(f"{base}{path}", ua)
            where = f"{name} で {path}"
            if status != 200:
                failures.append(f"(b) {where} が HTTP {status}（200 ではない）")
            elif headers.get("cf-mitigated"):
                failures.append(f"(b) {where} に cf-mitigated: {headers['cf-mitigated']}（Cloudflare が門前払いしている）")
            elif sentence not in page_text(body):
                failures.append(f"(b) {where} の中に本文の最初の一文（{sentence}）がない")
            else:
                passes.append(f"(b) {where}: 200、本文あり")
            if status == 200 and not meta_checked:
                meta_checked = True
                problem = meta_robots_problem(body)
                if problem:
                    failures.append(f"(c) {path}: {problem}")
                else:
                    passes.append(f"(c) {path}: meta robots に max-snippet:-1、nosnippet・noarchive なし")
    key = indexnow_key()
    if not key:
        failures.append("(d) public/ に IndexNow の鍵のファイルがありません")
    else:
        status, _, body = budget.fetch(f"{base}/{key}.txt")
        if status == 200 and body.strip() == key:
            passes.append("(d) IndexNow の鍵のファイル: 200")
        else:
            failures.append(f"(d) IndexNow の鍵のファイルが HTTP {status}（中身が鍵と同じでないこともある）")
    passes.append(f"通信 {budget.used} 回（上限 {budget.limit} 回）")
    return passes, failures


def report(passes: list[str], failures: list[str]) -> str:
    lines = [f"PASS {line}" for line in passes] + [f"FAIL {line}" for line in failures]
    lines.append("")
    lines.append(f"結果: {'すべて PASS' if not failures else f'{len(failures)} 件 FAIL'}")
    if failures:
        lines.append(SOURCE_OF_TRUTH)
    return "\n".join(lines)


def should_record(now: datetime | None = None) -> bool:
    return (now or datetime.now(timezone.utc)).astimezone(JST).date().isoformat() >= RECORD_FROM


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default=BASE)
    parser.add_argument("--robots-file", help="手元の robots.txt だけを確かめる（通信なし）")
    parser.add_argument("--record", action="store_true", help=f"{RECORD_FROM} 以降は結果を state/pipeline_health.json に書く")
    args = parser.parse_args(argv)
    if args.robots_file:
        failures = check_robots(Path(args.robots_file).read_text("utf-8"), search_agents())
        print(report([] if failures else ["robots.txt: Content-signal なし、AI検索の巡回に Disallow: / なし"], failures))
        return 1 if failures else 0
    passes, failures = check_live(args.base.rstrip("/"))
    print(report(passes, failures))
    if args.record:
        if should_record():
            sys.path.insert(0, str(ROOT / "scripts"))
            import pipeline_health  # noqa: PLC0415
            pipeline_health.record_llmo_access(failures)
            print("[llmo] 結果を state/pipeline_health.json に記録しました（変わったときだけ書き直します）")
        else:
            print(f"[llmo] {RECORD_FROM} までは表示だけです（state には書きません）")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

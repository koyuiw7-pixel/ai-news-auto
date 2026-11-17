#!/usr/bin/env python3
"""Claude API と OpenAI API の比べ書き（公開しない・記事のファイルを書き換えない・SNS に出さない）。

最近の記事 N 本の元の資料を、本番と同じ部品（scripts/trial_types.py の run_one: 資料の取り直し → 事実の束 → 型 →
生成 → 品質ゲート（事実確認=check・指摘の手直し=helper）→ 後処理）で、会社ごとに1回ずつ書き直して比べる。
会社の切り替えは llm.provider_order（LLM_PROVIDER_ORDER）だけで、すべての段（書く段・確認・手直し）が同じ会社になる。
有料の API が使えないとき（予算・失敗）は今までどおり無料モデルに落ちる。その本数は「無料に落ちた」として別に数える。

結果: 会社ごとの合格率・使った額・公開できた記事1本あたりの額・段ごとの額。--out の JSON と、同じ名前の .md に書く。
OpenAI の分も OpenAI の期間の予算（scripts/llm.py の openai_block_reason）の中でしか使わない。

  python3 scripts/compare_providers.py --n 8 --out out/provider_compare.json            # 最近の8本
  python3 scripts/compare_providers.py --slug a --slug b --purpose sns --out x.json       # 記事と段を指定
  gh workflow run compare_providers.yml -f n=8                                            # GitHub で（キーは secrets）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import llm  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PREFIX = {"claude": llm.API_PREFIX, "openai": llm.OPENAI_PREFIX}


def log(msg: str) -> None:
    print(msg, flush=True)


def recent_slugs(n: int, articles_dir: Path | None = None) -> list[str]:
    """公開中の最近の記事（元の資料の URL があるもの。地震・Muse・取り下げは除く）を新しい順に n 本"""
    rows = []
    for path in (articles_dir or ROOT / "content" / "articles").glob("*.json"):
        try:
            a = json.loads(path.read_text("utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not a.get("sourceUrl") or not (a.get("sourcePublishedAt") or a.get("publishedAt")):
            continue
        if a.get("earthquake") or a.get("muse") or a.get("retired") or a.get("duplicateOf"):
            continue
        if "jma.go.jp" in str(a.get("sourceUrl")):
            continue
        rows.append((str(a.get("publishedAt") or ""), a.get("slug") or path.stem))
    rows.sort(reverse=True)
    return [slug for _, slug in rows[:n]]


def provider_env(provider: str) -> None:
    """この会社だけを使う（ほかの会社の API には落とさない）"""
    os.environ["LLM_PROVIDER_ORDER"] = provider
    os.environ["CLAUDE_API_FALLBACK_PURPOSES"] = ""
    os.environ.pop("CLAUDE_API_DISABLE", None)
    os.environ.pop("OPENAI_API_DISABLE", None)
    if provider == "openai":
        # OpenAI だけで比べるために、この実行では Claude API を使わない（Claude の経路は provider_order で外れるが念のため）
        os.environ["CLAUDE_API_DISABLE"] = "1"
    llm._api_off = None  # noqa: SLF001 - 会社を替えたら、前の会社の「この実行では使わない」を持ち越さない
    llm._openai_off = None  # noqa: SLF001
    llm._limit_logged.clear()  # noqa: SLF001


def stage_costs(calls: list) -> dict:
    out: dict[str, dict] = {}
    for purpose, model, usd in calls:
        acc = out.setdefault(purpose, {"calls": 0, "usd": 0.0, "models": {}})
        acc["calls"] += 1
        acc["usd"] = round(acc["usd"] + usd, 6)
        acc["models"][model] = acc["models"].get(model, 0) + 1
    return out


def summarize(provider: str, rows: list[dict]) -> dict:
    done = [r for r in rows if "error" not in r]
    accepted = [r for r in done if r.get("accepted")]
    usd = round(sum(r.get("usd", 0.0) for r in rows), 6)
    stages: dict[str, dict] = {}
    for r in rows:
        for purpose, s in (r.get("stages") or {}).items():
            acc = stages.setdefault(purpose, {"calls": 0, "usd": 0.0})
            acc["calls"] += s["calls"]
            acc["usd"] = round(acc["usd"] + s["usd"], 6)
    return {
        "provider": provider, "articles": len(rows), "errors": len(rows) - len(done), "accepted": len(accepted),
        "pass_rate": round(len(accepted) / len(rows), 3) if rows else 0.0,
        "usd": usd, "usd_per_accepted": round(usd / len(accepted), 4) if accepted else None,
        "fell_back_to_free": sum(1 for r in rows if r.get("fell_back")),
        "stages": stages,
    }


def markdown(report: dict) -> str:
    lines = [f"# Claude API と OpenAI API の比べ書き（{report['n']}本・書く段 {report['purpose']}）", "",
             "| 会社 | 合格 | 合格率 | 使った額 | 公開できた1本あたり | 無料に落ちた本数 | 失敗 |", "|---|---|---|---|---|---|---|"]
    for s in report["summary"]:
        per = f"${s['usd_per_accepted']:.3f}" if s["usd_per_accepted"] is not None else "—"
        lines.append(f"| {s['provider']} | {s['accepted']}/{s['articles']} | {s['pass_rate']:.0%} | ${s['usd']:.3f} | {per} | "
                     f"{s['fell_back_to_free']} | {s['errors']} |")
    lines += ["", "## 段ごとの額", "", "| 会社 | 段 | 回数 | 額 |", "|---|---|---|---|"]
    for s in report["summary"]:
        for purpose, st in sorted(s["stages"].items()):
            lines.append(f"| {s['provider']} | {purpose} | {st['calls']} | ${st['usd']:.4f} |")
    lines += ["", "## 記事ごと", "", "| 記事 | " + " | ".join(p for p in report["providers"]) + " |",
              "|---|" + "---|" * len(report["providers"])]
    by = {p: {r["slug"]: r for r in report["results"][p]} for p in report["providers"]}
    for slug in report["slugs"]:
        cells = []
        for p in report["providers"]:
            r = by[p].get(slug) or {}
            if "error" in r:
                cells.append("失敗")
            else:
                cells.append(f"{'合格' if r.get('accepted') else '不合格'} ${r.get('usd', 0):.3f}{'（無料に落ちた）' if r.get('fell_back') else ''}")
        lines.append(f"| {slug} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=8, help="最近の記事を何本（--slug が無いとき）")
    ap.add_argument("--slug", action="append", default=[])
    ap.add_argument("--purpose", default="core", help="書く段（core / sns / rest など）")
    ap.add_argument("--providers", default="claude,openai")
    ap.add_argument("--attempts", type=int, default=2)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    providers = [p for p in args.providers.replace(" ", "").split(",") if p in llm.PROVIDERS]
    missing = [p for p, key in (("claude", "ANTHROPIC_API_KEY"), ("openai", "OPENAI_API_KEY")) if p in providers and not os.environ.get(key)]
    if missing:
        log(f"[compare] キーが無いので比べられません: {', '.join(missing)}（GitHub の secrets に OPENAI_API_KEY / ANTHROPIC_API_KEY）")
        return 2
    slugs = args.slug or recent_slugs(args.n)
    if not slugs:
        log("[compare] 比べる記事がありません")
        return 2
    import trial_types  # noqa: PLC0415 - 重い部品は比べるときだけ読み込む

    log(f"[compare] {len(slugs)}本 × {', '.join(providers)}（書く段 {args.purpose}）")
    log(llm.openai_summary_line())
    results: dict[str, list[dict]] = {}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report: dict = {}
    for provider in providers:
        provider_env(provider)
        rows = results.setdefault(provider, [])
        for slug in slugs:
            mark = llm.run_cost_mark()
            try:
                row = trial_types.run_one(slug, args.purpose, args.attempts, True)
            except Exception as error:  # noqa: BLE001
                log(f"   [NG] {provider} {slug}: {str(error)[:300]}")
                row = {"slug": slug, "error": str(error)[:500]}
            usd, detail = llm.cost_since(mark)
            row["provider"] = provider
            row["usd"] = usd
            row["cost_detail"] = detail
            row["stages"] = stage_costs(llm.RUN_COST["calls"][mark[1]:])
            row["fell_back"] = any(not str(h.get("model") or "").startswith(PREFIX[provider]) for h in row.get("history") or [])
            rows.append(row)
            log(f"   {provider} {slug}: {'合格' if row.get('accepted') else '不合格'} ${usd:.4f}（{detail}）")
            report = {"n": len(slugs), "purpose": args.purpose, "providers": providers, "slugs": slugs,
                      "summary": [summarize(p, results.get(p, [])) for p in providers if results.get(p)], "results": results}
            out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8")
    out_path.with_suffix(".md").write_text(markdown(report), "utf-8")
    log("\n" + markdown(report))
    log(llm.openai_summary_line())
    return 0


if __name__ == "__main__":
    sys.exit(main())

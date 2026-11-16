#!/usr/bin/env python3
"""Muse の「追記」（もう出ている記事への書き足し）を、事実確認に通してから記事に足す（2026-11-16）。

これまで: Muse は ~/Downloads/saisoku-articles/addenda/ に追記のファイルを置いていたが、運び役（scripts/muse_articles_push.py）は
フォルダの直下の「YYYYMMDD-….md」しか見ないので、追記は1本もサイトに届いていなかった（ドコモの復旧の追記は手で入れた）。

流れ:
  1. Mac: addenda/*.md → scripts/muse_articles_push.py が content/muse_inbox/addenda/ に入れて main に push
  2. Actions（muse_inbox.yml の「Muse addenda」の段）: このスクリプトが1本ずつ
     - 対象の記事を決める。ファイルの先頭（本文の最初の「## 」より前。--- の欄なら title / notes / target）に書かれた
       slug（記事の URL の最後の部分）のうち、本当にある記事が「ちょうど1本」のときだけ。決められなければ足さない（推測しない）
     - 出典（「出典：… URL」の行・--- の sources）の公式ページを読み、追記の文をそのページと突き合わせる
       （Muse の記事と同じ事実確認 quality.fact_check・同じ合格点 muse_articles.MUSE_PASS_SCORE。落とす理由は嘘だけ）
     - もう過ぎた予定を「これから」と書いていないか（source_date）・追記で新しい不合格が増えていないか（quality.added_problems）
     - 合格: 本文の最初の章のあとに「## 続報（M月D日）：見出し」の章を足し、更新履歴（updates。kind: followup）を1行書く
       （scripts/updated_at.py の touch_updated。手で入れたドコモの追記と同じ形）。記事の museAddenda にファイル名を残す＝二重に足さない
  3. 結果: state/muse_articles.json の items["addenda/<ファイル名>"]（Mac の運び役が addenda/done・addenda/rejected に移す）

  python3 scripts/muse_addenda.py                   # muse_inbox.yml から
  python3 scripts/muse_addenda.py --check <file.md>  # 対象の記事と形だけ確かめる（LLM・ネットを使わない。何も書かない）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import muse_articles  # noqa: E402
import muse_format  # noqa: E402
import source_date  # noqa: E402
import updated_at  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"
INBOX = ROOT / "content" / "muse_inbox" / "addenda"
KEY_PREFIX = "addenda/"  # state/muse_articles.json の items の名前（記事の入稿と取り違えない）
SITE = "https://ai-tech-express.jp"
JST = timezone(timedelta(hours=9))
BODY_MIN = 80  # 地の文の字数
BODY_MAX = 5000
MAX_SOURCES = 8
MAX_TRIES = 4  # 事実確認の LLM が使えない回が続いたら、この回数で見送りにする（入稿に残り続けないように）
SLUG_RE = re.compile(r"(?<![A-Za-z0-9_-])[a-z0-9]+(?:-[a-z0-9]+)+(?![A-Za-z0-9_-])")
URL_RE = re.compile(r"https?://[^\s<>\"'）)」』]+")
SOURCE_LINE_RE = re.compile(r"^\s*(?:[-*・]\s*)?出典\s*[:：]\s*(.*)$")
HEADING_PREFIX_RE = re.compile(r"^(?:(?:追記用?|追加分?|続報|ブロック\s*[0-9０-９]+)\s*[:：]\s*)+")
# 編集部あての連絡の行（読者に見せる文ではない）。本文に入れない
EDITOR_LINE_RE = re.compile(r"^\s*(?:次に読む記事として|使い方\s*[:：]|対象(?:記事|スラッグ)?\s*[:：])")
NO_TARGET = ("対象の記事を1本に決められません。ファイルの先頭の行に「対象スラッグ: <記事の URL の最後の部分>」を書いてください"
             "（ledger.md の URL の /articles/ のうしろ）。記事1本につき追記のファイルも1つにします")


def log(message: str) -> None:
    print(message, flush=True)


class AddendumError(ValueError):
    """追記として受け取れない（理由は Muse に返す文）"""


def _split(text: str) -> tuple[str, str, list[dict]]:
    """(対象を探す先頭の部分, 本文, --- の欄の sources)"""
    text = muse_format.nfc(text).replace("\r\n", "\n").lstrip("﻿")
    m = re.match(r"\s*---\n(.*?)\n---[ \t]*\n(.*)\Z", text, re.S)
    if m:
        head, body = m.group(1), m.group(2)
        try:
            sources = muse_format.parse(text).get("sources") or []
        except muse_format.FormatError:
            sources = []
        # 対象は title / notes / target の行からだけ探す（sources の URL の中の語を slug と取り違えない）
        lines = [ln for ln in head.split("\n") if re.match(r"^(?:title|notes|target|slug|対象[^:：]*)\s*[:：]", ln.strip(), re.I)]
        return "\n".join(lines), body, sources
    first = re.search(r"^##\s", text, re.M)
    if not first:
        return text, "", []
    return text[: first.start()], text[first.start():], []


def target_candidates(head: str) -> list[str]:
    """先頭の部分に書かれた slug らしい語（順番どおり・重複なし）。記事の URL の形でも拾う"""
    out: list[str] = []
    for token in SLUG_RE.findall(URL_RE.sub(lambda m: m.group(0).rsplit("/articles/", 1)[-1] if "/articles/" in m.group(0) else " ", head)):
        if token not in out:
            out.append(token)
    return out


def resolve_target(head: str, articles_dir: Path | None = None) -> tuple[str | None, str]:
    """(slug, 理由)。先頭に書かれた slug のうち、本当にある記事がちょうど1本のときだけ slug を返す"""
    folder = articles_dir or ARTICLES_DIR
    found = [s for s in target_candidates(head) if (folder / f"{s}.json").exists()]
    if len(found) == 1:
        return found[0], ""
    if len(found) > 1:
        return None, f"対象の記事が{len(found)}本書かれています（{' / '.join(found[:4])}）。{NO_TARGET}"
    named = target_candidates(head)
    if named:
        return None, f"「{' / '.join(named[:3])}」という記事は見つかりません。{NO_TARGET}"
    return None, NO_TARGET


def _sources_of_line(rest: str) -> list[dict]:
    out, pos = [], 0
    for m in URL_RE.finditer(rest):
        name = rest[pos:m.start()].strip(" 　／/・、,:：-")
        out.append({"url": m.group(0).rstrip("。、.,"), "name": name, "facts": ""})
        pos = m.end()
    return out


def parse(text: str, filename: str = "", articles_dir: Path | None = None) -> dict:
    """{slug, heading, body, sources:[{url,name,facts}]}。受け取れない形なら AddendumError"""
    head, raw, sources = _split(text)
    slug, why = resolve_target(head, articles_dir)
    if not slug:
        raise AddendumError(why)
    lines_out: list[str] = []
    heading = ""
    in_source_list = False
    for line in raw.split("\n"):
        if re.fullmatch(r"\s*-{3,}\s*", line):
            continue
        if m := SOURCE_LINE_RE.match(line):
            found = _sources_of_line(m.group(1))
            sources += found
            in_source_list = not found  # 「出典：」だけの行のあとは、箇条書きの出典が続く
            continue
        if in_source_list:
            if not line.strip():
                continue
            if re.match(r"^\s*[-*・]\s+", line) and URL_RE.search(line):
                sources += _sources_of_line(re.sub(r"^\s*[-*・]\s+", "", line))
                continue
            in_source_list = False
        if EDITOR_LINE_RE.match(line):
            continue
        if h := re.match(r"^(#{1,6})\s+(.*?)\s*$", line):
            title = HEADING_PREFIX_RE.sub("", h.group(2)).strip()
            if not heading and len(h.group(1)) <= 2:
                heading = title
                continue
            # 追記は1つの章として足す。中の見出しは小見出し（###）にそろえる
            line = f"{'#' * max(3, len(h.group(1)))} {title}"
        lines_out.append(line.rstrip())
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(lines_out)).strip().replace("｜", "　")
    seen: set[str] = set()
    uniq = []
    for s in sources:
        url = str(s.get("url") or "").strip()
        if url and url not in seen:
            seen.add(url)
            uniq.append({"url": url, "name": str(s.get("name") or "").strip(), "facts": str(s.get("facts") or "")})
    problems = []
    if not heading:
        problems.append("追記の見出し（「## 」の行）がありません")
    length = muse_format.plain_len(body)
    if not BODY_MIN <= length <= BODY_MAX:
        problems.append(f"追記の本文の長さが合いません（{length}字。{BODY_MIN}〜{BODY_MAX}字）")
    if not uniq:
        problems.append("出典がありません。「出典：ページの名前 https://…」の行で、公式ページの URL を書いてください")
    if problems:
        raise AddendumError(" / ".join(problems))
    return {"slug": slug, "heading": heading.replace("｜", "　"), "body": body, "sources": uniq[:MAX_SOURCES], "file": muse_format.nfc(filename)}


def usable_sources(sources: list[dict]) -> tuple[list[dict], list[str]]:
    """(使える出典, 外した URL)。主要な報道機関（muse_format.press_outlet）は報道として使う。ほかの報道・ニュースブログは出典にしない"""
    import public_interest  # noqa: PLC0415

    keep, dropped = [], []
    for s in sources:
        outlet = muse_format.press_outlet(s["url"], s.get("name") or "")
        if outlet:
            keep.append({**s, "press": outlet})
        elif public_interest.is_press_url(s["url"]):
            dropped.append(s["url"])
        else:
            keep.append(s)
    return keep, dropped


def _norm(text: str) -> str:
    return re.sub(r"[\s　#*>\-|]+", "", text or "")


def already_applied(article: dict, add: dict) -> bool:
    """同じファイルをもう足した・同じ文がもう本文にある（手で入れた・名前を変えて置き直した）"""
    if add.get("file") and add["file"] in (article.get("museAddenda") or []):
        return True
    body = _norm(article.get("body") or "")
    first = next((p for p in re.split(r"\n\s*\n", add["body"]) if len(_norm(p)) >= 40 and not p.lstrip().startswith("#")), "")
    return bool(first) and _norm(first)[:120] in body


def target_problem(article: dict) -> str:
    if article.get("type") == "roundup" or article.get("disaster"):
        return "この記事（まとめ・地震や津波の記事）には追記を足せません"
    if not str(article.get("body") or "").strip():
        return "対象の記事に本文がありません"
    return ""


def insert_section(markdown: str, section: str) -> str:
    """最初の章のあとに足す。本文が地の文で始まる記事は最初の「## 」の前、見出しで始まる記事は2つ目の「## 」の前（無ければ末尾）"""
    text = (markdown or "").strip()
    heads = [m.start() for m in re.finditer(r"^## ", text, re.M)]
    if heads and heads[0] == 0:
        heads = heads[1:]
    if not heads:
        return text + "\n\n" + section.strip() + "\n"
    at = heads[0]
    return text[:at].rstrip() + "\n\n" + section.strip() + "\n\n" + text[at:]


def fact_check(article: dict, add: dict, source_text: str, multi: bool) -> dict:
    """追記の文だけを、追記の出典と突き合わせる。もとの記事の題名・概要・要点は確認済みの事実として渡す（scripts/followup.py と同じ）"""
    import quality  # noqa: PLC0415

    pseudo = {"title": add["heading"], "lede": "", "highlights": [], "body": add["body"], "easy": ""}
    if multi:
        pseudo["museSources"] = add["sources"]  # 出典が何本もあるときの長さ（quality.source_cap）
    known = "\n".join([f"タイトル: {article.get('title', '')}", f"概要: {article.get('description', '')}"]
                      + [f"要点: {h}" for h in article.get("highlights") or []])
    return quality.fact_check(pseudo, source_text, context=known)


def apply(article: dict, add: dict, now: datetime | None = None) -> dict:
    """追記を足した新しい記録（もとの dict は変えない）。更新日時と更新履歴は updated_at.touch_updated だけが書く"""
    now = now or datetime.now(timezone.utc)
    record = json.loads(json.dumps(article, ensure_ascii=False))
    local = now.astimezone(JST)
    cites = " ／ ".join(f"[{s.get('name') or s['url']}]({s['url']})" for s in add["sources"])
    section = f"## 続報（{local.month}月{local.day}日）：{add['heading']}\n\n{add['body']}\n\n出典: {cites}"
    record["body"] = insert_section(record.get("body") or "", section)
    if record.get("writer") == "muse" or record.get("museSources"):
        listed = [s for s in record.get("museSources") or [] if isinstance(s, dict) and s.get("url")]
        if not listed and record.get("sourceUrl"):
            listed = [{"url": record["sourceUrl"], "name": str(record.get("sourceName") or "")}]
        for s in add["sources"]:
            if all(x["url"] != s["url"] for x in listed):
                listed.append({"url": s["url"], "name": s.get("name") or ""})
        record["museSources"] = listed
    first = add["sources"][0]
    updated_at.touch_updated(record, "followup", at=now.isoformat(timespec="seconds"), title=f"「{add['heading']}」を追記しました",
                             source_url=first["url"], source_name=first.get("name") or "")
    if add.get("file"):
        record["museAddenda"] = [*(record.get("museAddenda") or []), add["file"]]
    return record


def review(path: Path, tries: int = 0) -> tuple[str, str, dict | None]:
    """("applied", slug, record) / ("already", slug, None) / ("reject", 理由, None) / ("retry", 理由, None)"""
    try:
        add = parse(path.read_text("utf-8"), path.name)
    except (OSError, UnicodeDecodeError) as error:
        return "reject", f"ファイルを読めません（{str(error)[:60]}）", None
    except AddendumError as error:
        return "reject", str(error), None
    target = ARTICLES_DIR / f"{add['slug']}.json"
    try:
        article = json.loads(target.read_text("utf-8"))
    except (OSError, ValueError) as error:
        return "reject", f"対象の記事を読めません（{add['slug']}: {str(error)[:60]}）", None
    if why := target_problem(article):
        return "reject", why, None
    if already_applied(article, add):
        return "already", add["slug"], None
    today = datetime.now(JST).date()
    texts = [add["heading"], add["body"]]
    if dated := source_date.past_change(texts, today):
        return "reject", "日付: " + dated[0][:400], None
    add["sources"], dropped = usable_sources(add["sources"])
    if not add["sources"]:
        return "reject", "報道機関のページだけでは追記の出典にできません。公式の発表のページを出典にしてください: " + " / ".join(dropped[:3]), None
    unread: list[str] = []
    fetched = muse_articles.fetch_sources(add["sources"], skip_unreadable_first=True, unread=unread)
    if not fetched:
        return "reject", "出典（公式ページ）を1本も読めませんでした。URL が正しいか、ログインなしで開けるページかを確かめてください", None
    if dated := source_date.check(texts, fetched, today):
        return "reject", "日付: " + dated[0][:400], None
    tail = ("\n読めなかった出典（ここにだけ書かれた事実は確かめられません）: " + " / ".join(unread[:5])) if unread else ""
    source_text = muse_articles.source_text_of(fetched, add["heading"])
    try:
        fact = fact_check(article, add, source_text, multi=len(fetched) > 1)
    except Exception as error:  # noqa: BLE001 - LLM が使えない回は見送りにせず、次の回にもう一度
        if tries + 1 >= MAX_TRIES:
            return "reject", f"事実確認を{MAX_TRIES}回実行できませんでした（{str(error)[:100]}）。時間をおいて置き直してください", None
        return "retry", f"事実確認を実行できませんでした（{str(error)[:100]}）。次の回にもう一度試します", None
    need = muse_articles.MUSE_PASS_SCORE
    log(f"   [addenda] 事実確認 grounded={fact['grounded']} score={fact['score']}（必要 {need}） {' | '.join(fact['problems'][:3])[:300]}")
    if not (fact["grounded"] and fact["score"] >= need):
        why = " / ".join(fact["problems"][:4]) or f"出典との整合性が低い（{fact['score']}点。{need}点以上）"
        return "reject", f"事実確認で不合格: {why[:600]}{tail}", None
    # 読めた出典だけを記事に残す（読めなかったページを出典として見せない）
    add["sources"] = [{"url": s["url"], "name": s.get("name") or s.get("title") or "", "facts": ""} for s in fetched]
    record = apply(article, add)
    # すべての段で同じ合格の基準（scripts/web_articles.py の続報と同じ）: 追記で新しく増えた不合格（文体の決まり・投資の助言・
    # 自分で試したような書き方・センシティブ）があれば足さない。もとの記事にもとからある分は数えない
    import quality  # noqa: PLC0415

    if added := quality.added_problems(article, record):
        return "reject", "追記の書き方（直して置き直してください）: " + " / ".join(added[:3])[:400], None
    return "applied", add["slug"], record


def report(applied: int) -> None:
    """muse_inbox.yml の「Commit & push」の段に、記事に足した本数を渡す（1本以上ならデプロイする）"""
    if gh := os.environ.get("GITHUB_OUTPUT"):
        with open(gh, "a", encoding="utf-8") as fh:
            fh.write(f"applied={applied}\n")


def process(args) -> int:
    files = sorted(INBOX.glob("*.md")) if INBOX.exists() else []
    applied = 0
    if not files:
        log("[addenda] 追記はありません")
    results = muse_articles.load_results()
    started = time.time()
    for path in files:
        name = muse_format.nfc(path.name)
        key = KEY_PREFIX + name
        if applied >= args.max or time.time() - started > args.budget:
            log(f"[addenda] この回はここまで（残りは次の回）: {name}")
            break
        log(f"\n[addenda] {name}")
        tries = int((results["items"].get(key) or {}).get("tries") or 0)
        status, out, record = review(path, tries)
        row = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "kind": "addendum", "title": f"追記: {name}"}
        if status == "retry":
            results["items"][key] = {**row, "status": "waiting", "reason": out, "tries": tries + 1}
            muse_articles.save_results(results)
            log(f"   [addenda] {out}（入稿はそのまま残します）")
            break
        if status == "applied":
            (ARTICLES_DIR / f"{out}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            applied += 1
            report(applied)  # 1本ごとに書く（途中で時間切れになっても、足した回はデプロイされるように。同じ名前は最後の行が使われる）
        if status in ("applied", "already"):
            row.update({"status": "published", "slug": out, "url": f"{SITE}/articles/{out}",
                        "reason": "" if status == "applied" else "この追記はもう記事に入っています（足していません）"})
        else:
            row.update({"status": "rejected", "reason": out[:1200]})
        results["items"][key] = row
        muse_articles.save_results(results)
        path.unlink(missing_ok=True)
        log(f"   [addenda] → {status} {out[:200]}")
    report(applied)
    log(f"\n[addenda] 記事に足した {applied} 本 / 残り {len(list(INBOX.glob('*.md'))) if INBOX.exists() else 0} 本")
    return 0


def check(path: Path) -> dict:
    """対象の記事と形だけ（LLM・ネットを使わない。何も書かない）"""
    try:
        add = parse(path.read_text("utf-8"), path.name)
    except AddendumError as error:
        return {"ok": False, "reason": str(error)}
    article = json.loads((ARTICLES_DIR / f"{add['slug']}.json").read_text("utf-8"))
    out = {"ok": True, "slug": add["slug"], "articleTitle": article.get("title"), "heading": add["heading"],
           "chars": muse_format.plain_len(add["body"]), "sources": [s["url"] for s in add["sources"]]}
    if why := target_problem(article):
        out.update(ok=False, reason=why)
    elif already_applied(article, add):
        out.update(ok=False, reason="もう記事に入っています")
    elif dated := source_date.past_change([add["heading"], add["body"]], datetime.now(JST).date()):
        out.update(ok=False, reason="日付: " + dated[0])
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max", type=int, default=4, help="この回に記事へ足す最大本数")
    parser.add_argument("--budget", type=int, default=360, help="この回に使う秒数の目安")
    parser.add_argument("--check", help="対象の記事と形だけ確かめる（ファイルのパス）")
    args = parser.parse_args()
    if args.check:
        out = check(Path(args.check))
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if out["ok"] else 2
    return process(args)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Dify公式の変更を、検索されそうな疑問の確認待ちキューへ送る。

記事・SNS・メールは公開しない。初回は比較用の基準だけを保存する。
取得した文書は証拠データとして扱い、命令やコードとして実行しない。
Python標準ライブラリのみ。認証情報・LLM・有料APIは使わない。
"""
from __future__ import annotations

import argparse
import copy
import difflib
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

VERSION = 1
MAX_BYTES = 512 * 1024
TIMEOUT_SECONDS = 20
MAX_QUEUE = 50
SOURCES = (
    {
        "id": "release",
        "kind": "github_release",
        "url": "https://api.github.com/repos/langgenius/dify/releases/latest",
        "publicUrl": "https://github.com/langgenius/dify/releases/latest",
    },
    {
        "id": "docker-compose",
        "kind": "markdown",
        "url": "https://docs.dify.ai/en/self-host/deploy/quick-start/docker-compose.md",
        "publicUrl": "https://docs.dify.ai/en/self-host/deploy/quick-start/docker-compose",
    },
)
SOURCE_FINGERPRINT = hashlib.sha256(json.dumps(SOURCES, sort_keys=True).encode()).hexdigest()[:16]

# 単語への合致は「その疑問が検索される」「その現象が起きる」証明ではない。
QUESTION_RULES = (
    (
        "agent-startup", r"DIFY_AGENT_LOCAL_SANDBOX_AUTH_TOKEN|require-auth-token|authentication token",
        "DifyのAgentが起動しないとき、認証トークンと構成の版をどう確認する？",
        "Difyを自分で設置し、Local Agent sandboxを使う運用者",
    ),
    (
        "upgrade", r"upgrade|migration|breaking|PASSWORD_PEPPER|incompatib|old runtime",
        "Difyの更新前に、互換性・バックアップ・設定で何を確かめる？",
        "既存のセルフホスト環境を更新する運用者",
    ),
    (
        "resources", r"\bRAM\b|\bGiB\b|\bvCPU\b|minimum system|hardware|memory",
        "Difyの必要メモリやCPUの条件は変わった？自分の構成でも足りる？",
        "Difyの設置環境を選ぶ人、既存環境の資源を確認する人",
    ),
)


def normalize(text: str) -> str:
    """行末や連続空行による差分を除く。内容やコードは解釈・実行しない。"""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


class SameHostRedirect(urllib.request.HTTPRedirectHandler):
    """公式URLから別ホスト・HTTPへの転送は取得前に拒否する。"""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        before, after = urllib.parse.urlparse(req.full_url), urllib.parse.urlparse(newurl)
        if after.scheme != "https" or after.hostname != before.hostname or after.username or after.password:
            raise ValueError("unexpected redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_source(source: dict) -> bytes:
    request = urllib.request.Request(source["url"], headers={
        "User-Agent": "SaisokuDifySourceWatch/1.0 (+https://ai-tech-express.jp)",
        "Accept": "application/json" if source["kind"] == "github_release" else "text/markdown, text/plain",
    })
    with urllib.request.build_opener(SameHostRedirect()).open(request, timeout=TIMEOUT_SECONDS) as response:
        if response.status != 200:
            raise ValueError("unexpected HTTP status")
        mime = response.headers.get_content_type()
        expected = {"application/json"} if source["kind"] == "github_release" else {"text/markdown", "text/plain"}
        if mime not in expected:
            raise ValueError("unexpected content type")
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("source exceeds size limit")
    return data


def parse_source(source: dict, raw: bytes) -> dict:
    if len(raw) > MAX_BYTES:
        raise ValueError("source exceeds size limit")
    text = raw.decode("utf-8")
    if source["kind"] == "github_release":
        release = json.loads(text)
        if not isinstance(release, dict):
            raise ValueError("unexpected release response")
        if release.get("draft") is not False or release.get("prerelease") is not False:
            raise ValueError("not a published stable release")
        tag = release.get("tag_name", "")
        if not re.fullmatch(r"v?\d+\.\d+\.\d+(?:[.+-][A-Za-z0-9.-]+)?", tag):
            raise ValueError("unexpected release tag")
        url = release.get("html_url", "")
        if url != f"https://github.com/langgenius/dify/releases/tag/{tag}":
            raise ValueError("unexpected release URL")
        body = release.get("body")
        if not isinstance(body, str) or len(body.strip()) < 30:
            raise ValueError("missing release notes")
        # download_count・更新時刻・作者アイコンなどは本文変更として扱わない。
        text = normalize(f"# {tag}\n{release.get('name', '')}\n\n{body}")
        meta = {"sourceUrl": url, "releaseTag": tag, "publishedAt": release.get("published_at")}
    else:
        # ドキュメント索引の共通前置きは監視対象から除く。
        match = re.search(r"(?m)^# Deploy Dify with Docker Compose\s*$", text)
        if not match or "Before Deployment" not in text:
            raise ValueError("expected documentation body missing")
        text = normalize(text[match.start():])
        meta = {"sourceUrl": source["publicUrl"]}
    return {**meta, "text": text, "hash": hashlib.sha256(text.encode()).hexdigest()}


def excerpt(lines: list[str], pattern: str = "") -> str:
    """確認用に短い原文だけを保持（前後各12語以内）。全文はURLへ戻る。"""
    candidates = [line for line in lines if line.strip()]
    if pattern:
        matching = [line for line in candidates if re.search(pattern, line, re.I)]
        candidates = matching or candidates
    if not candidates:
        return ""
    line = candidates[0].strip()
    words = list(re.finditer(r"\S+", line))[:12]
    return line[:min(words[-1].end() if words else 0, 160)]


def candidates_for(source: dict, before: dict, after: dict, observed_at: str) -> list[dict]:
    removed, added = [], []
    for line in difflib.ndiff(before["text"].splitlines(), after["text"].splitlines()):
        if line.startswith("- "):
            removed.append(line[2:])
        elif line.startswith("+ "):
            added.append(line[2:])
    changed_text = "\n".join(removed + added)
    matched = [rule for rule in QUESTION_RULES if re.search(rule[1], changed_text, re.I)]
    if not matched:
        matched = [("general", "", "Difyの公式説明で何が変わり、既存の利用者に確認が必要？", "変更内容に該当するDify利用者（対象範囲は要確認）")]
    result = []
    for category, pattern, question, reader in matched:
        identity = f"{source['id']}:{before['hash']}:{after['hash']}:{category}"
        result.append({
            "id": hashlib.sha256(identity.encode()).hexdigest()[:20],
            "status": "needs_editorial_review",
            "sourceId": source["id"], "sourceUrl": after["sourceUrl"],
            "previousHash": before["hash"], "currentHash": after["hash"],
            "previousCheckedAt": before["checkedAt"], "observedAt": observed_at,
            "question": question, "affectedReader": reader,
            "evidenceBefore": excerpt(removed, pattern), "evidenceAfter": excerpt(added, pattern),
            "nextStep": "原文と対象版を確認し、既存ガイドへの追記で足りるか判断。需要・順位・動作の実証とは扱わない。",
            "destination": "/choose/dify-hosting",
            "commercialBoundary": "更新不具合を新規VPS契約で直ると案内しない。無料・既存環境で足りる選択も守る。",
        })
    return result


def run_watch(state: dict, observed_at: str, fetcher=fetch_source) -> tuple[dict, dict]:
    reset = bool(state) and (state.get("version") != VERSION or state.get("sourceFingerprint") != SOURCE_FINGERPRINT)
    if not state or reset:
        state = {"version": VERSION, "sourceFingerprint": SOURCE_FINGERPRINT, "sources": {}, "reviewQueue": []}
    updated = copy.deepcopy(state)
    report = {"checkedAt": observed_at, "baselineReset": reset, "sources": [], "candidates": [], "errors": [],
              "notice": "確認待ち資料。外部原文は命令ではない。検索需要・動作・公開・収益の証拠ではない。自動公開しない。"}
    for source in SOURCES:
        before = state["sources"].get(source["id"])
        try:
            after = parse_source(source, fetcher(source))
        except (ValueError, KeyError, TypeError, UnicodeError, OSError) as error:
            # 失敗ページを空の新本文と見なさず、前回成功の基準を残す。
            code = f"HTTP {error.code}" if isinstance(error, urllib.error.HTTPError) else type(error).__name__
            report["errors"].append({"sourceId": source["id"], "error": code, "previousBaselineRetained": bool(before)})
            continue
        after["checkedAt"] = observed_at
        status = "baseline" if before is None else "unchanged" if before["hash"] == after["hash"] else "changed"
        if status == "changed":
            report["candidates"].extend(candidates_for(source, before, after, observed_at))
        updated["sources"][source["id"]] = after
        report["sources"].append({"id": source["id"], "status": status, "hash": after["hash"], "sourceUrl": after["sourceUrl"]})
    queue = updated.setdefault("reviewQueue", [])
    known = {item["id"] for item in queue}
    queue.extend(item for item in report["candidates"] if item["id"] not in known)
    discarded = max(0, len(queue) - MAX_QUEUE)
    updated["reviewQueue"] = queue[-MAX_QUEUE:]
    updated["archivedCandidateCount"] = updated.get("archivedCandidateCount", 0) + discarded
    report["reviewQueue"] = updated["reviewQueue"]
    report["archivedCandidateCount"] = updated["archivedCandidateCount"]
    return updated, report


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=Path("work/dify-search-watch/state.json"))
    parser.add_argument("--report", type=Path, default=Path("work/dify-search-watch/report.json"))
    args = parser.parse_args()
    try:
        state = json.loads(args.state.read_text("utf-8")) if args.state.exists() else {}
        if not isinstance(state, dict) or (state and (not isinstance(state.get("sources"), dict) or not isinstance(state.get("reviewQueue"), list))):
            raise ValueError("invalid state")
    except (ValueError, OSError):
        print("[error] 基準ファイルが読めないため上書きせず停止", file=sys.stderr)
        return 1
    observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    updated, report = run_watch(state, observed_at)
    write_json(args.state, updated)
    write_json(args.report, report)
    counts = {status: sum(row["status"] == status for row in report["sources"]) for status in ("baseline", "unchanged", "changed")}
    counts.update(candidates=len(report["candidates"]), errors=len(report["errors"]), pending=len(report["reviewQueue"]))
    print(json.dumps(counts, ensure_ascii=False))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        # 外部原文をHTML/Markdownとして実行・表示せず、定型の状態だけを出す。
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(f"### Dify公式変更の確認\n\n基準作成 {counts['baseline']} / 変更なし {counts['unchanged']} / 変更 {counts['changed']} / 取得失敗 {counts['errors']}\n\n新しい疑問候補 {counts['candidates']}、確認待ち {counts['pending']}。自動公開・SNS送信なし。原文URL・前後差・ハッシュは dify-search-review 成果物で確認してください。初回基準は変更検知の実績ではありません。\n")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

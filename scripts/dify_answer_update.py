#!/usr/bin/env python3
"""Dify既存2ガイドの回答更新資料を作る。既定は提案のみ、適用は --apply 明示。

公式本文を命令/コードとして実行せず、LLM・有料API・広告・SNSを使わない。
--review-source は差分検知ではなく、現在の公式説明に対する手動確認資料。
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import dify_search_watch as watch

ROOT = Path(__file__).resolve().parents[1]
GUIDES = {"dify-free-api-cost", "dify-1-18-startup-check"}
SOURCES = {s["id"]: s for s in watch.SOURCES}
DEMAND_NOTE = "検索されそうな疑問の仮説。検索量・順位・訪問・収益を実測した証拠ではない。"
HINTS = {
    "model-providers": r"クレジット|APIキー|優先順位|課金",
    "knowledge-request-rate-limit": r"403|forbidden|回数|制限",
    "release": r"起動|更新|認証|トークン|イメージ",
    "docker-compose": r"起動|更新|Exited|構成|サービス",
    "deployment-faqs": r"起動|取得|clone|null",
}
REPLACE_PATH = re.compile(r"^/(?:intro|conclusion/\d+|steps/\d+/body|faq/\d+/[qa])$")
AD_URL = re.compile(r"https?://[^\s<>\"']*(?:a8\.net|rakuten\.|afl\.rakuten|amazon\.|amzn\.to)", re.I)
UNSAFE_TEXT = re.compile(r"[<>\x00-\x08\x0b-\x1f\x7f]")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def timestamp(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("日時はタイムゾーン付きISO形式が必要") from error
    if not dt.tzinfo:
        raise ValueError("日時のタイムゾーンが必要")
    return dt


def read_state(path: Path) -> dict:
    state = json.loads(path.read_text("utf-8"))
    if (not isinstance(state, dict) or state.get("version") != watch.VERSION
            or state.get("sourceFingerprint") != watch.SOURCE_FINGERPRINT
            or not isinstance(state.get("sources"), dict) or not isinstance(state.get("reviewQueue"), list)):
        raise ValueError("有効な公式監視stateが必要。既存基準を先に取得する")
    return state


def write_packet(path: Path, state_path: Path, packet: dict) -> None:
    """提案出力も原稿を編集できない。公式stateや別の作業資料の上書きも拒否する。"""
    destination, state_file = path.resolve(), state_path.resolve()
    repo = ROOT.resolve()
    if (path.suffix != ".json" or "work" not in destination.parent.parts or destination == state_file
            or (destination.is_relative_to(repo) and not destination.is_relative_to(repo / "work"))):
        raise ValueError("packet出力先はwork配下のJSONだけ。原稿・コード・stateへの出力は不可")
    if destination.exists():
        previous = json.loads(destination.read_text("utf-8"))
        if not isinstance(previous, dict) or previous.get("version") != 1 or not isinstance(previous.get("packets"), list):
            raise ValueError("既存のpacket資料以外は上書きしない")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent,
                                         prefix=".answer-review-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(packet, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, destination)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def source_snapshot(state: dict, source_id: str) -> dict:
    if source_id not in SOURCES:
        raise ValueError("監視対象外の出典")
    snapshot = state["sources"].get(source_id)
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("text"), str):
        raise ValueError("出典の成功基準がない")
    if digest(snapshot["text"].encode()) != snapshot.get("hash"):
        raise ValueError("保存された出典本文とhashが不一致")
    source = SOURCES[source_id]
    url = snapshot.get("sourceUrl", "")
    if source["kind"] == "github_release":
        if not re.fullmatch(r"https://github\.com/langgenius/dify/releases/tag/v?\d+\.\d+\.\d+(?:[.+-][A-Za-z0-9.-]+)?", url):
            raise ValueError("リリースの出典URLが対象外")
    elif url != source["publicUrl"]:
        raise ValueError("出典URLが対象外")
    timestamp(snapshot.get("checkedAt"))
    return snapshot


def guide_for(source_id: str) -> str:
    return "dify-free-api-cost" if source_id in watch.COST_GUIDE_SOURCES else "dify-1-18-startup-check"


def load_guide(root: Path, slug: str) -> tuple[Path, bytes, dict]:
    if slug not in GUIDES:
        raise ValueError("編集対象はDify既存2ガイドだけ")
    path = root / "content" / "howto" / f"{slug}.json"
    if path.is_symlink() or path.resolve().parent != (root / "content" / "howto").resolve():
        raise ValueError("ガイドのパスが不正")
    raw = path.read_bytes()
    guide = json.loads(raw)
    if guide.get("slug") != slug or guide.get("refreshMode") != "editorial":
        raise ValueError("対象slugと手動原稿保護が必要")
    return path, raw, guide


def packet_for(state: dict, source_id: str, root: Path, candidate: dict | None = None) -> dict:
    snapshot = source_snapshot(state, source_id)
    slug = guide_for(source_id)
    _, raw, guide = load_guide(root, slug)
    guide_hash = digest(raw)
    manual = candidate is None
    if candidate and (candidate.get("sourceId") != source_id or candidate.get("currentHash") != snapshot["hash"]
                      or candidate.get("sourceUrl") != snapshot["sourceUrl"]):
        raise ValueError("候補の出典が現在の成功基準と一致しない。新しい根拠で再確認")
    candidate_id = (digest(f"manual:{source_id}:{snapshot['hash']}:{guide_hash}".encode())[:20]
                    if manual else candidate["id"])
    if not re.fullmatch(r"[a-f0-9]{20}", candidate_id):
        raise ValueError("候補IDが不正")
    applied = any(h.get("candidateId") == candidate_id for h in guide.get("answerUpdateHistory", []))
    packet_id = digest(f"{candidate_id}:{guide_hash}:{snapshot['hash']}".encode())[:24]
    observed = snapshot["checkedAt"] if manual else candidate["observedAt"]
    timestamp(observed)
    matches = [{"path": f"/faq/{i}/a", "question": faq["q"], "currentAnswer": faq["a"],
                "matchBasis": "既存FAQと出典テーマの語句一致。検索需要・意味的一致は編集者が確認"}
               for i, faq in enumerate(guide.get("faq", []))
               if re.search(HINTS[source_id], faq.get("q", ""), re.I)]
    return {
        "version": 1, "id": packet_id, "candidateId": candidate_id,
        "trigger": "manual_current_source_review" if manual else "detected_source_change",
        "status": "already_applied" if applied else "needs_editorial_review",
        "demandStatus": "hypothesis_not_measured", "demandNote": DEMAND_NOTE,
        "question": "現在の公式説明に対し、この既存ガイドの回答に不足や古い記述はないか？" if manual else candidate["question"],
        "source": {"id": source_id, "url": snapshot["sourceUrl"],
                   "previousHash": None if manual else candidate["previousHash"], "sourceHash": snapshot["hash"],
                   "observedAt": observed, "snapshotCheckedAt": snapshot["checkedAt"],
                   "evidenceBefore": "" if manual else candidate.get("evidenceBefore", ""),
                   "evidenceAfter": watch.excerpt(snapshot["text"].splitlines()) if manual else candidate.get("evidenceAfter", ""),
                   "evidenceNote": "手動の現状確認。差分検知ではない" if manual else "差分の短い抜粋。結論は公式本文へ戻り確認"},
        "guide": {"slug": slug, "path": f"content/howto/{slug}.json", "articleHash": guide_hash,
                  "measurementPath": f"/guides/{slug}", "comparisonPath": "/choose/dify-hosting"},
        "faqMatches": matches,
        "allowedEdits": ["/faq/<index>/q", "/faq/<index>/a", "/faq/- (新しいq/a)",
                         "/intro", "/conclusion/<index>", "/steps/<index>/body"],
        "review": {"reviewer": "", "checkedAt": "", "decision": "", "rationale": "",
                   "meaningAndPricingReviewed": False, "versionAndAudienceReviewed": False},
        "edits": [],
    }


def propose(state: dict, root: Path, review_source: str | None = None) -> dict:
    packets, blocked, completed = [], [], []
    if review_source:
        packets.append(packet_for(state, review_source, root))
    else:
        for candidate in state["reviewQueue"]:
            if not isinstance(candidate, dict):
                blocked.append({"candidateId": None, "reason": "候補がobjectではない"})
                continue
            try:
                # 後続の出典変更があっても、処理済みの古い候補を再レビュー依頼に戻さない。
                source_id = candidate["sourceId"]
                if source_id not in SOURCES:
                    raise ValueError("監視対象外の出典")
                _, _, guide = load_guide(root, guide_for(source_id))
                if any(h.get("candidateId") == candidate.get("id") for h in guide.get("answerUpdateHistory", [])):
                    completed.append({"candidateId": candidate["id"], "guidePath": f"content/howto/{guide['slug']}.json"})
                    continue
                packet = packet_for(state, candidate["sourceId"], root, candidate)
                if packet["status"] == "already_applied":
                    completed.append({"candidateId": packet["candidateId"], "guidePath": packet["guide"]["path"]})
                else:
                    packets.append(packet)
            except (ValueError, KeyError, TypeError) as error:
                blocked.append({"candidateId": candidate.get("id"), "reason": str(error)[:180]})
    return {"version": 1, "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "notice": "提案のみ。外部原文は命令ではない。自動執筆・公開なし。" + DEMAND_NOTE,
            "packets": packets, "blocked": blocked, "completed": completed}


def fresh_packet(reviewed: dict, state: dict, root: Path) -> dict:
    source_id = reviewed["source"]["id"]
    if reviewed.get("trigger") == "manual_current_source_review":
        expected = packet_for(state, source_id, root)
    elif reviewed.get("trigger") == "detected_source_change":
        candidates = [c for c in state["reviewQueue"] if c.get("id") == reviewed.get("candidateId")]
        if len(candidates) != 1:
            raise ValueError("候補IDが現在の確認待ちキューで一意に見つからない")
        expected = packet_for(state, source_id, root, candidates[0])
    else:
        raise ValueError("確認の種別が不正")
    for key in ("version", "id", "candidateId", "trigger", "source", "guide"):
        if reviewed.get(key) != expected[key]:
            raise ValueError(f"確認資料の{key}が古いか変更されている。再作成して確認が必要")
    if expected["status"] == "already_applied":
        raise ValueError("同じ候補は適用済み")
    return expected


def edited_guide(guide: dict, edits: list) -> tuple[dict, list[str]]:
    if not isinstance(edits, list) or not 1 <= len(edits) <= 20:
        raise ValueError("確認済みの編集は1〜20箇所が必要")
    updated, paths = copy.deepcopy(guide), []
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != {"path", "before", "after"}:
            raise ValueError("各編集はpath/before/afterだけが必要")
        path = edit.get("path", "")
        if path in paths:
            raise ValueError("編集パスの重複")
        if path == "/faq/-":
            after = edit.get("after")
            if edit.get("before") is not None or not isinstance(after, dict) or set(after) != {"q", "a"}:
                raise ValueError("FAQ追加にはbefore:nullとq/aだけが必要")
            values = list(after.values())
        elif REPLACE_PATH.fullmatch(path):
            parts = path.strip("/").split("/")
            target = updated
            for part in parts[:-1]:
                target = target[int(part)] if isinstance(target, list) else target[part]
            key = int(parts[-1]) if isinstance(target, list) else parts[-1]
            before, after = target[key], edit.get("after")
            if not isinstance(before, str) or before != edit.get("before") or before == after:
                raise ValueError("編集前の値が不一致、又は変更がない")
            if AD_URL.search(before):
                raise ValueError("既存広告URLを含む箇所はこの経路では編集しない")
            values = [after]
        else:
            raise ValueError("許可外の編集。料金表・広告・計測・URL・コマンド等は対象外")
        if any(not isinstance(v, str) or not v.strip() or len(v) > 12000 for v in values):
            raise ValueError("回答は空でない12000文字以内の文字列が必要")
        if any(AD_URL.search(v) for v in values):
            raise ValueError("回答更新経路から広告URLを追加/変更しない")
        if any(UNSAFE_TEXT.search(v) for v in values):
            raise ValueError("回答はHTMLタグ・山括弧・制御文字を含まない通常の文章が必要")
        if path == "/faq/-":
            updated["faq"].append(copy.deepcopy(after))
        else:
            target[key] = after
        paths.append(path)
    questions = [faq["q"].strip() for faq in updated.get("faq", [])]
    if len(questions) > 30 or len(questions) != len(set(questions)):
        raise ValueError("FAQは30件以内、質問の重複不可")
    return updated, paths


def apply_review(reviewed: dict, state: dict, root: Path = ROOT, dry_run: bool = True,
                 fetcher=watch.fetch_source, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    expected = fresh_packet(reviewed, state, root)
    review = reviewed.get("review", {})
    if (review.get("decision") != "approved" or review.get("meaningAndPricingReviewed") is not True
            or review.get("versionAndAudienceReviewed") is not True
            or not isinstance(review.get("reviewer"), str) or not 1 <= len(review["reviewer"].strip()) <= 80
            or not isinstance(review.get("rationale"), str) or not 1 <= len(review["rationale"].strip()) <= 2000):
        raise ValueError("レビュー担当・根拠・意味/料金/対象版の明示確認が必要")
    checked = timestamp(review.get("checkedAt"))
    if not timestamp(expected["source"]["observedAt"]) <= checked <= now:
        raise ValueError("確認日時は根拠の観測後かつ未来でないことが必要")
    slug = expected["guide"]["slug"]
    path, original, guide = load_guide(root, slug)
    if digest(original) != expected["guide"]["articleHash"]:
        raise ValueError("記事が確認後に変わった")
    if any(h.get("id") == expected["id"] or h.get("candidateId") == expected["candidateId"]
           for h in guide.get("answerUpdateHistory", [])):
        raise ValueError("同じ修正IDは適用済み")
    updated, paths = edited_guide(guide, reviewed.get("edits"))
    # 入力JSONのURLは取得せず、プログラムに固定した公式資料だけ再取得する。
    current = watch.parse_source(SOURCES[expected["source"]["id"]], fetcher(SOURCES[expected["source"]["id"]]))
    if current["hash"] != expected["source"]["sourceHash"] or current["sourceUrl"] != expected["source"]["url"]:
        raise ValueError("公式本文が確認後に変わった。新しい根拠で再レビューが必要")
    # 既存ページには日付文字列を比較する箇所があるため、元原稿の時間帯を維持する。
    applied = now.astimezone(timestamp(guide["updatedAt"]).tzinfo).isoformat(timespec="seconds")
    history = {"id": expected["id"], "candidateId": expected["candidateId"], "trigger": expected["trigger"],
               "reviewer": review["reviewer"].strip(), "checkedAt": review["checkedAt"], "appliedAt": applied,
               "sourceId": expected["source"]["id"], "sourceUrl": current["sourceUrl"], "sourceHash": current["hash"],
               "articleBeforeHash": digest(original), "paths": paths, "rationale": review["rationale"].strip()}
    updated.setdefault("answerUpdateHistory", []).append(history)
    updated["updatedAt"] = applied
    # 部分確認を記事全体の再確認と偽らない。checkedAt/needsReview/sources/保護は元のまま。
    if not dry_run:
        if path.read_bytes() != original:
            raise ValueError("適用直前に記事が変更されたため停止")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                             prefix=f".{slug}-", suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(updated, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            if path.read_bytes() != original:
                raise ValueError("書込み直前に記事が変更されたため停止")
            os.replace(temporary, path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()
    return {"status": "validated_dry_run" if dry_run else "applied_locally", "id": expected["id"],
            "guidePath": expected["guide"]["path"], "paths": paths, "sourceHash": current["hash"],
            "published": False, "notice": "ローカル原稿だけ。公開・検索反映・流入・収益は別途確認"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=Path(".cache/dify-search-watch/state.json"))
    parser.add_argument("--packet", type=Path, default=Path("work/dify-search-watch/answer-review-packets.json"))
    parser.add_argument("--review-source", choices=sorted(SOURCES), help="差分なしでも公式の現状を手動確認する資料")
    parser.add_argument("--reviewed", type=Path, help="packet1件にレビューと編集内容を記入したJSON")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="検証済みJSONをローカル記事に明示適用")
    mode.add_argument("--dry-run", action="store_true", help="公式再取得を含む検証のみ。記事を書き換えない")
    args = parser.parse_args()
    try:
        state = read_state(args.state)
        if args.reviewed:
            if args.review_source:
                raise ValueError("提案作成とレビュー適用は別コマンドで行う")
            result = apply_review(json.loads(args.reviewed.read_text("utf-8")), state, dry_run=not args.apply)
        else:
            if args.apply or args.dry_run:
                raise ValueError("--apply/--dry-runには--reviewedが必要")
            result = propose(state, ROOT, args.review_source)
            write_packet(args.packet, args.state, result)
            result = {"status": "proposal_only", "packets": len(result["packets"]), "blocked": len(result["blocked"])}
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, KeyError, IndexError, TypeError, OSError) as error:
        print(f"[blocked] {type(error).__name__}: {str(error)[:220]}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""ノワールの記事（layout: "noir"）の表紙の写真を、いつも写真にする（台帳 W36。2026-11-07 オーナー）。

オーナー「黒地にしたいわけではない。背景は写真を差し込みたい。何もないとただ暗い感じ」。
表紙の背景の決まり（サイトは lib/noir.ts の noirCover が同じ順で選ぶ）:
  1. 公式発表の、大きな文字の無い本物の写真（heroOk: true）。今までどおり
  2. AI で作った写真風のイメージ（話題に合う場面。文字・ロゴ・人の顔・製品・画面は描かない）。表紙に「画像はイメージ（AI生成）」と出す
     - 記事の見出し画像がもともと AI のイメージなら、それをそのまま使う（作り直さない）
     - それ以外（告知のバナー・図・フリー素材など）は、表紙用に1枚作って coverImage / coverCredit に入れる。
       製品・機械・ロボット・端末・画面は描かせず（画像判定で確かめ、写ったら作り直す）、場所・光・雰囲気だけにする
       （thumbnail / imageCredit は変えない。SNS カード・一覧の写真は今までどおり）
  3. AI で作れなかったとき: 公式の画像（バナーでも）を強くぼかして暗くした背景
  4. 何も無いときだけ、今までの黒い表紙に題名
作るのは無料の Cloudflare Workers AI（scripts/images.py と同じ AI_MODELS・1日の上限 IMAGE_AI_DAILY_MAX を共有）。有料の画像 API は使わない。

  python3 scripts/noir_cover.py              # 対象と、どの背景になるかを表示（書き込まない）
  python3 scripts/noir_cover.py --apply      # 足りない記事に表紙のイメージを作って記事 JSON に書く（今あるノワールの記事の後追い）
新しい記事は scripts/images.py が写真を選んだあとに ensure_cover を呼ぶ。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ARTICLES = Path(__file__).resolve().parent.parent / "content" / "articles"
LAYOUT = "noir"
# 作れなかった記事を、何度も作り直して1日の枚数を使い切らない
MAX_TRIES = 3


def is_noir(article: dict) -> bool:
    return article.get("layout") == LAYOUT


def official_hero(article: dict) -> bool:
    """1. 公式の写真をそのまま表紙に出せる（lib/noir.ts の noirPhoto と同じ）"""
    credit = article.get("imageCredit") or {}
    return bool(article.get("thumbnail")) and credit.get("kind") == "official" and article.get("heroOk") is True


def cover_path(article: dict) -> str:
    """表紙の背景がどれになるか（lib/noir.ts の noirCover と同じ順）: official / ai / ai-thumbnail / blur / black"""
    if official_hero(article):
        return "official"
    cover = article.get("coverCredit") or {}
    if article.get("coverImage") and cover.get("kind") == "ai":
        return "ai"
    credit = article.get("imageCredit") or {}
    if article.get("thumbnail") and credit.get("kind") == "ai":
        return "ai-thumbnail"
    if article.get("thumbnail"):
        return "blur"
    return "black"


def needs_cover(article: dict) -> bool:
    """表紙用の AI のイメージを作る記事か（ノワール・公式の写真が出せない・まだ無い・見出し画像が AI ではない）"""
    if not is_noir(article) or article.get("noPhoto"):
        return False  # noPhoto: 地震・津波の記事（写真・イメージ画像を付けない）
    if cover_path(article) in ("official", "ai", "ai-thumbnail"):
        return False
    if (article.get("imageCredit") or {}).get("kind") == "official" and "heroOk" not in article:
        return False  # 公式の写真の判定（heroOk）がまだ。判定してから決める（scripts/images.py・noir_hero_backfill.py）
    return int(article.get("coverTries") or 0) < MAX_TRIES


def make_cover(article: dict, *, fast: bool = False, dry_run: bool = False) -> dict | None:
    """表紙用の写真風の AI のイメージを1枚作って KV に置く。(coverImage, coverCredit) の dict。作れなければ None"""
    import images  # noqa: PLC0415  （重い依存は作るときだけ）

    # 表紙は話題の雰囲気だけ。発表の記事かどうかに関係なく、製品・機械・ロボット・画面・アプリの画面は描かない
    # （2026-11-07 の後追いで、データ分析の記事にノート PC の作り物の画面、ロボットの記事に作り物のロボットが出た）
    product = images.real_object_article(article)
    plan = images.visual_plan(article, product=product, service=not product)
    made = None
    drew_product = False
    for attempt in range(3):
        # images.process と同じ作り直し: 顔・文字が出たら作り直し、3回目は人を描かない場面。製品を描いたら製品の無い場面
        use = plan if attempt < 2 else {**plan, "scene": images.objects_only_scene(plan, article)}
        if drew_product:
            use = {**plan, "scene": images.NO_PRODUCT_SCENE}
        made = images.generate_ai(use, article, fast=fast)
        if made is None:
            return None  # 上限・トークン無し・どのモデルも失敗
        if images.shows_face(made[0]):
            images.log("   [cover] AI 画像に人の顔か文字が写ったので作り直す")
            made = None
            continue
        if images.depicts_product(made[0], plan.get("product", "")):
            images.log("   [cover] AI 画像に製品か似た物が写ったので、製品の無い場面で作り直す")
            made = None
            drew_product = True
            continue
        plan = use
        break
    if made is None:
        return None
    image, model = made
    slug = article.get("slug") or "article"
    url, _ = images.store(f"{slug}-cover", image, dry_run)
    credit = {
        "kind": "ai",
        "model": model,
        "prompt": (plan.get("scene") or "")[:300],
        "provider": "Cloudflare Workers AI",
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    credit["noProduct"] = True  # 製品・機械・画面を描かない場面で作り、写っていないことを確かめた
    return {"coverImage": url, "coverCredit": credit}


def ensure_cover(article: dict, *, fast: bool = False, dry_run: bool = False) -> str:
    """ノワールの記事に表紙の背景を持たせる。戻り値は表紙の背景（cover_path の値）。記事の dict を書き換える（保存は呼ぶ側）"""
    if not needs_cover(article):
        return cover_path(article)
    try:
        made = make_cover(article, fast=fast, dry_run=dry_run)
    except Exception as error:  # noqa: BLE001 - 作れなくても記事の公開は止めない（ぼかした公式の画像か黒い表紙）
        print(f"   [cover] 表紙のイメージを作れない: {str(error)[:160]}", flush=True)
        made = None
    if made:
        article.update(made)
        article.pop("coverTries", None)
    else:
        article["coverTries"] = int(article.get("coverTries") or 0) + 1
    return cover_path(article)


def save(path: Path, article: dict) -> None:
    path.write_text(json.dumps(article, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="作って記事 JSON に書く（無ければ表示だけ）")
    parser.add_argument("--slug", nargs="*", default=[])
    parser.add_argument("--max", type=int, default=20)
    parser.add_argument("--budget", type=float, default=0, help="秒。過ぎたら残りは次の回")
    args = parser.parse_args(argv)
    started = time.time()
    made = 0
    for path in sorted(ARTICLES.glob("*.json")):
        article = json.loads(path.read_text("utf-8"))
        if not is_noir(article) or (args.slug and article.get("slug") not in args.slug and path.stem not in args.slug):
            continue
        before = cover_path(article)
        if not args.apply or not needs_cover(article) or made >= args.max or (args.budget and time.time() - started > args.budget):
            print(f"{path.stem}: {before}" + ("（表紙のイメージを作る対象）" if needs_cover(article) else ""))
            continue
        after = ensure_cover(article)
        made += 1
        save(path, article)
        print(f"{path.stem}: {before} → {after}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

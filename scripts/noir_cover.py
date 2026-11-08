#!/usr/bin/env python3
"""ノワールの記事（layout: "noir"）の表紙の写真を、いつも写真にする（台帳 W36。2026-11-07 オーナー）。

オーナー「黒地にしたいわけではない。背景は写真を差し込みたい。何もないとただ暗い感じ」。
同じ日に「タイトルや内容となんの関連もない画像。画像はイメージとあるのに何もイメージできない」（誰もいない展示会場の AI 画像）。
だから表紙のイメージは、記事の話題とのつながりが読者に見えるものだけ。つながりの見えない場面を出すくらいなら、公式の画像をそのまま見せる。

表紙の背景の決まり（サイトは lib/noir.ts の noirCover が同じ順で選ぶ）:
  1. 公式発表の、大きな文字の無い本物の写真（heroOk: true）。今までどおり
  2. 表紙用の AI のイメージ（coverImage / coverCredit。thumbnail / imageCredit は変えない）。表紙に「画像はイメージ（AI生成）」と出す
     - 話題の場面を3つの切り口（人の手元・後ろ姿で話題の作業／話題が起きる場所・職場／話題に関わる物）で考え、
       1枚作るたびに無料の画像判定で ①人の顔・文字が無い ②見出しとのつながりが読者に見える を確かめる。
       公式の画像が無い新製品の発表は製品（の種類）を描いてよい（札は「公式画像がないためイメージ（AI生成）」）。
       発表ではない記事（リコールなど）はブランド・型の無い一般の物（タイヤ・電池など）を描いてよい（2026-11-07 オーナー）。
       だめなら次の切り口で作り直す（作り直しは2回まで）。誰もいない会場・抽象的な光のような、話題と関係の無い場面は使わない
     - 見出し画像がもともと AI のイメージなら、同じ確かめ（②）を通ったときだけ表紙にも使う（作り直さない）
  3. 作れなかったとき: 公式・素材の見出し画像（告知のバナーでも）を、ぼかさず・暗くせずにそのまま見せ、題名は画像の下の帯（panel）
     （2026-11-07 午後オーナー「画像反映されていない」「何もないとただ暗い感じ」。強くぼかして暗くした表紙はやめた）
  4. 何も無いとき・見出しの AI の絵が確かめを通らないときだけ、明るい紙に題名（type）
作るのは無料の Cloudflare Workers AI（scripts/images.py と同じ AI_MODELS・1日の上限 IMAGE_AI_DAILY_MAX を共有）。有料の画像 API は使わない。

  python3 scripts/noir_cover.py                    # 対象と、どの背景になるかを表示（書き込まない）
  python3 scripts/noir_cover.py --apply            # 足りない記事に表紙のイメージを作って記事 JSON に書く（今あるノワールの記事の後追い）
  python3 scripts/noir_cover.py --apply --recheck  # 今ある表紙のイメージも、見出しとのつながりを確かめ直す（だめなら作り直す・ぼかしにする）
新しい記事は scripts/images.py が写真を選んだあとに ensure_cover を呼ぶ。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ARTICLES = Path(__file__).resolve().parent.parent / "content" / "articles"
LAYOUT = "noir"
# 作れなかった記事を、何度も作り直して1日の枚数を使い切らない
MAX_TRIES = 3
# 1つの記事で作る枚数（最初の1枚＋作り直し2回）
MAX_DRAWS = 3

SCENE_SYSTEM = "You are a photo editor at a Japanese news site. You plan illustration photos that make the news topic recognizable. Return JSON only."
SCENE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "topic_en": {"type": "STRING"},
        "scenes": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["topic_en", "scenes"],
}
def is_noir(article: dict) -> bool:
    return article.get("layout") == LAYOUT


def official_hero(article: dict) -> bool:
    """1. 公式の写真をそのまま表紙に出せる（lib/noir.ts の noirPhoto と同じ）"""
    credit = article.get("imageCredit") or {}
    return bool(article.get("thumbnail")) and credit.get("kind") == "official" and article.get("heroOk") is True


def cover_path(article: dict) -> str:
    """表紙の背景がどれになるか（lib/noir.ts の noirCover と同じ順）: official / ai / panel / type
    panel: 公式・素材の見出し画像を、ぼかさず・暗くせずそのまま見せて題名は下の帯（2026-11-07 午後オーナー「画像反映されていない」。
    強くぼかして暗くした表紙はやめた）。type: 写真が何も無い・見出しの AI の絵が確かめを通らないとき、明るい紙に題名"""
    if official_hero(article):
        return "official"
    if article.get("noPhoto"):
        return "type"
    cover = article.get("coverCredit") or {}
    if article.get("coverImage") and cover.get("kind") == "ai":
        return "ai"
    if article.get("thumbnail") and (article.get("imageCredit") or {}).get("kind") != "ai":
        return "panel"
    return "type"


def needs_cover(article: dict) -> bool:
    """表紙用の AI のイメージを用意する記事か（ノワール・公式の写真が出せない・まだ無い）"""
    if not is_noir(article) or article.get("noPhoto"):
        return False  # noPhoto: 地震・津波の記事（写真・イメージ画像を付けない）
    if cover_path(article) in ("official", "ai"):
        return False
    if (article.get("imageCredit") or {}).get("kind") == "official" and "heroOk" not in article:
        return False  # 公式の写真の判定（heroOk）がまだ。判定してから決める（scripts/images.py・noir_hero_backfill.py）
    return int(article.get("coverTries") or 0) < MAX_TRIES


def cover_scenes(article: dict) -> tuple[str, list[str]]:
    """(見出しの英語の要約, 話題が分かる場面3つ)。場面は 人の手元・後ろ姿／場所・職場／関わる物 の3つの切り口"""
    import images  # noqa: PLC0415
    import llm  # noqa: PLC0415

    prompt = f"""Article (Japanese):
title: {article.get('title', '')}
summary: {article.get('description', '')}
genre: {article.get('genre', '')}

Return:
- "topic_en": the headline's topic in one short English sentence.
- "scenes": exactly 3 English sentences, each describing a different photorealistic editorial photo that makes THIS news topic
  recognizable at a glance to a reader who reads the headline:
  1. people's hands, or people seen from behind, doing the real activity or work the news is about
  2. the real place or workplace where this news matters (e.g. a tax office counter, a farm, a factory floor, a shop, a station)
  3. concrete everyday objects strongly tied to the topic (e.g. receipts and coins, a hard hat and blueprints, a SIM card tray)
  Rules for every scene: no text, signs, letters or logos; no brand or model names; no identifiable faces; no screens showing readable text.
  For a product or service launch you MAY show the kind of product generically (no brand, logo or model). For other news (recalls,
  outages, prices) you MAY show the generic category (e.g. a car tire, a battery, a smartphone) without brand or model.
  Never a generic empty office, desk, meeting room, exhibition hall, corridor or abstract light that could illustrate any news.
  Good examples for software news (screens show only abstract shapes, never readable text):
  - an AI app answering faster: over-the-shoulder view of an office worker's hands holding a smartphone, using a chat assistant app
  - a data analytics or BI service: an analyst at a desk with printed bar and line charts beside a laptop showing an abstract dashboard
  - a database or cloud service: an engineer seen from behind in a bright data center between server racks, holding a laptop
  - company knowledge for AI: hands sorting thick binders of company manuals next to a laptop with an AI chat window"""
    data, _ = llm.generate_json(SCENE_SYSTEM, prompt, SCENE_SCHEMA, tier=images.llm_tier(), temperature=0.5, max_output_tokens=1024)
    scenes = [re.sub(r"\s+", " ", str(s)).strip()[:400] for s in data.get("scenes") or [] if str(s).strip()]
    return str(data.get("topic_en") or "").strip()[:200], scenes[:MAX_DRAWS]


def relevant(image, article: dict, topic: str) -> bool:
    """見出しとのつながりが読者に見え、誤解を招かないか（無料の画像判定 Workers AI。scripts/images.py の headline_check と同じ。
    見出し画像の AI 画像も同じ確かめを通す）。判定できないときは見えない側に倒す"""
    import images  # noqa: PLC0415

    return images.headline_check(image, article, topic) is None


def make_cover(article: dict, *, fast: bool = False, dry_run: bool = False) -> dict | None:
    """表紙用の写真風の AI のイメージを作って KV に置く。(coverImage, coverCredit) の dict。
    話題とのつながりが見える画像が作れなければ None（呼ぶ側は公式の画像をそのまま見せる表紙にする）"""
    import images  # noqa: PLC0415  （重い依存は作るときだけ）

    # 2026-11-07 オーナー: 公式の画像が無い新製品の発表は、AI が製品（の種類）を描いてよい。札は「公式画像がないためイメージ（AI生成）」。
    # リコールなど発表ではない記事は、ブランド・型の無い一般の物（タイヤ・電池など）を描いてよい
    launch = images.launch_article(article)
    topic, scenes = cover_scenes(article)
    if not scenes:
        return None
    for scene in scenes[:MAX_DRAWS]:
        made = images.generate_ai({"scene": scene}, article, fast=fast)
        if made is None:
            return None  # 上限・トークン無し・どのモデルも失敗
        image, model = made
        if images.shows_face(image):
            images.log("   [cover] 人の顔か文字が写ったので、別の切り口で作り直す")
            continue
        if not relevant(image, article, topic):
            images.log("   [cover] 見出しとのつながりが見えないので、別の切り口で作り直す")
            continue
        slug = article.get("slug") or "article"
        url, _ = images.store(f"{slug}-cover", image, dry_run)
        credit = {
            "kind": "ai",
            "model": model,
            "prompt": scene[:300],
            "provider": "Cloudflare Workers AI",
            "relevant": True,  # 見出しとのつながりが見えると確かめた
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        if launch:
            credit["launch"] = True  # 新製品・サービスの発表（表紙の札は「公式画像がないためイメージ（AI生成）」）
        return {"coverImage": url, "coverCredit": credit}
    return None


def reuse_thumbnail(article: dict) -> dict | None:
    """見出し画像がもともと AI のイメージで、見出しとのつながりが見えるなら、それを表紙にも使う（作り直さない）"""
    import images  # noqa: PLC0415

    credit = article.get("imageCredit") or {}
    if credit.get("kind") != "ai" or not article.get("thumbnail"):
        return None
    data, _, _ = images.http_get(article["thumbnail"], ua=images.BOT_UA, timeout=30)
    image = images.open_image(data)
    topic = ""
    if images.shows_face(image) or not relevant(image, article, topic):
        images.log("   [cover] 見出しの AI のイメージは表紙に使わない（顔・文字か、見出しとのつながりが見えない）")
        return None
    return {"coverImage": article["thumbnail"], "coverCredit": {**credit, "reused": True, "relevant": True}}


def ensure_cover(article: dict, *, fast: bool = False, dry_run: bool = False) -> str:
    """ノワールの記事に表紙の背景を持たせる。戻り値は表紙の背景（cover_path の値）。記事の dict を書き換える（保存は呼ぶ側）"""
    if not needs_cover(article):
        return cover_path(article)
    made = None
    try:
        made = reuse_thumbnail(article) or make_cover(article, fast=fast, dry_run=dry_run)
    except Exception as error:  # noqa: BLE001 - 作れなくても記事の公開は止めない（公式の画像をそのまま見せる表紙か、明るい紙に題名）
        print(f"   [cover] 表紙のイメージを作れない: {str(error)[:160]}", flush=True)
    if made:
        article.update(made)
        article.pop("coverTries", None)
    else:
        article["coverTries"] = int(article.get("coverTries") or 0) + 1
    return cover_path(article)


def recheck(article: dict) -> bool:
    """今ある表紙のイメージが見出しとつながっているかを確かめ直す。だめなら外して True（作り直しの対象にする）"""
    import images  # noqa: PLC0415

    if cover_path(article) != "ai" or (article.get("coverCredit") or {}).get("model") == "muse":
        return False  # Muse の写真は Muse が記事に合うかを確かめて描いたもの（台帳 I8）。Workers AI の判定で外さない
    data, _, _ = images.http_get(article["coverImage"], ua=images.BOT_UA, timeout=30)
    image = images.open_image(data)
    if relevant(image, article, ""):
        return False
    for key in ("coverImage", "coverCredit", "coverTries"):
        article.pop(key, None)
    return True


def save(path: Path, article: dict) -> None:
    path.write_text(json.dumps(article, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="作って記事 JSON に書く（無ければ表示だけ）")
    parser.add_argument("--recheck", action="store_true", help="今ある表紙のイメージも見出しとのつながりを確かめ直す")
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
        if args.apply and args.recheck and recheck(article):
            print(f"{path.stem}: 表紙のイメージが見出しとつながらないので作り直す")
            article["coverTries"] = 0
        if not args.apply or not needs_cover(article) or made >= args.max or (args.budget and time.time() - started > args.budget):
            print(f"{path.stem}: {before}" + ("（表紙のイメージを作る対象）" if needs_cover(article) else ""))
            if args.apply and cover_path(article) != before:
                save(path, article)
            continue
        after = ensure_cover(article)
        made += 1
        save(path, article)
        print(f"{path.stem}: {before} → {after}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

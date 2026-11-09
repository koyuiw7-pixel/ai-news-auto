#!/usr/bin/env python3
"""Muse（Meta の AI アプリ・オーナーの契約）が描いた表紙の写真を記事に付ける（2026-11-08 オーナー承認・台帳 I8）。

画像の順（どの経路でも同じ）:
  1. 使える公式の写真（heroOk など今までの決まり。scripts/noir_cover.py の cover_path == "official"）
  2. Muse の写真（1日 MUSE_IMAGE_DAILY 枚まで。リポジトリの変数。未設定なら20。Muse が自分で出来を確かめる）
  3. Workers AI の表紙（scripts/noir_cover.py。無料の1日40枚の中だけ）
  4. 文字だけの表紙（最後の手段。次の日の作り直しは台帳 I7）

Muse には鍵を渡さない。Muse はオーナーの Mac の ~/Downloads/saisoku-images/ で
  - requests.md（こちらが書く。依頼の一覧。Muse は書き換えない）を読み、
  - <slug>.jpg（1200×675）を置き、done-YYYYMMDD.md に置いたファイル名と、描けなかった記事の理由を書き足す。
Mac の運び役（scripts/muse_images_push.py。scripts/muse_articles_push.py と同じ launchd の25分ごとの回）が画像を確かめて
content/muse_images/ に push し、Auto Article Pipeline の「Muse images」の段（この script）が:
  ①届いた画像を確かめ直して KV（/img/。表紙と同じ置き場）に置き、記事の coverImage・coverCredit {kind: "ai", model: "muse"} を書く
    （画像の URL が変わるので /cover・/card の ?v= も変わり、古い画像のキャッシュは使われない）
  ②今日の記事のうち写真の無いものを、優先の順に依頼の一覧（state/muse_images.json の items）に足す（1日の上限まで）
状態は state/muse_images.json（requested / delivered / applied / skipped と理由）。Mac がそれを読んで requests.md と ledger.md を書く。

  python3 scripts/muse_images.py            # 届いた画像を付けて、依頼の一覧を更新する
  python3 scripts/muse_images.py --dry-run  # KV に置かず・書き込まずに表示だけ
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
INBOX = ROOT / "content" / "muse_images"
STATE = ROOT / "state" / "muse_images.json"
SITE = "https://ai-tech-express.jp"
JST = timezone(timedelta(hours=9))
DEFAULT_DAILY = 30  # 2026-11-09 オーナー承認どおり 20→30（変数 MUSE_IMAGE_DAILY も 30）
KEEP_DAYS = 7
MODEL = "muse"
PROVIDER = "Meta AI（Muse）"
# 画像の確かめ（Mac の運び役と同じ基準）
OUT_SIZE = (1200, 675)
MIN_WIDTH = 800
ASPECT_RANGE = (1.5, 2.1)  # 16:9 は 1.78。この範囲なら 1200×675 に縮小・切り抜きしてよい
DARK_MEAN = 18  # 明るさの平均（0〜255）がこれ未満は「ほぼ真っ暗」。2026-11-09: 夜のサーバー室の絵（26）を落としていたので 28→18（暗めの絵は通す）
FLAT_STDDEV = 10  # 明るさのばらつきがこれ未満は「ほぼ一色」
MIN_BYTES = 10_000

# 優先の段（数字が小さいほど先）。1・2 は「優先が高い」＝ Workers AI の表紙があっても Muse の写真に替える
TIER_SNS = 1  # SNS・動画に出す予定の記事（requests.md で「急」）
TIER_INTENT = 2  # 手続き・お金・値上げ・給付・リコール・障害
TIER_CORE = 3  # サイトの軸（暮らしとお金の「自分ごと」ニュース）のそのほか
TIER_OFF = 4  # 軸の外の海外の技術の話
HIGH_TIERS = (TIER_SNS, TIER_INTENT)
TIER_NAMES = {TIER_SNS: "SNS・動画に出す", TIER_INTENT: "手続き・お金", TIER_CORE: "暮らしの話題", TIER_OFF: "海外の技術"}
INTENT_RE = re.compile(r"手続き|申請|申し込み|届け出|期限|締め切り|対象者|いつから|値上げ|値下げ|料金|価格|改定|給付|補助|助成|支援金|還付|"
                       r"税|年金|保険料|手当|ポイント|リコール|回収|障害|不具合|停止|運休|欠航|詐欺|流出|給与|年収|賃金|家計|物価")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def jst_day(stamp: str | None = None) -> str:
    if not stamp:
        return now_utc().astimezone(JST).strftime("%Y-%m-%d")
    try:
        return datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).astimezone(JST).strftime("%Y-%m-%d")
    except ValueError:
        return ""


def daily_cap() -> int:
    try:
        return max(0, int(os.environ.get("MUSE_IMAGE_DAILY") or DEFAULT_DAILY))
    except ValueError:
        return DEFAULT_DAILY


def load_state(path: Path = STATE) -> dict:
    try:
        data = json.loads(path.read_text("utf-8"))
        if isinstance(data, dict) and isinstance(data.get("items"), dict):
            return data
    except (OSError, ValueError):
        pass
    return {"items": {}}


def save_state(state: dict, path: Path = STATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- 記事の写真の状態
def is_muse_cover(article: dict) -> bool:
    return bool(article.get("coverImage")) and (article.get("coverCredit") or {}).get("model") == MODEL


def photo_state(article: dict) -> str:
    """official（使える公式の写真）/ muse / ai（Workers AI の表紙）/ none（写真が無い・文字だけ）"""
    import noir_cover  # noqa: PLC0415

    # ロゴ・サイト共通の画像・ほかの記事の画像は「写真が無い」と同じに扱う（Muse に頼む。2026-11-09 台帳 S49）
    credit = article.get("imageCredit") or {}
    thumb = str(article.get("thumbnail") or "")
    if (credit.get("kind") == "official" and credit.get("imageKind") in ("logo", "generic")) or borrowed(thumb, str(article.get("slug") or "")):
        if is_muse_cover(article):
            return "muse"
        return "ai" if article.get("coverImage") else "none"
    if article.get("layout") == noir_cover.LAYOUT:
        path = noir_cover.cover_path(article)
        if path == "official":
            return "official"
        if path == "ai":
            return "muse" if is_muse_cover(article) else "ai"
        return "none"
    # ノワール以外の記事: 見出しの写真が公式・素材の写真なら使える
    kind = (article.get("imageCredit") or {}).get("kind")
    if is_muse_cover(article):
        return "muse"
    if article.get("thumbnail") and kind not in ("ai", "card"):
        return "official"
    if article.get("coverImage") or (article.get("thumbnail") and kind == "ai"):
        return "ai"
    return "none"


def borrowed(url: str, slug: str) -> bool:
    """自前の画像（/img/<名前>）の名前が、この記事の slug で始まらない（ほかの記事のために保存した画像）"""
    m = re.search(r"/img/([^/?#]+)$", url or "")
    return bool(m and slug) and not m.group(1).startswith(slug[:120])


def eligible(article: dict) -> bool:
    """Muse に頼んでよい記事か（地震・津波の写真なし・まとめ・重複・取り下げは頼まない）"""
    if article.get("noPhoto") or article.get("type") == "roundup" or article.get("duplicateOf") or article.get("retired"):
        return False
    return True


# --------------------------------------------------------------------------- 優先の順
def sns_slugs(root: Path = ROOT) -> set[str]:
    """SNS・動画に出す予定の記事（Threads などの予約・動画の候補）"""
    out: set[str] = set()
    since = (now_utc() - timedelta(hours=36)).isoformat()

    def read(name: str) -> dict:
        try:
            return json.loads((root / "state" / name).read_text("utf-8"))
        except (OSError, ValueError):
            return {}

    for key, row in (read("threads_posted.json").get("posted") or {}).items():
        if not isinstance(row, dict) or row.get("style") == "digest" or str(key).startswith("digest-"):
            continue  # まとめの投稿は、まとめの号の画像を使う（記事の表紙ではない）
        when = str(row.get("dueAt") or row.get("postedAt") or "")
        if when and when < since:
            continue
        items = row.get("items")
        if isinstance(items, list) and items:
            out.update(str(s) for s in items)  # まとめの投稿（digest）は載せる記事の一覧
        else:
            out.add(str(key))
    video = read("sns_video.json")
    out.update(str(k) for k in (video.get("queued") or {}))
    for row in read("muse_queue.json").get("items") or []:
        if isinstance(row, dict) and row.get("status") == "queued" and row.get("slug"):
            out.add(str(row["slug"]))
    return out


def priority(article: dict, sns: set[str]) -> int:
    if article.get("slug") in sns:
        return TIER_SNS
    title = str(article.get("title") or "")
    kind = "other"
    japanese = True
    try:
        import news_mix  # noqa: PLC0415

        kind = news_mix.classify(article)
        japanese = news_mix.is_japanese_item(article)
    except Exception:  # noqa: BLE001 - 判定できないときは題名の語だけで決める
        pass
    if kind in ("money", "alert") or INTENT_RE.search(title):
        return TIER_INTENT
    if kind in ("enterprise_dev", "research", "quirky") or (not japanese and kind not in ("life", "brand", "jp_corp")):
        return TIER_OFF
    return TIER_CORE


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\*\*|__|`", "", str(text or ""))).strip()


def key_points(article: dict) -> list[str]:
    points = [clean(p) for p in article.get("highlights") or [] if clean(p)]
    if not points:
        points = [clean(s) + "。" for s in re.split(r"。", str(article.get("description") or "")) if clean(s)]
    return [p[:120] for p in points[:3]]


def reader_angle(article: dict) -> str:
    work = article.get("workMoney") or {}
    for text in (work.get("points") or [])[:1] + (article.get("todayActions") or [])[:1]:
        if clean(text):
            return clean(text)[:140]
    lede = [clean(s) for s in str(article.get("lede") or "").split("。") if clean(s)]
    return (lede[-1] + "。")[:140] if lede else clean(article.get("description"))[:140]


def request_row(article: dict, tier: int, day: str) -> dict:
    slug = article.get("slug")
    return {
        "day": day,
        "status": "requested",
        "priority": tier,
        "urgent": tier == TIER_SNS,
        "title": clean(article.get("title"))[:120],
        "url": f"{SITE}/articles/{slug}",
        "points": key_points(article),
        "angle": reader_angle(article),
        "had": photo_state(article),
        "requestedAt": now_utc().isoformat(timespec="seconds"),
    }


def skip(row: dict, reason: str) -> None:
    row["status"] = "skipped"
    row["reason"] = reason
    row["at"] = now_utc().isoformat(timespec="seconds")


def update_requests(state: dict, articles: dict[str, dict], sns: set[str], cap: int, today: str | None = None) -> list[str]:
    """今日の依頼の一覧を直す。戻り値は新しく頼んだ記事の slug"""
    today = today or jst_day()
    items = state.setdefault("items", {})
    # 頼んだあとに公式の写真・先の AI の表紙が付いた、記事が消えた → 依頼を取り下げる（Muse の手間を使わせない）
    for slug, row in items.items():
        if row.get("status") != "requested":
            continue
        article = articles.get(slug)
        if article is None or not eligible(article):
            skip(row, "記事が取り下げ・重複になった")
            continue
        got = photo_state(article)
        tier = priority(article, sns)
        row["priority"], row["urgent"] = tier, tier == TIER_SNS
        if got == "official":
            skip(row, "公式の写真が付いた")
        elif got == "muse":
            skip(row, "Muse の写真がもう付いている")
        elif got == "ai" and tier not in HIGH_TIERS:
            skip(row, "先に Workers AI の表紙が付いた（優先が高くない記事は替えない）")
    used = sum(1 for r in items.values() if r.get("day") == today and r.get("status") in ("requested", "delivered", "applied"))
    candidates = []
    for slug, article in articles.items():
        # SNS に出す予定の記事は、前の日の記事でも頼む（2026-11-09: 前の日の子ども手当の記事が写真なしで出た。台帳 S49）
        if slug in items or not eligible(article) or (
                slug not in sns and jst_day(article.get("generatedAt") or article.get("publishedAt")) != today):
            continue
        got = photo_state(article)
        if got in ("official", "muse"):
            continue
        tier = priority(article, sns)
        if got == "ai" and tier not in HIGH_TIERS:
            continue
        # 同じ段の中では写真の無い記事が先、次に新しい記事
        candidates.append((tier, 0 if got == "none" else 1, str(article.get("generatedAt") or ""), slug, article))
    candidates.sort(key=lambda c: c[2], reverse=True)
    candidates.sort(key=lambda c: (c[0], c[1]))
    added = []
    for tier, _, _, slug, article in candidates:
        if used >= cap:
            break
        items[slug] = request_row(article, tier, today)
        added.append(slug)
        used += 1
    return added


def prune(state: dict) -> None:
    since = (now_utc().astimezone(JST) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    state["items"] = {k: v for k, v in state.get("items", {}).items() if str(v.get("day") or "") >= since}


# --------------------------------------------------------------------------- 画像の確かめ（Mac の運び役も同じ関数を使う）
def image_problems(image) -> list[str]:
    """PIL の画像。だめな理由の一覧（空なら使える）"""
    from PIL import ImageStat  # noqa: PLC0415

    problems = []
    w, h = image.size
    if w < MIN_WIDTH:
        problems.append(f"小さすぎます（幅 {w}px。{OUT_SIZE[0]}×{OUT_SIZE[1]} で置いてください）")
    ratio = w / h if h else 0
    if not ASPECT_RANGE[0] <= ratio <= ASPECT_RANGE[1]:
        problems.append(f"縦横の比が 16:9 から遠すぎます（{w}×{h}。{OUT_SIZE[0]}×{OUT_SIZE[1]} で置いてください）")
    stat = ImageStat.Stat(image.convert("L").resize((160, 90)))
    if stat.mean[0] < DARK_MEAN:
        problems.append(f"ほぼ真っ暗です（明るさ {stat.mean[0]:.0f}/255）")
    if stat.stddev[0] < FLAT_STDDEV:
        problems.append(f"ほぼ一色で、何が写っているか分かりません（ばらつき {stat.stddev[0]:.0f}）")
    return problems


def fit_size(image):
    """1200×675 にそろえる（縦横の比が少し違えば真ん中で切る）"""
    from PIL import Image, ImageOps  # noqa: PLC0415

    if image.size == OUT_SIZE:
        return image
    return ImageOps.fit(image.convert("RGB"), OUT_SIZE, method=Image.LANCZOS, centering=(0.5, 0.5))


# --------------------------------------------------------------------------- 届いた画像を付ける
def muse_credit() -> dict:
    return {
        "kind": "ai",
        "model": MODEL,
        "provider": PROVIDER,
        "relevant": True,  # Muse が記事に合うかを確かめて描いた（合わなければ描かずに理由を書く約束）
        "at": now_utc().isoformat(timespec="seconds"),
    }


def apply_one(path: Path, article: dict, row: dict | None, *, dry_run: bool = False) -> tuple[str, str]:
    """(状態, 理由か URL)。記事の dict を書き換える（保存は呼ぶ側）"""
    import images  # noqa: PLC0415 （Pillow・KV）

    data = path.read_bytes()
    if len(data) < MIN_BYTES:
        return "skipped", f"画像のファイルが空か小さすぎます（{len(data)} バイト）"
    try:
        image = images.open_image(data)
    except Exception as error:  # noqa: BLE001
        return "skipped", f"画像を開けません（{str(error)[:80]}）"
    problems = image_problems(image)
    if problems:
        return "skipped", "画像: " + "／".join(problems)
    if not eligible(article):
        return "skipped", "記事が取り下げ・重複・写真を付けない記事になった"
    got = photo_state(article)
    tier = int((row or {}).get("priority") or TIER_CORE)
    if got == "official":
        return "skipped", "公式の写真が付いたので使いませんでした"
    if got == "ai" and tier not in HIGH_TIERS:
        return "skipped", "先に Workers AI の表紙が付いた記事で、優先が高くないので替えませんでした"
    url, _ = images.store(f"{article.get('slug')}-muse", fit_size(image), dry_run)
    before = article.get("coverImage") or ""
    article["coverImage"] = url
    article["coverCredit"] = muse_credit()  # 同じ記事に Muse が描き直して置いたときは新しい方に替える（URL が変わるのでキャッシュも替わる）
    article.pop("coverTries", None)
    return "applied", url + (f"（Workers AI の表紙 {before} から替えた）" if before and got == "ai" else "")


def run(*, dry_run: bool = False) -> int:
    state = load_state()
    state["dailyCap"] = cap = daily_cap()
    items = state.setdefault("items", {})
    articles: dict[str, dict] = {}
    paths: dict[str, Path] = {}
    for path in ARTICLES.glob("*.json"):
        try:
            article = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        slug = str(article.get("slug") or path.stem)
        articles[slug], paths[slug] = article, path
    changed = False
    # Muse が描けなかった記事の理由（Mac の運び役が <slug>.skip.txt にして送る）
    for note in sorted(INBOX.glob("*.skip.txt")) if INBOX.exists() else []:
        slug = note.name[: -len(".skip.txt")]
        row = items.setdefault(slug, {"day": jst_day(), "title": clean((articles.get(slug) or {}).get("title"))[:120]})
        if row.get("status") != "applied":
            skip(row, "Muse: " + clean(note.read_text("utf-8", errors="replace"))[:200])
            row["by"] = "muse"
        print(f"[muse-img] {slug}: Muse が描けなかった（{row.get('reason', '')[:80]}）")
        if not dry_run:
            note.unlink()
        changed = True
    for path in sorted(INBOX.glob("*.jpg")) if INBOX.exists() else []:
        slug = path.stem
        row = items.get(slug)
        article = articles.get(slug)
        if article is None:
            status, detail = "skipped", "この名前の記事がありません（ファイル名は記事の URL の最後の部分＝slug）"
        else:
            try:
                status, detail = apply_one(path, article, row, dry_run=dry_run)
            except Exception as error:  # noqa: BLE001 - KV に置けない等。画像は残して次の回にもう一度
                print(f"::warning::[muse-img] {slug}: 付けられませんでした（次の回にもう一度）: {str(error)[:160]}")
                if row is not None:
                    row["status"] = "delivered"
                    changed = True
                continue
        row = items.setdefault(slug, {"day": jst_day(), "title": clean((article or {}).get("title"))[:120],
                                      "url": f"{SITE}/articles/{slug}"})
        row["status"], row["at"] = status, now_utc().isoformat(timespec="seconds")
        if status == "applied":
            row["image"] = detail.split("（")[0]
            row.pop("reason", None)
            if not dry_run:
                paths[slug].write_text(json.dumps(article, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            row["reason"] = detail
        print(f"[muse-img] {slug}: {'付けました' if status == 'applied' else '使いませんでした'} {detail[:160]}")
        if not dry_run:
            path.unlink()
        changed = True
    added = update_requests(state, articles, sns_slugs(), cap)
    prune(state)
    today = jst_day()
    rows = [r for r in items.values() if r.get("day") == today]
    counts = {s: sum(1 for r in rows if r.get("status") == s) for s in ("requested", "delivered", "applied", "skipped")}
    print(f"[muse-img] 今日の依頼 {counts['requested'] + counts['delivered'] + counts['applied']}/{cap} 枚"
          f"（待ち {counts['requested']}・反映 {counts['applied']}・見送り {counts['skipped']}）。新しく頼んだ記事: {', '.join(added) or 'なし'}")
    if added or changed or load_state() != state:
        state["updatedAt"] = now_utc().isoformat(timespec="seconds")
        if not dry_run:
            save_state(state)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    return run(dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())

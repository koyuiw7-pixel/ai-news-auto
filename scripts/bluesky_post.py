"""Bluesky（AT Protocol を直接）に記事を出す。Buffer は使わない

（2026-11-06 まで）出していたもの:
- 投稿履歴 state/threads_posted.json の各記録（Threads に出したもの）のうち、まだ Bluesky に出していないもの
  - 速報（breaking）と朝のまとめ（digest）は すぐ
  - 通常の予約は Threads の時刻（dueAt）から DELAY_MIN 分後
- --fill のとき: Threads 側に出すものがなければ、直近12時間の良い記事（検索に出す記事）で
  まだ Bluesky に出していない最新の1本（記録は state/bluesky_extra.json）
1日6本まで（Threads と同じ上限）・深夜（1〜5時）は出さない。通常の投稿は1回の実行で1本まで、前の投稿から40分あけていた。
結果は channels.bluesky に URI を記録。失敗しても他の SNS には影響しない
2026-11-05（オーナー承認）: Bluesky は Threads の投稿を待たずに、SNS の予定（threads_post が枠に入れた「動画待ち」の記録）から
直接出す。Buffer（Threads・X・Facebook）が止まっていても、枠の時刻＋ DELAY_MIN 分に出す。
本文は Threads に送る予定の本文（SNS_HOOK_FORMAT の型も同じ）からリンクの行を除いたもの。同じ記事は1回だけ（channels.bluesky・自分の投稿の確かめ）
2026-11-05 夕方（オーナー決定「動画を待たない」「動画を作る記事を限定」・sns_rules ルール8・台帳 S13）: 動画を作る限られた記事
（sns_plan.video_post）だけ、Muse の動画を待つ期限（枠＋1時間）まで待って動画（app.bsky.embed.video）で出す。ほかの投稿と、
動画が無い・Bluesky が動画を受け付けないときは、記事の写真のリンクカードで出す（文字だけでは出さない）。朝のまとめは号のシェア画像のまま。

2026-11-06（オーナー承認・台帳 S40。2026-11-07 から）: Bluesky は Threads の写しをやめ、Bluesky だけの上限（1日3本）と枠で出す。
  7:30 = 朝の要の1本（その日の朝のまとめ。無ければ夜のあいだのいちばんの記事）
  13:00 = その日いちばんの速報・記事（ここまでに出た記事から）
  21:00 = 夜の1本（13時からの記事のいちばん。無ければその日の記事）
1つの枠に1本。枠に遅れたら次の枠の前（最後の枠は 23時）までに出してよい。7時より前・23時より後は出さない。
Threads の本数（sns_plan.daily_cap）とは別に数え、お互いの本数に数えない。ミサイル・災害の知らせは今までどおり枠の外ですぐ出し、本数に数えない。
文面は Bluesky だけの2行（1行目＝事実・2行目＝読者にとって何が変わるか。問いかけで終えない）＋ハッシュタグ1つ＋記事のリンク（本文＋リンクカード）。
どちらの行も記事の文（lede・やさしい版・description／workMoney・verdict.take・highlights）からそのまま選ぶ（LLM は使わない。事実は記事にあるものだけ）。
記録は state/bluesky_extra.json（kind=brief・slot）。朝のまとめは今までどおり投稿履歴の channels.bluesky

2026-11-09（オーナー承認・台帳 S51）: Bluesky も Threads で人が来ている形にそろえる。ふつうの記事の投稿は
  ①Threads と同じ読者向けの文面（1行目＝誰の話か・数字1つ・決め手は記事に）がある記事を、速報の次に必ず先に選ぶ
  ②暗いリンクカードをやめ、記事の画像（Muse の説明の図 public/fig/<slug>-fig*.png → 記事の本物の写真が載るカード。X と同じ選び方・
    ルール24）を app.bsky.embed.images で大きく付ける。記事のリンク（utm_source=bluesky）は本文の「続き（◯◯）→」の facet
  動画・朝のまとめ・急ぎの知らせ（写しの投稿）は今までどおり

  python3 scripts/bluesky_post.py --dry-run [--fill]  # 下書きを表示（投稿しない。ログインできなければ画像なしで表示）
  python3 scripts/bluesky_post.py [--fill]            # 投稿（BLUESKY_HANDLE / BLUESKY_APP_PASSWORD が必要）
  python3 scripts/bluesky_post.py --merge FILE [--merge-extra FILE2]  # 手元の記録を最新の state に足す
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import threads_post as tp  # noqa: E402
import sns_rules  # noqa: E402
import sns_reader  # noqa: E402  2026-11-08 夜: Threads と同じ読者向けの書き方（ルール23）

PDS = "https://bsky.social/xrpc"
DELAY_MIN = 20
# 1日（日本時間）の自分の投稿の上限。2026-11-07〜 Bluesky だけの上限（sns_plan.json の bluesky.daily_cap＝3本。Threads と別に数える。台帳 S40）
PER_DAY = tp.sns_plan.bluesky_daily_cap()
LOOKBACK_H = 6  # 出せる時刻（枠・Muse の待ちの期限の遅い方）からこれより古い記録は出さない（取りこぼしを後から大量に出さない）
MORNING_HOURS = 12  # 朝の枠でまとめが無いときに使う記事の新しさ（生成から）
FILL_MIN_AGE_MIN = 25  # 生成直後はまだ公開（デプロイ）前のことがあるので待つ（11/8: 15分ではカードがまだ 404 のことがあった）
FAILED_RETRY_H = 3  # 失敗した記事は、この時間たてば枠の候補に戻す（一時的な失敗でずっと外さない。11/8 九州電力の記事）
SIMILAR_HOURS = 24  # この時間内に出した投稿と同じ話題の記事は使わない
EXTRA_PATH = tp.ROOT / "state" / "bluesky_extra.json"
MAX_GRAPHEMES = 300
MAX_BLOB = 1_000_000


def log(message: str) -> None:
    print(message, flush=True)


def xrpc(method: str, body: dict | bytes | None = None, token: str = "", ctype: str = "application/json") -> dict:
    data = body if isinstance(body, bytes) else json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{PDS}/{method}", data=data, method="POST" if data is not None else "GET")
    if data is not None:
        req.add_header("Content-Type", ctype)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read() or b"{}")


def login() -> dict:
    handle = os.environ.get("BLUESKY_HANDLE", "").strip()
    password = os.environ.get("BLUESKY_APP_PASSWORD", "").strip()
    if not handle or not password:
        raise RuntimeError("BLUESKY_HANDLE / BLUESKY_APP_PASSWORD がありません")
    return xrpc("com.atproto.server.createSession", {"identifier": handle, "password": password})


def fetch(url: str, limit: int = MAX_BLOB + 1) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "saisoku-bluesky/1.0"})
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read(limit), res.headers.get_content_type()


def shrink(data: bytes) -> bytes | None:
    """1MB を超える画像（写真入りの PNG など）を JPEG にして 1MB 以下にする。Pillow が無ければ None"""
    try:
        import io

        from PIL import Image  # noqa: PLC0415
    except ImportError:
        return None
    try:
        image = Image.open(io.BytesIO(data)).convert("RGB")
        for quality in (86, 80, 72, 64):
            buf = io.BytesIO()
            image.save(buf, "JPEG", quality=quality, optimize=True)
            if buf.tell() <= MAX_BLOB:
                return buf.getvalue()
    except Exception:  # noqa: BLE001
        return None
    return None


def upload_thumb(session: dict, urls: list[str], used: list[str] | None = None) -> dict | None:
    """1MB 以下の画像をアップロードして blob を返す。どれも無理なら None（カードは画像なし）。使った URL は used に足す"""
    for url in urls:
        try:
            data, ctype = fetch(url, 8 * 1024 * 1024)
            if not ctype.startswith("image/"):
                continue
            if len(data) > MAX_BLOB:
                data = shrink(data) or b""
                ctype = "image/jpeg"
                if not data:
                    continue
            blob = xrpc("com.atproto.repo.uploadBlob", data, session["accessJwt"], ctype)["blob"]
            if used is not None:
                used.append(url)
            return blob
        except Exception as error:  # noqa: BLE001
            log(f"  [bluesky] 画像を使えません {url}: {error}")
    return None


VIDEO_STATE = tp.ROOT / "state" / "sns_video.json"
VIDEO_SERVICE = "https://video.bsky.app/xrpc"
MAX_VIDEO = 50 * 1024 * 1024


def video_of(slug: str, videos: dict | None = None) -> dict:
    """この記事の SNS 用の動画（{"url", "variant"}）。Threads に付けた版 → 短い版 → 全部の版。無ければ {}"""
    if videos is None:
        try:
            videos = json.loads(VIDEO_STATE.read_text("utf-8")).get("videos") or {}
        except (OSError, ValueError):
            videos = {}
    rec = videos.get(slug) or {}
    urls = rec.get("urls") or {}
    import sns_video_followup as fu  # noqa: PLC0415

    for variant in (rec.get("variant"), "short", "full"):
        version = (rec.get("versions") or {}).get(variant) or {}
        if variant and urls.get(variant) and version.get("ok", True) and fu.qa_ok(version):
            credit = ((((rec.get("versions") or {}).get(variant) or {}).get("post") or {}).get("voice") or {}).get("credit", "")
            return {"url": urls[variant], "variant": variant, "credit": credit}
    return {}


def needs_video(entry: dict, key: str = "") -> bool:
    """動画で出したい記録か。2026-11-05 夕方 オーナー決定「動画を作る記事を限定」: 朝のまとめ・問いかけ・急ぎの安全の知らせ以外で、
    動画を作る限られた記事（sns_plan.video_post＝Muse に頼んだ記事）だけ。key が無ければ False"""
    if entry.get("style") in ("digest", "poll") or entry.get("urgent") or not key:
        return False
    return tp.sns_plan.video_post(key)


class VideoUnsupported(RuntimeError):
    """Bluesky がこの動画を受け付けない（大きさ・形式・処理の失敗）。一時的な失敗（通信・時間切れ）とは分ける"""


def upload_video(session: dict, url: str) -> dict:
    """SNS 用の動画を Bluesky の動画サービスに上げて、処理が終わった blob を返す（失敗したら例外）"""
    data, ctype = fetch(url, MAX_VIDEO + 1)
    if len(data) > MAX_VIDEO or not ctype.startswith("video/"):
        raise VideoUnsupported(f"動画を使えません（{ctype}・{len(data) / 1e6:.1f}MB）")
    pds = next((s.get("serviceEndpoint", "") for s in ((session.get("didDoc") or {}).get("service") or []) if s.get("id") == "#atproto_pds"), "")
    host = urllib.parse.urlsplit(pds).netloc or "bsky.social"
    auth = xrpc(f"com.atproto.server.getServiceAuth?aud={urllib.parse.quote('did:web:' + host)}&lxm=com.atproto.repo.uploadBlob"
                f"&exp={int(datetime.now(timezone.utc).timestamp()) + 1800}", None, session["accessJwt"])["token"]
    name = re.sub(r"[^A-Za-z0-9._-]", "-", url.rsplit("/", 1)[-1])[:80] or "video.mp4"
    req = urllib.request.Request(f"{VIDEO_SERVICE}/app.bsky.video.uploadVideo?did={urllib.parse.quote(session['did'])}&name={urllib.parse.quote(name)}",
                                 data=data, method="POST", headers={"Content-Type": "video/mp4", "Authorization": f"Bearer {auth}"})
    try:
        with urllib.request.urlopen(req, timeout=180) as res:
            job = json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as error:
        job = json.loads(error.read() or b"{}")  # 同じ動画を上げ直したとき（already_exists）も jobId が返る
    job = job.get("jobStatus", job)
    for _ in range(60):
        if job.get("blob"):
            return job["blob"]
        if job.get("error") == "unconfirmed_email":
            raise RuntimeError("Bluesky のアカウントのメールアドレスが未確認のため、動画を上げられません（Bluesky の設定でメールを確認すると出せるようになります）")
        if job.get("state") == "JOB_STATE_FAILED":
            raise VideoUnsupported(f"Bluesky の動画の処理に失敗しました: {str(job)[:200]}")
        if not job.get("jobId"):
            raise RuntimeError(f"Bluesky の動画を上げられませんでした: {str(job)[:200]}")
        time.sleep(5)
        with urllib.request.urlopen(f"{VIDEO_SERVICE}/app.bsky.video.getJobStatus?jobId={urllib.parse.quote(job['jobId'])}", timeout=30) as res:
            job = json.loads(res.read() or b"{}").get("jobStatus", {})
    raise RuntimeError("Bluesky の動画の処理が5分で終わりませんでした")


def build_record(text: str, link: str, title: str, desc: str, thumb: dict | None, video: dict | None = None, full_text: str = "",
                 image: dict | None = None) -> dict:
    """本文＋改行＋リンク。リンクは facet（UTF-8 のバイト位置）とリンクカードの両方で付ける。
    full_text（読者向けの書き方・ルール23）は、リンクの表示（短い形）を中に含んだ投稿の本文そのもの。
    image（{"blob", "width", "height", "alt"}。2026-11-09 オーナー承認・台帳 S51）があれば、リンクカードではなく
    記事の画像そのもの（app.bsky.embed.images）を大きく見せ、リンクは本文の facet だけにする"""
    shown = re.sub(r"^https?://|\?.*$", "", link)  # 表示は短く（リンク先は UTM 付き）
    if full_text and shown in full_text:
        full = full_text.strip()
        text = full
        start = len(full[: full.index(shown)].encode())
    else:
        room = MAX_GRAPHEMES - len(shown) - 1
        text = text.strip()
        if len(text) > room:
            text = text[: room - 1].rstrip() + "…"
        full = f"{text}\n{shown}"
        start = len(f"{text}\n".encode())
    external = {"uri": link, "title": title[:300], "description": desc[:300]}
    if thumb:
        external["thumb"] = thumb
    # ハッシュタグも facet にする（付けないと Bluesky で押せず、タグの検索にも出ない）
    tags = [{"index": {"byteStart": len(text[:m.start()].encode()), "byteEnd": len(text[:m.end()].encode())},
             "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": m.group(0)[1:]}]}
            for m in re.finditer(r"(?<!\S)#[^\s#]+", text)]
    return {
        "$type": "app.bsky.feed.post",
        "text": full,
        "createdAt": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "langs": ["ja"],
        "facets": tags + [{
            "index": {"byteStart": start, "byteEnd": start + len(shown.encode())},
            "features": [{"$type": "app.bsky.richtext.facet#link", "uri": link}],
        }],
        # 記事の投稿は動画（リンクは本文の facet）。ふつうの記事の投稿は記事の画像（S51）。朝のまとめ・急ぎの知らせはリンクカード
        "embed": ({"$type": "app.bsky.embed.video", "video": video, "aspectRatio": {"width": 1920, "height": 1080}, "alt": title[:300]}
                  if video else image_embed(image, title) if image and image.get("blob")
                  else {"$type": "app.bsky.embed.external", "external": external}),
    }


def image_embed(image: dict, title: str) -> dict:
    """記事の画像1枚の埋め込み（縦横を付けるとタイムラインで切れずに出る）"""
    item = {"image": image["blob"], "alt": str(image.get("alt") or title)[:1000]}
    if image.get("width") and image.get("height"):
        item["aspectRatio"] = {"width": int(image["width"]), "height": int(image["height"])}
    return {"$type": "app.bsky.embed.images", "images": [item]}


def post_images(article: dict) -> list[dict]:
    """ふつうの記事の投稿に付ける画像の候補 [{"url", "width", "height", "from", "alt"}]（よい順）。2026-11-09 オーナー承認（台帳 S51）:
    Threads で人が来ている形にそろえ、Muse の説明の図（public/fig/<slug>-fig*.png・16:9）を先に、無ければ記事の本物の写真が載るカード。
    X と同じ選び方（x_post.figure_image・ルール24）。文字だけのカード・ロゴ・ほかの記事の画像は使わない（無ければ []）"""
    import x_post  # noqa: PLC0415  （x_post が bluesky_post を読み込むので、ここで読む）

    out = []
    if fig := x_post.figure_image(article):
        alt = next((str(f.get("alt") or "") for f in article.get("figures") or [] if isinstance(f, dict)
                    and str(f.get("src") or "").rsplit("/", 1)[-1] == fig[0].rsplit("/", 1)[-1]), "")
        out.append({"url": fig[0], "width": fig[1][0], "height": fig[1][1], "from": "figure", "alt": alt})
    if not sns_rules.photo_problem(article):
        out.append({"url": tp.card_url(article), "width": x_post.CARD_SIZE[0], "height": x_post.CARD_SIZE[1], "from": "card", "alt": ""})
    return out


PUBLIC_API = "https://public.api.bsky.app/xrpc"


def existing_uri(session: dict, link: str, fetcher=None) -> str:
    """同じ記事（同じ号）の投稿が、自分の直近の投稿にもうあれば、その URI（1記事1投稿。2026-11-04 の二重投稿のあと）。
    読めなければ例外（出さない。次の回にもう一度）"""
    m = re.search(r"/(?:articles|digest)/[^/?#\s]+", link)
    if not m:
        return ""
    needle = m.group(0)
    actor = urllib.parse.quote(session.get("did") or session.get("handle") or "")
    if fetcher is None:
        def fetcher(url):
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "saisoku-bluesky/1.0"}), timeout=30) as res:
                return json.loads(res.read() or b"{}")
    feed = fetcher(f"{PUBLIC_API}/app.bsky.feed.getAuthorFeed?actor={actor}&limit=60&filter=posts_no_replies").get("feed") or []
    for item in feed:
        post = item.get("post") or {}
        if needle in json.dumps(post.get("record") or {}, ensure_ascii=False) or needle in json.dumps(post.get("embed") or {}, ensure_ascii=False):
            return post.get("uri", "")
    # 公開のフィードは反映が数分遅れることがある（速報の Bluesky 投稿と通常の Bluesky の実行が重なったとき）。
    # 自分のサーバー（PDS）の記録そのものも読む（書いた直後から見える。2026-11-04 一貫性の点検）
    if session.get("did"):
        repo = urllib.parse.quote(session["did"])
        for rec in fetcher(f"{PDS}/com.atproto.repo.listRecords?repo={repo}&collection=app.bsky.feed.post&limit=50").get("records") or []:
            if needle in json.dumps(rec.get("value") or {}, ensure_ascii=False):
                return rec.get("uri", "")
    return ""


def create_record(session: dict, record: dict, p: dict, media: list[dict]) -> dict:
    """Bluesky に1件出す。出す直前に SNS ルールの門番（sns_rules）を通し、同じ記事の投稿がもう無いかを自分の投稿で確かめる
    （あればそれを返す＝二重に出さない）。違反なら SnsRuleViolation（出さない）"""
    sns_rules.enforce("bluesky", record["text"], media, p.get("gate"), source="bluesky_post", kind=p.get("kind", "article"), links=[p["link"]],
                      video_unsupported=bool(p.get("videoUnsupported")))
    if uri := existing_uri(session, p["link"]):
        log(f"  [bluesky] 同じ記事の投稿がもうあります（{uri}）。二重に出しません")
        return {"uri": uri, "existing": True}
    return xrpc("com.atproto.repo.createRecord",
                {"repo": session["did"], "collection": "app.bsky.feed.post", "record": record}, session["accessJwt"])


def plan(key: str, entry: dict, platform: str = "bluesky") -> dict | None:
    """投稿の中身（本文・リンク・カード）。出せないもの（アンケートなど）は None。
    platform: utm_source と autofix の投稿先（Instagram の直接投稿も同じ予定の本文を使う。scripts/instagram_post.py・台帳 S36）"""
    style = entry.get("style")
    if style == "poll":
        return None
    if style == "digest":
        import morning_digest as md
        items = []
        for slug in entry.get("items") or []:
            path = tp.ARTICLES_DIR / f"{slug}.json"
            if path.exists():
                items.append(json.loads(path.read_text("utf-8")))
        text = str((entry.get("postPlan") or {}).get("text") or "").strip()
        if not text:
            recorded_at = entry.get("dueAt") or entry.get("postedAt")
            if not items or not recorded_at:
                return None
            text = md.compose(items, datetime.fromisoformat(recorded_at.replace("Z", "+00:00")))
        # リンク先はその日の号のページ（/digest/<YYYYMMDD>。カードの画像も号のシェア画像）。古い記録・号を出せなかった日は /news
        page = str((entry.get("postPlan") or {}).get("link") or "")
        covers = [tp.card_url(items[0])] if items else []  # 写真だけのカード（見出し入りのカバーは使わない。ルール2）
        if "/digest/" in page:
            return {"text": text, "link": tp.utm_link(page, platform, "digest"),
                    "title": f"{text.splitlines()[0]}　サイソクニュース", "desc": "直近のAIニュースを3本だけ。写真と要約つき。",
                    "images": [f"{page.rstrip('/')}/share.png?v={md.dp.image_rev()}", *covers],
                    "kind": "digest", "gate": {"link": page, "items": items}}
        link = tp.utm_link(f"{tp.site_url()}/news", platform, "digest")
        return {"text": text, "link": link, "title": "AIニュースまとめ　サイソクニュース",
                "desc": "直近のAIニュースを1分で。", "images": covers, "kind": "digest", "gate": {"link": link, "items": items}}
    path = tp.ARTICLES_DIR / f"{key}.json"
    if not path.exists():
        return None
    article = json.loads(path.read_text("utf-8"))
    # 問いかけは Threads に出したものと同じにする（記録が無ければ話題・主役から作る）
    text = tp.compose(article, [], breaking=bool(entry.get("breaking")), fixed_question=str(entry.get("questionText") or ""),
                    fixed_pattern=str(entry.get("questionPattern") or ""))
    if planned := planned_text(entry):
        text = planned  # Threads と同じ予定の本文（SNS_HOOK_FORMAT の型も同じ。2026-11-05）
    spec = tp.ROOT / "content" / "sns_reposts" / f"{key}.json"
    if spec.exists():  # オーナーに見せて承認をもらった出し直しの文面（Threads と同じ）
        text = json.loads(spec.read_text("utf-8")).get("classic") or text
    text, _ = sns_rules.autofix(text, article, platform)  # 「要約すると、」・数字の単位・災害の話題の呼びかけ/問い（ルール13・14・S35）
    text = re.sub(r"\s*👇\s*$", "", text)
    link = tp.utm_link(f"{tp.site_url()}/articles/{key}", platform, entry.get("format") or "classic")
    return {
        "text": text, "link": link, "title": article.get("seoTitle") or article["title"],
        "desc": article.get("description", ""),
        # 写真だけのカード（16:9）だけを使う。見出し入りのカバー・縦横の分からない元の写真は使わない（ルール2）
        "images": [tp.card_url(article)], "gate": article,
    }


def planned_slot(entry: dict) -> datetime | None:
    """SNS の予定の枠の時刻（動画待ちの記録の pending.slot）"""
    return _parse((entry.get("pending") or {}).get("slot"))


def due(entry: dict, delay: int | None = None) -> datetime | None:
    """出す時刻。delay は枠からの遅れ（分。既定は Bluesky の DELAY_MIN。Instagram は別の分で呼ぶ）"""
    delay = DELAY_MIN if delay is None else delay
    if entry.get("status") == "awaiting_video" and (slot := planned_slot(entry)) and not entry.get("breaking") and entry.get("style") != "digest":
        return slot + timedelta(minutes=delay)  # Threads（Buffer）を待たずに、予定の枠から出す（2026-11-05）
    raw = entry.get("dueAt") or entry.get("postedAt")
    if not raw:
        return None
    when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    fast = entry.get("breaking") or entry.get("style") == "digest"
    return when if fast else when + timedelta(minutes=delay)


def load_extra(path: Path | None = None) -> dict:
    """埋め合わせで出した記事の記録 {slug: {uri, at, title}}"""
    path = path or EXTRA_PATH
    try:
        data = json.loads(path.read_text("utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_extra(extra: dict, path: Path | None = None) -> None:
    path = path or EXTRA_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(extra, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse(raw: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")) if raw else None
    except ValueError:
        return None


def sent(state: dict, extra: dict | None = None) -> list[tuple[str, datetime]]:
    """Bluesky に出した記録（キー, 時刻）。投稿履歴の記録（朝のまとめ・急ぎの知らせ・以前の写し）と state/bluesky_extra.json の両方"""
    out = [(k, t) for k, e in state["posted"].items() if (t := _parse(e.get("blueskyAt")))]
    out += [(k, t) for k, e in (extra or {}).items() if isinstance(e, dict) and (t := _parse(e.get("at")))]
    return out


def exempt(key: str, entry: dict | None) -> bool:
    """1日の上限に数えない投稿（ミサイル・災害の知らせ。sns_plan.cap_exempt と同じ判定。記録に無ければ記事で見る）"""
    entry = entry or {}
    if tp.sns_plan.cap_exempt(entry):
        return True
    path = tp.ARTICLES_DIR / f"{key}.json"
    try:
        return path.exists() and tp.sns_plan.cap_exempt(json.loads(path.read_text("utf-8")))
    except (OSError, ValueError):
        return False


def counted(state: dict, extra: dict | None, start: datetime, end: datetime) -> int:
    """start〜end に出した Bluesky の投稿のうち、上限に数えるものの数（ミサイル・災害は数えない）"""
    n = 0
    for key, when in sent(state, extra):
        if start <= when < end and not (key in state["posted"] and key not in (extra or {}) and exempt(key, state["posted"][key])):
            n += 1
    return n


def _day_start(now: datetime) -> datetime:
    return now.astimezone(tp.JST).replace(hour=0, minute=0, second=0, microsecond=0)


def posted_today(state: dict, now: datetime, extra: dict | None = None) -> int:
    """今日（日本時間）の上限に数える Bluesky の投稿の数（Threads の本数とは別。台帳 S40）"""
    start = _day_start(now)
    return counted(state, extra, start, start + timedelta(days=1))


def last_sent(state: dict, extra: dict | None = None) -> datetime | None:
    times = [t for _, t in sent(state, extra)]
    return max(times) if times else None


def fast(entry: dict) -> bool:
    """間隔を待たずにすぐ出すもの（速報・朝のまとめ）"""
    return bool(entry.get("breaking")) or entry.get("style") == "digest"


def muse_until(key: str, entry: dict, now: datetime) -> datetime | None:
    """この記事の投稿が Muse の動画を待っている期限（待っていなければ None。Threads と同じ判定）"""
    if not needs_video(entry, key) or entry.get("breaking"):
        return None
    try:
        import sns_video_followup as fu  # noqa: PLC0415

        videos = json.loads(VIDEO_STATE.read_text("utf-8")).get("videos") or {} if VIDEO_STATE.exists() else {}
        return fu.muse_waiting(key, entry, now, videos.get(key))
    except Exception:  # noqa: BLE001 - 分からなければ待たない（自動動画も同じ検査）
        return None


def pending(state: dict, now: datetime, extra: dict | None = None, channel: str = "bluesky", delay: int | None = None) -> list[tuple[str, dict]]:
    """まだこの SNS（channel）に出していない、出す時刻の来た記録。Instagram（scripts/instagram_post.py）も同じ選び方を使う"""
    out = []
    for key, entry in state["posted"].items():
        when = due(entry, delay)
        if not when or (entry.get("channels") or {}).get(channel) or entry.get(f"{channel}Failed") or entry.get("ownerHold"):
            continue  # ownerHold: オーナーに見せるまで出さない記事
        if key in (extra or {}):  # 埋め合わせで先に出した記事は Threads に出た後も重ねない
            continue
        if entry.get("status") == "skipped_no_video":
            continue  # 前の決まりで見送った記録（出し直さない）
        if entry.get("status") == "awaiting_video" and not planned_slot(entry):
            continue
        ready = when
        if muse_until(key, entry, now):
            continue  # Muse の動画を待っている（期限のあとは自動動画で出す）
        m_until = None
        try:
            import sns_plan  # noqa: PLC0415

            m_until = sns_plan.muse_wait_until(key, planned_slot(entry) or when, breaking=bool(entry.get("breaking")))
        except Exception:  # noqa: BLE001
            m_until = None
        if m_until and m_until > ready:
            ready = m_until  # Muse を待った分だけ、遅れて出すのを許す
        if when <= now and now - ready <= timedelta(hours=LOOKBACK_H):
            out.append((key, entry))
    return sorted(out, key=lambda kv: due(kv[1], delay))


def planned_text(entry: dict) -> str:
    """Threads に送る予定の本文から、記事のリンクの行と案内の行を除いたもの（無ければ ""）"""
    text = str((((entry.get("pending") or {}).get("inputs") or {}).get("threads") or {}).get("text") or "")
    if not text:
        return ""
    lines = [ln for ln in text.splitlines() if "http" not in ln and not ln.strip().startswith(tp.THREADS_LINK_LINE)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


TITLE_NOISE = re.compile(r"[\s「」『』【】()（）・、。，．,.！？!?:：|｜\-—〜~\"'“”]")
QUOTED = re.compile(r"[「『\"“]([^」』\"”]{2,40})[」』\"”]")


def _norm(text: str) -> str:
    return TITLE_NOISE.sub("", text or "").lower()


def similar(a: str, b: str) -> bool:
    """同じ話題の題名か（ゆるい判定）: 文字の並びがかなり似ている／「」『』の製品名が同じ"""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb or SequenceMatcher(None, na, nb).ratio() >= 0.6:
        return True
    return bool({_norm(x) for x in QUOTED.findall(a)} & {_norm(x) for x in QUOTED.findall(b)} - {""})


def _indexable_rule():
    """検索に出す記事の基準（scripts/indexnow.py と同じ）。読み込めなければ簡易版"""
    try:
        import indexnow
        return indexnow.is_indexable, indexnow.duplicate_slugs
    except Exception:  # noqa: BLE001
        def simple(article: dict, dups=frozenset()) -> bool:
            return (len(article.get("body", "")) >= 1500 and article.get("genreSlug") in {"ai", "tech-gadget"}
                    and article.get("slug") not in dups)
        return simple, lambda articles: set()


def load_articles() -> list[dict]:
    out = []
    for path in tp.ARTICLES_DIR.glob("*.json"):
        try:
            article = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(article, dict) and article.get("slug"):
            out.append(article)
    return out


def _recent_titles(state: dict, extra: dict, now: datetime, by_slug: dict) -> list[str]:
    """直近 SIMILAR_HOURS 時間に Bluesky に出した投稿の題名（同じ話題を続けないため）"""
    out = []
    for key, when in sent(state, extra):
        if now - when > timedelta(hours=SIMILAR_HOURS):
            continue
        title = (extra.get(key) or {}).get("title") if key in extra else ""
        title = title or (by_slug.get(key) or {}).get("title") or ""
        if title:
            out.append(title)
    return out


def blocked(rec: dict | None, now: datetime) -> bool:
    """この記事を枠の候補から外すか（もう出した＝uri がある・FAILED_RETRY_H 時間以内に失敗した）"""
    if not isinstance(rec, dict) or not rec:
        return False
    if rec.get("uri") or rec.get("at"):
        return True
    when = _parse(rec.get("failedAt"))
    if not when:
        return True  # 以前の失敗の記録（時刻なし）は今までどおり外したまま（直すときは記録を消す）
    return now - when < timedelta(hours=FAILED_RETRY_H)


def brief_candidates(state: dict, extra: dict, now: datetime, since: datetime, articles: list[dict] | None = None) -> list[dict]:
    """枠に出せる記事（いい順）: since 以降に作った検索に出す記事で、まだ Bluesky に出しておらず、SNS に出す話題で、
    直近に出した投稿と同じ話題でなく、Bluesky の2行の文面を作れるもの。並べ順は 速報 → SNS の点数（レーン）→ 新しさ"""
    articles = load_articles() if articles is None else articles
    is_indexable, duplicate_slugs = _indexable_rule()
    dups = duplicate_slugs(articles)
    by_slug = {a["slug"]: a for a in articles}
    recent = _recent_titles(state, extra, now, by_slug)
    out = []
    for article in articles:
        generated = _parse(article.get("generatedAt"))
        if not generated or generated.tzinfo is None or not since <= generated <= now - timedelta(minutes=FILL_MIN_AGE_MIN):
            continue
        slug = article["slug"]
        entry = state.get("posted", {}).get(slug) or {}
        if (entry.get("channels") or {}).get("bluesky") or entry.get("blueskyFailed") or entry.get("ownerHold"):
            continue
        if blocked(extra.get(slug), now) or blocked(extra.get(article.get("roundupSlug") or "\0"), now):
            continue  # もう出した・少し前に失敗した記事（同じ記事で失敗し続けない。時間がたてば戻す）
        if tp.sns_plan.excluded(article) or not is_indexable(article, dups):
            continue
        if not post_images(article):
            continue  # 記事に合う本物の画像（Muse の図・写真のカード）がまだ無い（台帳 S49・S51）。画像が付けば次の回に出す
        if any(similar(article.get("title", ""), title) for title in recent):
            continue
        if not (sns_reader.bluesky_post(article) or brief_lines(article)):
            continue
        breaking = bool(article.get("breaking") or entry.get("breaking"))
        # 2026-11-08 夜 オーナー: 軸は暮らしの安全・お金・手続き（レーン＋手続きの言葉）。読者向けの文面がある記事を先に
        # 2026-11-09 オーナー承認（台帳 S51）: Threads で人が来ている書き方（読者向けの文面）がある記事を、速報の次に必ず先にする
        ready = bool(sns_reader.bluesky_post(article))
        out.append(((breaking, ready, sns_reader.rank_key(article, "bluesky", generated)[0], generated), article))
    out.sort(key=lambda x: x[0], reverse=True)
    return [a for _, a in out]


def digest_today(state: dict, now: datetime) -> tuple[str, dict] | None:
    """今日（日本時間）の朝のまとめで、まだ Bluesky に出していないもの"""
    today = now.astimezone(tp.JST).date()
    for key, entry in sorted(state["posted"].items(), reverse=True):
        when = due(entry)
        if entry.get("style") != "digest" or not when or when > now or when.astimezone(tp.JST).date() != today:
            continue
        if (entry.get("channels") or {}).get("bluesky") or entry.get("blueskyFailed") or entry.get("ownerHold"):
            continue
        return key, entry
    return None


def slot_pick(slot: tuple[int, datetime, datetime], state: dict, extra: dict, now: datetime,
              articles: list[dict] | None = None) -> tuple[str, dict, str] | None:
    """この枠に出す1本。朝の枠は朝のまとめ（無ければ夜のあいだの記事）、昼の枠はその日の記事のいちばん、
    夜の枠は昼の枠からの記事のいちばん（無ければその日の記事）"""
    index, start, _ = slot
    # 2026-11-10（台帳 S54）: 朝6時台の枠を足したので、朝のまとめ（7:15）は最初の2つの枠のどちらかで写す（6:30 はまだまとめが無い）
    if index <= 1 and (found := digest_today(state, now)):
        return found[0], found[1], "mirror"
    if index == 0:
        ranges = [now - timedelta(hours=MORNING_HOURS)]
    elif index == 1:
        ranges = [_day_start(now), now - timedelta(hours=MORNING_HOURS)]
    else:
        previous = tp.sns_plan.bluesky_slot_window(start - timedelta(minutes=1))
        ranges = [previous[1] if previous else start, _day_start(now)]
    articles = load_articles() if articles is None else articles
    for since in ranges:
        found = brief_candidates(state, extra, now, since, articles)
        if found:
            return found[0]["slug"], {"article": found[0]}, "brief"
    return None


def choose(state: dict, extra: dict, now: datetime, fill: bool = False, articles: list[dict] | None = None) -> list[tuple[str, dict, str]]:
    """この実行で出すもの [(キー, 記録, 種類)]。種類は mirror（投稿履歴の記録＝朝のまとめ・急ぎの知らせ）か brief（Bluesky だけの文面）。
    ミサイル・災害の知らせは枠の外ですぐ（本数に数えない）。ほかは Bluesky の枠（7:30・13:00・21:00）に1本ずつ・1日 PER_DAY 本まで。
    fill は以前の埋め合わせの指定（今は使わない。ワークフローの呼び方のために残す）"""
    out = [(k, e, "mirror") for k, e in pending(state, now, extra) if exempt(k, e)]
    slot = tp.sns_plan.bluesky_slot_window(now)
    if not slot or posted_today(state, now, extra) >= PER_DAY:
        return out
    if counted(state, extra, slot[1], slot[2]):
        return out  # この枠はもう出した（1つの枠に1本）
    pick = slot_pick(slot, state, extra, now, articles)
    return out + [pick] if pick else out


# ---- Bluesky だけの文面（2026-11-06 オーナー承認・台帳 S40・sns_rules ルール19） ----
SENTENCE_RE = re.compile(r"[^。！!]+[。！!]")
# 2行目に向かない文（何も変わらないとだけ言う文）。ほかに無いときだけ使う
LOW_IMPACT_RE = re.compile(r"影響は(?:小さ|限定|あまりな|ほぼな)")
EASY_LEAD_RE = re.compile(r"##\s*ひとことで言うと\s*\n+([^\n#]+)")
# 2026-11-09 オーナー承認（台帳 S51・ルール19）: 「#暮らし」「#ニュース」のような広いタグは Bluesky ではほとんど検索されないのでやめ、
# 記事の話題そのもの（会社・サービス・制度の名前）のタグを1つだけ付ける。見出し（無ければ記事のタグ）に言葉がある記事だけ・上から順に1つ。
# 当たらなければ付けない（付ければ見つけてもらえるときだけ）
TOPIC_TAGS: list[tuple[str, str]] = [
    (r"ドコモ|docomo", "#ドコモ"), (r"\bau\b|KDDI", "#au"), (r"ソフトバンク", "#ソフトバンク"), (r"楽天モバイル", "#楽天モバイル"),
    (r"ahamo", "#ahamo"), (r"povo", "#povo"), (r"PayPay", "#PayPay"), (r"楽天カード", "#楽天カード"), (r"楽天ポイント", "#楽天ポイント"),
    (r"マイナ保険証", "#マイナ保険証"), (r"マイナンバーカード|マイナカード", "#マイナンバーカード"), (r"マイナポイント", "#マイナポイント"),
    (r"新NISA|NISA", "#NISA"), (r"iDeCo|イデコ", "#iDeCo"), (r"ふるさと納税", "#ふるさと納税"), (r"確定申告", "#確定申告"),
    (r"年末調整", "#年末調整"), (r"医療費控除", "#医療費控除"), (r"児童手当", "#児童手当"), (r"年金", "#年金"),
    (r"最低賃金", "#最低賃金"), (r"電気料金|電気代", "#電気代"), (r"ガス料金|ガス代", "#ガス代"), (r"ガソリン", "#ガソリン価格"),
    (r"地震保険", "#地震保険"), (r"火災保険", "#火災保険"), (r"住宅ローン", "#住宅ローン"), (r"日銀|日本銀行", "#日銀"),
    (r"金利", "#金利"), (r"物価|消費者物価", "#物価"), (r"値上げ", "#値上げ"), (r"リコール", "#リコール"),
    (r"フィッシング|詐欺", "#詐欺"), (r"ゆうちょ", "#ゆうちょ銀行"), (r"三井住友銀行", "#三井住友銀行"), (r"三菱UFJ", "#三菱UFJ銀行"),
    (r"みずほ", "#みずほ銀行"), (r"ローソン", "#ローソン"), (r"セブン-?イレブン|セブンイレブン", "#セブンイレブン"),
    (r"ファミリーマート|ファミマ", "#ファミマ"), (r"ChatGPT", "#ChatGPT"), (r"Gemini", "#Gemini"), (r"Claude", "#Claude"),
    (r"Copilot", "#Copilot"), (r"iPhone", "#iPhone"), (r"Android", "#Android"), (r"Windows", "#Windows"),
]


def _sentences(text: str) -> list[str]:
    return [m.group(0).strip() for m in SENTENCE_RE.finditer(str(text or "").replace("\n", ""))]


def brief_hashtag(article: dict) -> str:
    """話題のハッシュタグ1つ（TOPIC_TAGS。台帳 S51）。見出しに無ければ記事のタグで探す。当たらなければ ""。
    地震・津波・急ぎの安全の知らせには付けない（台帳 S35）。流出・リコールなどは会社・サービスの名前のタグだけ（煽る言葉は付けない）"""
    article = article or {}
    if article.get("disaster") or sns_rules.is_urgent(article):
        return ""
    safety = sns_rules.safety_topic(article)
    for source in (str(article.get("title") or ""), " ".join(str(t) for t in article.get("tags") or [])):
        for pattern, tag in TOPIC_TAGS:
            if safety and tag in ("#詐欺", "#リコール", "#値上げ"):
                continue
            if re.search(pattern, source, re.I):
                return tag
    return ""


def brief_lines(article: dict, room: int = MAX_GRAPHEMES) -> tuple[str, str] | None:
    """(1行目＝事実, 2行目＝読者にとって何が変わるか)。どちらも記事の文そのもの。room は本文（2行＋ハッシュタグ）の文字数の上限。
    作れなければ None"""
    easy = EASY_LEAD_RE.search(str(article.get("easy") or ""))
    facts = [x for src in (article.get("lede"), easy.group(1) if easy else "", article.get("description")) for x in _sentences(src)[:1]]
    facts = [x for x in facts if len(x) >= 20 and not sns_rules.brief_line_problems(x)]
    impacts, weak = [], []
    sources = [*((article.get("workMoney") or {}).get("points") or []), (article.get("verdict") or {}).get("take"), *(article.get("highlights") or [])]
    for src in sources:
        for x in _sentences(src):
            if len(x) < 12 or sns_rules.brief_line_problems(x):
                continue
            (weak if LOW_IMPACT_RE.search(x) else impacts).append(x)
    tag = brief_hashtag(article)
    for fact in facts:
        for impact in impacts + weak:
            if sns_rules.near_duplicate(fact, impact):
                continue
            if len(fact) + len(impact) + len(tag) + 2 <= room:
                return fact, impact
    return None


def brief_text(article: dict, room: int = MAX_GRAPHEMES) -> str:
    lines = brief_lines(article, room)
    if not lines:
        return ""
    tag = brief_hashtag(article)
    return "\n".join([*lines, tag] if tag else lines)


def plan_reader(article: dict) -> dict | None:
    """2026-11-08 夜（ルール23）: Threads の読者向けの文面を Bluesky に合わせたもの（最後に「続き（◯◯）→ URL」・リンクカード・
    utm_source=bluesky・utm_content=reader_body）。無ければ None"""
    if article.get("disaster") or sns_rules.is_urgent(article):
        return None
    got = sns_reader.bluesky_post(article)
    if not got:
        return None
    pics = post_images(article)
    return {"text": got["text"], "full_text": got["text"], "link": got["link"], "title": article.get("seoTitle") or article["title"],
            "desc": article.get("description", ""), "images": [x["url"] for x in pics] or [tp.card_url(article)], "pictures": pics,
            "gate": article, "kind": "reader"}


def plan_brief(article: dict) -> dict | None:
    """Bluesky だけの文面の投稿の中身（リンクは本文＋リンクカード。utm_campaign=brief・utm_content=card_body）。
    読者向けの文面（plan_reader）があればそちらを使う"""
    if reader := plan_reader(article):
        return reader
    key = article["slug"]
    link = tp.utm_link(f"{tp.site_url()}/articles/{key}", "bluesky", sns_rules.BRIEF_CAMPAIGN, ptype="card", pos="body")
    shown = re.sub(r"^https?://|\?.*$", "", link)
    text = brief_text(article, MAX_GRAPHEMES - len(shown) - 1)
    if not text:
        return None
    fixed, _ = sns_rules.autofix(text, article, "bluesky")  # 数字の単位・【速報】・話題に合わないタグ（ルール13・14・S35）
    pics = post_images(article)
    return {
        "text": fixed, "link": link, "title": article.get("seoTitle") or article["title"], "desc": article.get("description", ""),
        # Muse の図か写真だけのカード（16:9）を記事の画像として付ける（ルール2・S51）
        "images": [x["url"] for x in pics] or [tp.card_url(article)], "pictures": pics, "gate": article, "kind": "brief",
    }


def merge(mine_path: str, channel: str = "bluesky") -> int:
    """手元の記録（channel の時刻・失敗・channels.<channel>）を最新の state に足す。Instagram も同じものを使う"""
    mine = json.loads(Path(mine_path).read_text("utf-8"))
    state = tp.load_state()
    added = 0
    for key, entry in mine.get("posted", {}).items():
        target = state.get("posted", {}).get(key) or state.get("extraPending", {}).get(key)
        if target is None:
            continue
        for field in (f"{channel}At", f"{channel}Failed", f"{channel}Permalink"):
            if entry.get(field) and not target.get(field):
                target[field] = entry[field]
        uri = (entry.get("channels") or {}).get(channel)
        if uri and not (target.get("channels") or {}).get(channel):
            target.setdefault("channels", {})[channel] = uri
            added += 1
    tp.save_state(state)
    log(f"[{channel}] 投稿履歴に {added} 件を足しました")
    return 0


def merge_extra(mine_path: str) -> int:
    """埋め合わせの記録を最新の state/bluesky_extra.json に足す（和集合。既にあるものは変えない）"""
    mine = load_extra(Path(mine_path))
    extra = load_extra()
    added = 0
    for key, entry in mine.items():
        if key not in extra:
            extra[key] = entry
            added += 1
    if added or not EXTRA_PATH.exists():
        save_extra(extra)
    log(f"[bluesky] 埋め合わせの記録に {added} 件を足しました")
    return 0


def delete_approved(slug: str, session: dict | None = None, call=None) -> str:
    """（オーナー承認の出し直しだけ）content/sns_reposts/<slug>.json の deletedBlueskyUri の自分の投稿を消す。
    ownerApprovedDeleteRepost の無い記事・自分のものでない URI は消さない"""
    spec_path = tp.ROOT / "content" / "sns_reposts" / f"{slug}.json"
    spec = json.loads(spec_path.read_text("utf-8")) if spec_path.exists() else {}
    uri = str(spec.get("deletedBlueskyUri") or "")
    if not spec.get("ownerApprovedDeleteRepost") or not uri:
        raise SystemExit(f"[bluesky] {slug}: オーナー承認の出し直しの記録（ownerApprovedDeleteRepost と deletedBlueskyUri）がありません")
    session = session or login()
    m = re.fullmatch(r"at://([^/]+)/app\.bsky\.feed\.post/([A-Za-z0-9]+)", uri)
    if not m or m.group(1) != session.get("did"):
        raise SystemExit(f"[bluesky] 自分の投稿の URI ではないので消しません: {uri}")
    (call or xrpc)("com.atproto.repo.deleteRecord", {"repo": m.group(1), "collection": "app.bsky.feed.post", "rkey": m.group(2)}, session["accessJwt"])
    log(f"[bluesky] オーナー承認で前の投稿を消しました: {uri}")
    return uri


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fill", action="store_true", help="（以前の埋め合わせ。2026-11-07 から使わない。呼び方のために残す）")
    parser.add_argument("--alerts-only", action="store_true", help="ミサイル・災害の知らせだけ出す（速報のワークフローから。枠の投稿は bluesky.yml）")
    parser.add_argument("--merge", default="")
    parser.add_argument("--merge-extra", default="")
    parser.add_argument("--slug", default="", help="確認用: この記録を対象にする（--dry-run と一緒に）")
    parser.add_argument("--delete-approved", default="", metavar="SLUG", help="オーナー承認の出し直しで、前の Bluesky の投稿を消す（content/sns_reposts）")
    args = parser.parse_args()
    if args.delete_approved:
        delete_approved(args.delete_approved)
        return 0
    if args.merge or args.merge_extra:
        if args.merge:
            merge(args.merge)
        if args.merge_extra:
            merge_extra(args.merge_extra)
        return 0
    live = os.environ.get("THREADS_MODE") == "live" and not args.dry_run
    state = tp.load_state()
    extra = load_extra()
    now = datetime.now(timezone.utc)
    if now.astimezone(tp.JST).hour in tp.BREAKING_QUIET_HOURS_JST and live:
        log("[bluesky] 深夜のため出しません")
        return 0
    if args.slug:
        todo = [(args.slug, state["posted"][args.slug], "mirror")]
    else:
        todo = choose(state, extra, now, args.fill)
        if args.alerts_only:  # 速報のワークフローは Bluesky だけの記録（bluesky_extra）を残さないので、枠の投稿はしない
            todo = [t for t in todo if t[2] == "mirror" and exempt(t[0], t[1])]
        log(f"[bluesky] 今日 {posted_today(state, now, extra)}/{PER_DAY} 本・前回 {last_sent(state, extra)}")
        if not todo and not live:  # 下書きは直近24時間のいちばんの記事を見本にする（枠の外でも文面を確かめられる）
            todo = [(a["slug"], {"article": a}, "brief") for a in brief_candidates(state, extra, now, now - timedelta(hours=24))[:1]]
    if not todo:
        log("[bluesky] 出すものはありません（上限・枠・対象なし）")
        return 0
    session = None
    try:
        session = login()
        log(f"[bluesky] ログイン OK: {session.get('handle')} ({session.get('did')})")
    except Exception as error:  # noqa: BLE001  Bluesky の失敗で他を止めない
        log(f"[bluesky] ログイン失敗: {error}")
        if live:
            return 0
    for key, entry, kind in todo:
        try:
            p = plan_brief(entry["article"]) if kind == "brief" else plan(key, entry)
            if not p:
                if kind == "brief":
                    extra[key] = {"failed": "skip", "title": entry["article"].get("title", ""), "kind": "brief"}
                else:
                    entry["blueskyFailed"] = "skip"
                continue
            used: list[str] = []
            media: list[dict] = []
            blob = None
            image = None
            # Bluesky だけの文面は記事のリンクカードで出す（台帳 S40）。動画は急ぎの知らせ以外の写しの投稿だけ
            vid = video_of(key) if p.get("kind", "article") not in ("digest", "brief", "reader") and not sns_rules.is_urgent(p.get("gate")) else {}
            if vid:
                media = [{"type": "video", "url": vid["url"], "width": 1920, "height": 1080}]
                if session and live:
                    try:
                        blob = upload_video(session, vid["url"])
                    except Exception as error:  # noqa: BLE001
                        # Bluesky が動画を受け付けない・上げられない → 記事の写真のカードで出す（2026-11-05 夕方 オーナー「動画を待たない」）
                        log(f"  [bluesky] {key}: 動画を上げられません（{str(error)[:120]}）。リンクカード（記事の写真）で出します")
                        p["videoUnsupported"] = True
                p["link"] = tp.utm_link(f"{tp.site_url()}/articles/{key}", "bluesky", "sns_video", vid["variant"],
                                        ptype="hook" if entry.get("hookFormat") else "")
                if vid.get("credit") and len(p["text"]) + len(vid["credit"]) + 60 <= MAX_GRAPHEMES:
                    p["text"] = f"{p['text'].rstrip()}\n音声：{vid['credit']}"  # VOICEVOX の規約のクレジット（入るときだけ）
                thumb = None
                if p.get("videoUnsupported"):
                    thumb = upload_thumb(session, p["images"], used)
                    media = [{"type": "image", "url": u} for u in used]
            elif p.get("pictures"):
                # 2026-11-09 オーナー承認（台帳 S51）: ふつうの記事の投稿は、暗いリンクカードではなく記事の画像（Muse の図 → 写真のカード）を
                # 大きく付け、記事のリンクは本文の「続き（◯◯）→」の facet。上げられた画像の縦横で門番に通す
                by_url = {x["url"]: x for x in p["pictures"]}
                thumb = upload_thumb(session, list(by_url), used) if session and (live or args.slug) else None
                pick = by_url.get(used[0]) if used else (None if live else p["pictures"][0])
                if pick:
                    media = [{"type": "image", "url": pick["url"], "width": pick["width"], "height": pick["height"]}]
                    if thumb:
                        image = {"blob": thumb, "width": pick["width"], "height": pick["height"], "alt": pick.get("alt") or p["title"]}
            else:
                # 動画を作らない投稿・動画がまだ無い投稿・朝のまとめは、記事の写真（号のシェア画像）のリンクカード（ルール8・台帳 S13）
                thumb = upload_thumb(session, p["images"], used) if session and (live or args.slug) else None
                media = [{"type": "image", "url": u} for u in (used or ([] if live else p["images"][:1]))]  # 下書きは上げずに写真の URL で確かめる
            if live and kind == "brief" and not thumb and not blob:
                # 記事のカードがまだ開けない（公開の直後）。失敗として外さず、次の回にもう一度（11/8 九州電力の記事がこれで外れていた）
                log(f"  [bluesky] {key}: 記事のカードがまだ開けません。次の回にもう一度")
                continue
            record = build_record(p["text"], p["link"], p["title"], p["desc"], None if image else thumb, video=blob,
                                  full_text=p.get("full_text", ""), image=image)
            if not live:
                log(f"--- {key} ({kind})\n{json.dumps(record, ensure_ascii=False, indent=1)}")
                for v in sns_rules.check_post("bluesky", record["text"], media, p.get("gate"),
                                              kind=p.get("kind", "article"), links=[p["link"]]):
                    log(f"  [check] {v}")
                continue
            if vid and not blob and not p.get("videoUnsupported"):
                raise RuntimeError("動画を Bluesky に上げられませんでした")
            res = create_record(session, record, p, media)
            at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            if kind == "brief":
                slot = tp.sns_plan.bluesky_slot_window(now)
                extra[key] = {"uri": res["uri"], "at": at, "title": entry["article"].get("title", ""), "kind": "brief",
                              "slot": slot[1].strftime("%H:%M") if slot else "", "style": "reader" if p.get("kind") == "reader" else "classic"}
            else:
                entry.setdefault("channels", {})["bluesky"] = res["uri"]
                entry["blueskyAt"] = at
            log(f"  [bluesky] {key} ({kind}): https://bsky.app/profile/{session['handle']}/post/{res['uri'].rsplit('/', 1)[-1]}")
        except Exception as error:  # noqa: BLE001
            log(f"  [bluesky] {key} 失敗: {error}")
            if "メールアドレスが未確認" in str(error) and live:
                import sns_video_followup as fu  # noqa: PLC0415

                fu.missing_issue(key, f"Bluesky に動画で出せませんでした: {error}")
            if kind == "brief":  # 同じ記事で毎回失敗し続けないよう、記録して次へ（時刻なし＝本数に数えない。FAILED_RETRY_H 時間で候補に戻す）
                extra[key] = {"failed": str(error)[:200], "failedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                              "title": entry["article"].get("title", ""), "kind": "brief"}
            else:
                entry["blueskyFailed"] = str(error)[:200]
    if live:
        tp.save_state(state)
        if any(kind == "brief" for _, _, kind in todo):
            save_extra(extra)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

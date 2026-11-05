"""Instagram（@saisoku637・ビジネスアカウント）に、公式の Instagram Graph API（Content Publishing）で直接出す。Buffer は使わない
（2026-11-05 オーナー承認・台帳 S36）。Bluesky の直接投稿（scripts/bluesky_post.py）と同じ作り:

- 出すもの: SNS の予定（state/threads_posted.json）の記録のうち、まだ Instagram に出していないもの。選び方は bluesky_post.pending
  （同じ枠・Muse の動画待ち・取りこぼしを後から大量に出さない）を channel="instagram" で使う。枠の時刻＋ DELAY_MIN 分
  （Bluesky の20分と同じ分にならないよう13分。実行も Bluesky の */10 とずらして 5,15,25…分）。
- 記事の投稿は動画（リール。state/sns_video.json の SNS 用の動画 https://ai-tech-express.jp/video/...mp4）だけ（sns_rules ルール8）。
  動画の無い記事は出さない。朝のまとめは号のシェア画像（16:9 に近い 1200×630）、急ぎの安全の知らせは記事の写真だけのカード（16:9）。
  Instagram は JPEG しか受け付けないので、サイトの画像は Cloudflare の画像変換（/cdn-cgi/image/format=jpeg/...）で JPEG にして渡す。
- 文面は Threads・Bluesky と同じ予定の本文（bluesky_post.plan → sns_rules.autofix）。キャプションのリンクは押せないので
  URL は書かず、最後に「記事はプロフィールのリンクから」の1行（sns_rules.INSTAGRAM_LINK_LINE）。出す直前に sns_rules.enforce を通す。
- 1日 PER_DAY 本（朝のまとめは数えない）・通常は前の投稿から GAP_MIN 分あける・深夜（1〜5時）は出さない・
  content_publishing_limit（24時間で100本）を超えない。同じ記事は1回だけ（channels.instagram・自分の直近の投稿の文面も確かめる）。
- 結果は channels.instagram（メディアの id）・instagramAt・instagramPermalink に記録。失敗は instagramFailed（他の SNS には影響しない）。

切り替え（リポジトリの変数 INSTAGRAM_MODE）: off（既定。何もしない）／ dry（文面・画像・動画の URL を作って確かめるだけ。コンテナも作らない）／ live（出す）。
必要なもの: 変数 IG_USER_ID（Instagram のビジネスアカウントの id）・シークレット IG_ACCESS_TOKEN（システムユーザーのトークン）。無ければ何もしない。

  python3 scripts/instagram_post.py --dry-run           # 下書きを表示（投稿しない・コンテナも作らない）
  python3 scripts/instagram_post.py                     # INSTAGRAM_MODE=live のときだけ投稿
  python3 scripts/instagram_post.py --test-container image|video  # コンテナを作るだけ（公開しない）。トークン・権限の確認
  python3 scripts/instagram_post.py --token-check       # トークンの健康診断（読むだけ。期限を state/instagram_token.json に。7日未満で issue）
  python3 scripts/instagram_post.py --merge FILE        # 手元の記録を最新の state に足す

トークン（2026-11-05: Meta が出せたのは60日で切れるシステムユーザーのトークン）: 毎日 --token-check で期限を確かめ、残り7日未満・使えないときは
issue（ラベル instagram-token）でオーナーに知らせる。シークレット META_APP_SECRET と GH_SECRETS_TOKEN（シークレットを書ける GitHub のトークン）が
両方あるときだけ、自動で延ばしてシークレットを入れ替える（無ければ知らせるだけ）。
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
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bluesky_post as bp  # noqa: E402
import sns_rules  # noqa: E402
import threads_post as tp  # noqa: E402

CHANNEL = "instagram"
GRAPH_VERSION = os.environ.get("IG_GRAPH_VERSION") or "v25.0"  # 2026-02-18 公開・2028-07-29 まで（developers.facebook.com の版の一覧）
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
DELAY_MIN = 13  # 枠の時刻からの遅れ（Bluesky は20分。同じ分に並ばないように）
PER_DAY = min(int(os.environ.get("INSTAGRAM_PER_DAY") or 6), tp.sns_plan.daily_cap())  # 朝のまとめは数えない
GAP_MIN = int(os.environ.get("INSTAGRAM_GAP_MIN") or 40)
POLL_SEC = 20
POLL_MAX_SEC = 300  # 動画の処理を待つのは5分まで（公式の案内: 1分ごと・5分まで）
VIDEO_SIZE = {"width": 1920, "height": 1080}
MODES = ("off", "dry", "live")


def log(message: str) -> None:
    print(message, flush=True)


def mode() -> str:
    m = (os.environ.get("INSTAGRAM_MODE") or "off").strip().lower()
    return m if m in MODES else "off"


def credentials() -> tuple[str, str]:
    return (os.environ.get("IG_USER_ID") or "").strip(), (os.environ.get("IG_ACCESS_TOKEN") or "").strip()


class GraphError(RuntimeError):
    def __init__(self, message: str, code: int | None = None, status: int | None = None):
        self.code, self.status = code, status
        super().__init__(message)

    @property
    def auth(self) -> bool:
        """トークン・権限の問題（記事ごとの失敗にしない。直れば次の回に出す）"""
        return self.code in (10, 102, 190, 200) or self.status == 401


def graph(method: str, path: str, params: dict | None = None, token: str = "", opener=None) -> dict:
    """Graph API を呼ぶ。トークンは Authorization ヘッダーで送る（URL・ログに出さない）"""
    params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
    url = f"{GRAPH}/{path.lstrip('/')}"
    data = None
    if method == "GET":
        if params:
            url += "?" + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={"Authorization": f"Bearer {token}", "User-Agent": "saisoku-instagram/1.0"})
    try:
        with (opener or urllib.request.urlopen)(req, timeout=60) as res:
            return json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as error:
        try:
            err = (json.loads(error.read() or b"{}").get("error") or {})
        except ValueError:
            err = {}
        raise GraphError(f"Instagram API {error.code}: {err.get('message') or error.reason}（code {err.get('code')}"
                         f"{'/' + str(err.get('error_subcode')) if err.get('error_subcode') else ''}）", err.get("code"), error.code) from None


# ---- 画像・動画・本文 ----

def jpeg_url(url: str) -> str:
    """サイトの画像を JPEG で返す URL（Cloudflare の画像変換。大きさは変えない）。サイトの外の URL はそのまま"""
    parts = urllib.parse.urlsplit(url)
    if not (parts.hostname or "").endswith(sns_rules.SITE_HOST) or parts.path.startswith("/cdn-cgi/"):
        return url
    return urllib.parse.urlunsplit(parts._replace(path=f"/cdn-cgi/image/format=jpeg,quality=88{parts.path}"))


def caption(text: str, credit: str = "") -> str:
    """予定の本文（リンクの行は bluesky_post.plan で除いてある）＋プロフィールへの案内。URL・👇・多すぎるハッシュタグは外す"""
    lines = [ln for ln in str(text or "").splitlines() if not sns_rules.URL_RE.search(ln) and not ln.strip().startswith(tp.THREADS_LINK_LINE)]
    body = re.sub(r"\s*👇\s*$", "", re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip())
    tags = sns_rules.HASHTAG_RE.findall(body)
    for extra_tag in tags[sns_rules.INSTAGRAM_HASHTAG_MAX:]:
        body = re.sub(rf"(?<!\S){re.escape(extra_tag)}(?!\S)", "", body)
    body = re.sub(r"[ \t]+\n", "\n", body).strip()
    out = f"{body}\n\n{sns_rules.INSTAGRAM_LINK_LINE}"
    if credit:
        out += f"\n音声：{credit}"  # VOICEVOX の規約のクレジット
    return out


def build(key: str, entry: dict) -> dict | None:
    """投稿の中身 {caption, link, media（門番用）, params（コンテナ）, kind, gate}。出せないものは None（理由は skip）"""
    p = bp.plan(key, entry, platform=CHANNEL)
    if not p:
        return None
    kind = p.get("kind", "article")
    if kind == "digest":
        image = next((u for u in p.get("images") or [] if "/digest/" in u), "") or next(iter(p.get("images") or []), "")
        if not image:
            return {"skip": "朝のまとめの画像がありません"}
        url = jpeg_url(image)
        return {"caption": caption(p["text"]), "link": p["link"], "kind": kind, "gate": p["gate"],
                "media": [{"type": "image", "url": url}], "params": {"image_url": url}}
    if sns_rules.is_urgent(p.get("gate")):  # 急ぎの安全の知らせ（ルール8の例外）は写真だけのカード
        url = jpeg_url(tp.card_url(p["gate"]))
        return {"caption": caption(p["text"]), "link": p["link"], "kind": kind, "gate": p["gate"],
                "media": [{"type": "image", "url": url}], "params": {"image_url": url}}
    vid = bp.video_of(key)
    if not vid:
        return {"skip": "動画がまだありません（写真のカードでは出さない。ルール8）"}
    link = tp.utm_link(f"{tp.site_url()}/articles/{key}", CHANNEL, "sns_video", vid["variant"], ptype="hook" if entry.get("hookFormat") else "")
    return {"caption": caption(p["text"], vid.get("credit", "")), "link": link, "kind": kind, "gate": p["gate"],
            "media": [{"type": "video", "url": vid["url"], **VIDEO_SIZE}],
            "params": {"media_type": "REELS", "video_url": vid["url"], "share_to_feed": "true"}}


# ---- 選び方（bluesky_post と同じ。数え方だけ Instagram の記録） ----

def sent(state: dict, digest: bool = True) -> list[tuple[str, datetime]]:
    return [(k, t) for k, e in state.get("posted", {}).items()
            if (t := bp._parse(e.get(f"{CHANNEL}At"))) and (digest or e.get("style") != "digest")]


def posted_today(state: dict, now: datetime) -> int:
    """今日（日本時間）出した本数（朝のまとめは数えない）"""
    today = now.astimezone(tp.JST).date()
    return sum(1 for _, t in sent(state, digest=False) if t.astimezone(tp.JST).date() == today)


def last_sent(state: dict) -> datetime | None:
    times = [t for _, t in sent(state)]
    return max(times) if times else None


def choose(state: dict, now: datetime) -> list[tuple[str, dict]]:
    """この実行で出すもの。朝のまとめ・速報は間隔を待たない（1回に1本ずつ）。通常は上限内で1本・前の投稿から GAP_MIN 分あける"""
    todo = [(k, e) for k, e in bp.pending(state, now, None, channel=CHANNEL, delay=DELAY_MIN) if e.get("style") != "poll"]
    digests = [(k, e) for k, e in todo if e.get("style") == "digest"]
    if digests:
        return digests[:1]
    if posted_today(state, now) >= PER_DAY:
        return []
    fast = [(k, e) for k, e in todo if e.get("breaking")]
    if fast:
        return fast[:1]
    last = last_sent(state)
    if last and now - last < timedelta(minutes=GAP_MIN):
        return []
    return todo[:1]


# ---- 投稿 ----

def _norm(text: str) -> str:
    return re.sub(r"\s+", "", sns_rules.HASHTAG_RE.sub("", str(text or "")))


def existing_media(ig: str, token: str, text: str, call=None) -> str:
    """同じ文面の投稿が自分の直近の投稿にもうあれば、その id（二重に出さない）。読めなければ例外（出さない）"""
    want = _norm(text.replace(sns_rules.INSTAGRAM_LINK_LINE, ""))
    if not want:
        return ""
    res = (call or graph)("GET", f"{ig}/media", {"fields": "id,caption,timestamp", "limit": 30}, token)
    for item in res.get("data") or []:
        got = _norm(str(item.get("caption") or "").replace(sns_rules.INSTAGRAM_LINK_LINE, ""))
        if got and (got == want or SequenceMatcher(None, got, want).ratio() >= 0.9):
            return str(item.get("id") or "")
    return ""


def quota_left(ig: str, token: str, call=None) -> int | None:
    """24時間の投稿の残り（content_publishing_limit）。読めなければ None"""
    try:
        res = (call or graph)("GET", f"{ig}/content_publishing_limit", {"fields": "quota_usage,config"}, token)
    except GraphError as error:
        if error.auth:
            raise
        log(f"  [instagram] 投稿の上限を読めません: {error}")
        return None
    row = (res.get("data") or [{}])[0]
    total = int(((row.get("config") or {}).get("quota_total")) or 100)
    return total - int(row.get("quota_usage") or 0)


def wait_container(container: str, token: str, call=None, sleep=time.sleep, max_sec: int = POLL_MAX_SEC) -> str:
    """コンテナの処理を待つ（FINISHED を返す）。ERROR・EXPIRED・時間切れは例外"""
    waited = 0
    while True:
        res = (call or graph)("GET", container, {"fields": "status_code,status"}, token)
        code = res.get("status_code")
        if code in ("FINISHED", "PUBLISHED"):
            return code
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram がメディアを処理できませんでした（{code}: {str(res.get('status') or '')[:200]}）")
        if waited >= max_sec:
            raise TimeoutError(f"Instagram のメディアの処理が{max_sec // 60}分で終わりませんでした（{code}）")
        sleep(POLL_SEC)
        waited += POLL_SEC


def publish(ig: str, token: str, key: str, item: dict, call=None, sleep=time.sleep) -> dict:
    """1件出す。直前に SNS ルールの門番（sns_rules.enforce）を通し、同じ文面の投稿がもう無いかを確かめる。
    違反なら SnsRuleViolation（出さない）。{"id", "permalink", "existing"?}"""
    sns_rules.enforce(CHANNEL, item["caption"], item["media"], item["gate"], source="instagram_post", kind=item["kind"], links=[item["link"]])
    call = call or graph
    if found := existing_media(ig, token, item["caption"], call):
        log(f"  [instagram] 同じ文面の投稿がもうあります（{found}）。二重に出しません")
        return {"id": found, "existing": True}
    container = call("POST", f"{ig}/media", {**item["params"], "caption": item["caption"]}, token)["id"]
    wait_container(container, token, call, sleep)
    media_id = call("POST", f"{ig}/media_publish", {"creation_id": container}, token)["id"]
    permalink = ""
    try:
        permalink = call("GET", media_id, {"fields": "permalink"}, token).get("permalink", "")
    except GraphError as error:
        log(f"  [instagram] リンクを読めません（投稿はできています）: {error}")
    return {"id": media_id, "permalink": permalink}


def reachable(url: str, want: str) -> str:
    """dry 用: URL が公開されていて、種類（image/jpeg・video/）が合うか。問題があればその説明、無ければ \"\""""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "saisoku-instagram/1.0", "Range": "bytes=0-1023"})
        with urllib.request.urlopen(req, timeout=30) as res:
            ctype = res.headers.get_content_type()
    except Exception as error:  # noqa: BLE001
        return f"取りに行けません（{type(error).__name__}: {error}）"
    return "" if ctype.startswith(want) else f"種類が {ctype}（{want} が要る）"


def test_container(kind: str) -> int:
    """コンテナを作るだけ（公開しない）。トークン・権限・メディアの URL を確かめる。作ったコンテナは24時間で消える"""
    ig, token = credentials()
    if not ig or not token:
        log("[instagram] IG_USER_ID / IG_ACCESS_TOKEN がまだありません（何もしません）")
        return 1
    me = graph("GET", ig, {"fields": "username,name"}, token)  # 読むだけの呼び出しでトークンを確かめる
    log(f"[instagram] アカウント OK: @{me.get('username')}（{me.get('name', '')}）")
    rec = inspect_token(ig, token, datetime.now(timezone.utc), load_token_state())
    log(f"[instagram] トークンの期限: {rec['expiresAt']}{'（見込み）' if rec['estimated'] else ''}・権限 {rec.get('scopes', '?')}")
    log(f"[instagram] 24時間の投稿の残り: {quota_left(ig, token)}")
    state = tp.load_state()
    target = None
    for key, entry in reversed(list(state.get("posted", {}).items())):
        if entry.get("style"):
            continue
        if kind == "video" and not bp.video_of(key):
            continue
        if (tp.ARTICLES_DIR / f"{key}.json").exists():
            target = key
            break
    if not target:
        log("[instagram] 試しに使える記事がありません")
        return 1
    if kind == "video":
        params = {"media_type": "REELS", "video_url": bp.video_of(target)["url"], "share_to_feed": "true"}
    else:
        params = {"image_url": jpeg_url(tp.card_url({"slug": target}))}
    log(f"[instagram] コンテナを作ります（公開しません）: {target} {params}")
    container = graph("POST", f"{ig}/media", {**params, "caption": "（確認用。公開しません）"}, token)["id"]
    try:
        status = wait_container(container, token)
    except Exception as error:  # noqa: BLE001
        log(f"[instagram] コンテナ {container}: {error}")
        return 1
    log(f"[instagram] コンテナ {container}: {status}（公開していません。24時間で消えます）")
    return 0


# ---- トークンの健康診断（2026-11-05: Meta が出せたのは60日で切れるシステムユーザーのトークンだけ） ----
TOKEN_STATE = tp.ROOT / "state" / "instagram_token.json"
TOKEN_DAYS = 60  # 期限を読めないときの見込み（最初に見た日から60日）
TOKEN_WARN_DAYS = 7
TOKEN_ISSUE_LABEL = "instagram-token"
APP_ID = os.environ.get("META_APP_ID") or "1613125453175173"  # Saisoku Poster


def fingerprint(token: str) -> str:
    """トークンを見分ける短い印（sha256 の先頭8文字。トークンそのものは記録しない）"""
    import hashlib  # noqa: PLC0415

    return hashlib.sha256(token.encode()).hexdigest()[:8] if token else ""


def load_token_state(path: Path | None = None) -> dict:
    try:
        data = json.loads((path or TOKEN_STATE).read_text("utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def inspect_token(ig: str, token: str, now: datetime, prev: dict | None = None, call=None) -> dict:
    """トークンを読むだけの呼び出しで確かめる（/debug_token で期限、/{IG_USER_ID}?fields=username で使えるか）。
    期限を読めなければ、最初に見た日から60日の見込み（estimated）"""
    call = call or graph
    prev = prev or {}
    fp = fingerprint(token)
    rec = {"checkedAt": iso_z(now), "fingerprint": fp, "valid": False, "expiresAt": "", "estimated": False, "username": "", "error": ""}
    rec["firstSeenAt"] = prev.get("firstSeenAt") if prev.get("fingerprint") == fp and prev.get("firstSeenAt") else iso_z(now)
    try:
        rec["username"] = call("GET", ig, {"fields": "username"}, token).get("username", "")
        rec["valid"] = True
    except GraphError as error:
        rec["error"] = str(error)[:200]
    try:
        data = call("GET", "debug_token", {"input_token": token}, token).get("data") or {}
        if data:
            rec["valid"] = rec["valid"] and data.get("is_valid", True)
            rec["scopes"] = sorted(data.get("scopes") or [])
            exp = int(data.get("expires_at") or 0)
            rec["expiresAt"] = iso_z(datetime.fromtimestamp(exp, timezone.utc)) if exp else "never"
            if data.get("data_access_expires_at"):
                rec["dataAccessExpiresAt"] = iso_z(datetime.fromtimestamp(int(data["data_access_expires_at"]), timezone.utc))
    except GraphError as error:
        rec["debugError"] = str(error)[:200]
    if not rec["expiresAt"]:
        rec["expiresAt"] = iso_z(datetime.fromisoformat(rec["firstSeenAt"].replace("Z", "+00:00")) + timedelta(days=TOKEN_DAYS))
        rec["estimated"] = True
    return rec


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def days_left(rec: dict, now: datetime) -> float | None:
    if rec.get("expiresAt") in ("", "never", None):
        return None
    return (datetime.fromisoformat(rec["expiresAt"].replace("Z", "+00:00")) - now).total_seconds() / 86400


def refresh_token(token: str, call=None) -> str:
    """（META_APP_SECRET があるときだけ）システムユーザーのトークンを延ばす。新しいトークン（失敗は例外）"""
    secret = (os.environ.get("META_APP_SECRET") or "").strip()
    if not secret:
        raise RuntimeError("META_APP_SECRET がありません")
    res = (call or graph)("GET", "oauth/access_token", {"grant_type": "fb_exchange_token", "client_id": APP_ID, "client_secret": secret,
                                                         "set_token_expires_in_60_days": "true", "fb_exchange_token": token}, token)
    new = str(res.get("access_token") or "")
    if not new:
        raise RuntimeError("新しいトークンが返りませんでした")
    return new


def store_secret(new_token: str, run=None) -> None:
    """新しいトークンをリポジトリのシークレット IG_ACCESS_TOKEN に入れる（シークレットを書ける GH_SECRETS_TOKEN が要る）"""
    import subprocess  # noqa: PLC0415

    admin = (os.environ.get("GH_SECRETS_TOKEN") or "").strip()
    if not admin:
        raise RuntimeError("GH_SECRETS_TOKEN（シークレットを書ける GitHub のトークン）がありません")
    (run or subprocess.run)(["gh", "secret", "set", "IG_ACCESS_TOKEN"], input=new_token, text=True, check=True, capture_output=True,
                            env={**os.environ, "GH_TOKEN": admin}, timeout=60)


def token_alert(body: str, close: bool = False, gh=None) -> None:
    """オーナーへの知らせ（ラベル instagram-token の issue。開いていればコメント）。close=True なら開いている issue を閉じる"""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        log(f"[instagram] （知らせ）{body}")
        return
    gh = gh or sns_rules._gh
    try:
        found = gh("issue", "list", "--label", TOKEN_ISSUE_LABEL, "--state", "open", "--limit", "1", "--json", "number", "--jq", ".[0].number // empty")
        if close:
            if found:
                gh("issue", "close", found, "--comment", body)
            return
        if found:
            gh("issue", "comment", found, "--body", body)
            return
        try:
            gh("label", "create", TOKEN_ISSUE_LABEL, "--color", "D93F0B", "--description", "Instagram のトークンの期限・不具合", "--force")
        except Exception:  # noqa: BLE001
            pass
        gh("issue", "create", "--title", "Instagram のトークンの更新が必要です", "--label", TOKEN_ISSUE_LABEL, "--body", body)
    except Exception as error:  # noqa: BLE001
        log(f"[instagram] issue を立てられませんでした: {type(error).__name__}")


def token_check(now: datetime | None = None, call=None, gh=None, path: Path | None = None) -> int:
    """トークンの健康診断。期限を state/instagram_token.json に記録し、残り7日未満・使えないときはオーナーに知らせる。
    META_APP_SECRET と GH_SECRETS_TOKEN があれば、7日未満で自動で延ばす（無ければ知らせるだけ）"""
    now = now or datetime.now(timezone.utc)
    ig, token = credentials()
    path = path or TOKEN_STATE
    if not ig or not token:
        log("[instagram] IG_USER_ID / IG_ACCESS_TOKEN がまだありません（健康診断はしません）")
        return 0
    rec = inspect_token(ig, token, now, load_token_state(path), call)
    left = days_left(rec, now)
    log(f"[instagram] トークン: {'使える' if rec['valid'] else '使えない'}・@{rec['username']}・期限 {rec['expiresAt']}"
        f"{'（見込み）' if rec['estimated'] else ''}・残り {'—' if left is None else f'{left:.1f}日'}")
    howto = ("Meta のビジネス設定 → システムユーザー → 「トークンを生成」（アプリ Saisoku Poster・instagram_basic と instagram_content_publish）で"
             "新しいトークンを作り、GitHub のシークレット IG_ACCESS_TOKEN を入れ替えてください。")
    if rec["valid"] and left is not None and left < TOKEN_WARN_DAYS:
        if os.environ.get("META_APP_SECRET") and os.environ.get("GH_SECRETS_TOKEN"):
            try:
                store_secret(refresh_token(token, call))
                rec["refreshedAt"] = iso_z(now)
                rec["firstSeenAt"] = iso_z(now)
                rec["expiresAt"], rec["estimated"] = iso_z(now + timedelta(days=TOKEN_DAYS)), True
                log("[instagram] トークンを自動で延ばしました（シークレットを入れ替え）")
                token_alert(f"Instagram のトークンを自動で延ばしました（{rec['refreshedAt']}）。", gh=gh)
                left = None
            except Exception as error:  # noqa: BLE001
                log(f"[instagram] 自動で延ばせませんでした: {error}")
                rec["refreshError"] = str(error)[:200]
        if left is not None:
            token_alert(f"Instagram のトークンの期限まで あと{max(left, 0):.1f}日（{rec['expiresAt']}{'・見込み' if rec['estimated'] else ''}）。\n\n{howto}", gh=gh)
    elif not rec["valid"]:
        token_alert(f"Instagram のトークンが使えません（{rec.get('error') or '無効'}）。\n\n{howto}", gh=gh)
    else:
        token_alert(f"Instagram のトークンは使えます（期限 {rec['expiresAt']}）。", close=True, gh=gh)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--merge", default="")
    parser.add_argument("--slug", default="", help="確認用: この記録を対象にする（--dry-run と一緒に）")
    parser.add_argument("--test-container", choices=("image", "video"), default="", help="コンテナを作るだけ（公開しない）")
    parser.add_argument("--token-check", action="store_true", help="トークンの健康診断（期限を記録・7日未満で知らせる）")
    args = parser.parse_args()
    if args.token_check:
        return token_check()
    if args.merge:
        return bp.merge(args.merge, channel=CHANNEL)
    if args.test_container:
        return test_container(args.test_container)
    m = mode()
    if m == "off" and not args.dry_run:
        log("[instagram] INSTAGRAM_MODE が off のため何もしません（dry で確認・live で投稿）")
        return 0
    live = m == "live" and not args.dry_run
    ig, token = credentials()
    if live and (not ig or not token):
        log("[instagram] IG_USER_ID / IG_ACCESS_TOKEN がまだありません（何もしません）")
        return 0
    state = tp.load_state()
    now = datetime.now(timezone.utc)
    if live and now.astimezone(tp.JST).hour in tp.BREAKING_QUIET_HOURS_JST:
        log("[instagram] 深夜のため出しません")
        return 0
    if args.slug:
        todo = [(args.slug, state["posted"][args.slug])]
    else:
        todo = choose(state, now)
        log(f"[instagram] 今日 {posted_today(state, now)}/{PER_DAY} 本（まとめを除く）・前回 {last_sent(state)}")
        if not todo and not live:  # 下書きは動画のある最新の記事を見本にする
            todo = [(k, e) for k, e in state["posted"].items() if not e.get("style") and bp.video_of(k)][-1:]
    if not todo:
        log("[instagram] 出すものはありません（上限・間隔・対象なし）")
        return 0
    if not live:
        if ig and token:
            try:
                log(f"[instagram] トークン OK・24時間の投稿の残り: {quota_left(ig, token)}")
            except GraphError as error:
                log(f"[instagram] トークンを確かめられません: {error}")
        for key, entry in todo:
            item = build(key, entry)
            if not item or item.get("skip"):
                log(f"--- {key}: 出しません（{(item or {}).get('skip', '出せない種類')}）")
                continue
            log(f"--- {key} ({item['kind']})\n{item['caption']}\n[link] {item['link']}\n[container] {json.dumps(item['params'], ensure_ascii=False)}")
            for media in item["media"]:
                if problem := reachable(media["url"], "video/" if media["type"] == "video" else "image/jpeg"):
                    log(f"  [check] {media['url']}: {problem}")
            for v in sns_rules.check_post(CHANNEL, item["caption"], item["media"], item["gate"], kind=item["kind"], links=[item["link"]]):
                log(f"  [check] {v}")
        return 0
    left = quota_left(ig, token)
    if left is not None and left <= 0:
        log("[instagram] 24時間の投稿の上限に届いています（次の回に）")
        return 0
    for key, entry in todo:
        try:
            item = build(key, entry)
            if not item:
                entry[f"{CHANNEL}Failed"] = "skip"
                continue
            if item.get("skip"):
                log(f"  [instagram] {key}: {item['skip']}")
                continue
            res = publish(ig, token, key, item)
            entry.setdefault("channels", {})[CHANNEL] = res["id"]
            entry[f"{CHANNEL}At"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            if res.get("permalink"):
                entry[f"{CHANNEL}Permalink"] = res["permalink"]
            log(f"  [instagram] {key}: {res.get('permalink') or res['id']}")
        except GraphError as error:
            log(f"  [instagram] {key} 失敗: {error}")
            if error.auth:  # トークン・権限の問題は記事の失敗にしない（直れば次の回に出す）
                summary = os.environ.get("GITHUB_STEP_SUMMARY")
                if summary:
                    with open(summary, "a", encoding="utf-8") as f:
                        f.write(f"### Instagram のトークン・権限の問題\n\n{error}\n")
                break
            entry[f"{CHANNEL}Failed"] = str(error)[:200]
        except sns_rules.SnsRuleViolation as error:
            log(f"  [instagram] {key} 門番が止めました: {error}")
            entry[f"{CHANNEL}Failed"] = str(error)[:200]
        except Exception as error:  # noqa: BLE001  Instagram の失敗で他を止めない
            log(f"  [instagram] {key} 失敗: {error}")
            entry[f"{CHANNEL}Failed"] = str(error)[:200]
    tp.save_state(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

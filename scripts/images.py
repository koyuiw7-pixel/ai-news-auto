#!/usr/bin/env python3
"""記事の写真を選ぶ（3段階）。写真の無い記事・ロゴだけの記事を、大手ニュースサイトのような写真入りにする。

  1. 元記事の写真: og:image / twitter:image / 本文中のいちばん大きい画像。
     幅 800px 未満・極端な縦横比・ロゴ（無地の地に文字だけ）・サイト共通の既定画像は使わない
  2. フリー素材: Wikimedia Commons と Openverse（CC0・パブリックドメイン・CC BY だけ。商用可・改変可）。
     検索語は記事から軽量モデル（scripts/llm.py の bulk）が作る具体的な英語の名詞句
  3. AI 生成: Cloudflare Workers AI（flux-2-klein-4b → flux-1-schnell）。文字・ロゴ・実在の人物なし。1日 IMAGE_AI_DAILY_MAX 枚まで

2・3 の画像は 1200×630 の JPEG（約100KB）と一覧用 640×336 の WebP（約30KB）にして
Workers KV（saisoku-images）へ置き、サイトの /img/<名前> で配信する（cloudflare/worker.ts）。
記事 JSON には thumbnail（画像の URL）と imageCredit（出典・ライセンス・作者）を書く。
YouTube のサムネイルはそのまま使う。

  python3 scripts/images.py --changed            # このワークツリーで増えた・変わった記事だけ（auto_run.yml）
  python3 scripts/images.py --recent 40          # 新しい40本のうち未確認のもの
  python3 scripts/images.py --all --max 50       # 全記事（新しい順）を点検して直す（さかのぼり）
  python3 scripts/images.py --slug <slug> --dry-run

必要な環境変数: CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN（Workers AI）/ CF_KV_TOKEN（KV への書き込み。無ければ
CLOUDFLARE_API_TOKEN）。手元では wrangler のログイン情報を使う。検索語づくりは GEMINI_API_KEY など（llm.py と同じ）。
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import llm  # noqa: E402

try:
    from PIL import Image, ImageOps

    Image.MAX_IMAGE_PIXELS = 60_000_000
except ImportError:  # pragma: no cover - CI では requirements.txt で入る
    Image = None
    ImageOps = None

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"
ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or "51e37d82e15d397b9666dc3d09bd5b92"
KV_NAMESPACE = os.environ.get("IMAGES_KV_ID") or "358e46161fdb4857865dec69dd72285b"
IMAGE_BASE = (os.environ.get("IMAGE_BASE_URL") or "https://ai-tech-express.jp/img/").rstrip("/") + "/"
AI_DAILY_MAX = int(os.environ.get("IMAGE_AI_DAILY_MAX") or "40")
PREVIEW_DIR: Path | None = None  # --preview で指定すると、出来上がった JPEG をここにも書く（確認用）

# Wikimedia は連絡先入りの UA を求める（https://meta.wikimedia.org/wiki/User-Agent_policy）
BOT_UA = "SaisokuNewsBot/1.0 (+https://ai-tech-express.jp/contact)"
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"

MIN_SOURCE_WIDTH = 800
MIN_STOCK_WIDTH = 1200
MAX_BYTES = 15 * 1024 * 1024
OUT_W, OUT_H = 1200, 630
SMALL_W, SMALL_H = 640, 336
JPEG_MAX_BYTES = 140 * 1024

# ロゴ・アイコン・既定画像らしい URL
LOGO_URL = re.compile(
    r"(logo|favicon|apple-touch|/icons?/|[-_/]icon[-_.]|noimage|no[-_]image|now[-_]?printing|placeholder|dummy|spacer|blank\.|sprite|avatar)",
    re.I,
)
GENERIC_OG = re.compile(r"(/|[-_])(ogp?|og[-_]?image|ogp[-_]?image|share|sns|social|default|site)[-_]?(image|img|default)?\d?\.(png|jpe?g|webp)$", re.I)
SHARED_DIR = re.compile(r"/(common|themes?|assets?|shared|static|img/common|images/common|site)/", re.I)
# 素材の題名で避けるもの（人物・図・文字の多いもの）
BAD_STOCK_TITLE = re.compile(
    r"\b(logos?|maps?|diagrams?|charts?|graphs?|plots?|posters?|flyers?|leaflets?|signs?|signage|screenshots?|screen shot|flags?|emblems?|"
    r"coat of arms|portraits?|selfies?|headshots?|signatures?|documents?|scanned|page \d+|book cover|cover art|stamps?|banknotes?|"
    r"banners?|infographics?|illustrations?|drawings?|cartoons?|icons?|texts?|memes?|watermarks?|nude|naked|weapons?|corpses?|blood)\b",
    re.I,
)
# 人物が主役の写真（特に子ども）は避ける
PEOPLE_TITLE = re.compile(r"\b(child|children|kid|kids|girl|girls|boy|boys|baby|toddler|woman|women|man|men|people|person|selfie|face|family|teen|student|students)\b", re.I)


def log(message: str) -> None:
    print(message, flush=True)


# --------------------------------------------------------------------------- #
# 通信
# --------------------------------------------------------------------------- #


def http_get(url: str, *, ua: str = BROWSER_UA, accept: str = "*/*", timeout: int = 20, limit: int = MAX_BYTES, referer: str = "") -> tuple[bytes, str, str]:
    """(中身, Content-Type, 最終URL)。大きすぎるものは途中で打ち切って例外"""
    headers = {"User-Agent": ua, "Accept": accept, "Accept-Language": "ja,en;q=0.8"}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as res:
        length = int(res.headers.get("Content-Length") or 0)
        if length > limit:
            raise ValueError(f"大きすぎる（{length // 1024}KB）")
        data = res.read(limit + 1)
        if len(data) > limit:
            raise ValueError("大きすぎる")
        return data, res.headers.get("Content-Type", ""), res.geturl()


def http_json(url: str, *, ua: str = BOT_UA, timeout: int = 20) -> dict:
    data, _, _ = http_get(url, ua=ua, accept="application/json", timeout=timeout, limit=4 * 1024 * 1024)
    return json.loads(data.decode("utf-8"))


_cf_token_cache: dict[str, str] = {}


def wrangler_token() -> str:
    """手元の wrangler ログイン（OAuth）のトークン。期限切れなら wrangler whoami で更新させる"""
    if "wrangler" in _cf_token_cache:
        return _cf_token_cache["wrangler"]
    paths = [
        Path.home() / "Library" / "Preferences" / ".wrangler" / "config" / "default.toml",
        Path.home() / ".config" / ".wrangler" / "config" / "default.toml",
        Path.home() / ".wrangler" / "config" / "default.toml",
    ]
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text("utf-8")
        exp = re.search(r'expiration_time\s*=\s*"([^"]+)"', text)
        if exp:
            try:
                expires = datetime.fromisoformat(exp.group(1).replace("Z", "+00:00"))
                if (expires - datetime.now(timezone.utc)).total_seconds() < 300:
                    subprocess.run(["npx", "--yes", "wrangler", "whoami"], cwd=ROOT.parent if not (ROOT / "node_modules").exists() else ROOT, capture_output=True, timeout=120)
                    text = path.read_text("utf-8")
            except Exception:  # noqa: BLE001
                pass
        match = re.search(r'oauth_token\s*=\s*"([^"]+)"', text)
        if match:
            _cf_token_cache["wrangler"] = match.group(1)
            return match.group(1)
    return ""


def cf_token(kind: str) -> str:
    if kind == "kv":
        token = os.environ.get("CF_KV_TOKEN") or os.environ.get("CLOUDFLARE_API_TOKEN")
    else:
        token = os.environ.get("CLOUDFLARE_API_TOKEN")
    return token or wrangler_token()


def kv_put(key: str, data: bytes) -> None:
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/storage/kv/namespaces/{KV_NAMESPACE}/values/{urllib.parse.quote(key, safe='')}"
    req = urllib.request.Request(
        url,
        data=data,
        method="PUT",
        headers={"Authorization": f"Bearer {cf_token('kv')}", "Content-Type": "application/octet-stream"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                body = json.loads(res.read() or b"{}")
                if body.get("success", True):
                    return
                raise RuntimeError(str(body)[:200])
        except urllib.error.HTTPError as error:
            detail = error.read()[:200]
            if error.code < 500 or attempt == 2:
                raise RuntimeError(f"KV への保存に失敗（{error.code} {detail!r}）") from error
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 + attempt * 3)


# --------------------------------------------------------------------------- #
# 画像の検査
# --------------------------------------------------------------------------- #


def open_image(data: bytes):
    if Image is None:
        raise RuntimeError("Pillow が必要です（pip install pillow）")
    image = Image.open(io.BytesIO(data))
    image.load()
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        bg = Image.new("RGB", image.size, "white")
        bg.paste(image, mask=image.split()[-1])
        image = bg
    return image.convert("RGB")


def graphic_stats(image) -> dict:
    """無地の地の割合（ロゴ・文字だけの画像の目印）と色の多さ"""
    small = image.resize((160, 84))
    pixels = small.tobytes()
    n = len(pixels) // 3
    bins: Counter = Counter()
    rg_sum = yb_sum = rg_sq = yb_sq = 0.0
    for i in range(0, len(pixels), 3):
        r, g, b = pixels[i], pixels[i + 1], pixels[i + 2]
        bins[(r >> 4, g >> 4, b >> 4)] += 1
        rg = r - g
        yb = 0.5 * (r + g) - b
        rg_sum += rg
        yb_sum += yb
        rg_sq += rg * rg
        yb_sq += yb * yb
    rg_mean, yb_mean = rg_sum / n, yb_sum / n
    rg_std = max(0.0, rg_sq / n - rg_mean**2) ** 0.5
    yb_std = max(0.0, yb_sq / n - yb_mean**2) ** 0.5
    colorful = (rg_std**2 + yb_std**2) ** 0.5 + 0.3 * (rg_mean**2 + yb_mean**2) ** 0.5
    top = bins.most_common(1)[0][1] / n
    return {"flat": round(top, 3), "bins": len(bins), "colorful": round(colorful, 1)}


def image_problem(image, min_width: int) -> str | None:
    """使えない理由（使えるなら None）"""
    w, h = image.size
    if w < min_width or h < 400:
        return f"小さい（{w}×{h}）"
    ratio = w / h
    if ratio < 1.2 or ratio > 2.6:
        return f"縦横比が合わない（{w}×{h}）"
    stats = graphic_stats(image)
    if stats["flat"] >= 0.88 or stats["bins"] <= 24:
        return f"ロゴ・無地の図（無地 {stats['flat']:.0%}・色 {stats['bins']}）"
    if stats["flat"] >= 0.75 and stats["colorful"] < 4:
        return f"文字だけの図（無地 {stats['flat']:.0%}）"
    return None


def url_problem(url: str, repeats: int) -> str | None:
    if not url or not re.match(r"^https?://", url):
        return "画像なし"
    path = urllib.parse.urlparse(url).path
    if re.search(r"\.(svg|gif|ico)(\?|$)", path, re.I):
        return "SVG・GIF・アイコン"
    if LOGO_URL.search(path):
        return "ロゴ・アイコンの URL"
    if repeats >= 3:
        return f"サイト共通の既定画像（{repeats}本で同じ画像）"
    if GENERIC_OG.search(path) and (SHARED_DIR.search(path) or not re.search(r"\d{4,}", path)):
        return "サイト共通の既定画像（ファイル名）"
    return None


def is_youtube(url: str) -> bool:
    return bool(re.match(r"^https://(i\.ytimg\.com|img\.youtube\.com)/", url or ""))


def is_ours(url: str) -> bool:
    return (url or "").startswith(IMAGE_BASE)


# --------------------------------------------------------------------------- #
# 1. 元記事の写真
# --------------------------------------------------------------------------- #


class _ImageCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.images: list[tuple[int, int, str]] = []  # (優先度, 宣言された幅, URL)
        self.depth_main = 0
        self.order = 0

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key in {"og:image", "og:image:url", "og:image:secure_url", "twitter:image", "twitter:image:src"} and a.get("content"):
                self.meta.setdefault(key, a["content"].strip())
            return
        if tag == "link" and a.get("rel", "").lower() == "image_src" and a.get("href"):
            self.meta.setdefault("image_src", a["href"].strip())
            return
        if tag in ("article", "main"):
            self.depth_main += 1
            return
        if tag not in ("img", "source"):
            return
        cls = f"{a.get('class', '')} {a.get('id', '')} {a.get('alt', '')}"
        if re.search(r"(logo|icon|avatar|profile|sns|share|banner|btn|button|arrow|badge|qr)", cls, re.I):
            return
        url, width = "", 0
        srcset = a.get("srcset") or a.get("data-srcset") or ""
        if srcset:
            best = 0
            for part in srcset.split(","):
                bits = part.strip().split()
                if not bits:
                    continue
                w = int(re.sub(r"\D", "", bits[1]) or 0) if len(bits) > 1 and bits[1].endswith("w") else 0
                if w >= best:
                    best, url = w, bits[0]
            width = best
        url = url or a.get("data-src") or a.get("data-original") or a.get("data-lazy-src") or a.get("src") or ""
        if not url or url.startswith("data:"):
            return
        try:
            width = width or int(re.sub(r"\D", "", a.get("width", "")) or 0)
        except ValueError:
            width = 0
        if 0 < width < MIN_SOURCE_WIDTH // 2:
            return
        self.order += 1
        priority = 0 if self.depth_main else 1
        self.images.append((priority, -width, self.order, url))

    def handle_endtag(self, tag):
        if tag in ("article", "main") and self.depth_main:
            self.depth_main -= 1


def source_candidates(page_url: str, known: str) -> list[str]:
    """元記事の画像候補（og:image → 本文中の大きい画像の順）"""
    out: list[str] = []
    if known:
        out.append(known)
    if not page_url:
        return out
    try:
        data, _, final = http_get(page_url, accept="text/html,application/xhtml+xml", timeout=20, limit=6 * 1024 * 1024)
    except Exception as error:  # noqa: BLE001
        # ボット除けで弾かれるページは、読み取りサービス（r.jina.ai）で描画後の HTML を取る（feeds.py と同じ）
        try:
            req = urllib.request.Request(
                "https://r.jina.ai/" + page_url,
                headers={"User-Agent": BOT_UA, "X-Return-Format": "html", **({"Authorization": f"Bearer {os.environ['JINA_API_KEY']}"} if os.environ.get("JINA_API_KEY") else {})},
            )
            with urllib.request.urlopen(req, timeout=45) as res:
                data = res.read(6 * 1024 * 1024)
            final = page_url
        except Exception as error2:  # noqa: BLE001
            log(f"   [img] 元記事を開けない: {str(error)[:60]} / {str(error2)[:60]}")
            return out
    head = data[:4000].decode("ascii", "ignore")
    match = re.search(r"charset=[\"']?([\w-]+)", head, re.I)
    text = ""
    for enc in [match.group(1) if match else None, "utf-8", "cp932", "euc-jp"]:
        if not enc:
            continue
        try:
            text = data.decode(enc)
            break
        except (LookupError, UnicodeDecodeError):
            continue
    parser = _ImageCollector()
    try:
        parser.feed(text or data.decode("utf-8", "ignore"))
    except Exception:  # noqa: BLE001
        pass
    for key in ("og:image", "og:image:secure_url", "og:image:url", "twitter:image", "twitter:image:src", "image_src"):
        if parser.meta.get(key):
            out.append(parser.meta[key])
    for _, _, _, url in sorted(parser.images)[:8]:
        out.append(url)
    seen, result = set(), []
    for url in out:
        full = urllib.parse.urljoin(final, html.unescape(url.strip()))
        if full not in seen and full.startswith("http"):
            seen.add(full)
            result.append(full)
    return result


def pick_source_image(article: dict, repeats: Counter) -> tuple[str | None, str]:
    """(使える元記事の画像URL, 使わなかった理由)"""
    current = article.get("thumbnail", "") or ""
    reasons = []
    page = article.get("sourceUrl", "") if article.get("sourceType") == "web" else ""
    for index, url in enumerate(source_candidates(page, current)[:6]):
        problem = url_problem(url, repeats.get(url, 0))
        if problem:
            reasons.append(problem)
            continue
        try:
            data, ctype, _ = http_get(url, accept="image/avif,image/webp,image/*,*/*;q=0.8", referer=page, timeout=20)
            if ctype and not ctype.startswith("image/") and "octet-stream" not in ctype:
                reasons.append("画像ではない")
                continue
            problem = image_problem(open_image(data), MIN_SOURCE_WIDTH)
        except Exception as error:  # noqa: BLE001
            problem = f"読めない（{str(error)[:40]}）"
        if problem:
            reasons.append(problem)
            continue
        return url, ""
    return None, " / ".join(dict.fromkeys(reasons)) or "候補なし"


# --------------------------------------------------------------------------- #
# 検索語（軽量モデル）
# --------------------------------------------------------------------------- #

QUERY_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "queries": {"type": "ARRAY", "items": {"type": "STRING"}},
        "query_ja": {"type": "STRING"},
        "scene": {"type": "STRING"},
    },
    "required": ["queries", "scene"],
}

# 記事づくりと Gemini の無料枠を取り合わないよう、Workers AI（1本あたり0.1円未満）→ Gemma の順に使う。
# Claude は使わない（オーナーの枠のため）
IMAGE_LLM_PREFER = [m.strip() for m in (os.environ.get("IMAGES_LLM_MODELS") or "cloudflare:@cf/openai/gpt-oss-120b,gemma-4-26b-a4b-it,gemini-3.1-flash-lite").split(",") if m.strip()]


def llm_tier() -> str:
    if "images" not in llm._tiers:
        bulk = llm.models_for("bulk")
        prefer = [m for m in IMAGE_LLM_PREFER if m in bulk]
        rest = [m for m in bulk if m not in prefer and not m.startswith(("claude:", "codex:"))]
        llm._tiers["images"] = prefer + rest
    return "images"


QUERY_SYSTEM = (
    "You are a photo editor at a Japanese news site. For each article you choose a stock photo for the thumbnail. "
    "Return JSON only."
)


def visual_plan(article: dict) -> dict:
    prompt = f"""Article (Japanese):
title: {article.get('title', '')}
summary: {article.get('description', '')}
genre: {article.get('genre', '')}
tags: {', '.join(article.get('tags', [])[:8])}
source: {article.get('sourceName') or article.get('channel', '')}

Return:
- "queries": 3 short English search queries (1-3 words each) for a free photo library such as Wikimedia Commons.
  Concrete, photographable nouns that a viewer would connect with the topic: places, objects, scenes, activities
  (e.g. "rice paddy", "evacuation shelter", "beverage cans", "server room", "tokyo skyline", "hospital corridor").
  Order from most specific to most generic. Add "japan" only when the place matters.
  NEVER use company names, brand or product names, logos, names of real people, or abstract words (innovation, policy, strategy, future).
- "query_ja": one Japanese search phrase (1-2 words) of the same kind.
- "scene": one English sentence describing a neutral, photorealistic editorial news photo for this article
  (subject, setting, light). No text, no signs, no logos, no brand names, no identifiable real people
  (people only from behind, as hands, or out of focus)."""
    data, model = llm.generate_json(QUERY_SYSTEM, prompt, QUERY_SCHEMA, tier=llm_tier(), temperature=0.3, max_output_tokens=2048)
    queries = []
    for q in data.get("queries") or []:
        q = re.sub(r"[^\w\s'-]", " ", str(q)).strip()
        q = re.sub(r"\s+", " ", q)
        if q and len(q) <= 40 and q.lower() not in queries:
            queries.append(q.lower())
    return {
        "queries": queries[:3],
        "query_ja": str(data.get("query_ja") or "").strip()[:20],
        "scene": str(data.get("scene") or "").strip()[:400],
        "model": model,
    }


# --------------------------------------------------------------------------- #
# 2. フリー素材
# --------------------------------------------------------------------------- #


def strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def normalize_license(name: str) -> str:
    name = (name or "").strip()
    low = name.lower()
    if low in ("cc0", "cc-0", "cc zero") or low.startswith("cc0"):
        return "CC0"
    if low.startswith("public domain") or low in ("pd", "pdm") or low.startswith("pd-"):
        return "Public Domain"
    match = re.match(r"^cc[ -]by[ -](\d(?:\.\d)?)(?:[ -]([a-z]+))?$", low)
    if match:
        port = f" {match.group(2).upper()}" if match.group(2) and match.group(2) not in ("sa",) else ""
        if match.group(2) == "sa":
            return ""
        return f"CC BY {match.group(1)}{port}"
    if re.match(r"^by$", low):
        return "CC BY"
    return ""


_wiki_failures = 0
_wiki_last = 0.0
WIKI_INTERVAL = float(os.environ.get("WIKI_INTERVAL") or "3")


def search_wikimedia(query: str, limit: int = 10, quality: bool = False) -> list[dict]:
    """quality=True は Commons の「Quality images」（写りの審査を通ったもの）だけから探す。
    混雑（429・503）は少し待って3回まで。5回続けて失敗したらその回は使わない"""
    global _wiki_failures
    if _wiki_failures >= 5:
        return []
    search = f'{query} filetype:bitmap filemime:image/jpeg filew:>{MIN_STOCK_WIDTH - 1} -incategory:"Images with watermarks"'
    if quality:
        search += ' incategory:"Quality images"'
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "generator": "search",
        "gsrnamespace": "6",
        "gsrlimit": str(limit),
        "gsrsearch": search,
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": "1280",
        "iiextmetadatafilter": "LicenseShortName|Artist|LicenseUrl|ImageDescription|ObjectName|Restrictions|AttributionRequired",
    }
    data = None
    global _wiki_last
    for attempt in range(3):
        # 続けて叩くと 503 で締め出されるので、間を空ける
        time.sleep(max(0.0, WIKI_INTERVAL - (time.time() - _wiki_last)))
        _wiki_last = time.time()
        try:
            data = http_json("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params), timeout=25)
            break
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                log(f"   [img] Wikimedia 検索に失敗: {error.code}")
                break
            wait = int(error.headers.get("Retry-After") or 0) or 5 * (attempt + 1)
            time.sleep(min(wait, 30))
        except Exception as error:  # noqa: BLE001
            log(f"   [img] Wikimedia 検索に失敗: {str(error)[:80]}")
            break
    if data is None:
        _wiki_failures += 1
        return []
    _wiki_failures = 0
    pages = sorted((data.get("query") or {}).get("pages") or [], key=lambda p: p.get("index", 0))
    out = []
    for page in pages:
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        value = lambda k: (meta.get(k) or {}).get("value", "")  # noqa: E731
        license_name = normalize_license(strip_tags(value("LicenseShortName")))
        if not license_name or strip_tags(value("Restrictions")):
            continue
        title = page.get("title", "").removeprefix("File:")
        out.append(
            {
                "provider": "Wikimedia Commons",
                "title": re.sub(r"\.(jpe?g)$", "", title, flags=re.I).replace("_", " "),
                "description": strip_tags(value("ImageDescription"))[:200],
                "creator": strip_tags(value("Artist"))[:80] or "不明",
                "creatorUrl": "",
                "license": license_name,
                "licenseUrl": strip_tags(value("LicenseUrl")),
                "sourceUrl": info.get("descriptionurl") or f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(page.get('title', ''))}",
                "download": info.get("thumburl") or info.get("url", ""),
                "width": int(info.get("width") or 0),
                "height": int(info.get("height") or 0),
                "query": query,
                "quality": quality,
            }
        )
    return out


_openverse_down = False


def search_openverse(query: str, limit: int = 12) -> list[dict]:
    """Openverse（Flickr など）。鍵なしの匿名利用（1日の上限は小さいので失敗したらその回は使わない）"""
    global _openverse_down
    if _openverse_down:
        return []
    params = {
        "q": query,
        "license": "cc0,pdm,by",
        "category": "photograph",
        "aspect_ratio": "wide",
        "size": "large",
        "mature": "false",
        "excluded_source": "wikimedia",
        "page_size": str(limit),
    }
    try:
        data = http_json("https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(params), timeout=15)
    except Exception as error:  # noqa: BLE001
        log(f"   [img] Openverse に失敗（この回は使わない）: {str(error)[:80]}")
        _openverse_down = True
        return []
    out = []
    for item in data.get("results") or []:
        license_name = {"cc0": "CC0", "pdm": "Public Domain", "by": f"CC BY {item.get('license_version') or ''}".strip()}.get(item.get("license", ""))
        if not license_name or not item.get("url"):
            continue
        # Flickr の中サイズ（_b=1024px 以下）は幅が足りない
        if re.search(r"staticflickr\.com/.+_[bczmnstq]\.jpg$", item["url"]) or "rawpixel" in str(item.get("source") or item.get("provider") or ""):
            continue
        out.append(
            {
                "provider": f"Openverse（{item.get('source') or item.get('provider') or ''}）".replace("（）", ""),
                "title": str(item.get("title") or "")[:120],
                "description": ", ".join(t.get("name", "") for t in (item.get("tags") or [])[:8]),
                "creator": str(item.get("creator") or "不明")[:80],
                "creatorUrl": item.get("creator_url") or "",
                "license": license_name,
                "licenseUrl": item.get("license_url") or "",
                "sourceUrl": item.get("foreign_landing_url") or "",
                "download": item["url"],
                "width": int(item.get("width") or 0),
                "height": int(item.get("height") or 0),
                "query": query,
            }
        )
    return out


def stock_ok(item: dict, used: set[str]) -> bool:
    w, h = item["width"], item["height"]
    if item["sourceUrl"] in used:
        return False
    if w and h and (w < MIN_STOCK_WIDTH or not (1.25 <= w / h <= 2.4)):
        return False
    if BAD_STOCK_TITLE.search(f"{item['title']} {item['description'][:80]}") or PEOPLE_TITLE.search(item["title"]):
        return False
    return True


VISION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "related": {"type": "BOOLEAN"},
        "brand_or_text": {"type": "BOOLEAN"},
        "person_main": {"type": "BOOLEAN"},
        "why": {"type": "STRING"},
    },
    "required": ["related", "brand_or_text", "person_main"],
}


def vision_check(image, article: dict) -> str | None:
    """選んだ素材を画像で確かめる（軽量モデル）。問題があれば理由。確かめられないときは None（通す）"""
    try:
        from google.genai import types
    except ImportError:
        return None
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        return None
    small = image.copy()
    small.thumbnail((640, 640))
    buf = io.BytesIO()
    small.save(buf, "JPEG", quality=80)
    prompt = (
        f"News article title (Japanese): {article.get('title', '')}\n"
        "This photo will be the article thumbnail, labeled as an illustrative image.\n"
        "related: is the photo clearly related to the article topic?\n"
        "brand_or_text: does it show a readable brand name, company logo, or prominent text/numbers?\n"
        "person_main: is an identifiable person's face (or any child) a main subject?"
    )
    try:
        have = llm.available_models()
    except Exception:  # noqa: BLE001
        return None
    order = list(dict.fromkeys(IMAGE_LLM_PREFER + llm.BULK_MODELS))
    for model in [m for m in order if m in have and m not in llm._exhausted][:4]:
        gemma = model.startswith("gemma")
        cfg = {"temperature": 0, "max_output_tokens": 300}
        if not gemma:
            cfg.update(response_mime_type="application/json", response_schema=VISION_SCHEMA)
        text = prompt + ('\nReturn JSON only: {"related": bool, "brand_or_text": bool, "person_main": bool, "why": "short"}' if gemma else "")
        try:
            response = llm._gemini_client().models.generate_content(
                model=model,
                contents=[types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"), text],
                config=types.GenerateContentConfig(**cfg),
            )
            llm._record_usage(model)
            data = llm.parse_json_lenient(response.text or "")
        except Exception as error:  # noqa: BLE001
            if llm._classify(error) == "quota":
                llm._exhausted.add(model)
            continue
        if not isinstance(data, dict) or "related" not in data:
            continue
        if data.get("related") is False:
            return "記事と関係が薄い"
        if data.get("brand_or_text"):
            return "ブランド名・文字が写っている"
        if data.get("person_main"):
            return "人物が主役"
        return None
    return None


PICK_SCHEMA = {"type": "OBJECT", "properties": {"pick": {"type": "INTEGER"}, "why": {"type": "STRING"}}, "required": ["pick"]}


def choose_stock(article: dict, candidates: list[dict]) -> dict | None:
    """候補の題名・説明から、記事に合う写真を軽量モデルに1枚選ばせる（合うものが無ければ None）"""
    if not candidates:
        return None
    lines = "\n".join(f"{i}: {'[QI] ' if c.get('quality') else ''}{c['title']} — {c['description'][:140]}" for i, c in enumerate(candidates))
    prompt = f"""Japanese news article:
title: {article.get('title', '')}
summary: {article.get('description', '')}

Candidate photos (index: title — description):
{lines}

Pick the ONE photo that would look natural as the thumbnail of this article on a major news site.
Rules:
- clearly related scene or object (a reader should see the connection at a glance), a real photograph
- generic is better than specific: reject photos tied to a different organization, government agency, military,
  event, product brand or foreign landmark that is not in the article (it would mislead readers)
- no map/document/logo/screenshot, no famous person as the subject, no visible brand logos
- "[QI]" marks photos that passed Wikimedia's quality review; prefer them when equally relevant
Return {{"pick": index}} or {{"pick": -1}} if none fits."""
    try:
        data, _ = llm.generate_json("You are a careful photo editor. Return JSON only.", prompt, PICK_SCHEMA, tier=llm_tier(), temperature=0.1, max_output_tokens=1024)
        index = int(data.get("pick", -1))
    except Exception as error:  # noqa: BLE001
        log(f"   [img] 選定に失敗、検索順の先頭を使う: {str(error)[:80]}")
        index = 0
    return candidates[index] if 0 <= index < len(candidates) else None


def find_stock(article: dict, plan: dict, used: set[str]) -> tuple[dict | None, object]:
    candidates: list[dict] = []
    seen = set()
    queries = plan["queries"] + ([plan["query_ja"]] if plan.get("query_ja") else [])
    def add(items: list[dict]) -> None:
        for item in items:
            if item["sourceUrl"] in seen or not stock_ok(item, used):
                continue
            seen.add(item["sourceUrl"])
            candidates.append(item)

    # 呼び出しを減らす: 審査済み（QI）は最初の検索語だけ、日本語の検索語は足りないときだけ
    for index, query in enumerate(queries):
        if index == len(plan["queries"]) and len(candidates) >= 6:
            break
        add((search_wikimedia(query, limit=6, quality=True) if index == 0 else []) + search_wikimedia(query))
        if len(candidates) >= 12:
            break
    # Openverse（Flickr など）は応答が遅く、実際の画像が小さいことも多いので、Commons で足りないときだけ
    if len(candidates) < 6:
        for query in plan["queries"]:
            add(search_openverse(query))
    if not candidates:
        return None, None
    # 同じ検索語の上位に偏らないよう、検索語ごとに交互に並べる
    by_query: dict[str, list[dict]] = {}
    for c in candidates:
        by_query.setdefault(c["query"], []).append(c)
    mixed = []
    while any(by_query.values()) and len(mixed) < 18:
        for q in list(by_query):
            if by_query[q]:
                mixed.append(by_query[q].pop(0))
    tried = 0
    while mixed and tried < 3:
        tried += 1
        pick = choose_stock(article, mixed)
        if not pick:
            return None, None
        try:
            data, ctype, _ = http_get(pick["download"], ua=BOT_UA, accept="image/jpeg,image/*", timeout=40)
            image = open_image(data)
            problem = image_problem(image, MIN_STOCK_WIDTH) or vision_check(image, article)
            if problem:
                raise ValueError(problem)
            return pick, image
        except Exception as error:  # noqa: BLE001
            log(f"   [img] 素材を使えない（{str(error)[:60]}）: {pick['title'][:50]}")
            mixed.remove(pick)
    return None, None


# --------------------------------------------------------------------------- #
# 3. AI 生成（Workers AI）
# --------------------------------------------------------------------------- #

AI_MODELS = ["@cf/black-forest-labs/flux-2-klein-4b", "@cf/black-forest-labs/flux-1-schnell"]


def ai_used_today() -> int:
    return sum(n for model, n in llm.usage_today().items() if model.startswith("cf-image:"))


def ai_prompt(plan: dict, article: dict) -> str:
    scene = plan.get("scene") or ", ".join(plan.get("queries") or []) or article.get("genre", "")
    return (
        f"Photorealistic editorial news photograph. {scene} "
        "Natural muted colors, soft natural light, documentary style, shot on a full-frame camera with a 35mm lens, "
        "wide landscape composition with empty space in the lower third. "
        "No text, no letters, no numbers, no signs, no logos, no watermark, no brand names, no identifiable faces."
    )


def _cf_ai(model: str, prompt: str, timeout: int) -> bytes:
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/{model}"
    headers = {"Authorization": f"Bearer {cf_token('ai')}"}
    if "flux-2" in model:
        boundary = uuid.uuid4().hex
        fields = {"prompt": prompt, "width": "1216", "height": "640"}
        body = "".join(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n' for k, v in fields.items())
        data = (body + f"--{boundary}--\r\n").encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    else:
        data = json.dumps({"prompt": prompt, "steps": 6}).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as res:
        raw = res.read()
        ctype = res.headers.get("Content-Type", "")
    if "json" in ctype:
        payload = json.loads(raw)
        image = (payload.get("result") or {}).get("image")
        if not image:
            raise RuntimeError(str(payload)[:200])
        return base64.b64decode(image)
    return raw


def generate_ai(plan: dict, article: dict, fast: bool = False) -> tuple[object, str] | None:
    if ai_used_today() >= AI_DAILY_MAX:
        log(f"   [img] AI 生成は今日の上限（{AI_DAILY_MAX}枚）に達した")
        return None
    if not cf_token("ai"):
        log("   [img] Workers AI のトークンが無いので AI 生成は飛ばす")
        return None
    prompt = ai_prompt(plan, article)
    models = AI_MODELS[1:] if fast else AI_MODELS
    for model in models:
        try:
            raw = _cf_ai(model, prompt, timeout=150 if "flux-2" in model else 60)
            image = open_image(raw)
            llm._record_usage("cf-image:" + model.rsplit("/", 1)[-1])
            return image, model.rsplit("/", 1)[-1]
        except Exception as error:  # noqa: BLE001
            detail = error.read()[:160] if isinstance(error, urllib.error.HTTPError) else str(error)[:160]
            log(f"   [img] {model} に失敗: {detail!r}")
    return None


# --------------------------------------------------------------------------- #
# 保存（KV）
# --------------------------------------------------------------------------- #


def render(image) -> tuple[bytes, bytes]:
    """1200×630 の JPEG（140KB 以下）と 640×336 の WebP"""
    fitted = ImageOps.fit(image, (OUT_W, OUT_H), method=Image.LANCZOS, centering=(0.5, 0.45))
    jpeg = b""
    for quality in (84, 80, 76, 72, 68, 62, 56, 50, 44, 38):
        buf = io.BytesIO()
        fitted.save(buf, "JPEG", quality=quality, optimize=True, progressive=True, subsampling=2)
        jpeg = buf.getvalue()
        if len(jpeg) <= JPEG_MAX_BYTES:
            break
    small = fitted.resize((SMALL_W, SMALL_H), Image.LANCZOS)
    buf = io.BytesIO()
    small.save(buf, "WEBP", quality=74, method=6)
    return jpeg, buf.getvalue()


def store(slug: str, image, dry_run: bool) -> str:
    jpeg, webp = render(image)
    key = f"{slug[:120]}-{hashlib.sha1(jpeg).hexdigest()[:8]}"
    if PREVIEW_DIR:
        (PREVIEW_DIR / f"{key}.jpg").write_bytes(jpeg)
    if not dry_run:
        kv_put(f"{key}.jpg", jpeg)
        kv_put(f"{key}.sm.webp", webp)
    log(f"   [img] 保存 {key}.jpg（{len(jpeg) // 1024}KB）/ .sm.webp（{len(webp) // 1024}KB）" + ("（dry-run）" if dry_run else ""))
    return f"{IMAGE_BASE}{key}.jpg"


# --------------------------------------------------------------------------- #
# 記事ごとの処理
# --------------------------------------------------------------------------- #


def load_articles() -> dict[Path, dict]:
    out = {}
    for path in ARTICLES_DIR.glob("*.json"):
        try:
            out[path] = json.loads(path.read_text("utf-8"))
        except Exception:  # noqa: BLE001
            continue
    return out


def newest_first(item: tuple[Path, dict]) -> str:
    article = item[1]
    return article.get("generatedAt") or article.get("publishedAt") or ""


def needs_check(article: dict) -> bool:
    """点検の対象か。YouTube のサムネイルがある動画記事・確認済みの記事は対象外"""
    if article.get("imageCredit"):
        return False
    thumb = article.get("thumbnail", "") or ""
    if is_youtube(thumb):
        return False
    return True


def age_hours(article: dict) -> float:
    try:
        made = datetime.fromisoformat(str(article.get("generatedAt") or article.get("publishedAt")).replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - made).total_seconds() / 3600
    except Exception:  # noqa: BLE001
        return 0.0


def save(path: Path, article: dict) -> None:
    path.write_text(json.dumps(article, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def process(path: Path, article: dict, ctx: dict) -> str:
    slug = article.get("slug") or path.stem
    title = (article.get("title") or "")[:40]
    thumb = article.get("thumbnail", "") or ""
    log(f"[img] {slug} | {title}")

    # 自前の画像（まとめ記事・別の切り口の記事が元記事の画像を引き継いだ）なら出典も引き継ぐ
    if is_ours(thumb):
        credit = ctx["credit_by_thumb"].get(thumb)
        if credit:
            article["imageCredit"] = credit
            if not ctx["dry_run"]:
                save(path, article)
            return "inherit"

    # 1. 元記事の写真
    url, why = pick_source_image(article, ctx["repeats"])
    if url:
        log(f"   [img] 元記事の写真を使う: {url[:100]}")
        article["thumbnail"] = url
        article["imageCredit"] = {"kind": "source", "provider": article.get("sourceName") or article.get("channel", ""), "sourceUrl": article.get("sourceUrl", "")}
        if not ctx["dry_run"]:
            save(path, article)
        return "source"
    log(f"   [img] 元記事の写真は使わない: {why}")

    # 2. フリー素材 → 3. AI 生成
    try:
        plan = visual_plan(article)
    except Exception as error:  # noqa: BLE001
        log(f"   [img] 検索語を作れない: {str(error)[:100]}")
        return "error"
    log(f"   [img] 検索語: {plan['queries']} / {plan.get('query_ja')} ({plan['model']})")

    credit: dict = {}
    image = None
    if not ctx.get("ai_only"):
        pick, image = find_stock(article, plan, ctx["used_stock"])
        if pick and image is not None:
            credit = {
                "kind": "stock",
                "title": pick["title"],
                "creator": pick["creator"],
                "creatorUrl": pick["creatorUrl"],
                "license": pick["license"],
                "licenseUrl": pick["licenseUrl"],
                "provider": pick["provider"],
                "sourceUrl": pick["sourceUrl"],
                "query": pick["query"],
            }
            ctx["used_stock"].add(pick["sourceUrl"])
            log(f"   [img] 素材: {pick['title'][:60]}（{pick['creator'][:30]} / {pick['license']}）")
    if image is None and _wiki_failures > 0 and not ctx.get("fast") and not ctx.get("ai_only") and age_hours(article) < ctx["defer_hours"]:
        # Commons が落ちているだけなら AI の枠を使わず、次の回に探し直す（速報の回と、何時間も直らないときは AI）
        log("   [img] Wikimedia Commons に繋がらないので次の回に回す")
        return "deferred"
    if image is None:
        made = generate_ai(plan, article, fast=ctx.get("fast", False))
        if not made:
            return "none"
        image, model = made
        credit = {"kind": "ai", "model": model, "prompt": plan.get("scene", "")[:300], "provider": "Cloudflare Workers AI"}
        log(f"   [img] AI 生成: {model}")

    try:
        new_url = store(slug, image, ctx["dry_run"])
    except Exception as error:  # noqa: BLE001
        log(f"   [img] 保存に失敗: {str(error)[:120]}")
        return "error"
    if thumb and thumb != new_url:
        credit["original"] = thumb
    credit["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    article["thumbnail"] = new_url
    article["imageCredit"] = credit
    if not ctx["dry_run"]:
        save(path, article)
    return credit["kind"]


def load_env_local() -> None:
    """手元実行用: .env.local の鍵を読む（git worktree の中なら親のリポジトリのものも探す）"""
    for base in [ROOT, *ROOT.parents]:
        path = base / ".env.local"
        if not path.exists():
            continue
        for line in path.read_text("utf-8").splitlines():
            match = re.match(r"^(GEMINI_API_KEY|GOOGLE_API_KEY|GROQ_API_KEY|OPENROUTER_API_KEY)=(.+)$", line.strip())
            if match and not os.environ.get(match.group(1)):
                os.environ[match.group(1)] = match.group(2).strip().strip("\"'")
        break
    # 手元では wrangler のログインで Workers AI（検索語づくり・画像生成）を使う
    if not os.environ.get("CLOUDFLARE_API_TOKEN") and wrangler_token():
        os.environ["CLOUDFLARE_API_TOKEN"] = wrangler_token()
        os.environ.setdefault("CLOUDFLARE_ACCOUNT_ID", ACCOUNT_ID)


def changed_paths() -> set[Path]:
    """このワークツリーで追加・変更された記事（git status）"""
    try:
        out = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", "content/articles"], cwd=ROOT, capture_output=True, text=True, timeout=30).stdout
    except Exception:  # noqa: BLE001
        return set()
    paths = set()
    for line in out.splitlines():
        name = line[3:].strip().strip('"')
        if name.endswith(".json"):
            paths.add((ROOT / name).resolve())
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--changed", action="store_true", help="追加・変更された記事だけ")
    parser.add_argument("--recent", type=int, default=0, help="新しい N 本のうち未確認のもの")
    parser.add_argument("--all", action="store_true", help="全記事（新しい順）")
    parser.add_argument("--slug", action="append", default=[], help="この記事だけ（複数可）")
    parser.add_argument("--max", type=int, default=20, help="1回で直す最大本数")
    parser.add_argument("--budget", type=float, default=0, help="この秒数を過ぎたら新しい記事に手を付けない")
    parser.add_argument("--fast", action="store_true", help="速報の回: AI は速いモデルだけ")
    parser.add_argument("--ai-only", action="store_true", help="素材を探さず AI 生成だけ（確認用）")
    parser.add_argument("--dry-run", action="store_true", help="保存しない")
    parser.add_argument("--preview", help="出来上がった JPEG をこのフォルダにも書く（確認用）")
    parser.add_argument("--shard", help="並列実行の分担（例: 0/3）")
    parser.add_argument("--defer-hours", type=float, default=3, help="Commons に繋がらないとき、作成からこの時間までは AI にせず次の回に回す")
    args = parser.parse_args()
    global PREVIEW_DIR
    if args.preview:
        PREVIEW_DIR = Path(args.preview)
        PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    load_env_local()
    started = time.time()

    articles = load_articles()
    repeats: Counter = Counter()
    for a in articles.values():
        for url in {a.get("thumbnail") or "", (a.get("imageCredit") or {}).get("original") or ""}:
            if url and not is_youtube(url) and not is_ours(url):
                repeats[url] += 1
    ctx = {
        "repeats": repeats,
        "used_stock": {(a.get("imageCredit") or {}).get("sourceUrl") for a in articles.values() if (a.get("imageCredit") or {}).get("kind") == "stock"},
        "credit_by_thumb": {a["thumbnail"]: a["imageCredit"] for a in articles.values() if a.get("imageCredit") and is_ours(a.get("thumbnail", ""))},
        "dry_run": args.dry_run,
        "fast": args.fast,
        "ai_only": args.ai_only,
        "defer_hours": args.defer_hours,
    }

    ordered = sorted(articles.items(), key=newest_first, reverse=True)
    if args.slug:
        targets = [(p, a) for p, a in ordered if a.get("slug") in args.slug or p.stem in args.slug]
        for _, a in targets:
            a.pop("imageCredit", None)
    elif args.changed or args.recent or args.all:
        # 追加・変更された記事を先に、次に新しい順の未確認の記事（前の回で直し損ねたもの）
        changed = changed_paths() if args.changed else set()
        first = [(p, a) for p, a in ordered if p.resolve() in changed]
        rest = ordered if args.all else ordered[: args.recent]
        seen: set[Path] = set()
        targets = []
        for p, a in first + rest:
            if p not in seen and needs_check(a):
                seen.add(p)
                targets.append((p, a))
    else:
        parser.error("--changed / --recent / --all / --slug のどれかを指定してください")

    if args.shard:
        # さかのぼりを並列に流すとき用（"0/3" なら 0,3,6…番目）
        index, total = (int(x) for x in args.shard.split("/"))
        targets = [t for i, t in enumerate(targets) if i % total == index]
    log(f"[img] 対象 {len(targets)} 本（最大 {args.max} 本）")
    tally: Counter = Counter()
    for path, article in targets:
        if sum(tally.values()) >= args.max:
            break
        if args.budget and time.time() - started > args.budget:
            log("[img] 時間切れ。残りは次の回に回す")
            break
        try:
            tally[process(path, article, ctx)] += 1
        except Exception as error:  # noqa: BLE001 - 1本の失敗で全体を止めない
            log(f"   [img] 失敗: {str(error)[:160]}")
            tally["error"] += 1
    log(f"[img] 結果: {dict(tally)}（AI 生成は今日 {ai_used_today()} / {AI_DAILY_MAX} 枚）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

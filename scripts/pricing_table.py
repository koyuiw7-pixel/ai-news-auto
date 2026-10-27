#!/usr/bin/env python3
"""AI料金・日本対応の早見表（/ai-pricing）のデータ content/pricing.json を作る。

数字はサイソクの記事に書かれたものだけを使う。
1. 料金が書かれていそうな AI 記事を選び、該当する行だけを LLM（bulk）に渡して料金の行を抜き出す
2. 抜き出した行は機械的に確かめる
   - 引用（quote）が記事の本文にそのまま存在する
   - 料金の数字がすべて引用の中にある
   - その段落が「（編集部注）」（動画に無い背景知識）ではない
3. 同じ製品・プランは、いちばん新しい記事の数字を採る

抽出結果は記事ごとに state/pricing_extract.json に残し、新しい記事だけ LLM に渡す。

  python3 scripts/pricing_table.py             # 新しい記事だけ抽出して表を作り直す
  python3 scripts/pricing_table.py --dry-run   # 対象の記事を表示するだけ
  python3 scripts/pricing_table.py --rebuild   # LLM を呼ばず、保存済みの抽出結果から表だけ作り直す
  python3 scripts/pricing_table.py --all       # 全記事をやり直す
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from indexnow import is_indexable  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"
OUT_PATH = ROOT / "content" / "pricing.json"
CACHE_PATH = ROOT / "state" / "pricing_extract.json"
EXTRACT_VERSION = 1

# 料金らしい書き方
PRICE_RE = re.compile(
    r"(\$\s?\d|\d[\d,.]*\s*(?:ドル|米ドル|セント|円)|100万トークン|1Mトークン|per\s?1M|/\s?1M|月額)", re.I
)
# AI の製品名（汎用の LLM・アシスタント・開発ツール）
PRODUCT_RE = re.compile(
    r"ChatGPT|GPT-|Codex|Claude|Opus|Sonnet|Haiku|Fable|Gemini|Gemma|Grok|Copilot|DeepSeek|Mistral|Llama|"
    r"Kimi|Perplexity|Qwen|Cursor|Notion AI|Midjourney|Sora|Veo|Runway|ElevenLabs|Nova|Bedrock|Jev",
    re.I,
)
TOKEN_UNIT_RE = re.compile(r"100万トークン|1Mトークン|百万トークン|per\s?1M|/\s?1M|1M tokens|100万", re.I)
INPUT_RE = re.compile(r"入力|インプット|input", re.I)
ESTIMATE_RE = re.compile(r"推定|※|予想|噂|リーク|試算|逆算|見込み")
EDITORIAL_RE = re.compile(r"編集部注|編集部の見立て|従来の価格設定|一般的に|通常は")

# 発信元 → 企業（lib/companies.ts の slug）
VENDOR_COMPANY = [
    (re.compile(r"OpenAI|ChatGPT|GPT|Codex|Sora", re.I), "openai"),
    (re.compile(r"Anthropic|Claude|Opus|Sonnet|Haiku|Fable", re.I), "anthropic"),
    (re.compile(r"Google|Gemini|Gemma|DeepMind|Veo", re.I), "google"),
    (re.compile(r"Microsoft|Azure|Copilot|GitHub", re.I), "microsoft"),
    (re.compile(r"NVIDIA|Nemotron", re.I), "nvidia"),
    (re.compile(r"\bMeta\b|Llama", re.I), "meta"),
    (re.compile(r"DeepSeek", re.I), "deepseek"),
    (re.compile(r"xAI|Grok", re.I), "xai"),
    (re.compile(r"Mistral", re.I), "mistral"),
    (re.compile(r"Moonshot|Kimi", re.I), "moonshot"),
]

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "rows": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "kind": {"type": "STRING", "enum": ["plan", "api"]},
                    "vendor": {"type": "STRING"},
                    "product": {"type": "STRING"},
                    "plan": {"type": "STRING", "nullable": True},
                    "monthlyPrice": {"type": "NUMBER", "nullable": True},
                    "inputPerM": {"type": "NUMBER", "nullable": True},
                    "outputPerM": {"type": "NUMBER", "nullable": True},
                    "cachedInputPerM": {"type": "NUMBER", "nullable": True},
                    "currency": {"type": "STRING", "enum": ["USD", "JPY"]},
                    "quote": {"type": "STRING"},
                },
                "required": ["kind", "vendor", "product", "currency", "quote"],
            },
        }
    },
    "required": ["rows"],
}

SYSTEM = """あなたはAIサービスの料金表を作る編集者です。渡された記事の抜粋から、AIサービスの料金だけを正確に抜き出します。
記事に書かれていない数字は絶対に作らない。迷ったら出さない。出力は指定の JSON だけ。"""

PROMPT = """次の記事の抜粋から、AIサービスの料金を行ごとに抜き出してください。

# 抜き出すもの
- kind="plan": 個人・法人向けの月額プラン（例: ChatGPT Plus 月額20ドル）。
  product はサービス名（ChatGPT / Claude / Gemini / GitHub Copilot など）、plan はプラン名（Plus / Pro / Max / Business など）、
  monthlyPrice は1か月あたりの金額。年額しか書かれていないものは出さない。
- kind="api": APIの従量料金（100万トークンあたり）。product はモデル名（例: GPT-6.1 Terra）、plan は null。
  inputPerM / outputPerM / cachedInputPerM は100万トークンあたりの金額。書かれていない項目は null。
- currency は金額の通貨（ドルなら USD、円なら JPY）。

# 出さないもの
- 「約5倍安い」「半額」のような比較だけで金額が無いもの。「〜ドル前後」「数セント」のような曖昧な金額。
- GPU・PC・サーバー・研修・コンサルなど、AIサービスの利用料ではないもの。
- 1分あたり・1枚あたり・1回あたりなど、月額でも100万トークンあたりでもない料金。
- 「（編集部注）」が付いた文や、記事の外の一般知識として書かれた料金。
- 今回の記事で別の製品と比べるために挙げただけの、過去のモデルの料金は出してよい（数字が書かれていれば）。

# quote（必須）
- その料金が書かれた文、または表の1行を、記事の抜粋からそのまま一字一句コピーする（要約・言い換え禁止）。
- 表の1行のときは、| で区切られた行をそのままコピーする。

# 記事
題名: {title}
公開日: {published}
判定欄の料金: {verdict_price}

抜粋:
<<<
{excerpt}
>>>"""


def log(message: str) -> None:
    print(message, flush=True)


# --------------------------------------------------------------------------- #
# 記事の読み込みと候補の選択
# --------------------------------------------------------------------------- #


def load_articles() -> list[dict]:
    items = []
    for path in sorted(ARTICLES_DIR.glob("*.json")):
        try:
            article = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(article, dict) and article.get("slug") and isinstance(article.get("body"), str):
            items.append(article)
    return items


def price_lines(article: dict) -> list[str]:
    """料金と製品名の両方が出てくる行（表は見出し行も添える）"""
    lines = article["body"].split("\n")
    picked: list[str] = []
    for index, line in enumerate(lines):
        if not (PRICE_RE.search(line) and PRODUCT_RE.search(line)):
            # 表の行は製品名が別の列にあることがあるので、料金だけで拾う
            if not (line.lstrip().startswith("|") and PRICE_RE.search(line)):
                continue
        if line.lstrip().startswith("|"):
            # 表の見出し（最初の | 行）を添える
            head = index
            while head > 0 and lines[head - 1].lstrip().startswith("|"):
                head -= 1
            header = lines[head]
            if header != line and header not in picked:
                picked.append(header)
        if line not in picked:
            picked.append(line)
    return picked


def is_candidate(article: dict) -> bool:
    if article.get("genreSlug", "ai") != "ai":
        return False
    if not is_indexable(article):
        return False
    verdict = article.get("verdict") or {}
    if re.search(r"\d", str(verdict.get("price") or "")) and PRODUCT_RE.search(article.get("title", "") + str(verdict.get("price"))):
        return True
    return bool(price_lines(article))


def content_hash(article: dict) -> str:
    verdict = article.get("verdict") or {}
    raw = f"{EXTRACT_VERSION}|{article['body']}|{verdict.get('price', '')}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# 機械的な確認
# --------------------------------------------------------------------------- #


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text or ""))
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"\s*\|\s*", "|", text)
    return re.sub(r"\s+", " ", text).strip()


def numbers_in(text: str) -> set[float]:
    """文中の数字（1,000 や $0.05 も）。セントはドルに直した値も足す"""
    found: set[float] = set()
    t = unicodedata.normalize("NFKC", text)
    for match in re.finditer(r"\d+(?:,\d{3})*(?:\.\d+)?", t):
        value = float(match.group(0).replace(",", ""))
        found.add(value)
        tail = t[match.end() : match.end() + 3]
        if tail.startswith("セント") or tail.lstrip().startswith("¢"):
            found.add(round(value / 100, 6))
        if tail.startswith("万"):
            found.add(value * 10000)
    return found


def has_number(value: float, pool: set[float]) -> bool:
    return any(abs(value - n) < 1e-9 for n in pool)


def verify(row: dict, article: dict) -> tuple[bool, str]:
    """(合格か, 不合格の理由)"""
    verdict = article.get("verdict") or {}
    body = article["body"]
    haystack_raw = "\n".join([body, str(verdict.get("price") or ""), *[str(h) for h in article.get("highlights") or []]])
    quote = norm(row.get("quote", ""))
    if len(quote) < 6:
        return False, "引用が短すぎる"
    if quote not in norm(haystack_raw):
        return False, "引用が記事に無い"
    # 引用を含む行（段落）が編集部注なら使わない
    for line in haystack_raw.split("\n"):
        if quote[:40] in norm(line):
            if EDITORIAL_RE.search(line):
                return False, "編集部注の段落"
            break
    pool = numbers_in(quote)
    fields = ["monthlyPrice"] if row["kind"] == "plan" else ["inputPerM", "outputPerM", "cachedInputPerM"]
    values = [row.get(f) for f in fields if isinstance(row.get(f), (int, float))]
    if not values:
        return False, "金額が無い"
    for value in values:
        if value < 0 or not has_number(float(value), pool):
            return False, f"数字 {value} が引用に無い"
    if row["kind"] == "plan":
        if not re.search(r"月|/mo|month", quote, re.I) and "月" not in str(verdict.get("price") or ""):
            return False, "月額と書かれていない"
    else:
        # 単位は同じ文か、表の行・「入力◯ドル/出力◯ドル」のときは記事の中に「100万トークン」があればよい
        in_context = (quote.startswith("|") or INPUT_RE.search(quote)) and TOKEN_UNIT_RE.search(body)
        if not (TOKEN_UNIT_RE.search(quote) or in_context):
            return False, "100万トークンあたりと書かれていない"
    if not PRODUCT_RE.search(f"{row.get('product', '')} {row.get('vendor', '')}"):
        return False, "AIの製品名ではない"
    if ESTIMATE_RE.search(quote):
        return False, "推定・注記つきの数字"
    if quote.startswith("|"):
        ok, reason = table_columns_ok(row, quote, body)
        if not ok:
            return False, reason
    if row["kind"] == "plan":
        plan = clean_plan(row.get("plan"))
        if not plan or re.search(r"[/、・,]", plan):
            return False, "プラン名が1つに決まらない"
    # 製品名が引用に無いときは、その製品が記事の主題で、表なら価格が1つだけの行に限る
    if not name_in(row.get("product"), quote):
        if not main_subject(row, article):
            return False, "引用に製品名が無い"
        if quote.startswith("|") and len(re.findall(r"\$\s?\d|\d\s*ドル", quote)) > 1:
            return False, "比較表の行で製品が決まらない"
    return True, ""


def squash(text: str | None) -> str:
    # 版数の区切り（5.5 の点）は残す（「Opus 5」が「Opus 5.5」に当たらないように）
    return re.sub(r"[\s\-‐‑–—_・()（）*]", "", unicodedata.normalize("NFKC", str(text or "")).lower())


def _contains(name: str, text: str) -> bool:
    """name が text にあり、直後に版数の続き（数字・.数字）が無い"""
    return re.search(re.escape(name) + r"(?![\d]|\.\d)", text) is not None


def name_in(product: str | None, quote: str) -> bool:
    name = squash(product)
    if not name:
        return False
    q = squash(quote)
    # 「Claude Opus 5.5」→「Opus 5.5」のように、発信元の名前を外した形でもよい
    short = re.sub(r"^(claude|openai|google|microsoft|deepseek|xai|meta)", "", name)
    return _contains(name, q) or (len(short) >= 4 and _contains(short, q))


class _Words:
    """列の見出しの判定（「キャッシュ入力」は入力ではなく、「キャッシュ書き込み」はキャッシュ入力ではない）"""

    def __init__(self, yes: str, no: str = r"$^") -> None:
        self.yes, self.no = re.compile(yes, re.I), re.compile(no, re.I)

    def search(self, text: str) -> bool:
        return bool(self.yes.search(text)) and not self.no.search(text)


FIELD_WORDS = {
    "inputPerM": _Words(r"入力|インプット|input", r"キャッシュ|cache"),
    "outputPerM": _Words(r"出力|アウトプット|output"),
    "cachedInputPerM": _Words(r"キャッシュ|cache", r"書き込み|書込|write"),
    "monthlyPrice": _Words(r"月|month|/mo"),
}


def cells(line: str) -> list[str]:
    return [c.strip() for c in norm(line).strip("|").split("|")]


def table_columns_ok(row: dict, quote: str, body: str) -> tuple[bool, str]:
    """表の行のとき、数字が正しい列（入力・出力・キャッシュ・月額）にあるかを見出しで確かめる"""
    lines = body.split("\n")
    index = next((i for i, line in enumerate(lines) if norm(line) == quote or quote in norm(line)), None)
    if index is None or not lines[index].lstrip().startswith("|"):
        return True, ""
    head = index
    while head > 0 and lines[head - 1].lstrip().startswith("|"):
        head -= 1
    header = cells(lines[head]) if head != index else []
    values = cells(lines[index])
    for field, words in FIELD_WORDS.items():
        value = row.get(field)
        if not isinstance(value, (int, float)):
            continue
        spots = [i for i, cell in enumerate(values) if has_number(float(value), numbers_in(cell))]
        if not spots:
            return False, f"数字 {value} が表の行に無い"
        # 列の見出しか、行の見出し（1列目）のどちらかに項目名があればよい
        by_column = any(i < len(header) and words.search(header[i]) for i in spots)
        by_label = bool(values) and words.search(values[0]) and not any(words.search(h) for h in header[1:])
        # セルの中に「入力$1」のように項目名が書かれている
        by_cell = any(words.search(values[i]) for i in spots if i > 0)
        if not (by_column or by_label or by_cell):
            return False, f"{value} の列が{field}ではない"
    return True, ""


def clean_plan(text: str | None) -> str:
    plan = clean_name(text)
    return re.sub(r"\s*(プラン|plan)$", "", plan, flags=re.I).strip()


# --------------------------------------------------------------------------- #
# 抽出
# --------------------------------------------------------------------------- #


def extract(article: dict) -> tuple[list[dict], str]:
    from llm import generate_json

    verdict = article.get("verdict") or {}
    lines = price_lines(article)
    excerpt = "\n".join(lines)[:7000] or "（本文に料金の行はありません）"
    prompt = PROMPT.format(
        title=article.get("title", ""),
        published=str(article.get("publishedAt", ""))[:10],
        verdict_price=verdict.get("price") or "（なし）",
        excerpt=excerpt,
    )
    data, model = generate_json(SYSTEM, prompt, SCHEMA, tier="bulk", temperature=0.1, max_output_tokens=4096)
    rows = [r for r in data.get("rows") or [] if isinstance(r, dict) and r.get("kind") in ("plan", "api")]
    return rows, model


def load_cache() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True) + "\n", "utf-8")


# --------------------------------------------------------------------------- #
# 表の組み立て
# --------------------------------------------------------------------------- #


def clean_name(text: str | None) -> str:
    text = unicodedata.normalize("NFKC", str(text or "")).strip()
    text = re.sub(r"\s+", " ", text)
    return text.strip("「」『』\"' ")


COMPANY_NAME = {
    "openai": "OpenAI", "anthropic": "Anthropic", "google": "Google", "microsoft": "Microsoft",
    "nvidia": "NVIDIA", "meta": "Meta", "deepseek": "DeepSeek", "xai": "xAI", "mistral": "Mistral AI",
    "moonshot": "Moonshot AI",
}
JAPAN_RANK = {"ok": 3, "partial": 2, "no": 1}


def key_of(row: dict) -> str:
    plan = squash(clean_plan(row.get("plan"))) if row["kind"] == "plan" else ""
    product = squash(row.get("product"))
    # 「ChatGPT Plus」を product に入れてきた場合も同じ行にまとめる
    if row["kind"] == "plan" and plan and product.endswith(plan):
        product = product[: -len(plan)]
    return f"{row['kind']}:{product}:{plan}"


def company_of(row: dict) -> str:
    text = f"{row.get('vendor', '')} {row.get('product', '')}"
    for pattern, slug in VENDOR_COMPANY:
        if pattern.search(text):
            return slug
    return "other"


def main_subject(row: dict, article: dict) -> bool:
    """この行の製品が記事の主題か（判定欄の日本対応・無料枠を流用してよいか）"""
    return name_in(row.get("product"), f"{article.get('title', '')} {article.get('seoTitle', '')}")


def completeness(row: dict) -> int:
    return sum(isinstance(row.get(f), (int, float)) for f in ("monthlyPrice", "inputPerM", "outputPerM", "cachedInputPerM"))


def price_rank(row: dict, article: dict) -> tuple:
    """数字を採る記事: 新しい日付 → 項目が多い → その製品が主題"""
    published = str(article.get("publishedAt", ""))
    return (published[:10], completeness(row), main_subject(row, article), published)


def verdict_rank(row: dict, article: dict) -> tuple:
    """日本対応・無料枠を採る記事: その製品が主題で判定がある → 判定済み → 新しい"""
    verdict = article.get("verdict") or {}
    subject = main_subject(row, article) and bool(verdict)
    known = subject and verdict.get("japan") in JAPAN_RANK
    return (subject, known, str(article.get("publishedAt", "")))


def family_and_version(product: str) -> tuple[str, float | None]:
    """「GPT-6.1 Terra」→ ("gpt terra", 6.1)、「Claude Opus 5.5」→ ("opus", 5.5)"""
    text = unicodedata.normalize("NFKC", product).lower()
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    version = float(match.group(1)) if match else None
    family = re.sub(r"\d+(?:\.\d+)?", " ", text)
    family = re.sub(r"^\s*claude\s+", "", family)
    family = re.sub(r"[\s\-_.]+", " ", family).strip()
    return family, version


def mark_legacy(items: list[dict]) -> None:
    """同じ系列に新しい版がある・同じ会社の最新から2世代以上古い API モデルは「旧モデル」にする"""
    apis = [i for i in items if i["kind"] == "api"]
    newest_family: dict[tuple[str, str], float] = {}
    newest_company: dict[str, float] = {}
    for item in apis:
        family, version = family_and_version(item["product"])
        if version is None:
            continue
        key = (item["companySlug"], family)
        newest_family[key] = max(newest_family.get(key, 0), version)
        newest_company[item["companySlug"]] = max(newest_company.get(item["companySlug"], 0), version)
    for item in items:
        item["legacy"] = False
        if item["kind"] != "api":
            continue
        family, version = family_and_version(item["product"])
        if version is None:
            continue
        if version < newest_family.get((item["companySlug"], family), version):
            item["legacy"] = True
        elif item["companySlug"] != "other" and version <= newest_company.get(item["companySlug"], version) - 2:
            item["legacy"] = True


def verdict_article(row: dict, articles: dict[str, dict]) -> dict | None:
    """その製品が題名に出てくる AI 記事のうち、判定欄（日本対応）がいちばん確かな記事"""
    found = [
        a for a in articles.values()
        if a.get("genreSlug", "ai") == "ai" and a.get("type") != "roundup" and a.get("verdict") and main_subject(row, a)
    ]
    if not found:
        return None
    return max(found, key=lambda a: (a["verdict"].get("japan") in JAPAN_RANK, a["verdict"].get("status") == "available", a.get("publishedAt", "")))


def build_items(cache: dict, articles: dict[str, dict]) -> list[dict]:
    groups: dict[str, list[tuple[dict, dict]]] = {}
    for slug, entry in cache.items():
        article = articles.get(slug)
        if not article or not is_candidate(article):
            continue
        for row in entry.get("rows", []):
            if row.get("ok"):
                groups.setdefault(key_of(row), []).append((row, article))

    has_free_plan = {
        key.split(":")[1]
        for key, rows in groups.items()
        if key.startswith("plan:") and any(r.get("monthlyPrice") == 0 for r, _ in rows)
    }

    items = []
    for key, rows in groups.items():
        row, article = max(rows, key=lambda ra: price_rank(*ra))
        v_row, v_article = max(rows, key=lambda ra: verdict_rank(*ra))
        subject = main_subject(v_row, v_article) and bool(v_article.get("verdict"))
        if row["kind"] == "api" and (not subject or (v_article.get("verdict") or {}).get("japan") not in JAPAN_RANK):
            # 料金の記事に判定が無ければ、そのモデルを題名にした別の記事の判定を使う
            # （プランは「Claude」のような短い名前で別の話題の記事に当たりやすいので使わない）
            other = verdict_article(row, articles)
            if other is not None and (not subject or other["verdict"].get("japan") in JAPAN_RANK):
                v_article, subject = other, True
        verdict = v_article.get("verdict") or {}
        company = company_of(row)
        plan_kind = row["kind"] == "plan"
        monthly = row.get("monthlyPrice") if plan_kind else None
        if plan_kind:
            # プランの「無料で試せる？」は、同じサービスに0円のプランが載っているかで決める
            free = True if monthly == 0 or key.split(":")[1] in has_free_plan else None
        else:
            free = verdict.get("free") if subject else None
        item = {
            "id": re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-"),
            "kind": row["kind"],
            "vendor": COMPANY_NAME.get(company) or clean_name(row.get("vendor")),
            "companySlug": company,
            "product": clean_name(row.get("product")),
            "plan": clean_plan(row.get("plan")) if plan_kind else None,
            "currency": row.get("currency") or "USD",
            "monthly": monthly,
            "input": row.get("inputPerM") if not plan_kind else None,
            "output": row.get("outputPerM") if not plan_kind else None,
            "cachedInput": row.get("cachedInputPerM") if not plan_kind else None,
            # 日本対応・無料枠は、その製品が主題の記事の判定欄だけを使う（他は「記事で未確認」）
            "japan": verdict.get("japan", "unknown") if subject else "unknown",
            "status": verdict.get("status") if subject else None,
            "free": free if isinstance(free, bool) else None,
            "source": {
                "slug": article["slug"],
                "title": article.get("seoTitle") or article.get("title", ""),
                "publishedAt": article.get("publishedAt", ""),
                "quote": clean_name(row.get("quote"))[:240],
            },
            "verdictSource": v_article["slug"] if subject and v_article["slug"] != article["slug"] else None,
            "confirmedIn": len({a["slug"] for _, a in rows}),
        }
        # 「ChatGPT Plus」のように product にプラン名まで入っていたら外す
        if plan_kind and item["plan"] and item["product"].lower().endswith(" " + item["plan"].lower()):
            item["product"] = item["product"][: -len(item["plan"]) - 1].strip()
        items.append(item)

    mark_legacy(items)

    def order(item: dict) -> tuple:
        price = item["monthly"] if item["kind"] == "plan" else (item["input"] or item["output"] or 0)
        return (item["kind"], item["legacy"], item["companySlug"], item["product"].lower(), price or 0)

    return sorted(items, key=order)


def write_table(cache: dict, articles: dict[str, dict], scanned: int, candidates: int) -> dict:
    items = build_items(cache, articles)
    rows_ok = sum(1 for e in cache.values() for r in e.get("rows", []) if r.get("ok"))
    rows_ng = sum(1 for e in cache.values() for r in e.get("rows", []) if not r.get("ok"))
    newest = max((i["source"]["publishedAt"] for i in items), default="")
    data = {
        "updatedAt": newest or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stats": {
            "articlesScanned": scanned,
            "candidateArticles": candidates,
            "rowsVerified": rows_ok,
            "rowsRejected": rows_ng,
            "plans": sum(1 for i in items if i["kind"] == "plan"),
            "apis": sum(1 for i in items if i["kind"] == "api"),
        },
        "items": items,
    }
    previous = None
    try:
        previous = json.loads(OUT_PATH.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    # 中身が同じなら書き換えない（生成時刻だけのコミットを作らない）
    if previous and previous.get("items") == data["items"] and previous.get("stats") == data["stats"]:
        log("[pricing] 変更なし")
        return previous
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", "utf-8")
    log(f"[pricing] {OUT_PATH.relative_to(ROOT)}: 月額プラン {data['stats']['plans']} / API {data['stats']['apis']}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rebuild", action="store_true", help="LLM を呼ばずに表だけ作り直す")
    parser.add_argument("--all", action="store_true", help="保存済みの抽出結果を使わずやり直す")
    parser.add_argument("--max", type=int, default=80, help="1回で LLM に渡す記事の上限")
    args = parser.parse_args()

    all_articles = load_articles()
    articles = {a["slug"]: a for a in all_articles}
    candidates = [a for a in all_articles if is_candidate(a)]
    candidates.sort(key=lambda a: a.get("publishedAt", ""), reverse=True)
    cache = {} if args.all else load_cache()
    todo = [a for a in candidates if cache.get(a["slug"], {}).get("hash") != content_hash(a)]
    log(f"[pricing] 記事 {len(all_articles)} 本 / 料金の記載あり {len(candidates)} 本 / 未抽出 {len(todo)} 本")

    if args.dry_run:
        for a in todo[: args.max]:
            log(f"  {str(a.get('publishedAt', ''))[:10]} {a['slug']}  ({len(price_lines(a))}行)")
        return 0

    if not args.rebuild and todo:
        from llm import _load_env_local

        _load_env_local()
        for index, article in enumerate(todo[: args.max], 1):
            try:
                rows, model = extract(article)
            except Exception as error:  # noqa: BLE001 - 1本の失敗で全体を止めない
                log(f"  [{index}] {article['slug']}: 抽出に失敗（{str(error)[:120]}）")
                continue
            checked = []
            for row in rows:
                ok, reason = verify(row, article)
                checked.append({**row, "ok": ok, **({"reason": reason} if reason else {})})
            passed = sum(1 for r in checked if r["ok"])
            log(f"  [{index}] {article['slug']}: {len(rows)}行 → 確認OK {passed}行（{model}）")
            for r in checked:
                if not r["ok"]:
                    log(f"      × {r.get('product')} {r.get('plan') or ''}: {r.get('reason')}")
            cache[article["slug"]] = {
                "hash": content_hash(article),
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "model": model,
                "rows": checked,
            }
            save_cache(cache)

    # 消えた記事の抽出結果は捨て、残りは今の本文でもう一度確かめる（記事の修正・確認ルールの変更に追従）
    cache = {slug: entry for slug, entry in cache.items() if slug in articles}
    for slug, entry in cache.items():
        for row in entry.get("rows", []):
            ok, reason = verify(row, articles[slug])
            row["ok"] = ok
            row.pop("reason", None)
            if reason:
                row["reason"] = reason
    save_cache(cache)
    write_table(cache, articles, len(all_articles), len(candidates))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

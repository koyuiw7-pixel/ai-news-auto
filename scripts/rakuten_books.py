"""
記事末の「試すなら」枠に出す本を、楽天ブックスの売れ筋から話題ごとに選んで保存する。

- 話題の定義は content/offers.json（topics[].search）。
- 結果は content/products.json に書き出し、サイトはビルド時にそれを読む。
- リンクは A8.net 経由の楽天アフィリエイト（A8 の楽天商品リンクと同じ形式）。
- 価格・評価は取得時点のもの。サイト側で「◯月◯日時点」と明記する。

使い方:
    python3 scripts/rakuten_books.py          # 取得して保存
    python3 scripts/rakuten_books.py --dry    # 表示だけ
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFERS = ROOT / "content" / "offers.json"
PRODUCTS = ROOT / "content" / "products.json"

# A8.net「楽天アフィリエイト」提携で発行されたID（A8 管理画面の楽天商品リンクから取得）
A8MAT = "4BELTP+50ED2Q+2HOM+BWGDT"
RAKUTEN_HGC = "g00q0724.2bo11c45.g00q0724.2bo12179/a26102173090_4BELTP_50ED2Q_2HOM_BWGDT"
PIXEL = "https://www15.a8.net/0.gif?a8mat=" + A8MAT

USER_AGENT = "Mozilla/5.0 (compatible; SaisokuBot/1.0; +https://ai-tech-express.jp)"
PER_TOPIC = 10
MIN_YEAR = 2025


def affiliate_url(rb_id: str, item_id: str) -> str:
    """A8 の楽天商品リンクと同じ構造のURLを組み立てる。"""
    pc = f"https://item.rakuten.co.jp/book/{rb_id}/"
    mobile = f"http://m.rakuten.co.jp/book/i/{item_id}/"
    inner = (
        f"https://hb.afl.rakuten.co.jp/hgc/{RAKUTEN_HGC}"
        f"?pc={urllib.parse.quote(pc, safe='')}&m={urllib.parse.quote(mobile, safe='')}"
    )
    return (
        f"https://rpx.a8.net/svt/ejp?a8mat={A8MAT}&rakuten=y"
        f"&a8ejpredirect={urllib.parse.quote(inner, safe='')}"
    )


def image_url(src: str) -> str:
    """検索結果の画像（tshop.r10s.jp）を、楽天の商品リンクが使う公式サムネイルURLに揃える。"""
    match = re.search(r"/book/cabinet/([^?\"]+)", src)
    if not match:
        return ""
    return f"https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/{match.group(1)}?_ex=400x400"


def fetch(keyword: str) -> str:
    url = (
        "https://books.rakuten.co.jp/search?"
        + urllib.parse.urlencode({"sitem": keyword, "g": "001", "s": "7"})
    )
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.headers.get_content_type() != "text/html":
            raise ProductParseError("検索ページがHTMLではありません")
        data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise ProductParseError("検索ページが想定サイズを超えています")
        return data.decode("utf-8", errors="strict")


class ProductParseError(ValueError):
    """検索ページを確認できない場合は、正常な0件として保存しない。"""


@dataclass
class Element:
    tag: str
    attrs: dict[str, str]
    children: list = field(default_factory=list)

    def has_class(self, name: str) -> bool:
        return name in self.attrs.get("class", "").split()

    def descendants(self):
        for child in self.children:
            if isinstance(child, Element):
                yield child
                yield from child.descendants()

    def text(self) -> str:
        return "".join(child.text() if isinstance(child, Element) else child for child in self.children)


class ProductHTMLParser(HTMLParser):
    # classの順番・追加、引用符、入れ子のspanをHTMLの構造として読む。
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Element("root", {})
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Element(tag, {key: value or "" for key, value in attrs})
        self.stack[-1].children.append(node)
        if tag not in self.VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if self.stack[-1].tag not in {"script", "style"}:
            self.stack[-1].children.append(data)


def parse(page: str) -> list[dict]:
    parser = ProductHTMLParser()
    parser.feed(page)
    cards = [node for node in parser.root.descendants() if node.has_class("rbcomp__item-list__item")]
    if not cards:
        raise ProductParseError("検索の商品カードが見つかりません（返却内容・HTML形式を確認）")
    items, malformed = [], 0
    for position, card in enumerate(cards, start=1):
        nodes = list(card.descendants())
        def field_node(suffix):
            return next((n for n in nodes if n.has_class("rbcomp__item-list__item__" + suffix)), None)
        category = next((n for n in nodes if n.has_class("rbcomp__category")), None)
        if category is not None and not category.has_class("book"):
            continue
        if not any(n.has_class("stock1") for n in nodes):
            continue
        rb = next((match for n in nodes if n.tag == "a"
                   if (match := re.fullmatch(r"https://books\.rakuten\.co\.jp/rb/(\d+)/?(?:\?[^#]*)?(?:#.*)?", n.attrs.get("href", "")))), None)
        item_id = next((n.attrs["data-item-id"] for n in nodes if re.fullmatch(r"\d+", n.attrs.get("data-item-id", ""))), None)
        title, price_node, release_node = field_node("title"), field_node("price"), field_node("subtext")
        price = re.search(r"([\d,]+)\s*円", price_node.text()) if price_node else None
        released = re.search(r"(\d{4})年\s*\d{1,2}月", release_node.text()) if release_node else None
        image = next((image_url(n.attrs.get("src", "")) for n in nodes if n.tag == "img" and image_url(n.attrs.get("src", ""))), "")
        if not (rb and item_id and title and title.text().strip() and price and image):
            malformed += 1
            continue
        review_node, author_node = field_node("review"), field_node("author")
        score_node = next((n for n in review_node.descendants() if n.tag == "em"), None) if review_node else None
        score = score_node.text().strip() if score_node else ""
        reviews = re.search(r"レビュー\s*([\d,]+)件", review_node.text()) if review_node else None
        author = next((n.text().strip() for n in author_node.descendants() if n.tag == "a"), "") if author_node else ""
        items.append({
            "rbId": rb.group(1), "itemId": item_id, "title": clean_title(title.text()),
            "author": author, "price": int(price.group(1).replace(",", "")),
            "rating": float(score) if re.fullmatch(r"[0-5](?:\.\d+)?", score) else None,
            "reviews": int(reviews.group(1).replace(",", "")) if reviews else 0,
            "year": int(released.group(1)) if released else 0, "image": image, "rank": position,
        })
    if malformed:
        raise ProductParseError(f"在庫ありの商品{malformed}件で必須情報を読めません（既存候補を保持）")
    return items


def clean_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    # シリーズ名などの括弧書きは省く（カードでは2行に収めたい）
    title = re.sub(r"\s*[（(][^）)]*(新書|文庫|ムック|教科書|シリーズ)[^）)]*[）)]\s*$", "", title)
    return title


def pick(items: list[dict], used: set[str], require: str, exclude: str, min_year: int = MIN_YEAR) -> list[dict]:
    """楽天の売れ筋順のまま、話題に合う・評価の低くない・新しめの本だけを残す。"""
    chosen = []
    for item in items:
        if not item["image"] or item["year"] < min_year or item["rbId"] in used:
            continue
        if item["rating"] is not None and item["rating"] < 3.0:
            continue
        if require and not re.search(require, item["title"], re.I):
            continue
        if exclude and re.search(exclude, item["title"], re.I):
            continue
        chosen.append(item)
        if len(chosen) >= PER_TOPIC:
            break
    return chosen


def partner_price(source: str) -> int | None:
    """提携先の商品価格を公式サイトから取り直す（値下げ・値上げに追従するため）。"""
    kind, _, ident = source.partition(":")
    try:
        if kind == "plaud":
            url = f"https://jp.plaud.ai/products/{ident}.js"
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))
            return int(data["price"]) // 100
        if kind == "oz":
            url = f"https://www.ozgaming-pcshop.com/view/item/{ident}"
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=20) as response:
                page = response.read().decode("utf-8", errors="ignore")
            match = re.search(r'makeshop-item-price:1">([\d,]+)', page)
            return int(match.group(1).replace(",", "")) if match else None
    except Exception as error:
        print(f"[partner] {source}: 価格取得失敗 {error}", file=sys.stderr)
    return None


def refresh_catalog(offers: dict, previous: dict, checked_at: str, *, fetcher=fetch,
                    price_fetcher=partner_price, sleeper=time.sleep) -> tuple[dict, dict]:
    """全体を確認できた場合だけ新snapshotを返す。部分失敗も既存全体を保持する。"""
    output = copy.deepcopy(previous)
    result = output.setdefault("books", {})
    dates = output.setdefault("checkedAtByTopic", {})
    partner_dates = output.setdefault("checkedAtByPartner", {})
    old_date = previous.get("fetchedAt")
    report = {"checkedAt": checked_at, "updatedTopics": [], "retainedTopics": [],
              "updatedPartners": [], "retainedPartners": [], "errors": [], "outcome": "failed"}
    used: set[str] = set()
    for topic in offers["topics"]:
        key = topic["key"]
        keywords = topic.get("search") or []
        if isinstance(keywords, str):
            keywords = [keywords]
        chosen: list[dict] = []
        failed = not keywords
        # 検索語を順に試し、話題に合う本が PER_TOPIC 冊そろうまで集める
        for keyword in keywords:
            try:
                items = parse(fetcher(keyword))
            except Exception as error:
                report["errors"].append({"topic": key, "type": type(error).__name__, "message": str(error)[:200]})
                failed = True
                continue
            picked = pick(items, used | {c["rbId"] for c in chosen}, topic.get("require", ""), topic.get("exclude", ""), topic.get("minYear", MIN_YEAR))
            chosen += [{**item, "keyword": keyword} for item in picked[: PER_TOPIC - len(chosen)]]
            sleeper(1.5)
            if len(chosen) >= PER_TOPIC:
                break
        old_books = previous.get("books", {}).get(key, [])
        # 途中の検索失敗や、今まであった候補が突然0件になった場合は話題単位で保持。
        # 取得成功と「選定条件に合う候補0件」を区別し、空配列で既存を消さない。
        if failed or (not chosen and old_books):
            result[key] = copy.deepcopy(old_books)
            dates.setdefault(key, old_date)
            report["retainedTopics"].append(key)
            if not failed:
                report["errors"].append({"topic": key, "type": "NoMatchingBooks", "message": "既存候補がある話題で選定結果0件のため保持"})
            used.update(item["rbId"] for item in old_books)
            continue
        used.update(item["rbId"] for item in chosen)
        result[key] = [{**item, "url": affiliate_url(item["rbId"], item["itemId"])} for item in chosen]
        dates[key] = checked_at
        report["updatedTopics"].append(key)
        print(f"[books] {key}: " + " / ".join(i["title"][:20] for i in chosen))

    # 全ての本が取得できない日は、提携先価格を含めて既存の完全なスナップショットを保持。
    if not any(result.get(key) for key in report["updatedTopics"]):
        report["errors"].append({"type": "NoFreshBooks", "message": "新たに確認できた本が0件のため保存しません"})
        return copy.deepcopy(previous), report

    partner_prices = output.setdefault("partnerPrices", {})
    for key, partner in offers.get("partners", {}).items():
        source = partner.get("source")
        if not source:
            continue
        try:
            price = price_fetcher(source)
        except Exception as error:
            price = None
            report["errors"].append({"partner": key, "type": type(error).__name__, "message": str(error)[:200]})
        if isinstance(price, int) and price > 0:
            partner_prices[key] = price
            partner_dates[key] = checked_at
            report["updatedPartners"].append(key)
            print(f"[partner] {key}: {price:,}円")
        else:
            partner_dates.setdefault(key, old_date)
            report["retainedPartners"].append(key)
            report["errors"].append({"partner": key, "type": "PriceNotVerified", "message": "価格を確認できないため既存値を保持"})

    partial = bool(report["retainedTopics"] or report["retainedPartners"])
    # 現行画面は全体のfetchedAtを「価格・評価の時点」として表示する。
    # 新旧価格を混在させず、1件でも確認できなければ日時を含め旧snapshot全体を保持。
    report["outcome"] = "partial" if partial else "success"
    if partial:
        return copy.deepcopy(previous), report
    output.update({"fetchedAt": checked_at, "pixel": PIXEL})
    return output, report


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="取得・解析だけ行い、商品ファイルを書き換えない")
    parser.add_argument("--output", type=Path, default=PRODUCTS, help="検証時はwork配下を指定")
    parser.add_argument("--report", type=Path, help="取得結果と保持した項目の確認用JSON")
    parser.add_argument("--if-older-than", type=float, default=0, help="完全な取得からこの時間（h）未満なら何もしない")
    args = parser.parse_args()
    previous = json.loads(PRODUCTS.read_text(encoding="utf-8")) if PRODUCTS.exists() else {}
    now = datetime.now(timezone.utc)
    if args.if_older_than and previous.get("fetchedAt"):
        age = (now - datetime.fromisoformat(previous["fetchedAt"])).total_seconds() / 3600
        if age < args.if_older_than:
            print(f"[books] 前回の完全取得から{age:.1f}時間なのでスキップ")
            if args.report:
                write_json(args.report, {"checkedAt": now.isoformat(), "outcome": "skipped"})
            return 0
    offers = json.loads(OFFERS.read_text(encoding="utf-8"))
    output, report = refresh_catalog(offers, previous, now.isoformat())
    if args.report:
        write_json(args.report, report)
    print("[books] " + json.dumps(report, ensure_ascii=False))
    if args.dry:
        print("[books] dry: 商品データは保存しません")
    elif report["outcome"] == "success":
        write_json(args.output, output)
        print(f"[books] saved {args.output}")
    # 部分失敗もCIでは失敗。検証先の--outputであっても不完全なsnapshotを書かない。
    if report["outcome"] != "success":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""消費者庁 リコール情報サイト（https://www.recall.caa.go.jp/）の新着から、リコールの記事の候補を作る（2026-11-28）。

なぜ: 「あなたの数字のニュース」（scripts/your_number.py）の軸の記事を増やして、軸の外を止めても1日の本数が減らないようにする
（オーナー「本数を減らさない」）。食品の自主回収は毎日出るのに、自動の記事にはほとんどなっていなかった。

- 食品の回収の大もとは厚生労働省の「食品衛生申請等システム」（i2fas.mhlw.go.jp）だが、その robots.txt は公開の画面
  （/faspub/）をすべて禁止している。だから i2fas は機械では読まない。消費者庁のリコール情報サイトは robots.txt が無く
  （404。制限なし）、食品の回収（i2fas の届出）も「参照情報」に i2fas の URL を付けて載せているので、ここを読む。
- 一覧（新規登録情報 screenkbn=03・全分類・掲載日の新しい順）を1回に1ページ読み、まだ記事にしていない項目の詳しいページだけ読む
  （1秒あける・1回に FETCH_MAX 件まで）。詳しいページは本文が Quill（JavaScript）の文字の中にあるので、それを読み出す
  （feeds.expand_quill）。読んだ結果は state/caa_recall.json に残し、同じページは読み直さない。
- 大事な項目だけ: 食品は、全国・通信販売・2つ以上の都道府県・5店舗以上・全店・500個以上・全国で知られた名前のどれかに当たるもの。
  1つの店だけで少しだけ売った品（店舗1つ・数が少ない）・事業者向けの業務用・売った先も対象の見分け方も無いものは見送る。
  車・バイクのリコールは国土交通省の発表から作るので、ここでは作らない。
- 「あなたの数字」の要素: 自分の品が対象か（商品名・内容量・賞味期限/消費期限・ロット・JAN）、日付（対応開始日。回収の期限が
  掲載内容に無ければ無いと書く）、窓口（連絡先の電話・受付時間・URL。掲載内容にあるものだけ）を資料の先頭にまとめて渡す。
- 記事の作り方は事故の見張りの回収と同じ形（item["_incident"] の kind=recall。対象の表 → 窓口 → 今やること）。

  python3 scripts/caa_recall.py --dry-run            # いまの一覧で、どれを候補にしてどれを見送るか（state を書かない）
  python3 scripts/caa_recall.py --measure --days 7   # 直近7日の掲載を数える（一覧を2ページまで・詳しいページも読む）
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import feeds  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "state" / "caa_recall.json"
ARTICLES_DIR = ROOT / "content" / "articles"
CONTENT_STATE = ROOT / "content" / "state.json"
INCIDENT_CONFIG = ROOT / "scripts" / "incident_watch.json"
JST = timezone(timedelta(hours=9))

BASE = "https://www.recall.caa.go.jp"
LIST_URL = f"{BASE}/result/index.php?screenkbn=03"   # 新規登録情報（全分類・掲載日の新しい順・15件）
LIST_POST = f"{BASE}/result/index.php"
SOURCE_NAME = "消費者庁 リコール情報サイト"
MAX_AGE_DAYS = 4        # 掲載からこの日数までの項目を候補にする
FETCH_MAX = 8           # 1回に読む詳しいページの数
FETCH_GAP_SEC = 1.0     # 詳しいページを読む間隔
KEEP_DAYS = 30
FOOD = "食料品"
# 車・バイクは国土交通省の発表（mlit-press）から作る。同じリコールを2本にしない
MLIT_TITLE_RE = re.compile(r"^(?:乗用車|軽乗用車|貨物車|トラック|バス|バイク|二輪|自動二輪|原付|大型|特種|乗合)")

ROW_RE = re.compile(
    r'category_(\d+)">([^<]*)<.*?detail\.php\?rcl=(\d+)[^"]*"[^>]*>(.*?)</a>.*?result_list_post_date">([^<]*)<'
    r'(?:.*?result_list_start_date">([^<]*)<)?', re.S)
DATE_RE = re.compile(r"(\d{4})\s*[/年.-]\s*(\d{1,2})\s*[/月.-]\s*(\d{1,2})")
RCL_RE = re.compile(r"(?:rcl=|/product/)(\d{11})")
I2FAS_RE = re.compile(r"RCL\d{9}")

PREFS = ("北海道", "青森", "岩手", "宮城", "秋田", "山形", "福島", "茨城", "栃木", "群馬", "埼玉", "千葉", "東京", "神奈川", "新潟", "富山",
         "石川", "福井", "山梨", "長野", "岐阜", "静岡", "愛知", "三重", "滋賀", "京都", "大阪", "兵庫", "奈良", "和歌山", "鳥取", "島根",
         "岡山", "広島", "山口", "徳島", "香川", "愛媛", "高知", "福岡", "佐賀", "長崎", "熊本", "大分", "宮崎", "鹿児島", "沖縄")
WIDE_RE = re.compile(r"全国|全都道府県|通信販売|通販|オンライン(?:ショップ|ストア|販売)?|インターネット|ネット(?:ショップ|販売|通販)|EC ?サイト|"
                     r"Amazon|アマゾン|楽天市場|Yahoo!?ショッピング|首都圏|関東|東北|北陸|東海|近畿|関西|中国地方|四国|九州|全店|各店舗|全店舗|各店|"
                     r"量販店|スーパーマーケット各社|コンビニエンスストア")
STORES_RE = re.compile(r"(\d[\d,]*)\s*(?:店舗|店)")
QTY_RE = re.compile(r"(\d[\d,]*)\s*(?:個|本|袋|パック|点|箱|缶|瓶|食|ケース|枚|台|セット|kg|キロ)")
QTY_LINE_RE = re.compile(r"(?:販売数量|数量|販売数|出荷数|製造数|回収対象数|対象数)[^\n]{0,60}")
SALES_LINE_RE = re.compile(r"(?:販売地域|販売先|販売場所|販売店|販売期間|販売日|販売数量|出荷先|流通)")
TINY_RE = re.compile(r"文化祭|学園祭|学校祭|収穫祭|イベント(?:会場)?で(?:の)?販売|即売会|直売所|自動販売機|マルシェ")
SPEC_RE = re.compile(r"賞味期限|消費期限|内容量|JAN|ロット|製造所固有記号|品番|型番|製造番号|製造日|加工日|規格")
B2B_RE = re.compile(r"業務用")
CONSUMER_RE = re.compile(r"消費者|一般|小売|店頭|店舗で販売|量販店|スーパー")
HAZARD_RE = re.compile(r"アレルゲン|アレルギー|特定原材料|表示(?:の)?欠落|表示漏れ|異物|金属|ガラス|プラスチック|硬質|健康被害|食中毒|"
                       r"ふぐ|毒|放射性|セシウム|残留農薬|基準値|カビ|腐敗|膨張|変敗|細菌|大腸菌|リステリア|サルモネラ|ボツリヌス|回収命令")

_session_state: dict | None = None


# --------------------------------------------------------------------------- #
# 取得
# --------------------------------------------------------------------------- #
def _get(url: str) -> str:
    data, _ = feeds._fetch_cached(url, timeout=30, accept="text/html,application/xhtml+xml;q=0.9,*/*;q=0.8")
    return feeds._decode(data)


def _post_list(page: int, per_page: int = 60) -> str:
    """一覧のページ送り（サイトの「60件ごとに表示」と同じ POST）。--measure のときだけ使う"""
    body = urllib.parse.urlencode({"screenkbn": "03", "category": "", "viewCountdden": str(per_page), "portarorder": "2",
                                   "actionorder": "0", "pagingHidden": str(page), "search": ""}).encode()
    request = urllib.request.Request(LIST_POST, data=body, headers={"User-Agent": feeds.UA, "Accept": "text/html",
                                                                    "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return feeds._decode(response.read(5_000_000))


def detail_url(rcl: str) -> str:
    return f"{BASE}/result/detail.php?rcl={rcl}"


# --------------------------------------------------------------------------- #
# 読み取り
# --------------------------------------------------------------------------- #
def _clean(text: str) -> str:
    text = html.unescape(re.sub(r"<br\s*/?>", "\n", text or "", flags=re.I))
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("​", "")
    lines = [re.sub(r"[ \t　]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def _date(text: str) -> datetime | None:
    match = DATE_RE.search(text or "")
    if not match:
        return None
    try:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)), tzinfo=JST)
    except ValueError:
        return None


def parse_list(page: str) -> list[dict]:
    """一覧の表 → [{rcl, category, title, posted, started}]（掲載日の新しい順）"""
    rows = []
    seen = set()
    for cat_no, cat, rcl, title, posted, started in ROW_RE.findall(page):
        if rcl in seen:
            continue
        seen.add(rcl)
        rows.append({"rcl": rcl, "categoryNo": cat_no, "category": _clean(cat), "title": _clean(title),
                     "posted": _date(posted), "started": _date(started or "")})
    return rows


def _caps(page: str) -> list[tuple[str, str]]:
    """詳しいページの (見出し, 中身) の組（Quill の文字は読み出した後のページで）"""
    out = []
    for block in re.findall(r"<li\b[^>]*>(.*?)</li>", page, re.S):
        cap = re.search(r'<span class="detail_cap"[^>]*>(.*?)</span>', block, re.S)
        if not cap:
            continue
        rest = block[cap.end():]
        out.append((_clean(cap.group(1)), _clean(re.sub(r"<script\b.*?</script>", "", rest, flags=re.S))))
    return out


def parse_detail(page: str, rcl: str = "") -> dict:
    """詳しいページ → 項目ごとの文字（掲載内容にあるものだけ）"""
    page = feeds.expand_quill(page)
    head = re.search(r'<div class="detail_title">\s*<h3>(.*?)</h3>(.*?)</div>', page, re.S)
    rec: dict = {"rcl": rcl, "title": _clean(head.group(1)) if head else "",
                 "headline": _clean(re.sub(r"<!--.*?-->", "", head.group(2), flags=re.S)) if head else ""}
    crumbs = re.findall(r'index\.php\?screenkbn=\d+&(?:amp;)?category=\d+"[^>]*>([^<]+)</a>', page)
    rec["category"] = _clean(crumbs[-1]) if crumbs else ""
    names = {"商品名": "product", "連絡先": "contact", "対応方法": "action", "対応開始日": "started", "対象の特定情報": "spec",
             "備考": "note", "参照情報": "reference"}
    for cap, text in _caps(page):
        key = names.get(cap)
        if key and text and key not in rec:
            rec[key] = text
    refs = re.findall(r'href="(https?://[^"]+)"[^>]*>\s*参照情報', page)
    rec["referenceUrls"] = [html.unescape(u) for u in refs]
    image = re.search(r'href="(/images/rci/img/product/[^"]+)"', page)
    rec["image"] = BASE + image.group(1) if image else None
    return rec


def _split_title(title: str) -> tuple[str, str]:
    """「会社「商品」（売った所） - 返金／回収」→ ("会社「商品」（売った所）", "返金／回収")"""
    match = re.match(r"^(.*?)\s*[-－‐]\s*([^-－‐]+)$", title or "")
    return (match.group(1).strip(), match.group(2).strip()) if match else ((title or "").strip(), "")


def maker_of(title: str) -> str:
    base, _ = _split_title(title)
    name = re.split(r"[「（(]", base, maxsplit=1)[0].strip()
    return name or base[:30]


def product_of(title: str, rec: dict | None = None) -> str:
    match = re.search(r"「([^」]+)」", title or "")
    if match:
        return match.group(1)
    base, _ = _split_title(title)
    inner = re.search(r"（([^）]+)）", base)
    return inner.group(1) if inner else (rec or {}).get("product", "") or base


# --------------------------------------------------------------------------- #
# 大事な項目か
# --------------------------------------------------------------------------- #
def _major_names() -> list[str]:
    try:
        return [str(n) for n in json.loads(INCIDENT_CONFIG.read_text("utf-8")).get("major_names") or [] if len(str(n)) >= 2]
    except (OSError, ValueError):
        return []


def _num(text: str) -> int:
    try:
        return int(text.replace(",", ""))
    except ValueError:
        return 0


def significance(row: dict, rec: dict, major_names: list[str] | None = None) -> tuple[bool, str]:
    """(候補にするか, 理由)。食品は売った範囲で決め、食品以外（家電・日用品・子ども用品など）は全部候補にする"""
    title = rec.get("title") or row.get("title") or ""
    category = rec.get("category") or row.get("category") or ""
    if MLIT_TITLE_RE.search(title):
        return False, "車・バイクのリコール（国土交通省の発表から作る）"
    spec = rec.get("spec") or ""
    text = unicodedata.normalize("NFKC", f"{title}\n{spec}\n{rec.get('note') or ''}")
    contact = rec.get("contact") or ""
    if category != FOOD:
        if not (contact or rec.get("action")):
            return False, "連絡先も対応方法も無い"
        return True, f"{category or '製品'}のリコール"
    names = major_names if major_names is not None else _major_names()
    maker = maker_of(title)
    reasons = []
    if any(n in title for n in names):
        reasons.append("全国で知られた名前")
    if m := WIDE_RE.search(text):
        reasons.append(f"売った範囲が広い（{m.group(0)}）")
    prefs = {p for p in PREFS if p in text}
    if len(prefs) >= 2:
        reasons.append(f"{len(prefs)}都道府県")
    stores = max((_num(s) for s in STORES_RE.findall(text)), default=0)
    if stores >= 5:
        reasons.append(f"{stores}店舗")
    qty = max((_num(q) for line in QTY_LINE_RE.findall(text) for q in QTY_RE.findall(line)), default=0)
    if qty >= 500:
        reasons.append(f"{qty:,}個など")
    if B2B_RE.search(title) and not CONSUMER_RE.search(spec):
        return False, "業務用（事業者向けの品）"
    if reasons:
        return True, "・".join(reasons)
    single_store = bool(re.search(r"（[^）]*店[^）]*）", title)) and not re.search(r"、|・", re.search(r"（([^）]*)）", title).group(1))
    if TINY_RE.search(text) or (single_store and (qty == 0 or qty < 300)) or (qty and qty < 100):
        return False, f"小さな範囲の品（{maker}・{'店舗1つ' if single_store else '数が少ない/催しの品'}{f'・{qty}個' if qty else ''}）"
    has_sales = bool(SALES_LINE_RE.search(spec))
    actionable = bool(SPEC_RE.search(spec)) and bool(contact)
    if not has_sales and not actionable:
        return False, "売った範囲も対象の見分け方・窓口も掲載内容に無い"
    if HAZARD_RE.search(text):
        return True, "健康への危険（異物・アレルゲン・毒など）があり、対象の見分け方と窓口がある"
    if actionable:
        return True, "対象の見分け方と窓口がある"
    return False, "対象の見分け方か窓口が掲載内容に無い"


# --------------------------------------------------------------------------- #
# 記事にしたか（重複）
# --------------------------------------------------------------------------- #
def covered_ids(days: int = 45) -> tuple[set[str], set[str]]:
    """(記事・処理済みにある消費者庁の管理番号, i2fas の整理番号)。記事の JSON と content/state.json の URL を見る"""
    rcls: set[str] = set()
    i2fas: set[str] = set()
    cutoff = time.time() - days * 86400
    for path in ARTICLES_DIR.glob("*.json"):
        try:
            if path.stat().st_mtime < cutoff:
                continue
            text = path.read_text("utf-8")
        except OSError:
            continue
        if "recall" not in text and "i2fas" not in text:
            continue
        rcls.update(RCL_RE.findall(text))
        i2fas.update(I2FAS_RE.findall(text))
    try:
        state = json.loads(CONTENT_STATE.read_text("utf-8"))
    except (OSError, ValueError):
        state = {}
    for rec in (state.get("processed_web") or {}).values():
        url = str((rec or {}).get("url") or "") if isinstance(rec, dict) else ""
        rcls.update(RCL_RE.findall(url))
        i2fas.update(I2FAS_RE.findall(url))
    return rcls, i2fas


def _recent_products(days: int = 30) -> list[str]:
    """直近の記事の題名（同じ商品の回収を2本にしない）"""
    cutoff = time.time() - days * 86400
    titles = []
    for path in ARTICLES_DIR.glob("*recall*.json"):
        try:
            if path.stat().st_mtime < cutoff:
                continue
            data = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        titles.append(_key(f"{data.get('title') or ''} {data.get('seoTitle') or ''}"))
    return titles


def _key(text: str) -> str:
    return re.sub(r"[\s・･、，,。「」『』（）()〈〉<>＜＞\-ー－]", "", unicodedata.normalize("NFKC", text or "")).lower()


def same_product(rec: dict, titles: list[str]) -> bool:
    maker, product = _key(maker_of(rec.get("title") or "")), _key(product_of(rec.get("title") or "", rec))
    if len(product) < 3:
        return False
    return any(product[:12] in t and (not maker or maker[:4] in t or len(product) >= 6) for t in titles)


# --------------------------------------------------------------------------- #
# 候補の形
# --------------------------------------------------------------------------- #
NO_DEADLINE_WORDS = re.compile(r"期限|まで|迄|締め?切")


def source_text(row: dict, rec: dict) -> str:
    """資料（記事の出典の中身）。掲載内容の項目を、読者が確かめる順（対象か → 窓口 → 日付）に並べる。書き足すのは見出しだけ"""
    title = rec.get("title") or row["title"]
    posted = row.get("posted")
    started = rec.get("started") or (f"{row['started']:%Y年%-m月%-d日}" if row.get("started") else "")
    lines = [f"出典: {SOURCE_NAME}（消費者庁）「{title}」",
             f"掲載日: {posted:%Y年%-m月%-d日}" if posted else "",
             f"分類: {rec.get('category') or row.get('category') or ''}",
             f"件名: {title}"]
    if rec.get("headline"):
        lines.append(f"回収の理由（掲載の見出し）: {rec['headline']}")
    if rec.get("product"):
        lines.append(f"商品名: {rec['product']}")
    if rec.get("spec"):
        lines += ["", "【対象の特定情報（自分の商品が対象か確かめる項目）】", rec["spec"]]
    if rec.get("contact"):
        lines += ["", "【連絡先（回収の受付・問い合わせの窓口）】", rec["contact"]]
    if rec.get("action"):
        lines += ["", "【対応方法】", rec["action"]]
    lines += ["", f"対応開始日: {started}" if started else ""]
    if not NO_DEADLINE_WORDS.search(f"{rec.get('action') or ''}\n{rec.get('note') or ''}"):
        lines.append("回収・返金の受付の期限: 掲載内容には書かれていない")
    if rec.get("note"):
        lines += ["", "【備考】", rec["note"]]
    label = re.sub(r"\s*参照情報\s*$", "", (rec.get("reference") or "").split("\n")[0]).strip()  # 掲載のとおりの呼び方
    for url in rec.get("referenceUrls") or []:
        lines.append(f"参照情報: {label + ' ' if label else ''}{url}")
    lines.append(f"掲載ページ: {detail_url(rec.get('rcl') or row['rcl'])}")
    return "\n".join(line for line in lines if line is not None).strip()


def build_item(row: dict, rec: dict, why: str, feed: dict | None = None) -> dict:
    feed = feed or {}
    title = rec.get("title") or row["title"]
    base, action = _split_title(title)
    # 公共性の枠（public_interest の recall）に当たる言い方。「リコール」はこのサイト自身の呼び方（交換／返金・修理・回収命令も含む）
    item_title = f"{base}のリコール（{action}）" if action else f"{base}のリコール"
    url = detail_url(row["rcl"])
    content = source_text(row, rec)
    summary = "。".join(x for x in [rec.get("headline") or "", f"対応開始日 {rec.get('started')}" if rec.get("started") else ""] if x)
    return {
        "id": feeds.item_id(url),
        "url": url,
        "title": item_title,
        "summary": summary[:600],
        "content": content[: feeds.TEXT_CAP],
        "published_at": row.get("posted"),
        "source_name": feed.get("name") or SOURCE_NAME,
        "source_slug": feed.get("slug") or "caa-recall",
        "lang": "ja",
        "image": rec.get("image"),
        "priority": feed.get("priority", 1),
        "caaRecall": {"rcl": row["rcl"], "category": rec.get("category") or row.get("category"), "why": why},
        # 事故の見張りの回収と同じ書き方・下限（対象の表 → 窓口 → 今やること。scripts/incident_watch.py の PROMPT_NOTE）
        "_incident": {"key": f"caa-recall-{row['rcl']}", "kind": "recall", "name": maker_of(title)},
    }


# --------------------------------------------------------------------------- #
# 記録（state/caa_recall.json）
# --------------------------------------------------------------------------- #
def load_state() -> dict:
    global _session_state
    if _session_state is None:
        try:
            _session_state = json.loads(STATE_PATH.read_text("utf-8"))
        except (OSError, ValueError):
            _session_state = {}
        _session_state.setdefault("items", {})
    return _session_state


def save_state(state: dict) -> None:
    cutoff = (datetime.now(JST) - timedelta(days=KEEP_DAYS)).isoformat()
    state["items"] = {k: v for k, v in state.get("items", {}).items() if str(v.get("at") or "") >= cutoff}
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# feeds.parse_feed から呼ぶ入口
# --------------------------------------------------------------------------- #
def candidates(feed: dict | None = None, rows: list[dict] | None = None, *, now: datetime | None = None, write: bool = True,
               fetch_max: int = FETCH_MAX, max_age_days: int = MAX_AGE_DAYS, report: list | None = None,
               get=None) -> list[dict]:
    """一覧の新しい項目のうち、大事で、まだ記事にしていないものの候補（feeds の共通の形）"""
    now = now or datetime.now(JST)
    get = get or _get
    rows = rows if rows is not None else parse_list(get((feed or {}).get("url") or LIST_URL))
    state = load_state() if write else {"items": dict(load_state().get("items", {}))}
    rcls, i2fas = covered_ids()
    titles = _recent_products()
    names = _major_names()
    items: list[dict] = []
    fetched = 0
    for row in rows:
        posted = row.get("posted")
        if not posted or now - posted > timedelta(days=max_age_days + 1):
            continue
        memo = state["items"].get(row["rcl"]) or {}
        if row["rcl"] in rcls:
            decision = ("covered", "記事にした・処理済み")
        elif memo.get("decision") == "skip":
            decision = ("skip", memo.get("why") or "")
        elif MLIT_TITLE_RE.search(row["title"]):
            decision = ("skip", "車・バイクのリコール（国土交通省の発表から作る）")
        else:
            rec = memo.get("record")
            if not rec:
                if fetched >= fetch_max:
                    continue  # 次の回に読む
                if fetched:
                    time.sleep(FETCH_GAP_SEC)
                fetched += 1
                try:
                    rec = parse_detail(get(detail_url(row["rcl"])), row["rcl"])
                except Exception as error:  # noqa: BLE001 - 1件読めなくても続ける
                    feeds.log(f"[caa-recall] 詳しいページを読めませんでした（{row['rcl']}: {str(error)[:80]}）")
                    continue
            ok, why = significance(row, rec, names)
            if ok and set(I2FAS_RE.findall(json.dumps(rec, ensure_ascii=False))) & i2fas:
                ok, why = False, "同じ届出（i2fas の整理番号）の記事がある"
            elif ok and same_product(rec, titles):
                ok, why = False, "同じ商品の回収の記事がある"
            decision = ("take" if ok else "skip", why)
            state["items"][row["rcl"]] = {"at": now.isoformat(), "decision": decision[0], "why": why, "title": row["title"][:120],
                                          **({"record": rec} if ok else {})}
            if ok:
                items.append(build_item(row, rec, why, feed))
        if report is not None:
            report.append({"rcl": row["rcl"], "posted": f"{posted:%m-%d}", "category": row.get("category"), "title": row["title"],
                           "decision": decision[0], "why": decision[1]})
    if write:
        save_state(state)
    return items


def parse_feed(feed: dict) -> list[dict]:
    return candidates(feed)


# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="state を書かずに、候補と見送りを表示")
    parser.add_argument("--measure", action="store_true", help="一覧を60件ずつ最大2ページ読んで、直近の日数分を数える")
    parser.add_argument("--days", type=int, default=MAX_AGE_DAYS)
    parser.add_argument("--fetch-max", type=int, default=FETCH_MAX)
    args = parser.parse_args()
    rows = None
    if args.measure:
        rows = []
        for page in (0, 1):
            got = parse_list(_post_list(page))
            rows += got
            if not got or (got[-1]["posted"] and datetime.now(JST) - got[-1]["posted"] > timedelta(days=args.days + 1)):
                break
            time.sleep(FETCH_GAP_SEC)
    report: list = []
    items = candidates(rows=rows, write=not args.dry_run, fetch_max=args.fetch_max, max_age_days=args.days, report=report)
    for r in report:
        print(f"{r['posted']} {r['decision']:7} [{r['category']}] {r['title'][:70]}  … {r['why']}")
    days = max(1, args.days)
    takes = [r for r in report if r["decision"] == "take"]
    food = [r for r in takes if r["category"] == FOOD]
    print(f"\n候補 {len(items)} 件（食品 {len(food)}・食品以外 {len(takes) - len(food)}）/ 見送り "
          f"{sum(1 for r in report if r['decision'] == 'skip')} / 記事にした・処理済み {sum(1 for r in report if r['decision'] == 'covered')}"
          f" / 一覧 {len(report)} 件（{days}日 → 候補 {len(items) / days:.1f} 件/日）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""地震・津波の速報（気象庁の防災情報XML）。LLM は使わず、XML の値を決まった書式に入れるだけ。

- 対象は震度5弱以上の地震と、大津波警報・津波警報（rules の quake）。見つけるのは見張り番の Worker（ops/watchdog/src/quake.js）
- 同じ地震（EventID）の続報は同じ記事（slug: quake-<EventID>）を書き直す（新しい記事は作らない）
- 推測・被害の記述・写真は入れない（noPhoto: true で scripts/images.py も写真を付けない）
- 結果は state/fast_lane.json に書く（lane: disaster。全体の上限には数えない）

  python3 scripts/quake.py --fast-meta '[{"url": "...xml", "eventId": "...", "urls": [...]}]'   # Worker から（auto_run.yml）
  python3 scripts/quake.py --render a.xml b.xml          # 手元の XML から記事を組み立てて表示するだけ（書き込まない）
  python3 scripts/quake.py --missed --hours 30           # 直近の対象の地震・津波で記事が無いものを表示（見逃しチェック）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fast_lane  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
JST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (compatible; SaisokuQuake/1.0; +https://ai-tech-express.jp)"
DATA_HOST = "www.data.jma.go.jp"
EQ_PAGE = "https://www.jma.go.jp/bosai/map.html#contents=earthquake_map"
TSUNAMI_PAGE = "https://www.jma.go.jp/bosai/map.html#contents=tsunami"
LONG_FEED = "https://www.data.jma.go.jp/developer/xml/feed/eqvol_l.xml"

RANK = {"1": 1, "2": 2, "3": 3, "4": 4, "5-": 5, "5+": 6, "6-": 7, "6+": 8, "7": 9}
INT_NAME = {"1": "1", "2": "2", "3": "3", "4": "4", "5-": "5弱", "5+": "5強", "6-": "6弱", "6+": "6強", "7": "7"}
MAJOR, WARNING, ADVISORY = "大津波警報", "津波警報", "津波注意報"
WARN_CODES = {"52": MAJOR, "53": MAJOR, "51": WARNING, "62": ADVISORY}


def log(message: str) -> None:
    print(message, flush=True)


def conf() -> dict:
    return fast_lane.rules().get("quake") or {}


# --------------------------------------------------------------------------- #
# XML の読み取り
# --------------------------------------------------------------------------- #


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find(el, *path):
    """名前空間を気にせず子要素をたどる"""
    for name in path:
        if el is None:
            return None
        el = next((c for c in el if _local(c.tag) == name), None)
    return el


def _all(el, name):
    return [c for c in (el if el is not None else []) if _local(c.tag) == name]


def _text(el, *path) -> str:
    node = _find(el, *path) if path else el
    return (node.text or "").strip() if node is not None else ""


def parse(xml: bytes | str) -> dict:
    """1つの電文（震度速報・震源・震度に関する情報・津波警報など）を辞書に"""
    root = ET.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
    control, head, body = _find(root, "Control"), _find(root, "Head"), _find(root, "Body")
    out = {
        "title": _text(control, "Title"),
        "status": _text(control, "Status"),
        "eventId": _text(head, "EventID"),
        "infoType": _text(head, "InfoType"),
        "reportAt": _text(head, "ReportDateTime"),
        "headline": _text(head, "Headline", "Text"),
        "maxInt": "",
        "areas": [],  # [(震度, 細分区域名)]
        "origin": "", "hypocenter": "", "coord": "", "magnitude": "",
        "comments": [],
        "tsunami": [],  # [{area, kind, code, arrival, height}]
    }
    if out["title"] == "震度速報":
        # 震度速報は震源が無く、TargetDateTime が地震の発生時刻
        out["origin"] = _text(head, "TargetDateTime")
    eq = _find(body, "Earthquake")
    if eq is not None:
        out["origin"] = _text(eq, "OriginTime")
        area = _find(eq, "Hypocenter", "Area")
        out["hypocenter"] = _text(area, "Name")
        coord = _find(area, "Coordinate")
        out["coord"] = (coord.get("description") or "").strip() if coord is not None else ""
        mag = _find(eq, "Magnitude")
        if mag is not None:
            out["magnitude"] = (mag.get("description") or "").strip() or (mag.text or "").strip()
    obs = _find(body, "Intensity", "Observation")
    if obs is not None:
        out["maxInt"] = _text(obs, "MaxInt")
        for pref in _all(obs, "Pref"):
            for area in _all(pref, "Area"):
                if _text(area, "MaxInt"):
                    out["areas"].append((_text(area, "MaxInt"), _text(area, "Name")))
    comments = _find(body, "Comments")
    for c in comments if comments is not None else []:
        text = _text(c, "Text")
        if text:
            out["comments"].append(text)
    forecast = _find(body, "Tsunami", "Forecast")
    for item in _all(forecast, "Item"):
        kind = _find(item, "Category", "Kind")
        first = _find(item, "FirstHeight")
        arrival = _text(first, "ArrivalTime") if first is not None else ""
        cond = _text(first, "Condition") if first is not None else ""
        height = _find(item, "MaxHeight", "TsunamiHeight")
        out["tsunami"].append({
            "area": _text(item, "Area", "Name"),
            "kind": _text(kind, "Name"),
            "code": _text(kind, "Code"),
            "arrival": arrival,
            "condition": cond,
            "height": (height.get("description") or "").strip() if height is not None else "",
        })
    return out


def warn_level(bulletin: dict) -> str:
    """電文の中で一番強い津波の警報（大津波警報 / 津波警報 / 津波注意報 / 空）"""
    found = {WARN_CODES.get(t["code"]) for t in bulletin.get("tsunami", [])}
    return next((k for k in (MAJOR, WARNING, ADVISORY) if k in found), "")


def triggers(bulletin: dict) -> bool:
    """新しく記事にする電文か（震度5弱以上・大津波警報・津波警報。訓練・試験は除く）"""
    if bulletin.get("status") != "通常" or bulletin.get("infoType") == "取消":
        return False
    min_int = conf().get("min_int", "5-")
    if RANK.get(bulletin.get("maxInt", ""), 0) >= RANK[min_int]:
        return True
    return warn_level(bulletin) in (MAJOR, WARNING)


# --------------------------------------------------------------------------- #
# 続報のまとめ（同じ EventID の電文を新しい順に重ねる）
# --------------------------------------------------------------------------- #


def _dt(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=JST)


def merge(bulletins: list[dict]) -> dict:
    """同じ地震の電文をまとめる。震源は 震源・震度 > 震源 の新しいもの、震度は 震源・震度 > 震度速報 の新しいもの、津波は最新の警報"""
    ok = [b for b in bulletins if b.get("status") == "通常"]
    ok.sort(key=lambda b: _dt(b["reportAt"]) or datetime.min.replace(tzinfo=timezone.utc))
    ev = {"eventId": next((b["eventId"] for b in ok if b["eventId"]), ""), "bulletins": ok}

    def latest(pred):
        return next((b for b in reversed(ok) if pred(b)), None)

    hypo = latest(lambda b: b["hypocenter"] and b["infoType"] != "取消")
    inten = latest(lambda b: b["maxInt"] and b["title"] == "震源・震度に関する情報") or latest(lambda b: b["maxInt"])
    tsu = latest(lambda b: b["title"].startswith("津波警報"))
    ev.update({
        "hypocenter": hypo["hypocenter"] if hypo else "",
        "coord": hypo["coord"] if hypo else "",
        "magnitude": hypo["magnitude"] if hypo else "",
        "origin": (hypo or {}).get("origin") or next((b["origin"] for b in reversed(ok) if b["origin"]), ""),
        "maxInt": inten["maxInt"] if inten else "",
        "areas": inten["areas"] if inten else [],
        "tsunami": tsu["tsunami"] if tsu else [],
        "tsunamiAt": tsu["reportAt"] if tsu else "",
        "hadWarning": any(warn_level(b) for b in ok if b["title"].startswith("津波警報")),
        "comments": (latest(lambda b: b["comments"] and b["title"] == "震源・震度に関する情報") or latest(lambda b: b["comments"]) or {}).get("comments", []),
        "headlines": [(b["reportAt"], b["title"], b["headline"]) for b in ok if b["headline"]],
        "firstAt": ok[0]["reportAt"] if ok else "",
        "lastAt": ok[-1]["reportAt"] if ok else "",
        "cancelled": bool(ok) and ok[-1]["infoType"] == "取消",
    })
    ev["warn"] = warn_level({"tsunami": ev["tsunami"]})
    if not ev["origin"]:
        ev["origin"] = ev["firstAt"]
    return ev


def safety(ev: dict) -> bool:
    """夜間・上限を超えてもプッシュ通知する（大津波警報・津波警報・震度6弱以上）"""
    push_min = conf().get("push_min_int", "6-")
    return ev.get("warn") in (MAJOR, WARNING) or RANK.get(ev.get("maxInt", ""), 0) >= RANK[push_min]


# --------------------------------------------------------------------------- #
# 記事の組み立て（決まった書式。推測・被害の記述は入れない）
# --------------------------------------------------------------------------- #


def _jst(value: str, fmt: str = "%Y年%-m月%-d日 %-H時%M分") -> str:
    dt = _dt(value)
    return dt.astimezone(JST).strftime(fmt) if dt else "不明"


def _half(text: str) -> str:
    """全角の数字・英字を半角に（「Ｍ５．３」→「M5.3」）"""
    return unicodedata.normalize("NFKC", text or "")


def _depth(coord: str) -> str:
    # 例「北緯３８．１度　東経１４２．９度　深さ　２４ｋｍ」「ごく浅い」
    text = _half(coord)
    m = re.search(r"深さ\s*([0-9]+)\s*km", text)
    if m:
        return f"約{m.group(1)}km"
    if "ごく浅い" in text:
        return "ごく浅い"
    if "700km以上" in text:
        return "700km以上"
    return "不明（調査中）"


def _latlon(coord: str) -> str:
    text = _half(coord)
    m = re.search(r"(北緯|南緯)\s*([0-9.]+)度\s*(東経|西経)\s*([0-9.]+)度", text)
    return f"{m.group(1)}{m.group(2)}度 {m.group(3)}{m.group(4)}度" if m else ""


def _mag(text: str) -> str:
    """「Ｍ５．３」→「M5.3」。「Ｍ８を超える巨大地震」などは半角にしてそのまま"""
    t = _half(text).strip()
    return t or "不明（調査中）"


def _mag_long(text: str) -> str:
    return _mag(text).replace("M", "マグニチュード", 1) if text else "調査中"


def _top_area(ev: dict) -> str:
    top = [name for i, name in ev["areas"] if i == ev["maxInt"]]
    return top[0] if top else ""


def intensity_groups(ev: dict) -> list[tuple[str, list[str]]]:
    """震度の大きい順に（震度4以上。無ければ上位1段）"""
    groups: dict[str, list[str]] = {}
    for i, name in ev["areas"]:
        groups.setdefault(i, []).append(name)
    order = sorted(groups, key=lambda k: RANK.get(k, 0), reverse=True)
    keep = [k for k in order if RANK.get(k, 0) >= RANK["4"]] or order[:1]
    return [(k, groups[k]) for k in keep]


def tsunami_groups(ev: dict) -> list[tuple[str, list[dict]]]:
    groups: dict[str, list[dict]] = {}
    for t in ev["tsunami"]:
        kind = WARN_CODES.get(t["code"])
        if kind:
            groups.setdefault(kind, []).append(t)
    return [(k, groups[k]) for k in (MAJOR, WARNING, ADVISORY) if k in groups]


def _tsunami_line(t: dict) -> str:
    parts = []
    if t["arrival"]:
        parts.append(f"到達予想 {_jst(t['arrival'], '%-d日%-H時%M分')}")
    elif t["condition"]:
        parts.append(t["condition"])
    if t["height"]:
        parts.append(f"予想される高さ {t['height']}")
    return f"{t['area']}（{'・'.join(parts)}）" if parts else t["area"]


def headline_title(ev: dict) -> str:
    max_name = INT_NAME.get(ev["maxInt"], "")
    if ev["warn"] in (MAJOR, WARNING):
        areas = [t["area"] for k, ts in tsunami_groups(ev) if k == ev["warn"] for t in ts][:2]
        lead = f"【{ev['warn']}】{'・'.join(areas)}{'など' if len(areas) >= 2 else ''}"
        if max_name:
            return f"{lead}　最大震度{max_name}の地震（気象庁）"
        return f"{lead}（気象庁）"
    if not max_name:
        return "【地震】気象庁が地震の情報を発表"
    if ev["hypocenter"]:
        return f"【地震】{ev['hypocenter']}で最大震度{max_name}、{_mag(ev['magnitude'])}（気象庁）"
    area = _top_area(ev)
    return f"【地震】{area}{'など' if area else ''}で最大震度{max_name}　震源は調査中（気象庁）"


def render(ev: dict, now: datetime | None = None, previous: dict | None = None) -> dict:
    """記事 JSON（新規の形。既存の記事を書き直すときは write() が作成時刻などを引き継ぐ）"""
    now = now or datetime.now(timezone.utc)
    max_name = INT_NAME.get(ev["maxInt"], "")
    title = headline_title(ev)
    when = _jst(ev["origin"])
    hypo = ev["hypocenter"] or "調査中"
    rows = [
        ("発生時刻", f"{when}ごろ"),
        ("震源", f"{hypo}{f'（{_latlon(ev["coord"])}）' if _latlon(ev['coord']) else ''}"),
        ("深さ", _depth(ev["coord"]) if ev["coord"] else "調査中"),
        ("規模", _mag_long(ev["magnitude"])),
        ("最大震度", f"震度{max_name}（{_top_area(ev)}など）" if max_name else "発表なし"),
    ]
    tg = tsunami_groups(ev)
    if tg:
        rows.append(("津波", f"{'・'.join(k for k, _ in tg)}を発表中"))
    elif ev["hadWarning"]:
        rows.append(("津波", f"津波警報・注意報はすべて解除（{_jst(ev['tsunamiAt'], '%-d日%-H時%M分')}）"))
    else:
        tsunami_note = next((c for c in ev["comments"] if "津波" in c), "")
        rows.append(("津波", tsunami_note.split("\n")[0] if tsunami_note else "気象庁の発表を確認してください"))

    lines = []
    if ev.get("cancelled"):
        lines += ["> 気象庁が最新の情報を取り消しました。気象庁の発表を確認してください。", ""]
    lines += ["## 発表の概要", "", "| 項目 | 内容 |", "| --- | --- |"]
    lines += [f"| {k} | {v} |" for k, v in rows]
    lines += ["", f"（{_jst(ev['lastAt'], '%-m月%-d日 %-H時%M分')} 気象庁発表の情報にもとづく）", ""]
    groups = intensity_groups(ev)
    if groups:
        lines += ["## 各地の震度", ""]
        for k, names in groups:
            shown = names[:20]
            more = f" ほか{len(names) - len(shown)}地域" if len(names) > len(shown) else ""
            lines.append(f"- **震度{INT_NAME.get(k, k)}**: {'、'.join(shown)}{more}")
        lines += ["", "地域は気象庁の細分区域の名前です。", ""]
    if tg:
        lines += ["## 津波の警報・注意報", ""]
        for k, items in tg:
            lines.append(f"- **{k}**: {'、'.join(_tsunami_line(t) for t in items[:25])}")
        lines.append("")
    if ev["headlines"]:
        lines += ["## 気象庁の発表文", ""]
        for at, kind, text in ev["headlines"][-4:]:
            quoted = "\n> ".join(text.splitlines())
            lines += [f"**{_jst(at, '%-d日%-H時%M分')} {kind}**", "", f"> {quoted}", ""]
    if ev["comments"]:
        lines += ["## 気象庁からの付加情報", ""]
        lines += [f"- {c.replace(chr(10), ' ')}" for c in ev["comments"]]
        lines.append("")
    lines += [
        "## 最新情報は気象庁で確認してください",
        "",
        "この記事は速報です。情報は更新されることがあります。最新の情報・避難の判断は、気象庁と自治体の発表を確認してください。",
        "",
        f"- [気象庁 地震情報]({EQ_PAGE})",
        f"- [気象庁 津波警報・注意報]({TSUNAMI_PAGE})",
        "",
        "## この記事について",
        "",
        "気象庁が発表した防災情報XMLの値を、決まった書式に当てはめて自動で作成しています（AIによる文章の生成はしていません）。"
        "被害の状況や今後の見通しは含みません。続報が出ると、この記事を更新します。",
    ]
    body = "\n".join(lines).strip() + "\n"

    facts = [f"{when}ごろ発生"]
    if max_name:
        facts.append(f"最大震度{max_name}")
    if ev["hypocenter"]:
        facts.append(f"震源は{ev['hypocenter']}")
    if ev["magnitude"]:
        facts.append(_mag_long(ev["magnitude"]))
    if tg:
        facts.append(f"{'・'.join(k for k, _ in tg)}を発表中")
    description = f"気象庁の発表: {'、'.join(facts)}。最新情報は気象庁で確認してください。"
    highlights = [f"{when}ごろ、{'最大震度' + max_name + 'の' if max_name else ''}地震（気象庁発表）"]
    if ev["hypocenter"]:
        highlights.append(f"震源は{ev['hypocenter']}、深さ{_depth(ev['coord'])}、{_mag(ev['magnitude'])}")
    for k, items in tg:
        highlights.append(f"{k}: {'、'.join(t['area'] for t in items[:6])}{'など' if len(items) > 6 else ''}")
    threads = [title, *highlights[1:3], "最新情報は気象庁の発表を確認してください。"]

    slug = f"quake-{ev['eventId']}"
    published = _dt(ev["firstAt"]) or now
    article = {
        "slug": slug,
        "sourceType": "web",
        "sourceUrl": TSUNAMI_PAGE if ev["warn"] in (MAJOR, WARNING) and not max_name else EQ_PAGE,
        "sourceName": "気象庁",
        "title": title,
        "seoTitle": title[:60],
        "threadsPost": "\n".join(threads),
        "threadsHook": "breaking",
        "threadsStyle": 2,
        "lede": description,
        "description": description[:160],
        "keywords": ["地震", "気象庁", *(["津波"] if tg else []), *([ev["hypocenter"]] if ev["hypocenter"] else []), *([f"震度{max_name}"] if max_name else [])],
        "tags": ["地震", "防災", *(["津波"] if tg else [])],
        "highlights": highlights[:3],
        "timetable": [],
        "verdict": None,
        "body": body,
        "easy": "",
        "channel": "気象庁",
        "channelId": "",
        "channelSlug": "jma",
        "genre": "社会・行政",
        "genreSlug": conf().get("genre", "public"),
        "disclaimer": "本記事は気象庁の防災情報XMLの値を決まった書式で自動掲載した速報です（AIによる文章の生成はしていません）。最新の情報・避難の判断は気象庁と自治体の発表を確認してください。",
        "videoId": "",
        "videoUrl": "",
        "videoTitle": ev["headlines"][-1][1] if ev["headlines"] else "地震情報",
        "publishedAt": published.astimezone(timezone.utc).isoformat(),
        "generatedAt": now.isoformat(),
        "thumbnail": "",
        "model": "template",
        "affiliates": [],
        "breaking": True,
        "disaster": True,
        "noPhoto": True,
        "safetyAlert": safety(ev),
        "fastLane": True,
        "sourcePublishedAt": published.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "quakeEventId": ev["eventId"],
        "quakeLevel": {"maxInt": ev["maxInt"], "tsunami": ev["warn"]},
    }
    if not previous:
        minutes = int(-(-((now - published).total_seconds() / 60) // 1)) + 3  # 書き出し＋デプロイの約3分
        if 0 < minutes <= 60:
            article["speedMinutes"] = minutes
    return article


def write(article: dict, now: datetime) -> tuple[str, Path]:
    """新規なら作り、あれば書き直す（作成時刻・速さのラベル・更新履歴を引き継ぐ）。("created"|"updated"|"same", path)"""
    path = ARTICLES / f"{article['slug']}.json"
    if path.exists():
        old = json.loads(path.read_text("utf-8"))
        keep = {k: old[k] for k in ("generatedAt", "speedMinutes", "publishedAt", "sourcePublishedAt", "updates") if k in old}
        merged = {**article, **keep}
        if not old.get("speedMinutes"):
            merged.pop("speedMinutes", None)
        compare = {k: v for k, v in merged.items() if k not in ("generatedAt", "updatedAt", "updates")}
        if compare == {k: v for k, v in old.items() if k not in ("generatedAt", "updatedAt", "updates")}:
            return "same", path
        merged["updatedAt"] = now.isoformat()
        merged["updates"] = [*old.get("updates", []), {"at": now.isoformat(), "title": article["title"], "sourceUrl": article["sourceUrl"], "sourceName": "気象庁"}][-20:]
        # 夜間に送れなかった安全の通知は、続報で警報が出たら改めて送れるよう safetyAlert は最新の値
        path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", "utf-8")
        return "updated", path
    ARTICLES.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(article, ensure_ascii=False, indent=2) + "\n", "utf-8")
    return "created", path


# --------------------------------------------------------------------------- #
# 取得
# --------------------------------------------------------------------------- #


def fetch(url: str, timeout: int = 15) -> bytes:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.netloc != DATA_HOST:
        raise ValueError(f"気象庁の XML ではありません: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read()


def feed_entries(feed_url: str) -> list[dict]:
    root = ET.fromstring(fetch(feed_url))
    out = []
    for entry in _all(root, "entry"):
        link = _find(entry, "link")
        out.append({"title": _text(entry, "title"), "url": link.get("href") if link is not None else "", "updated": _text(entry, "updated")})
    return out


def collect(event_id: str, urls: list[str]) -> list[dict]:
    """渡された電文と、いまの feed にある同じ地震の電文（待っている間に出た続報）を集める"""
    seen, bulletins = set(), []
    titles = set(conf().get("titles") or [])
    extra: list[str] = []
    try:
        start = datetime.strptime(event_id[:12], "%Y%m%d%H%M").replace(tzinfo=JST) - timedelta(minutes=5)
        for e in feed_entries(conf()["feed"]):
            at = _dt(e["updated"])
            if e["title"] in titles and at and at >= start:
                extra.append(e["url"])
    except Exception as error:  # noqa: BLE001
        log(f"[quake] feed を読めませんでした（渡された電文だけで作ります）: {str(error)[:80]}")
    for url in [*urls, *extra]:
        if not url or url in seen:
            continue
        seen.add(url)
        try:
            b = parse(fetch(url))
        except Exception as error:  # noqa: BLE001
            log(f"[quake] 電文を読めませんでした {url}: {str(error)[:80]}")
            continue
        if b["eventId"] == event_id:
            bulletins.append(b)
    return bulletins


def ack(key: str, result: dict, started: datetime) -> None:
    data = fast_lane.load_acks()
    data["items"][key] = {
        **result, "lane": "disaster", "startedAt": started.isoformat(timespec="seconds"),
        "finishedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "run": os.environ.get("GITHUB_RUN_ID", ""),
    }
    fast_lane.save_acks(data)


def run_fast(meta_raw: str, fast_url: str) -> int:
    started = datetime.now(timezone.utc)
    metas = fast_lane.parse_meta(meta_raw) or ([{"url": fast_url}] if fast_url else [])
    if not metas:
        log("[quake] 対象がありません")
        return 0
    for meta in metas:
        urls = [u for u in [meta.get("url"), *(meta.get("urls") or [])] if isinstance(u, str)]
        event_id = str(meta.get("eventId") or "")
        if not event_id:
            try:
                event_id = parse(fetch(urls[0]))["eventId"]
            except Exception as error:  # noqa: BLE001
                log(f"[quake] 電文を読めませんでした: {str(error)[:120]}")
                continue
        key = str(meta.get("id") or f"quake-{event_id}")
        bulletins = collect(event_id, urls)
        base = {"url": urls[0] if urls else "", "title": "", "source": "jma-quake"}
        if not bulletins:
            ack(key, {**base, "outcome": "retry", "reason": "電文を読めない"}, started)
            continue
        ev = merge(bulletins)
        path = ARTICLES / f"quake-{event_id}.json"
        if not path.exists() and not any(triggers(b) for b in bulletins):
            log(f"[quake] {event_id}: 対象の基準（震度{conf().get('min_int')}以上・津波警報）に届かないため記事にしません")
            ack(key, {**base, "outcome": "skipped", "reason": "基準未満"}, started)
            continue
        previous = json.loads(path.read_text("utf-8")) if path.exists() else None
        article = render(ev, datetime.now(timezone.utc), previous)
        outcome, _ = write(article, datetime.now(timezone.utc))
        log(f"[quake] {outcome}: {article['slug']} {article['title']}（電文 {len(bulletins)} 件・安全の通知 {article['safetyAlert']}）")
        ack(key, {**base, "title": article["title"], "outcome": "updated" if outcome == "same" else outcome, "slug": article["slug"],
                  "reason": "変更なし" if outcome == "same" else ""}, started)
    return 0


def missed(hours: int) -> int:
    """直近 hours 時間の対象の地震・津波で、記事が無いもの（見逃しチェック用。書き込まない）"""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    titles = {"震度速報", "震源・震度に関する情報", "津波警報・注意報・予報a"}
    events: dict[str, list[dict]] = {}
    try:
        entries = feed_entries(LONG_FEED)
    except Exception as error:  # noqa: BLE001
        log(f"[quake] feed を読めませんでした: {error}")
        return 0
    for e in entries:
        at = _dt(e["updated"])
        if e["title"] not in titles or not at or at < since:
            continue
        try:
            b = parse(fetch(e["url"]))
        except Exception:  # noqa: BLE001
            continue
        events.setdefault(b["eventId"], []).append(b)
    found = []
    for eid, bs in events.items():
        if not any(triggers(b) for b in bs):
            continue
        ev = merge(bs)
        exists = (ARTICLES / f"quake-{eid}.json").exists()
        found.append((eid, headline_title(ev), exists))
    lines = ["### 地震・津波（気象庁）", ""]
    if not found:
        lines.append(f"- 直近{hours}時間に対象（震度{conf().get('min_int', '5-').replace('-', '弱').replace('+', '強')}以上・津波警報）はありません")
    for eid, title, exists in found:
        lines.append(f"- {'記事あり' if exists else '**記事なし**'}: {title}（EventID {eid}）")
    print("\n".join(lines))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    for eid, title, exists in found:
        if not exists:
            print(f"::warning::地震・津波の記事がありません: {title}（EventID {eid}）")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fast-meta", default="")
    parser.add_argument("--fast-url", default="")
    parser.add_argument("--render", nargs="*", help="手元の XML から記事を組み立てて表示するだけ")
    parser.add_argument("--json", action="store_true", help="--render の結果を JSON で出す")
    parser.add_argument("--now", default="", help="--render の現在時刻（ISO。速さのラベルの確認用）")
    parser.add_argument("--missed", action="store_true")
    parser.add_argument("--hours", type=int, default=30)
    args = parser.parse_args()
    if args.render is not None:
        bulletins = [parse(Path(p).read_bytes()) for p in args.render]
        ev = merge(bulletins)
        now = _dt(args.now) if args.now else None
        article = render(ev, now)
        article["_triggers"] = any(triggers(b) for b in bulletins)
        if args.json:
            print(json.dumps(article, ensure_ascii=False))
        else:
            print(f"# {article['title']}\n\n{article['description']}\n\n{article['body']}\n---\nslug={article['slug']} safetyAlert={article['safetyAlert']} speedMinutes={article.get('speedMinutes')} 対象={article['_triggers']}")
        return 0
    if args.missed:
        return missed(args.hours)
    return run_fast(args.fast_meta, args.fast_url)


if __name__ == "__main__":
    raise SystemExit(main())

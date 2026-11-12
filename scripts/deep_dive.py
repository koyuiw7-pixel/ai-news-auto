#!/usr/bin/env python3
"""読まれた記事を、別の疑問に答える記事3〜4本に深掘りする（2026-11-10 オーナー承認・台帳 A70）。

11/9 は記事が約90本で、夜（20時〜翌9時）はほぼ0本だった。公式の新しい発表が夜はほとんど出ないため。
一方で、読まれた記事（ドコモの流出・児童手当・年金生活者支援給付金など）の読者は、まだ知りたいことを持っている。
そこで、前の日に人に読まれた記事（content/popular.json。scripts/popular_articles.py が自前の計測から作る）の上位5本から、
次の型のうち「公式の出典ページに答えがある型」だけを選んで、別の角度の記事（angleOf 付き。scripts/angle_articles.py と同じ扱い）を作る。

  対象の確かめ方 / 家族の分 / 手続き / 不安Q&A / 比較・早見表

- 事実は元の記事の公式の出典ページ（報道は使わない W31）だけ。読めるページは無料の取得の経路（Jina の鍵が無くても読む）で取る。
- 書き方・門はふつうの記事と同じ（scripts/web_articles.py の compose_with_facts → 公開前の門 → 品質の門の事実確認）。門は緩めない。
  人の目を通らないので、事実確認の点数は Muse の記事と同じ PASS_SCORE 以上に限る。
- 同じ元記事・同じ型の記事は1本だけ（記事の angleOf と deepDive、state/deep_dive.json で二重に作らない）。
  題名がこの7日の記事とほぼ同じなら出さない。
- 今日の本数に数える（content/state.json の processed_web。scripts/pacing.py の live_today）。
- .github/workflows/deep_dive.yml が夜（20時〜翌9時）に1時間ごと・昼に2回動かし、1回 --max 本ずつ出す（夜に記事が並ぶように）。

  python3 scripts/deep_dive.py --dry-run            # 元記事・出典・作れる型を表示（LLM を使わない）
  python3 scripts/deep_dive.py --max 2 --budget 1500
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
POPULAR = ROOT / "content" / "popular.json"
STATE = ROOT / "state" / "deep_dive.json"
JST = timezone(timedelta(hours=9))

TOP_BASES = 5  # 深掘りする元記事の数（前の日に読まれた順）
MIN_VIEWS = 5  # これより読まれていない記事は深掘りしない（当たっていない話題を増やさない）
ANGLES_PER_BASE = 4  # 1本の元記事から作る最大本数
DAILY_CAP = int(os.environ.get("DEEP_DIVE_DAILY_CAP") or 20)
PASS_SCORE = 80  # scripts/muse_articles.py の MUSE_PASS_SCORE と同じ（人の目を通らない書き手）
RETRY_DAYS = 3  # 門に落ちた型を作り直すまでの日数
MAX_SOURCES = 5
DEDUPE_DAYS = 7
# 暮らしとお金の「自分ごと」の範囲（台帳 A63）。AI・スポーツ・エンタメ・科学の記事は深掘りしない
CORE_GENRES = {"public", "business", "lifestyle", "investment", "real-estate", "tech-gadget"}

# 型: (key, 記事の方向, 答える疑問, 読者, 公式ページにこの言葉がいくつあれば答えられるか, 必要な数)
ANGLES: list[dict] = [
    {"key": "check", "label": "対象の確かめ方", "direction": "自分が対象かどうかの確かめ方に絞る",
     "question": "自分は対象？どこを見れば分かる？", "reader": "対象かどうか分からず不安な人",
     "support": r"対象|該当|確認|確かめ|条件|要件|基準|お知らせ|通知", "need": 4},
    {"key": "family", "label": "家族の分", "direction": "家族（配偶者・子ども・親・家族の回線）の分がどうなるかに絞る",
     "question": "家族の分はどうなる？家族の代わりに確かめられる？", "reader": "家族の分も気になる人",
     "support": r"家族|配偶者|子ども|子供|児童|扶養|世帯|親|遺族|法定代理人|未成年|同居", "need": 4},
    {"key": "procedure", "label": "手続き", "direction": "申請・届出・問い合わせの手順に絞る（どこで・何を持って・いつまでに）",
     "question": "手続きはどこで、何が要って、いつまで？", "reader": "これから手続きする人",
     "support": r"申請|手続|届出|届け出|請求|窓口|提出|必要書類|期限|受付", "need": 4},
    {"key": "qa", "label": "不安Q&A", "direction": "読者が抱きそうな不安と、公式ページにある答えに絞る（Q&A の形）",
     "question": "よくある不安と、その答えは？", "reader": "ニュースを見て不安になった人",
     "support": r"Q&A|Q＆A|よくある|ご質問|質問|注意|ご注意|お願い|場合", "need": 3},
    {"key": "compare", "label": "比較・早見表", "direction": "金額・条件・期限を表で比べることに絞る",
     "question": "金額・条件・期限を一覧で比べると？", "reader": "自分の場合の数字を早く知りたい人",
     "support": r"\d[\d,，.]*\s*(?:円|万円|%|％|日|か月|カ月|ヶ月|年|件|時間|kWh)", "need": 8},
]
ANGLE_BY_KEY = {a["key"]: a for a in ANGLES}
# 元の記事の題名がすでにその型に答えている（「対象の確かめ方と今やること」など）ときは、その型を作らない
COVERED_RE = {
    "check": re.compile(r"確かめ方|対象か|対象になる|対象は"),
    "family": re.compile(r"家族の分|家族の回線"),
    "procedure": re.compile(r"手続き|申請方法|請求の仕方"),
    "qa": re.compile(r"Q&A|Q＆A|よくある質問"),
    "compare": re.compile(r"比較|比べ|早見"),
}

DEEP_NOTE = """

# 今回の記事の角度（必ず守る）
当サイトには、この話題の全体を解説した記事「{base_title}」（/articles/{base_slug}）がすでにあり、多くの人に読まれています。
今回は、その読者が次に知りたい次の1点だけに答える記事を書いてください。全体の解説はくり返さないこと。
- 記事の型: {label}
- 記事の方向: {direction}
- この記事が答える疑問: {question}
- 想定する読者: {reader}
- title と seo_title は、この疑問がそのまま検索されたときに見つかる言い方にする（元の記事と同じ題名にしない）。
- 本文の冒頭近くで、全体の解説は元の記事へ、と一文で案内し、[{base_title}](/articles/{base_slug}) へリンクする。
- この疑問で検索する人が使う言葉（対象・確かめ方・手続き・いつまで・家族 など）を、資料で答えられるものだけ本文の最初の段落に入れる（SEO A14）。
- 使う事実は、上の公式の資料にあるものだけ。資料に書かれていないことは「公式の発表には記載がありません」と書く。推測で埋めない。
- この疑問に答えられる事実が資料に足りないときは、is_relevant を false にし、skip_reason に足りない点を書く（無理に書かない）。
"""


def log(message: str) -> None:
    print(message, flush=True)


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def save_state(data: dict) -> None:
    attempts = data.get("attempts") or {}
    if len(attempts) > 400:
        attempts = dict(sorted(attempts.items(), key=lambda kv: str(kv[1].get("at") or ""), reverse=True)[:400])
    data["attempts"] = attempts
    data["updatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", "utf-8")


def load_article(slug: str) -> dict | None:
    return load_json(ARTICLES / f"{slug}.json", None)


def all_articles() -> dict[str, dict]:
    out = {}
    for path in ARTICLES.glob("*.json"):
        data = load_json(path, None)
        if isinstance(data, dict):
            out[path.stem] = data
    return out


def story_urls(art: dict) -> set[str]:
    """同じ発表かを見る URL（一番の出典と、書き手が挙げた出典。RSS は外す）と duplicateOf"""
    urls = [art.get("sourceUrl")] + [s.get("url") for s in art.get("museSources") or [] if isinstance(s, dict)]
    out = {"url:" + str(u).strip().rstrip("/").split("#")[0] for u in urls
           if u and not re.search(r"\.(?:rdf|xml|rss)(?:$|\?)", str(u))}
    if art.get("duplicateOf"):
        out.add("slug:" + str(art["duplicateOf"]))
    out.add("slug:" + str(art.get("slug")))
    return out


def group_stories(slugs: list[str], articles: dict[str, dict]) -> list[list[str]]:
    """同じ発表の記事をまとめる（出典の URL が1つでも同じ・duplicateOf でつながる）。ドコモの流出のように同じ発表の記事が2本読まれても、深掘りは1組だけ"""
    parent = {s: s for s in slugs}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    owner: dict[str, str] = {}
    for slug in slugs:
        for key in story_urls(articles[slug]):
            if key in owner:
                parent[find(slug)] = find(owner[key])
            else:
                owner[key] = slug
    groups: dict[str, list[str]] = {}
    for slug in slugs:
        groups.setdefault(find(slug), []).append(slug)
    return list(groups.values())


def pick_bases(popular: dict, articles: dict[str, dict], top: int = TOP_BASES, min_views: int = MIN_VIEWS) -> list[tuple[dict, int]]:
    """深掘りする元記事 [(記事, 読まれた回数)]。別の角度の記事が当たったときは、その元の記事を深掘りする。
    同じ発表の記事は1つにまとめ（読まれた回数は合計）、いちばん読まれた記事を元にする"""
    views: dict[str, int] = {}
    for row in popular.get("items") or []:
        slug = str(row.get("slug") or "")
        art = articles.get(slug)
        if not art:
            continue
        base = str(art.get("angleOf") or slug)
        if base not in articles:
            continue
        views[base] = views.get(base, 0) + int(row.get("views") or 0)
    ranked = []
    for group in group_stories(sorted(views), articles):
        rows = sorted(((s, views[s]) for s in group), key=lambda kv: (-kv[1], kv[0]))
        ranked.append((rows[0][0], sum(n for _, n in rows), [s for s, _ in rows[1:]]))
    out = []
    for slug, n, siblings in sorted(ranked, key=lambda r: (-r[1], r[0])):
        art = articles[slug]
        if n < min_views or art.get("genreSlug") not in CORE_GENRES or art.get("angleOf"):
            continue
        art["_siblings"] = siblings
        out.append((art, n))
        if len(out) >= top:
            break
    return out


def source_urls(base: dict) -> list[dict]:
    """元の記事の公式の出典（報道・RSS は外す）[{url, name}]。一番の出典が先頭"""
    import public_interest  # noqa: PLC0415

    rows: list[dict] = []
    if base.get("sourceUrl"):
        rows.append({"url": base["sourceUrl"], "name": base.get("sourceName") or base.get("channel") or ""})
    for key in ("museSources", "factSources", "officialDesk"):
        for s in base.get(key) or []:
            if isinstance(s, dict) and s.get("url"):
                rows.append({"url": s["url"], "name": s.get("name") or ""})
    seen: set[str] = set()
    out = []
    for r in rows:
        url = str(r["url"]).strip()
        key = url.rstrip("/")
        if not url.startswith("https://") or key in seen or re.search(r"\.(?:rdf|xml|rss)(?:$|\?)", url):
            continue
        if public_interest.is_press_url(url):
            continue
        seen.add(key)
        out.append({"url": url, "name": r["name"]})
    return out[:MAX_SOURCES]


# 角度の記事の「答える疑問の役割」（SEO A17・2026-11-10）。同じ元記事に同じ役割のページを2本作らない。
# Google は同じサイトから上位に出すのは普通2件まで。年金生活者支援給付金・児童手当・ドコモで各4ページになっていた。
# 手で作った角度の記事（scripts/angle_articles.py。deepDive の印が無い）は題名から役割を読む。上から順に最初に当たったもの
ROLE_RULES: list[tuple[str, re.Pattern]] = [
    ("今日やること", re.compile(r"今日やる|今やる|やること|まずやる|すぐやる")),
    ("対象の確かめ方", re.compile(r"確かめ方|対象は|対象か|対象になる|誰が使える|使えるか|使うには")),
    ("家族の分", re.compile(r"家族|配偶者|法定代理人|子どもの分")),
    ("手続き", re.compile(r"手続|申請|届出|届け出|請求の仕方|窓口")),
    ("不安Q&A", re.compile(r"Q&A|Q＆A|不安|よくある")),
    ("比較・早見表", re.compile(r"比較|比べ|早見|違い")),
]
FIGURE_RE = re.compile(r"(?:最大|約|計|合計)*[0-9０-９][0-9０-９,，.]*(?:万|億|千)?(?:件|円|人|%|％|倍|社|台|回)")


def query_role(text: str) -> str:
    """題名・方向の文から、答える疑問の役割（ROLE_RULES の名前。当たらなければ空）"""
    for role, pattern in ROLE_RULES:
        if pattern.search(text or ""):
            return role
    return ""


def role_of(record: dict) -> str:
    """角度の記事の役割（queryRole → 深掘りの型 → 題名の順）"""
    if record.get("queryRole"):
        return str(record["queryRole"])
    if record.get("deepDive") in ANGLE_BY_KEY:
        return ANGLE_BY_KEY[record["deepDive"]]["label"]
    return query_role(str(record.get("title") or ""))


def existing_roles(articles: dict[str, dict], base_slug: str, siblings: list[str] | None = None) -> set[str]:
    """この元記事（と同じ発表の記事）の角度の記事が、すでに答えている役割"""
    bases = {base_slug, *(siblings or [])}
    return {r for a in articles.values() if a.get("angleOf") in bases and (r := role_of(a))}


def leading_figure(title: str) -> str:
    """元の記事の題名の最初の数字（「最大約30万件」→「30万件」。「最大・約」は外す。無ければ空）"""
    m = FIGURE_RE.search(title or "")
    return re.sub(r"^(?:最大|約|計|合計)+", "", m.group(0)) if m else ""


def sibling_problem(title: str, role: str, base: dict, articles: dict[str, dict]) -> str | None:
    """角度の記事の候補を出してよいか。同じ役割がある・元の記事の最初の数字で始まる題名なら理由（SEO A17）"""
    if role and role in existing_roles(articles, base["slug"], list(base.get("_siblings") or [])):
        return f"同じ役割（{role}）のページがすでにある"
    figure = leading_figure(str(base.get("title") or ""))
    if figure and figure in (title or "")[:16]:
        return f"題名が元の記事と同じ数字（{figure}）で始まる（同じ質問のページになる）"
    return None


def supported(angle: dict, text: str) -> bool:
    """公式の出典ページに、この型に答える材料があるか（言葉の数で見る安い確かめ。最後は品質の門の事実確認）"""
    hits = re.findall(angle["support"], text or "")
    if angle["key"] == "compare":
        return len(set(hits)) >= angle["need"] if hits and isinstance(hits[0], str) else len(hits) >= angle["need"]
    return len(hits) >= angle["need"]


def existing_angles(articles: dict[str, dict], base_slug: str, siblings: list[str] | None = None) -> set[str]:
    """この元記事（と同じ発表の記事）にすでにある深掘りの型"""
    bases = {base_slug, *(siblings or [])}
    return {str(a.get("deepDive")) for a in articles.values() if a.get("angleOf") in bases and a.get("deepDive")}


def angle_count(articles: dict[str, dict], base_slug: str) -> int:
    return sum(1 for a in articles.values() if a.get("angleOf") == base_slug)


def attempt_key(base_slug: str, key: str) -> str:
    return f"{base_slug}|{key}"


def blocked_attempt(state: dict, base_slug: str, key: str, now: datetime | None = None) -> str | None:
    row = (state.get("attempts") or {}).get(attempt_key(base_slug, key))
    if not row:
        return None
    if row.get("status") == "published":
        return "作成済み"
    now = now or datetime.now(timezone.utc)
    try:
        at = datetime.fromisoformat(str(row.get("at")))
    except ValueError:
        return None
    if now - at < timedelta(days=RETRY_DAYS):
        return f"{RETRY_DAYS}日以内に見送り（{str(row.get('reason') or '')[:60]}）"
    return None


def plan(bases: list[tuple[dict, int]], articles: dict[str, dict], state: dict, texts: dict[str, str]) -> list[tuple[dict, dict]]:
    """[(元記事, 型)]。読まれた順に、元記事ごとに型の順で、まだ無い・出典に答えがある型を ANGLES_PER_BASE 本まで。
    元記事を交互に回す（1本の話題だけで夜が埋まらないように）"""
    per_base: list[list[tuple[dict, dict]]] = []
    for base, _views in bases:
        slug = base["slug"]
        siblings = list(base.get("_siblings") or [])
        have = existing_angles(articles, slug, siblings)
        roles = existing_roles(articles, slug, siblings)
        room = ANGLES_PER_BASE - len(have)
        rows = []
        titles = " ".join([base.get("title") or ""] + [articles[s].get("title") or "" for s in siblings if s in articles])
        for angle in ANGLES:
            if room <= 0:
                break
            if angle["key"] in have or any(blocked_attempt(state, b, angle["key"]) for b in [slug, *siblings]):
                continue
            # 手で作った角度の記事が、同じ役割にすでに答えている（SEO A17）
            if angle["label"] in roles:
                continue
            if COVERED_RE[angle["key"]].search(titles):
                continue
            if not supported(angle, texts.get(slug, "")):
                continue
            rows.append((base, angle))
            room -= 1
        per_base.append(rows)
    out = []
    while any(per_base):
        for rows in per_base:
            if rows:
                out.append(rows.pop(0))
    return out


def deep_id(base_slug: str, key: str) -> str:
    return "deep-" + hashlib.sha1(attempt_key(base_slug, key).encode("utf-8")).hexdigest()[:10]


def made_today(state: dict, now: datetime | None = None) -> int:
    today = (now or datetime.now(JST)).astimezone(JST).date()
    n = 0
    for row in (state.get("attempts") or {}).values():
        if row.get("status") != "published":
            continue
        try:
            if datetime.fromisoformat(str(row.get("at"))).astimezone(JST).date() == today:
                n += 1
        except ValueError:
            continue
    return n


def title_duplicate(title: str, base_slug: str, days: int = DEDUPE_DAYS) -> str | None:
    """題名がこの7日の記事（元の記事も含む。同じ題名の言い換えは出さない）とほぼ同じか"""
    import dedupe  # noqa: PLC0415

    grams = dedupe.bigrams(title)
    for entry in dedupe.load_recent(days).entries:
        if dedupe.jaccard(grams, entry["bigrams"]) >= dedupe.JACCARD_DUP:
            return str(entry["label"])
    return None


def ensure_base_link(record: dict, base: dict) -> None:
    """元の記事へのリンク（本文と関連）を必ず残す"""
    link = f"/articles/{base['slug']}"
    record["relatedSlugs"] = list(dict.fromkeys([base["slug"]] + list(record.get("relatedSlugs") or [])))
    if link not in str(record.get("body") or ""):
        record["body"] = (str(record.get("body") or "").rstrip()
                          + f"\n\n発表の全体は「[{base.get('title')}]({link})」で解説しています。\n")


def build(base: dict, angle: dict, fetched: list[dict]) -> tuple[str, dict | str]:
    """("ok", record) / ("reject", 理由) / ("error", 理由)。ふつうの記事と同じ型・同じ門（scripts/muse_articles.py の build_article と同じ流れ）"""
    import llm  # noqa: PLC0415
    import main as m  # noqa: PLC0415
    import muse_articles  # noqa: PLC0415
    import quality  # noqa: PLC0415
    import web_articles as w  # noqa: PLC0415

    first = fetched[0]
    item = {
        "id": deep_id(base["slug"], angle["key"]), "url": first["url"], "title": base["title"],
        "source_name": first.get("name") or first.get("title") or base.get("sourceName") or "",
        "source_slug": base.get("channelSlug") or muse_articles.host_slug(first["url"]),
        # 発表の時刻としては記録しない（元の記事の発表。この記事は今日の解説）
        "published_at": datetime.now(timezone.utc), "published_guessed": True,
        "image": base.get("thumbnail") or first.get("image") or "", "newsType": "explainer",
    }
    source_text = muse_articles.source_text_of(fetched, f"{base['title']} {angle['question']}")
    lane = base.get("genreSlug") if base.get("genreSlug") in CORE_GENRES else "lifestyle"
    voice_key, voice_text = m.pick_voice()
    genre, system, prompt, schema, kind, context, bundle = w.compose_with_facts(item, source_text, lane, [], voice_text, first["page"],
                                                                                    extra_sources=fetched[1:])
    prompt += DEEP_NOTE.format(base_title=base["title"], base_slug=base["slug"], **angle)
    problems: list[str] = []
    for attempt in (1, 2):
        try:
            draft, model_name = llm.generate_json(system, prompt + (quality.feedback_block(problems) if problems else ""), schema,
                                                  temperature=0.4, max_output_tokens=32768, tier=w.write_tier("bulk"), purpose="core")
        except Exception as error:  # noqa: BLE001
            return "error", f"LLM が使えませんでした（{str(error)[:100]}）"
        if not draft.get("is_relevant", True):
            return "reject", f"公式の資料にこの型の答えが足りない: {str(draft.get('skip_reason') or '')[:200]}"
        try:
            record = w.build_web_record(item, draft, first["page"], model_name, voice_key, bundle)
        except (KeyError, TypeError, ValueError) as error:
            problems = [f"形式が不正: {error}"]
            continue
        record["angleOf"] = base["slug"]
        record["deepDive"] = angle["key"]
        ensure_base_link(record, base)
        w.pre_gate(record, source_text, context)
        blocked = w.publish_blocked(record)
        if blocked and blocked not in w.indexnow.PUBLISH_RETRYABLE:
            return "reject", f"公開前の門: {w.indexnow.PUBLISH_FEEDBACK[blocked]}"
        if blocked:
            problems = [f"公開前の門: {w.indexnow.PUBLISH_FEEDBACK[blocked]}"]
            continue
        # 「サイソクの見方」の章・中身の下限（2026-11-12 オーナー。scripts/own_view.py）: 足りなければ1回だけ足し、下の事実確認を通す
        w.own_view.ensure(record, source_text, context, log=log)
        w.quality_bar.ensure(record, source_text, context, log=log)  # 記事の8つの基準（scripts/quality_bar.py）。1回だけ手直し
        verdict = quality.evaluate(record, source_text, kind, context, check_facts=True)
        if not verdict["ok"] and not verdict.get("soft") and quality.repairable(verdict):
            try:
                fixed, info = quality.surgical_fix(record, source_text, kind, verdict.get("problems") or [], context)
            except Exception as error:  # noqa: BLE001
                fixed, info = None, f"その場の手直しに失敗（{str(error)[:80]}）"
            if fixed is not None:
                record, verdict = fixed, info
        if verdict.get("soft"):
            polished, info = quality.polish(record, source_text, kind, context)
            if polished is not None:
                record, verdict = polished, info
            verdict = {**verdict, "ok": verdict.get("ok") or verdict.get("soft")}
        score = verdict.get("score") or 0
        log(f"   [deep] 試行{attempt}: {'合格' if verdict.get('ok') else '不合格'} score={score}（必要 {PASS_SCORE}）"
            f" {' | '.join((verdict.get('problems') or [])[:3])[:300]}")
        if verdict.get("ok") and score >= PASS_SCORE and (hold := w.own_view.hold_reason(record)):
            return "reject", hold
        if verdict.get("ok") and score >= PASS_SCORE and (hold := w.quality_bar.hold_reason(record, verdict=verdict)):
            log(f"   [bar] 出さない: {hold}")
            return "reject", hold
        if verdict.get("ok") and score >= PASS_SCORE:
            if dup := title_duplicate(record.get("title") or "", base["slug"]):
                return "reject", f"題名がこの7日の記事とほぼ同じ: {dup}"
            if why := sibling_problem(record.get("title") or "", angle["label"], base, all_articles()):
                return "reject", why
            record["qualityScore"] = score
            record["queryRole"] = angle["label"]
            # 門の手直しで消えても、元の記事との結びは残す
            record["angleOf"], record["deepDive"] = base["slug"], angle["key"]
            ensure_base_link(record, base)
            w.finalize_facts(record, source_text)
            w.stamp_times(record, item, datetime.now(timezone.utc))
            return "ok", record
        problems = list(verdict.get("problems") or [])
        if verdict.get("ok") and score < PASS_SCORE:
            problems = [f"公式ページとの事実確認の点数が {score} 点（{PASS_SCORE} 点以上が必要）"] + problems
    return "reject", "品質の門で不合格: " + " / ".join(problems[:4])[:600]


def register_today(state_web: dict, base: dict, angle: dict, record: dict) -> None:
    """今日の本数に数える（scripts/pacing.py の live_today は processed_web の slug で数える）"""
    import news_mix  # noqa: PLC0415

    entry = {"url": record.get("sourceUrl", ""), "at": datetime.now(timezone.utc).isoformat(), "slug": record["slug"],
             "writer": "deep_dive", "angleOf": base["slug"], "deepDive": angle["key"], "score": record.get("qualityScore")}
    try:
        entry["mix"] = news_mix.classify({"title": record.get("title", ""), "url": record.get("sourceUrl", ""),
                                          "channelSlug": record.get("channelSlug", "")})
    except Exception:  # noqa: BLE001
        pass
    state_web.setdefault("processed_web", {})[deep_id(base["slug"], angle["key"])] = entry


def fetch_texts(bases: list[tuple[dict, int]]) -> tuple[dict[str, list[dict]], dict[str, str]]:
    import muse_articles  # noqa: PLC0415

    fetched: dict[str, list[dict]] = {}
    texts: dict[str, str] = {}
    for base, views in bases:
        urls = source_urls(base)
        got = muse_articles.fetch_sources(urls, skip_unreadable_first=True) if urls else []
        fetched[base["slug"]] = got
        texts[base["slug"]] = "\n".join(s.get("full_text") or s["text"] for s in got)
        log(f"[deep] 元記事 {base['slug']}（{views}回）出典 {len(got)}/{len(urls)} 本 {len(texts[base['slug']])}字")
    return fetched, texts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--max", type=int, default=2, help="この回に公開する最大本数")
    parser.add_argument("--budget", type=int, default=1500, help="この回に使う秒数の目安")
    parser.add_argument("--daily-cap", type=int, default=int(os.environ.get("WEB_DAILY_CAP") or 0), help="今日の記事の本数の上限（段）")
    parser.add_argument("--dry-run", action="store_true", help="元記事・出典・作れる型を表示するだけ（LLM を使わない）")
    args = parser.parse_args()

    import main as m  # noqa: PLC0415
    import pacing  # noqa: PLC0415

    started = time.time()
    articles = all_articles()
    for slug, art in articles.items():
        art.setdefault("slug", slug)
    popular = load_json(POPULAR, {})
    bases = pick_bases(popular, articles)
    if not bases:
        log(f"[deep] 深掘りする元記事がありません（読まれた記事 {len(popular.get('items') or [])} 本・{MIN_VIEWS}回以上の暮らしとお金の記事なし）")
        return 0
    state = load_json(STATE, {})
    state.setdefault("attempts", {})
    fetched, texts = fetch_texts(bases)
    todo = plan(bases, articles, state, texts)
    log(f"[deep] 作れる型 {len(todo)} 本: " + " / ".join(f"{b['slug'][:28]}:{a['label']}" for b, a in todo))
    if args.dry_run:
        return 0
    left = DAILY_CAP - made_today(state)
    if left <= 0:
        log(f"[deep] 今日の深掘りは上限（{DAILY_CAP}本）に達しました")
        return 0
    web_state = m.load_state()
    web_state.setdefault("processed_web", {})
    published = 0
    for base, angle in todo:
        if published >= min(args.max, left) or time.time() - started > args.budget:
            break
        if args.daily_cap and pacing.live_today(web_state) >= args.daily_cap:
            log(f"[deep] 今日の記事の本数（{args.daily_cap}本）がいっぱいです")
            break
        got = fetched.get(base["slug"]) or []
        if not got:
            continue
        log(f"\n[deep] {base['slug']} → {angle['label']}")
        status, out = build(base, angle, got)
        row = {"status": "published" if status == "ok" else ("waiting" if status == "error" else "rejected"),
               "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "angle": angle["label"]}
        if status == "error":
            log(f"   [deep] {out}（次の回にもう一度）")
            break
        if status != "ok":
            row["reason"] = str(out)[:600]
            state["attempts"][attempt_key(base["slug"], angle["key"])] = row
            save_state(state)
            log(f"   [deep] → 見送り: {str(out)[:200]}")
            continue
        record = out
        target = m.write_article(record)
        register_today(web_state, base, angle, record)
        row.update({"slug": record["slug"], "title": record.get("title") or ""})
        state["attempts"][attempt_key(base["slug"], angle["key"])] = row
        m.save_state(web_state)
        save_state(state)
        published += 1
        log(f"   [deep] 公開へ: {target.relative_to(ROOT)}「{record.get('title')}」（score {record.get('qualityScore')}）")
    log(f"\n[deep] 公開 {published} 本（今日の深掘り {made_today(state)} / {DAILY_CAP} 本）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

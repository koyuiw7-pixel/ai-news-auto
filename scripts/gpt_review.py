#!/usr/bin/env python3
"""公開した記事を ChatGPT（オーナーのサブスクリプション・gpt-6.1-terra）で見直す、Mac の仕事（2026-11-08 オーナー承認・台帳 A65）。

Haiku などで書いた記事を、公式の資料と並べて ChatGPT に見直させ、Sonnet に近い質にそろえる。直してよいのは:
  - 資料と食い違う事実の誤り（決まりは「うそをつかない」だけ）
  - 読みやすさと読者が先の組み立て（リードで読者に何が変わるかを言う・拾い読みできる見出し・役立つときだけ短い確認リストや表）
  - 題名をもっと目を引くものに（ただし厳密に事実のまま。「｜」は使わない）
直してはいけないもの: 資料に無い事実を足す・slug や URL・画像・広告（affiliates）・title/seoTitle/lede/description/body 以外の欄。

流れ（launchd で30分ごと。~/Library/LaunchAgents/com.komuro.saisoku-gpt-review.plist。ログは ~/.saisoku-gptreview/review.log）:
  1. 専用の作業用の写し（~/.saisoku-gptreview/repo。ASCII のパス）を origin/main にそろえる
  2. 直近に公開した記事から、まだ見直していないものを1回に最大 N 本（既定6）選ぶ。Muse の記事（writer: muse）・
     手で書いた記事（refreshMode: editorial）・編集部の確認済み（review.status: ok）・元の資料の URL が無い記事は飛ばす
  3. 元記事（sourceUrl）と記事が出典にした資料（factSources・sources）をふつうの HTTP GET で読む。読めなければその記事は飛ばす
  4. ChatGPT に記事と資料を渡し、直す欄だけの JSON を返させる。手元で確かめる（欄・数字・「｜」・長さ・URL・画像・決まった見出し）
  5. 通ったものだけ記事 JSON に書き、`gptReview`（reviewedBy: gpt-6.1-terra）を付けて main にコミット・push（rebase。force はしない）
  ChatGPT がエラーや利用上限の知らせを返したら、その回はそこで止める（ログに残す）。見直した記録は ~/.saisoku-gptreview/state.json。

  python3 scripts/gpt_review.py                 # 1回動かす
  python3 scripts/gpt_review.py --max 2         # 2本だけ
  python3 scripts/gpt_review.py --no-push       # 書くがコミット・push しない（試すとき）
  python3 scripts/gpt_review.py --install       # 作業用の写しを作り、launchd に登録して読み込む（最初の1回）
"""
from __future__ import annotations

import argparse
import copy
import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOME = Path.home()
BASE = Path(os.environ.get("GPT_REVIEW_HOME") or HOME / ".saisoku-gptreview")
CLONE = BASE / "repo"
STATE = BASE / "state.json"
LOCK = BASE / "run.lock"
REMOTE = "https://github.com/koyuiw7-pixel/ai-news-auto.git"
SITE = "https://ai-tech-express.jp"
LABEL = "com.komuro.saisoku-gpt-review"
PLIST = HOME / "Library" / "LaunchAgents" / f"{LABEL}.plist"
INTERVAL_SEC = 30 * 60
CODEX = os.environ.get("GPT_REVIEW_CODEX") or "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex"
MODEL = os.environ.get("GPT_REVIEW_MODEL") or "gpt-6.1-terra"
MAX_PER_RUN = int(os.environ.get("GPT_REVIEW_MAX") or 6)
LOOKBACK_HOURS = 72          # 直近この時間に公開した記事だけ
MIN_AGE_MIN = 15             # 公開の直後（画像・SNS の後処理が続く間）は触らない
CALL_GAP_SEC = 20            # ChatGPT の呼び出しの間をあける（礼儀として）
CALL_TIMEOUT_SEC = 900
MAX_SOURCES = 4
SOURCE_CAP = 15000           # 資料1本あたりの文字数
MAX_ATTEMPTS = 2             # 門に落ちた記事は2回まで試す
JST = timezone(timedelta(hours=9))
SPARSE = ["content/articles", "scripts", "state"]
EDITABLE = ("title", "seoTitle", "lede", "description", "body")
CO_AUTHOR = "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"}
# ChatGPT の利用上限・エラーの知らせ（出たらその回は止める）
LIMIT_RE = re.compile(r"usage limit|rate limit|too many requests|\b429\b|quota|hit your limit|limit reached|try again (?:in|later)|"
                      r"upgrade to pro|insufficient|unauthori[sz]ed|not logged in|login required|stream error|server error|\b5\d\d\b",
                      re.I)
STRONG_MODEL_RE = re.compile(r"sonnet|opus", re.I)
PRICE_SLOT_RE =re.compile(r"^###\s.+のプランと料金（公式の料金と円の目安）\s*$", re.M)
URL_RE = re.compile(r"https?://[^\s)\]>」』\"']+")
MD_TARGET_RE = re.compile(r"\]\(([^)\s]+)[^)]*\)")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")


def log(message: str) -> None:
    print(f"{datetime.now(JST):%m-%d %H:%M:%S} {message}", flush=True)


# --------------------------------------------------------------------------- #
# 作業用の写し（オーナーの作業用の checkout は使わない）
# --------------------------------------------------------------------------- #

def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(CLONE), *args], capture_output=True, text=True, env=GIT_ENV, check=check, timeout=300)


def ensure_clone() -> None:
    if (CLONE / ".git").exists():
        git("fetch", "--quiet", "origin", "main")
        git("checkout", "--quiet", "main", check=False)
        git("reset", "--quiet", "--hard", "origin/main")  # 専用の写し（オーナーの作業用の checkout ではない）
        if set(git("sparse-checkout", "list").stdout.split()) != set(SPARSE):
            git("sparse-checkout", "set", *SPARSE)
        return
    BASE.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "--quiet", "--filter=blob:none", "--sparse", REMOTE, str(CLONE)], check=True, env=GIT_ENV, timeout=900)
    git("sparse-checkout", "set", *SPARSE)
    git("config", "user.name", "koyuiw7-pixel")
    git("config", "user.email", "koyuiw7@gmail.com")


def articles_dir(root: Path | None = None) -> Path:
    return (root or CLONE) / "content" / "articles"


# --------------------------------------------------------------------------- #
# 記録
# --------------------------------------------------------------------------- #

def load_state() -> dict:
    try:
        data = json.loads(STATE.read_text("utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    items = state.get("items") or {}
    if len(items) > 3000:  # 古い記録から捨てる
        keep = sorted(items.items(), key=lambda kv: kv[1].get("at") or "")[-2000:]
        state["items"] = dict(keep)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", "utf-8")
    tmp.replace(STATE)


# --------------------------------------------------------------------------- #
# 選ぶ
# --------------------------------------------------------------------------- #

def _when(article: dict) -> datetime | None:
    for key in ("generatedAt", "detectedAt"):
        try:
            return datetime.fromisoformat(str(article.get(key)).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
    return None


def skip_reason(article: dict) -> str:
    """見直しの対象外の理由（空なら対象）"""
    if article.get("writer") == "muse":
        return "Muse の記事"
    if article.get("refreshMode") == "editorial":
        return "手で書いた記事（editorial）"
    if (article.get("review") or {}).get("status") == "ok":
        return "編集部の確認済み"
    if article.get("gptReview"):
        return "見直し済み"
    if not str(article.get("sourceUrl") or "").startswith("http"):
        return "元の資料の URL が無い"
    if article.get("type") or article.get("roundupKey"):
        return "まとめのページ"
    return ""


def candidates(root: Path, state: dict, now: datetime, limit: int) -> list[tuple[Path, dict]]:
    items = state.get("items") or {}
    rows = []
    for path in articles_dir(root).glob("*.json"):
        try:
            article = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        when = _when(article)
        if not when or not (now - timedelta(hours=LOOKBACK_HOURS) <= when <= now - timedelta(minutes=MIN_AGE_MIN)):
            continue
        if skip_reason(article):
            continue
        row = items.get(article.get("slug") or path.stem) or {}
        if row.get("status") in ("reviewed", "unchanged", "skipped") or int(row.get("attempts") or 0) >= MAX_ATTEMPTS:
            continue
        rows.append((when, path, article))
    # Haiku・Gemini など軽いモデルの記事を先に（Sonnet・Opus の記事は後）。同じ組では新しい順
    rows.sort(key=lambda r: r[0], reverse=True)
    rows.sort(key=lambda r: bool(STRONG_MODEL_RE.search(str(r[2].get("model") or ""))))
    return [(p, a) for _, p, a in rows[:limit]]


def source_urls(article: dict) -> list[str]:
    urls = [str(article.get("sourceUrl") or "")]
    for key in ("factSources", "sources"):
        for row in article.get(key) or []:
            if isinstance(row, dict):
                urls.append(str(row.get("url") or ""))
    out = []
    for url in urls:
        if url.startswith("http") and url not in out:
            out.append(url)
    return out[:MAX_SOURCES]


# --------------------------------------------------------------------------- #
# 資料を読む（ふつうの HTTP GET）
# --------------------------------------------------------------------------- #

def _scripts_path() -> None:
    for p in (Path(__file__).resolve().parent, CLONE / "scripts"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))


def fetch_source(url: str) -> str:
    """1本読む。HTML は本文の文字、PDF は pdftotext / pypdf。読めなければ例外"""
    _scripts_path()
    import feeds  # noqa: PLC0415

    data, _ = feeds.fetch(url, timeout=30, accept="text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8")
    if data[:5] == b"%PDF-":
        import source_links  # noqa: PLC0415

        text = source_links.pdf_text(data)
    else:
        parser = feeds._Extractor()
        try:
            parser.feed(feeds._decode(data))
            parser.close()
        except Exception:  # noqa: BLE001
            pass
        options = [feeds._collapse(parser.buffers[k]) for k in ("article", "main", "body")]
        text = next((c for c in options if len(c) >= 300), max(options, key=len))
    if len(re.sub(r"\s+", "", text or "")) < 200:
        raise ValueError("文字がほとんど取れない")
    return text[:SOURCE_CAP]


def fetch_sources(urls: list[str], fetcher=fetch_source) -> tuple[list[dict], str]:
    """[{url, text}]、失敗の理由（空なら全部読めた）。1本でも読めなければ記事ごと飛ばす（オーナーの指示）"""
    out = []
    for url in urls:
        try:
            out.append({"url": url, "text": fetcher(url)})
        except Exception as error:  # noqa: BLE001
            return out, f"資料を読めない（{url}: {str(error)[:80]}）"
    return out, ""


# --------------------------------------------------------------------------- #
# ChatGPT
# --------------------------------------------------------------------------- #

PROMPT = """あなたはニュースサイト「サイソクニュース」（https://ai-tech-express.jp）の校閲・編集の担当です。
読者は20〜50代の働く人。忙しく、「自分の暮らしやお金に何が変わるか」「何をすればいいか」をすぐ知りたい人です。
下の【記事】を、【資料】（記事の元の公式発表と、記事が出典にした資料）とだけ照らし合わせて見直し、直した欄だけを JSON で返してください。
コマンドは実行せず、ネットも見ず、ここにある文章だけで判断してください。

## 直してよいこと
1. 事実の誤り: 資料と食い違う数字・日付・曜日・名前・対象・条件を、資料のとおりに直す。いちばん大事な決まりは「うそをつかない」。
2. 読みやすさ・読者が先の組み立て:
   - リード（lede）の最初の文で、読者にとって何が変わるのか（いつから・誰が・いくら・何をすればいいか）を言う。
   - 見出し（## / ###）は、拾い読みしても中身が分かる具体的な言葉にする（決まり文句の見出しにしない）。
   - 役に立つときだけ、短い確認リスト（- の箇条書き）や表（| の Markdown の表）を足してよい。中身は資料にあることだけ。
   - 1文を短くし、言い回しを自然な大人の日本語にする。幼い書き方・あおり・感嘆符・決まり文句の前置きはしない。
3. 題名（title）をもっと目を引くものに: 読者が得る答え（何が・いくら・いつから・誰が対象）を先に出し、自分ごとだと一目で分かる言葉にする。
   元の題名より弱く・長く・回りくどくしない（「試算」「〜とみられる」などの正確さのための補足は、題名ではなくリードや本文で書けばよい）。
   ただし厳密に事実のまま、誇張しない（「史上初」「激変」「必見」などのあおりは使わない）。元の題名が十分に良ければ変えない。
   全角の縦棒「｜」と半角の「|」は題名に使わない（区切りは全角の空白）。長さは28〜48字くらい。seoTitle は検索で探される言葉を入れて32字以内くらい。
   description は検索結果に出る要約（80〜140字）。

## してはいけないこと
- 資料に無い事実・数字・日付・見通し・理由を足すこと（推測も一般論の数字もだめ）。記事の数字は、資料か元の記事にある数字だけ。
- 資料で確かめられない記事の文を、確かめずに書き換えて意味を変えること（確かめられない文は、そのままにするか削る）。
- URL・リンク先・画像（![...](...)）を変える・消す・足すこと。リンクの文字は変えてよいが、リンク先はそのまま全部残す。
- 次の見出しを変える・消すこと: {protected}
- 本文の長さを大きく変えること（元の本文の 80〜130% に収める）。「# 」（1つの #）の見出しは使わない。
- 投資の売買のすすめ、自分で試したような書き方（「筆者が試した」など）、報道機関の記事を出典にする書き方。

## 返す形（JSON だけ。前後に文章やコードの囲みを付けない）
{{
  "changed": true または false,
  "title": "新しい題名（変えないなら null）",
  "seoTitle": "新しい SEO 題名（変えないなら null。元に無い記事なら null）",
  "lede": "新しいリード（変えないなら null）",
  "description": "新しい要約（変えないなら null）",
  "body": "新しい本文の Markdown 全体（変えないなら null）",
  "fixes": [{{"before": "直した事実の元の書き方", "after": "直した後", "evidence": "資料のどこに書いてあるか（短い引用）"}}],
  "notes": "何をどう直したかの短いまとめ（日本語・1〜3文）"
}}
直すところが無ければ "changed": false で、ほかは null にしてください。

【記事】
{article}

【資料】
{sources}
"""


def protected_headings(article: dict) -> list[str]:
    body = article.get("body") or ""
    out = [m.group(0).strip() for m in PRICE_SLOT_RE.finditer(body)]
    titles = (article.get("sectionTitles") or {}).get("body") or {}
    for key in titles:
        for m in re.finditer(rf"^#{{2,3}}\s*{re.escape(str(key))}\s*$", body, re.M):
            out.append(m.group(0).strip())
    return list(dict.fromkeys(out))


def build_prompt(article: dict, sources: list[dict]) -> str:
    view = {k: article[k] for k in EDITABLE if k in article}
    protected = protected_headings(article)
    src = "\n\n".join(f"--- 資料{i + 1}: {s['url']} ---\n{s['text']}" for i, s in enumerate(sources))
    return PROMPT.format(article=json.dumps(view, ensure_ascii=False, indent=2), sources=src,
                         protected="、".join(f"「{h}」" for h in protected) or "（なし）")


class ChatGPTStop(Exception):
    """ChatGPT がエラー・利用上限を返した（この回はここで止める）"""


def call_chatgpt(prompt: str, runner=subprocess.run) -> str:
    with tempfile.TemporaryDirectory(prefix="gptreview-") as work:
        out = Path(work) / "last.txt"
        cmd = [CODEX, "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only", "-m", MODEL, "-C", work, "-o", str(out), "-"]
        try:
            proc = runner(cmd, input=prompt, capture_output=True, text=True, timeout=CALL_TIMEOUT_SEC, cwd=work,
                          env={**GIT_ENV, "NO_COLOR": "1"})
        except subprocess.TimeoutExpired as error:
            raise ChatGPTStop(f"ChatGPT が {CALL_TIMEOUT_SEC} 秒で返さない") from error
        except OSError as error:
            raise ChatGPTStop(f"ChatGPT を呼べない（{error}）") from error
        answer = out.read_text("utf-8").strip() if out.exists() else ""
        tail = ((proc.stderr or "") + "\n" + (proc.stdout or ""))[-1500:]
        if proc.returncode != 0:
            raise ChatGPTStop(f"ChatGPT がエラー（終了コード {proc.returncode}）: {tail.strip()[-400:]}")
        if not answer:
            raise ChatGPTStop(f"ChatGPT の答えが空: {tail.strip()[-400:]}")
        if not answer.lstrip().startswith(("{", "```")) and LIMIT_RE.search(answer):
            raise ChatGPTStop(f"ChatGPT の利用上限・エラーの知らせ: {answer[:300]}")
        return answer


def parse_answer(answer: str) -> dict:
    text = answer.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("JSON が無い")
    data = json.loads(text[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("JSON の形が違う")
    return data


# --------------------------------------------------------------------------- #
# 手元で確かめる
# --------------------------------------------------------------------------- #

def fix_bars(field: str, value: str) -> str:
    """「｜」は落とさずプログラムで置き換える（台帳 A60）。題名は半角の | も区切りとして置き換える"""
    if field in ("title", "seoTitle"):
        return re.sub(r"\s*[｜|]\s*", "　", value).strip()
    return value.replace("｜", "　")


def _strip_urls(text: str) -> str:
    text = MD_TARGET_RE.sub("]", text or "")
    return URL_RE.sub(" ", text)


def numbers(text: str) -> set[str]:
    """文の数字（リンク先・URL・番号付きリストの番号は除く）。全角は半角に、桁区切りのカンマは外す"""
    text = unicodedata.normalize("NFKC", _strip_urls(text))
    text = re.sub(r"^\s*\d+[.)]\s", "", text, flags=re.M)
    out = set()
    for raw in NUM_RE.findall(text):
        value = raw.replace(",", "")
        out.add(value)
        if "." in value:
            out.add(value.rstrip("0").rstrip("."))
    return out


def urls(text: str) -> set[str]:
    found = set(MD_TARGET_RE.findall(text or "")) | set(URL_RE.findall(MD_TARGET_RE.sub("]", text or "")))
    return {u.rstrip(".,、。") for u in found if u.startswith("http")}


def _plain_len(text: str) -> int:
    return len(re.sub(r"\s+", "", re.sub(r"[#*|`>\-]", "", _strip_urls(text or ""))))


def _all_old_text(article: dict) -> str:
    return json.dumps({k: v for k, v in article.items() if k not in ("affiliates",)}, ensure_ascii=False)


def validate(article: dict, data: dict, sources: list[dict]) -> tuple[dict, list[str]]:
    """(直す欄 {field: 新しい値}, 問題の一覧)。問題があれば使わない"""
    problems: list[str] = []
    unknown = [k for k, v in data.items() if v is not None and k not in (*EDITABLE, "changed", "fixes", "notes")]
    if unknown:
        problems.append(f"直してはいけない欄を返した（{', '.join(unknown)}）")
    patch: dict = {}
    for field in EDITABLE:
        value = data.get(field)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            problems.append(f"{field} が空か文字でない")
            continue
        if field == "seoTitle" and "seoTitle" not in article:
            continue  # 元に無い欄は足さない（形を変えない）
        value = fix_bars(field, value.strip())
        if value != (article.get(field) or "").strip():
            patch[field] = value
    allowed = numbers(_all_old_text(article)) | numbers("\n".join(s["text"] for s in sources))
    for field, value in patch.items():
        if "｜" in value:
            problems.append(f"{field} に「｜」が残っている")
        new_nums = sorted(n for n in numbers(value) - allowed)
        if new_nums:
            problems.append(f"{field} に、元の記事にも資料にも無い数字がある（{'、'.join(new_nums[:6])}）")
    limits = {"title": (12, 60), "seoTitle": (8, 45), "lede": (40, 400), "description": (40, 220)}
    for field, (low, high) in limits.items():
        if field in patch and not low <= len(patch[field]) <= high:
            problems.append(f"{field} の長さが {len(patch[field])} 字（{low}〜{high} 字）")
    if "body" in patch:
        old, new = article.get("body") or "", patch["body"]
        ratio = _plain_len(new) / max(1, _plain_len(old))
        if not 0.75 <= ratio <= 1.4:
            problems.append(f"本文の長さが元の {ratio:.0%}（75〜140%）")
        lost = urls(old) - urls(new)
        added = urls(new) - urls(old)
        if lost:
            problems.append(f"本文のリンク・URL が消えた（{', '.join(sorted(lost)[:3])}）")
        if added:
            problems.append(f"本文にリンク・URL が足された（{', '.join(sorted(added)[:3])}）")
        if sorted(IMAGE_RE.findall(old)) != sorted(IMAGE_RE.findall(new)):
            problems.append("本文の画像が変わった")
        for heading in protected_headings(article):
            if heading not in new:
                problems.append(f"決まった見出しが消えた（{heading}）")
        if re.search(r"^#\s", new, re.M) and not re.search(r"^#\s", old, re.M):
            problems.append("本文に「# 」の見出しが入った")
        if re.search(r"^\s*(<<<|>>>|```)", new, re.M) and not re.search(r"^\s*(<<<|>>>|```)", old, re.M):
            problems.append("本文に指示文の囲み・コードの囲みが混ざった")
    for field in ("title", "seoTitle"):
        if field in patch and re.search(r"[!！]", patch[field]):
            patch[field] = re.sub(r"[!！]+", "", patch[field]).strip()
    if patch and not problems:
        problems += shared_gate(article, {**article, **patch})
    return patch, problems


def shared_gate(before: dict, after: dict) -> list[str]:
    """記事を書くすべての段と同じ共通の門（quality.added_problems。書き換えで新しく増えた不合格だけ。
    投資助言・自分で試した書き方・報道を出典にする・私人の実名・決まりの文体）。門を動かせなければ書かない"""
    _scripts_path()
    try:
        import quality  # noqa: PLC0415

        return [f"共通の門: {p}" for p in quality.added_problems(before, after)]
    except Exception as error:  # noqa: BLE001
        return [f"共通の門を動かせない（{type(error).__name__}: {str(error)[:120]}）"]


def apply_patch(article: dict, patch: dict, data: dict, now: datetime) -> dict:
    new = copy.deepcopy(article)
    for field, value in patch.items():
        new[field] = value
    new["gptReview"] = {
        "reviewedBy": MODEL,
        "reviewedAt": now.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "changed": sorted(patch),
        "before": {k: article.get(k) for k in ("title", "lede") if k in patch},
        "fixes": [f for f in (data.get("fixes") or []) if isinstance(f, dict)][:8],
        "notes": str(data.get("notes") or "")[:400],
    }
    if note := recheck_search_title(new):
        new["gptReview"]["searchTitle"] = note
    return new


def recheck_search_title(article: dict) -> str | None:
    """書き直しで本文・リードから言葉が消えると、前に付けた searchTitle が記事に無い言葉の題名になる（台帳 A29）。
    main.write_article と同じ search_title.revalidate で確かめ直し、合わなくなった値は外す（<title> は記事の題名に戻る）。
    確かめられないときも外す（根拠のない題名を残さない）"""
    if "searchTitle" not in article:
        return None
    _scripts_path()
    try:
        import search_title  # noqa: PLC0415

        return search_title.revalidate(article)
    except Exception as error:  # noqa: BLE001
        value = article.pop("searchTitle", None)
        return f"検索の題名を確かめられないので外した（{value} / {type(error).__name__}）"


def dump(article: dict) -> str:
    return json.dumps(article, ensure_ascii=False, indent=2) + "\n"


# --------------------------------------------------------------------------- #
# コミット・push（rebase。force はしない）
# --------------------------------------------------------------------------- #

def write_patches(results: list[dict]) -> list[dict]:
    """いまの main の記事に書く。見直した時から元の欄が変わっていた記事は書かない（他の仕事の手直しを上書きしない）"""
    written = []
    for r in results:
        path = articles_dir() / f"{r['slug']}.json"
        try:
            current = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        if any(current.get(k) != r["old"].get(k) for k in EDITABLE) or current.get("gptReview"):
            log(f"見直しの間に記事が変わったので書かない: {r['slug']}")
            continue
        path.write_text(dump(apply_patch(current, r["patch"], r["data"], r["now"])), "utf-8")
        written.append(r)
    return written


def commit_and_push(results: list[dict], push: bool = True) -> str:
    for attempt in range(3):
        written = write_patches(results)
        if not written:
            return ""
        git("add", *[f"content/articles/{r['slug']}.json" for r in written])
        slugs = "\n".join(f"- {r['slug']}: {', '.join(sorted(r['patch']))}" for r in written)
        message = (f"chore(content): ChatGPT（{MODEL}）で記事を見直し (+{len(written)}本)\n\n"
                   f"公式の資料と照らして、事実・読みやすさ・題名を見直した（台帳 A65）。\n{slugs}\n\n{CO_AUTHOR}")
        git("commit", "--quiet", "-m", message)
        sha = git("rev-parse", "HEAD").stdout.strip()
        if not push:
            return sha
        pulled = git("pull", "--quiet", "--rebase", "origin", "main", check=False)
        if pulled.returncode != 0:
            git("rebase", "--abort", check=False)
            log(f"rebase で食い違い（{attempt + 1}回目）。最新の main に書き直します")
            git("fetch", "--quiet", "origin", "main")
            git("reset", "--quiet", "--hard", "origin/main")
            continue
        pushed = git("push", "--quiet", "origin", "HEAD:main", check=False)
        if pushed.returncode == 0:
            return git("rev-parse", "HEAD").stdout.strip()
        log(f"push できない（{attempt + 1}回目）: {pushed.stderr.strip()[:200]}")
        time.sleep(10)
        git("fetch", "--quiet", "origin", "main")
        git("reset", "--quiet", "--hard", "origin/main")
    return ""


# --------------------------------------------------------------------------- #
# 1回分
# --------------------------------------------------------------------------- #

def review_one(path: Path, article: dict, now: datetime, fetcher=fetch_source, caller=call_chatgpt) -> dict:
    """{status: reviewed|unchanged|skipped|failed, ...}。ChatGPTStop はそのまま上に投げる"""
    slug = article.get("slug") or path.stem
    sources, reason = fetch_sources(source_urls(article), fetcher)
    if reason:
        return {"slug": slug, "status": "skipped", "reason": reason}
    answer = caller(build_prompt(article, sources))
    try:
        data = parse_answer(answer)
    except (ValueError, json.JSONDecodeError) as error:
        return {"slug": slug, "status": "failed", "reason": f"答えの JSON を読めない（{error}）"}
    if data.get("changed") is False:
        return {"slug": slug, "status": "unchanged", "reason": str(data.get("notes") or "")[:200]}
    patch, problems = validate(article, data, sources)
    if problems:
        return {"slug": slug, "status": "failed", "reason": " / ".join(problems)[:600]}
    if not patch:
        return {"slug": slug, "status": "unchanged", "reason": "直す欄が無かった"}
    return {"slug": slug, "status": "reviewed", "patch": patch, "data": data, "now": now,
            "old": {k: article.get(k) for k in EDITABLE}, "notes": str(data.get("notes") or "")[:200]}


def run(limit: int, push: bool = True, slugs: list[str] | None = None) -> int:
    BASE.mkdir(parents=True, exist_ok=True)
    with open(LOCK, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("前の回がまだ動いているので、この回は休みます")
            return 0
        ensure_clone()
        state = load_state()
        state.setdefault("items", {})
        now = datetime.now(timezone.utc)
        if slugs:
            picked = []
            for s in slugs:
                p = articles_dir() / f"{s}.json"
                a = json.loads(p.read_text("utf-8"))
                if why := skip_reason(a):
                    log(f"対象外: {s}（{why}）")
                    continue
                picked.append((p, a))
        else:
            picked = candidates(CLONE, state, now, limit)
        if not picked:
            log("見直す記事はありません")
            return 0
        log(f"見直す記事: {len(picked)}本（{MODEL}）")
        results: list[dict] = []
        stopped = ""
        for i, (path, article) in enumerate(picked):
            slug = article.get("slug") or path.stem
            if i:
                time.sleep(CALL_GAP_SEC)
            started = time.time()
            try:
                result = review_one(path, article, now)
            except ChatGPTStop as error:
                stopped = str(error)
                log(f"ChatGPT を止めます（{slug}）: {stopped}")
                break
            row = state["items"].get(slug) or {}
            attempts = int(row.get("attempts") or 0) + (1 if result["status"] == "failed" else 0)
            state["items"][slug] = {"status": result["status"], "at": now.isoformat(timespec="seconds"),
                                    "attempts": attempts, "reason": result.get("reason") or result.get("notes") or "", "model": MODEL}
            log(f"{result['status']}: {slug}（{time.time() - started:.0f}秒）{result.get('reason') or ''}"
                + (f" 直した欄: {', '.join(sorted(result['patch']))}" if result.get("patch") else ""))
            if result["status"] == "reviewed":
                results.append(result)
        sha = ""
        if results:
            sha = commit_and_push(results, push=push)
            if sha:
                log(f"コミット {sha[:10]} を main に{'push しました' if push else '作りました（push しない）'}: "
                    + ", ".join(f"{SITE}/articles/{r['slug']}" for r in results))
            else:
                log("コミット・push できませんでした（次の回にもう一度）")
                for r in results:
                    state["items"][r["slug"]]["status"] = "retry"
        if stopped:
            state["lastStop"] = {"at": now.isoformat(timespec="seconds"), "reason": stopped[:500]}
        save_state(state)
        return 1 if stopped else 0


# --------------------------------------------------------------------------- #
# launchd
# --------------------------------------------------------------------------- #

def plist_text() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{LABEL}</string>
  <!-- サイソク: 公開した記事を ChatGPT（{MODEL}）で見直す（台帳 A65）。パスは ASCII（launchd は非ASCIIのパスを扱えない） -->
  <key>ProgramArguments</key>
  <array>
    <string>/opt/homebrew/bin/python3</string>
    <string>{CLONE}/scripts/gpt_review.py</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>StartInterval</key>
  <integer>{INTERVAL_SEC}</integer>
  <key>RunAtLoad</key>
  <false/>
  <key>StandardOutPath</key>
  <string>{BASE}/review.log</string>
  <key>StandardErrorPath</key>
  <string>{BASE}/review.log</string>
</dict>
</plist>
"""


def install() -> None:
    ensure_clone()
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    PLIST.write_text(plist_text(), "utf-8")
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(PLIST)], check=True)
    log(f"launchd に登録しました: {PLIST}（{INTERVAL_SEC // 60}分ごと）")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--max", type=int, default=MAX_PER_RUN, help="1回に見直す本数")
    parser.add_argument("--no-push", action="store_true")
    parser.add_argument("--slug", action="append", help="この記事だけ（何度でも）")
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    if args.install:
        install()
        return 0
    return run(args.max, push=not args.no_push, slugs=args.slug)


if __name__ == "__main__":
    sys.exit(main())

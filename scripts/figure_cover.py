#!/usr/bin/env python3
"""写真も AI のイメージも無い記事の「図の表紙」（2026-11-10 オーナー「画像がない記事が結構多いから対策しっかりね」。台帳 I9）。

写真ではなく、サイソクが作った図だと一目で分かる明るい図版（1200×630）。載せるのは記事の題名・要約にある言葉と数字だけ
（数字を作らない・言い換えない）。中身:
  - 左: 話題の絵記号（電気・炎・お金・子育て・書類・盾・スマホ・電車・家・病院・グラフ）を白い丸に
  - 右: ジャンルの札 → 題名の数字の前の言葉 → 大きな数字（題名の文字のまま）→ 数字の後の言葉 → 題名の後半（全角の空白の後）
  - 右下に「図：サイソクニュース作成」
文字は枠に収まるまで小さくし、収まらない言葉は出さない（途中で切らない・「…」にしない）。「｜」は使わない。
scripts/images.py が、公式の写真・AI のイメージ・フリー素材のどれも無いときに使う（IMAGE_FIGURE_COVER=1 のときだけ）。
記事には imageCredit {kind: "figure", imageKind: "cover"} を書く。サイトは写真ではなく図として扱い（切り抜かない・「図：サイソクニュース作成」）、
Muse・Workers AI の写真が後から届けば、そちらを表紙・一覧に出す。SNS には出さない（台帳 S49: 文字の画像では投稿しない）。

  python3 scripts/figure_cover.py --slug electricity-bill-nov-2026-subsidy-ends --out out/fig.jpg   # 1本を描いて保存（確認用）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "assets" / "fonts"
BLACK = FONT_DIR / "NotoSansJP-Black.otf"
BOLD = FONT_DIR / "NotoSansJP-Bold.otf"
W, H = 1200, 630

GENRE_COLORS = {
    "lifestyle": (214, 84, 16),
    "public": (25, 113, 194),
    "business": (11, 114, 133),
    "investment": (43, 138, 62),
    "ai": (95, 61, 196),
    "tech-gadget": (73, 80, 87),
    "science": (8, 127, 91),
}
DEFAULT_COLOR = (25, 113, 194)
INK = (33, 37, 41)
SUB_INK = (73, 80, 87)

# 話題 → 絵記号（上から順に当たったもの）
ICON_RULES: list[tuple[str, str]] = [
    (r"電気|電力|kWh|節電", "bolt"),
    (r"ガス|灯油|ストーブ|暖房|ガソリン|燃料", "flame"),
    (r"児童手当|子育て|子ども|こども|出産|育児|保育|妊娠|教育|学校|奨学", "family"),
    (r"漏えい|流出|個人情報|不正|詐欺|セキュリティ|サイバー", "shield"),
    (r"ドコモ|(?<![A-Za-z])au(?![A-Za-z])|ソフトバンク|楽天モバイル|携帯|スマホ|通信|アプリ", "phone"),
    (r"新幹線|鉄道|列車|運休|電車|JR", "train"),
    (r"住宅|家賃|マンション|住まい|空き家|相続", "house"),
    (r"病院|医療|薬|保険証|介護|健康", "medical"),
    (r"年金|給付|手当|ボーナス|賞与|給与|給料|手取り|賃金|預金|金利|国債|円|税|控除|還付|保険料|ポイント", "yen"),
    (r"申請|手続き|届|書類|期限|マイナンバー", "document"),
]

NUMBER_RE = re.compile(
    # 「月」「年」は「月10万円」の頭の言葉としてだけ付ける（「毎月5円」の「月」・「前年92万」の「年」を数字に入れない）
    r"(?:約|最大|最低|毎月|毎年|(?<![一-龥々])月|(?<![一-龥々])年|1人|一人)?"
    r"([0-9０-９][0-9０-９,，.．]*)\s*"
    r"(万円|億円|兆円|万人|万件|万|億|兆)?"
    r"(円|%|％|ポイント|倍|人|件|社|本|台|歳|日|時間|か月分|カ月分|ヶ月分|か月|カ月|ヶ月|年分|割|kWh|万)?"
)
# 「92万」「3億」「2兆」の後ろに続く下の位（「92万6,500円」「3億5,000万件」「2兆1,911億円」を1つの数字にする。途中で切ると別の数に読める）
LOWER_PLACE_RE = re.compile(
    r"[0-9０-９][0-9０-９,，.．]*\s*"
    r"(?:万円|億円|兆円|万人|万件|万|億)?"
    r"(?:円|%|％|ポイント|倍|人|件|社|本|台|歳|か月分|カ月分|ヶ月分|か月|カ月|ヶ月|割|kWh)?"
)
# 主役にしない数字の単位（条件の「1時間」より、その後の「約1円」を主役にする。ほかに数字が無ければ使う）
WEAK_UNITS = ("時間",)
# 数字の前後で切る言葉（題名の文の区切り）
CLAUSE_SPLIT = re.compile(r"[　、。！？!?]|\s{2,}")
TRAIL_PARTICLE = re.compile(r"(は|が|を|に|の|で|と|も|へ)$")
LEAD_PARTICLE = re.compile(r"^(は|が|を|に|の|で|と|も|へ)")


def color_of(article: dict) -> tuple[int, int, int]:
    return GENRE_COLORS.get(str(article.get("genreSlug") or ""), DEFAULT_COLOR)


def icon_of(article: dict) -> str:
    text = " ".join([str(article.get("title") or ""), " ".join(map(str, article.get("tags") or []))])
    for pattern, name in ICON_RULES:
        if re.search(pattern, text):
            return name
    return "chart"


def split_title(title: str) -> tuple[str, str]:
    """（前半, 後半）。全角の空白で分かれた題名の後半は補足の行にする"""
    title = re.sub(r"[｜|]", " ", str(title or "")).strip()
    head, _, tail = title.partition("　")
    return head.strip(), tail.strip()


def key_fact(title: str) -> dict:
    """題名の前半から、図の主役の数字と前後の言葉を抜き出す（題名の文字のまま。数字は作らない）。
    戻り値: {"label": 前の言葉, "number": 数字＋単位, "after": 後の言葉, "sub": 題名の後半}。数字が無ければ number は ""。
    「11月」「2026年」のような日付は主役にしない（単位の無い数字・月・年も）"""
    head, tail = split_title(title)
    best = None
    weak = None
    for m in NUMBER_RE.finditer(head):
        digits, scale, unit = m.group(1), m.group(2) or "", m.group(3) or ""
        if not (scale or unit):
            continue
        rest = head[m.end():m.end() + 1]
        if not unit and scale in ("万", "億", "兆") and rest in ("月", "年"):
            continue
        if unit in ("日", "年分") and not scale:
            continue  # 日付・年は主役にしない
        if re.match(r"^(月|年|日)", head[m.end():]) and not (scale or unit):
            continue
        if unit in WEAK_UNITS and not scale:
            weak = weak or m
            continue
        best = m
        break
    best = best or weak
    if best is None:
        return {"label": head, "number": "", "after": "", "sub": tail}
    start, end = best.start(), best.end()
    # 「92万」「3億」で止まった数字は、続く下の位までを1つにする（「92万6,500円」「3億5,000万件」）
    if not best.group(3) and (best.group(2) or "") in ("万", "億", "兆"):
        lower = LOWER_PLACE_RE.match(head[end:])
        if lower and lower.group(0).strip():
            end += len(lower.group(0).rstrip())
    # 「1万〜3万円」のような幅の書き方は、後ろの数字までを1つにする
    more = re.match(r"[〜～~\-－]\s*" + NUMBER_RE.pattern, head[end:])
    if more:
        end += more.end()
    # 前の言葉: 同じ文（読点・空白で区切った単位）の、数字より前
    before = head[:start]
    pieces = CLAUSE_SPLIT.split(before)
    label = TRAIL_PARTICLE.sub("", pieces[-1].strip()) if pieces else ""
    if not label and len(pieces) > 1:
        label = pieces[-2].strip()
    after_text = head[end:]
    after = CLAUSE_SPLIT.split(after_text)[0].strip()
    after = LEAD_PARTICLE.sub("", after) if len(after) > 1 else after
    number = head[start:end].strip()
    return {"label": label, "number": number, "after": after, "sub": tail}


# --------------------------------------------------------------------------- 描画
def _font(path: Path, size: int):
    from PIL import ImageFont  # noqa: PLC0415

    return ImageFont.truetype(str(path), size)


TOKEN = re.compile(r"[0-9０-９][0-9０-９,，.．%％]*|[A-Za-z&]+|.", re.S)
NO_LINE_START = set("、。，．・ー）」』】〕！？!?%％")
_PHRASER = None


def phrases(text: str) -> list[str]:
    """改行してよい区切り（文節）。BudouX があればそれで、無ければ数字・英単語・1文字ずつ（サイトの見出しと同じ BudouX）"""
    global _PHRASER
    if _PHRASER is None:
        try:
            import budoux  # noqa: PLC0415

            _PHRASER = budoux.load_default_japanese_parser()
        except Exception:  # noqa: BLE001
            _PHRASER = False
    if _PHRASER:
        out: list[str] = []
        for chunk in _PHRASER.parse(text):
            out.append(chunk)
        return out
    return TOKEN.findall(text)


def wrap(draw, text: str, font, width: int) -> list[str]:
    """幅に収まるように行に分ける（文節・数字・英単語の途中では切らない。行頭に句読点を置かない）。
    1つの文節が1行に収まらないときだけ、その中を文字で分ける"""
    tokens: list[str] = []
    for chunk in phrases(text):
        if draw.textlength(chunk, font=font) > width:
            tokens += TOKEN.findall(chunk)
        else:
            tokens.append(chunk)
    lines: list[str] = []
    line = ""
    for token in tokens:
        trial = line + token
        if draw.textlength(trial, font=font) <= width or not line:
            line = trial
            continue
        if token in NO_LINE_START:
            line = trial  # 句読点はぶら下げ
            continue
        lines.append(line)
        line = token.lstrip()
    if line:
        lines.append(line)
    return lines


def fit(draw, text: str, path: Path, width: int, max_lines: int, start: int, minimum: int):
    """(フォント, 行) が収まる一番大きい文字。最小でも収まらなければ (None, [])（途中で切らない）"""
    size = start
    while size >= minimum:
        font = _font(path, size)
        lines = wrap(draw, text, font, width)
        if len(lines) <= max_lines and all(draw.textlength(l, font=font) <= width + 2 for l in lines):
            return font, lines
        size -= 2
    return None, []


def _mix(color, other, t: float):
    return tuple(round(c * (1 - t) + o * t) for c, o in zip(color, other))


def draw_icon(draw, name: str, cx: int, cy: int, r: int, color) -> None:
    """白い丸の中の絵記号（太い線と面だけ。文字は使わない。ただし「円」の記号は ¥ の形で描く）"""
    s = r / 100.0
    lw = max(6, round(9 * s))

    def P(x, y):  # noqa: N802 - 中心からの位置（-100〜100）
        return (cx + x * s, cy + y * s)

    if name == "bolt":
        pts = [P(12, -70), P(-38, 8), P(-4, 8), P(-16, 70), P(38, -12), P(4, -12), P(18, -70)]
        draw.polygon(pts, fill=color)
    elif name == "flame":
        draw.ellipse([*P(-42, -10), *P(42, 70)], fill=color)
        draw.polygon([P(-40, 22), P(0, -78), P(40, 22)], fill=color)
        draw.ellipse([*P(-18, 22), *P(18, 60)], fill=(255, 255, 255))
        draw.polygon([P(-16, 38), P(0, 0), P(16, 38)], fill=(255, 255, 255))
    elif name == "yen":
        for i, y in enumerate((44, 22, 0)):
            draw.ellipse([*P(-58, y - 14), *P(58, y + 14)], fill=_mix(color, (255, 255, 255), 0.15 * i), outline=(255, 255, 255), width=3)
        draw.ellipse([*P(-46, -78), *P(46, 14)], fill=color)
        w2 = max(5, round(7 * s))
        draw.line([P(-20, -60), P(0, -34), P(20, -60)], fill=(255, 255, 255), width=w2)
        draw.line([P(0, -34), P(0, -2)], fill=(255, 255, 255), width=w2)
        draw.line([P(-18, -30), P(18, -30)], fill=(255, 255, 255), width=w2 - 1)
        draw.line([P(-18, -18), P(18, -18)], fill=(255, 255, 255), width=w2 - 1)
    elif name == "family":
        draw.ellipse([*P(-52, -66), *P(-14, -28)], fill=color)
        draw.rounded_rectangle([*P(-62, -22), *P(-4, 64)], radius=round(22 * s), fill=color)
        draw.ellipse([*P(16, -26), *P(46, 4)], fill=color)
        draw.rounded_rectangle([*P(8, 10), *P(54, 64)], radius=round(18 * s), fill=color)
    elif name == "shield":
        draw.polygon([P(0, -72), P(58, -50), P(52, 18), P(0, 72), P(-52, 18), P(-58, -50)], fill=color)
        draw.rounded_rectangle([*P(-22, -6), *P(22, 32)], radius=round(5 * s), fill=(255, 255, 255))
        draw.arc([*P(-15, -30), *P(15, 4)], 180, 360, fill=(255, 255, 255), width=max(4, round(6 * s)))
    elif name == "phone":
        draw.rounded_rectangle([*P(-36, -72), *P(36, 72)], radius=round(14 * s), fill=color)
        draw.rounded_rectangle([*P(-27, -56), *P(27, 48)], radius=round(4 * s), fill=(255, 255, 255))
        draw.ellipse([*P(-6, 54), *P(6, 66)], fill=(255, 255, 255))
        for y in (-38, -18, 2):
            draw.rounded_rectangle([*P(-18, y), *P(18, y + 10)], radius=round(3 * s), fill=_mix(color, (255, 255, 255), 0.55))
    elif name == "train":
        draw.rounded_rectangle([*P(-48, -68), *P(48, 52)], radius=round(26 * s), fill=color)
        draw.rounded_rectangle([*P(-34, -50), *P(34, -6)], radius=round(8 * s), fill=(255, 255, 255))
        draw.ellipse([*P(-30, 18), *P(-14, 34)], fill=(255, 255, 255))
        draw.ellipse([*P(14, 18), *P(30, 34)], fill=(255, 255, 255))
        draw.line([P(-30, 54), P(-46, 76)], fill=color, width=lw)
        draw.line([P(30, 54), P(46, 76)], fill=color, width=lw)
    elif name == "house":
        draw.polygon([P(0, -72), P(70, -8), P(-70, -8)], fill=color)
        draw.rectangle([*P(-50, -12), *P(50, 66)], fill=color)
        draw.rounded_rectangle([*P(-14, 18), *P(14, 66)], radius=round(4 * s), fill=(255, 255, 255))
    elif name == "medical":
        draw.rounded_rectangle([*P(-20, -64), *P(20, 64)], radius=round(8 * s), fill=color)
        draw.rounded_rectangle([*P(-64, -20), *P(64, 20)], radius=round(8 * s), fill=color)
    elif name == "document":
        draw.rounded_rectangle([*P(-46, -68), *P(46, 68)], radius=round(8 * s), fill=color)
        for y in (-42, -20, 2, 24):
            draw.rounded_rectangle([*P(-30, y), *P(30 if y < 24 else 6, y + 9)], radius=round(3 * s), fill=(255, 255, 255))
        draw.ellipse([*P(16, 30), *P(44, 58)], fill=(255, 255, 255))
        draw.ellipse([*P(22, 36), *P(38, 52)], fill=color)
    else:  # chart
        for i, h in enumerate((40, 70, 55, 100)):
            x = -60 + i * 32
            draw.rounded_rectangle([*P(x, 60 - h), *P(x + 22, 60)], radius=round(4 * s), fill=color)
        draw.line([P(-66, 64), P(66, 64)], fill=color, width=max(4, round(5 * s)))


def render(article: dict):
    """記事の図の表紙（PIL の RGB 画像 1200×630）"""
    from PIL import Image, ImageDraw  # noqa: PLC0415

    color = color_of(article)
    tint = _mix(color, (255, 255, 255), 0.90)
    image = Image.new("RGB", (W, H), tint)
    draw = ImageDraw.Draw(image)
    # 背景の大きな丸（明るい飾り。暗くしない）
    draw.ellipse([-260, -200, 640, 700], fill=_mix(color, (255, 255, 255), 0.82))
    draw.ellipse([960, 430, 1360, 830], fill=_mix(color, (255, 255, 255), 0.85))
    # 左: 絵記号
    cx, cy, r = 250, 300, 170
    draw.ellipse([cx - r - 14, cy - r - 14, cx + r + 14, cy + r + 14], fill=_mix(color, (255, 255, 255), 0.55))
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255))
    draw_icon(draw, icon_of(article), cx, cy, round(r * 0.78), color)

    fact = key_fact(str(article.get("title") or ""))
    x0, x1 = 500, W - 60
    width = x1 - x0
    y = 70
    # ジャンルの札
    genre = re.sub(r"[｜|]", "・", str(article.get("genre") or "")).strip()
    if genre:
        chip = _font(BOLD, 26)
        tw = draw.textlength(genre, font=chip)
        draw.rounded_rectangle([x0, y, x0 + tw + 36, y + 46], radius=23, fill=color)
        draw.text((x0 + 18, y + 5), genre, font=chip, fill=(255, 255, 255))
        y += 72
    blocks = []
    if fact["number"]:
        if fact["label"]:
            blocks.append(("label", fact["label"], BOLD, 2, 48, 30, INK))
        short = fact["after"] if len(fact["after"]) <= 3 else ""
        blocks.append(("number", fact["number"], BLACK, 1, 132, 64, color, short))
        if fact["after"] and not short:
            blocks.append(("after", fact["after"], BOLD, 1, 46, 28, INK))
    else:
        blocks.append(("label", fact["label"], BLACK, 3, 66, 36, INK))
    if fact["sub"]:
        blocks.append(("sub", fact["sub"], BOLD, 2, 32, 22, SUB_INK))
    bottom = H - 70
    for kind, text, path, lines_max, start, minimum, fill, *extra in blocks:
        inline = extra[0] if extra else ""
        font, lines = fit(draw, text + inline, path, width, lines_max, start, minimum) if inline else (None, [])
        if font:
            lines = [text]  # 「1,286円増」の「増」は数字の後ろに小さく並べる（幅は数字＋後の言葉で確かめた）
        else:
            inline = ""
            font, lines = fit(draw, text, path, width, lines_max, start, minimum)
        if not font:
            continue  # 収まらない言葉は出さない（途中で切らない）
        size = font.size
        gap = round(size * (0.12 if kind == "number" else 0.28))
        need = len(lines) * size + (len(lines) - 1) * gap
        if kind != "label" and y + need > bottom:
            continue
        if kind == "number":
            y += 6
        for line in lines:
            draw.text((x0, y - round(size * 0.12)), line, font=font, fill=fill)
            if inline:
                small = _font(BLACK, round(size * 0.55))
                draw.text((x0 + draw.textlength(line, font=font) + 8, y + round(size * 0.36)), inline, font=small, fill=INK)
            y += size + gap
        y += 18 if kind != "number" else 22
    credit = _font(BOLD, 22)
    note = "図：サイソクニュース作成"
    draw.text((W - 40 - draw.textlength(note, font=credit), H - 46), note, font=credit, fill=SUB_INK)
    return image


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--slug", action="append", required=True)
    parser.add_argument("--out", required=True, help="保存先（1本なら .jpg のファイル、複数ならフォルダ）")
    args = parser.parse_args(argv)
    out = Path(args.out)
    for slug in args.slug:
        article = json.loads((ROOT / "content" / "articles" / f"{slug}.json").read_text("utf-8"))
        target = out if len(args.slug) == 1 and out.suffix else out / f"{slug}.jpg"
        target.parent.mkdir(parents=True, exist_ok=True)
        render(article).save(target, "JPEG", quality=90)
        print(f"{slug}: {key_fact(article.get('title', ''))} -> {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

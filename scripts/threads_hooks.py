"""
Threads 投稿の「書き出し（1行目）」の型。

同じ型が続くとフィードで読み飛ばされるため、記事ごとに合う型を選び、直近で使った型は避ける。
型は SNS で反応を取りやすい書き出しの定番（問いかけ・数字・ビフォーアフター・逆説・共感・待望 など）を、
AIニュースに合わせて調整したもの。どの型でも「記事にある事実だけ」を使う。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "content" / "articles"

# key: 記録用の識別子 / name: 型の名前 / how: 書き方 / when: 使ってよい条件 / examples: 1行目の例
HOOKS: list[dict] = [
    {
        "key": "question",
        "name": "問いかけ型",
        "how": "読者の日常の作業や悩みに寄せて、友人に話しかけるように問う",
        "when": "読者の仕事・生活に直結する機能",
        "examples": ["議事録づくり、まだ手作業でやってますか？", "ChatGPTに資料を作らせて、手直しで結局疲れてません？"],
    },
    {
        "key": "finally",
        "name": "待望型",
        "how": "待たれていたものが来た高揚感を、短く言い切る",
        "when": "以前から予告・噂されていた機能の正式提供、日本での提供開始、プレビューからの一般提供など、本当に「待望」と言える発表だけ",
        "examples": ["ついに来た。Claudeが日本語の音声で話せるように。", "待ってた人、多いはず。Geminiのあの機能が無料プランにも。"],
    },
    {
        "key": "number",
        "name": "数字インパクト型",
        "how": "記事中でいちばん驚く数字を1つだけ、文頭に置く",
        "when": "性能・速度・価格・規模などに印象的な数字がある",
        "examples": ["処理速度、最大5倍。", "月額0円で、GPT-6クラスが使える。"],
    },
    {
        "key": "before_after",
        "name": "ビフォーアフター型",
        "how": "これまでとこれからを1行で対比する",
        "when": "作業時間・手順・コストがはっきり変わる発表",
        "examples": ["3時間かかってた資料づくりが、5分で終わる。", "これまで3つのツールを行き来してた作業が、1画面で完結。"],
    },
    {
        "key": "contrarian",
        "name": "逆説型",
        "how": "よくある見方をひっくり返して、本当の注目点を示す",
        "when": "派手な見出しの裏に、より重要なポイントがある",
        "examples": ["新モデルの性能より、大事なのは料金のほう。", "「すごいデモ」で終わらせるのはもったいない発表です。"],
    },
    {
        "key": "empathy",
        "name": "あるある共感型",
        "how": "読者が感じている小さな不満を、そのまま言葉にする",
        "when": "多くの人が困っている作業を解決する機能",
        "examples": ["AIの回答、毎回コピペして整えるの地味に面倒なんですよね。", "会議のあと、誰が何を言ったか思い出せない問題。"],
    },
    {
        "key": "conclusion",
        "name": "結論先出し型",
        "how": "読者がいちばん知りたい答えを先に言う",
        "when": "「使えるの？」「無料？」「日本で使える？」への答えがはっきりしている",
        "examples": ["結論：無料プランの人も今日から使えます。", "先に言うと、日本からはまだ使えません。"],
    },
    {
        "key": "callout",
        "name": "呼びかけ型",
        "how": "関係のある人を名指しして、手を止めてもらう",
        "when": "対象の読者がはっきりしている（開発者・動画編集者・営業など）",
        "examples": ["動画編集してる人、これはチェックしてほしい。", "コードを書く人には、今週いちばん大きいニュースかも。"],
    },
    {
        "key": "surprise",
        "name": "意外な一点型",
        "how": "発表動画の中で、見落とされがちな驚きの事実を挙げる",
        "when": "本文に、見出しになっていない意外な事実がある",
        "examples": ["発表動画でいちばん驚いたのは、最後の30秒でした。", "ほとんど話題になってないけど、これはかなり大きい。"],
    },
    {
        "key": "breaking",
        "name": "速報型",
        "how": "【速報】と付けて、誰が何をしたかだけを言う",
        "when": "大手企業の新モデル・新製品の発表直後など、ニュース性が高い",
        "examples": ["【速報】OpenAIが新しい音声エージェントを公開。", "【速報】Googleが Gemini の新モデルを発表しました。"],
    },
    {
        "key": "caution",
        "name": "注意喚起型",
        "how": "使う前に知っておくべき条件や落とし穴を先に伝える",
        "when": "料金・提供地域・プラン条件に注意点がある",
        "examples": ["これ、使う前に料金だけは確認しておいたほうがいいです。", "話題の新機能、実は対象プランが限られています。"],
    },
    {
        "key": "free",
        "name": "無料型",
        "how": "無料で試せることを最初に伝える",
        "when": "判定で無料で試せる（無料プラン・無料枠・OSS）ときだけ",
        "examples": ["これ、無料で試せます。", "お金をかけずに、今日から触れるAIの新機能です。"],
    },
    {
        "key": "future",
        "name": "変化の予告型",
        "how": "この発表で仕事や日常がどう変わるかを一言で言う",
        "when": "研究・デモ段階でも、将来の変化がはっきり描ける",
        "examples": ["数年後の会議は、たぶんこうなります。", "ロボットが家事をする未来、思ったより近いかもしれません。"],
    },
]

HOOK_KEYS = [hook["key"] for hook in HOOKS]
AVOID_RECENT = 4


def recent_hooks(limit: int = AVOID_RECENT) -> list[str]:
    """直近に生成した記事で使った書き出しの型（新しい順）"""
    found: list[tuple[str, str]] = []
    if not ARTICLES_DIR.exists():
        return []
    for path in ARTICLES_DIR.glob("*.json"):
        try:
            article = json.loads(path.read_text("utf-8"))
        except Exception:
            continue
        hook = article.get("threadsHook")
        if hook:
            found.append((article.get("generatedAt", ""), hook))
    found.sort(reverse=True)
    return [hook for _, hook in found[:limit]]


def prompt_block(recent: list[str] | None = None) -> str:
    """生成プロンプトに足す「書き出しの型」の説明"""
    recent = recent if recent is not None else recent_hooks()
    lines = [
        "## Threads 紹介文（threads_post）の書き出し",
        "threads_post の1行目は、次の型から、この記事にいちばん合うものを1つ選んで書く。選んだ型の key を threads_hook に入れる。",
        "各型の「使ってよい条件」を満たさない型は選ばない。例はあくまで雰囲気の参考で、そのまま使わない。",
    ]
    if recent:
        names = "、".join(h["name"] for h in HOOKS if h["key"] in recent)
        lines.append(f"直近の投稿で {names} を使ったので、今回はそれ以外から選ぶ（同じ型が続くと読み飛ばされるため）。")
    for hook in HOOKS:
        examples = "／".join(f"「{e}」" for e in hook["examples"])
        lines.append(f"- {hook['key']}（{hook['name']}）: {hook['how']}。使ってよい条件: {hook['when']}。例: {examples}")
    lines.append(
        "どの型でも、人が書いたような自然な口語にする。記事にない事実・誇張は書かない。"
        "「ついに」「待望」は待望型の条件を満たすときだけ使ってよい。"
    )
    return "\n".join(lines)


def clean_hook(value: object) -> str:
    key = str(value or "").strip()
    return key if key in HOOK_KEYS else ""

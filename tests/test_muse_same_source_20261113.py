"""2026-11-13: Muse の記事は、出典の URL が同じというだけでは重複にしない（オーナー「落とすのは嘘だけ」「とにかく数字」）。

きっかけ: 7日で37本が、話題は別なのに国税庁などの同じ公式ページを引いただけで落ちていた（点検 audit_20261113）。
同じ記事の出し直し（題名が似ている・同じ原稿の v2）と、見出し・固有名詞の重なりは今までどおり止める。ネット・LLM を使わない。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import dedupe  # noqa: E402
import muse_articles as ma  # noqa: E402
import story  # noqa: E402

NTA = "https://www.nta.go.jp/taxes/shiraberu/taxanswer/shotoku/1120.htm"


def draft(title: str, url: str = NTA) -> dict:
    return {"title": title, "sources": [{"url": url}], "notes": ""}


def article(slug: str, title: str, url: str = NTA, **extra) -> dict:
    return {"slug": slug, "title": title, "sourceUrl": url, **extra}


def use_articles(monkeypatch, rows: list[dict]) -> None:
    index = dedupe.Index()
    for row in rows:
        index.add(row["title"], row["sourceUrl"], None, label=row["slug"])
    monkeypatch.setattr(dedupe, "load_recent", lambda days: index)
    monkeypatch.setattr(ma, "_recent_articles", lambda days: rows)

    class NoStory:
        def __init__(self, days):
            pass

        def match(self, title, url=""):
            assert url == "", "出典の URL を渡すと「同じ出典URL」で落ちる"
            return None

    monkeypatch.setattr(story, "Recent", NoStory)


def test_same_source_different_topic_is_not_a_duplicate(monkeypatch):
    use_articles(monkeypatch, [article("iryohi-kojo", "医療費控除　10万円の壁は所得200万円未満なら5パーセントに下がる")])
    for title, name in (
        ("医療費控除の明細書の書き方 領収書は出さずに5年保管し、人と病院ごとにまとめて書けます", "20261112-手続き-医療費控除の明細書の書き方.md"),
        ("年末調整ではできない控除は医療費・寄附金・住宅ローン1年目、申告しないと税金は戻りません", "20261112-手続き-年末調整ではできない控除v2.md"),
    ):
        assert ma.duplicate_of(draft(title), name) is None, title


def test_same_source_as_another_muse_source_is_not_a_duplicate(monkeypatch):
    """前の記事が2件目以降の出典に使ったページ（museSources）でも同じ"""
    url = "https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl007/results.html"
    rows = [article("toyu", "灯油　補助が続いても上がる理由と12月からの見直し", "https://www.meti.go.jp/x", museSources=[{"url": url}])]
    use_articles(monkeypatch, rows)
    assert ma.duplicate_of(draft("レギュラー169.9円、前週比0.1円安、3週連続の値下がり", url), "20261112-お金-ガソリン価格の週次.md") is None


def test_same_source_and_similar_title_is_still_a_duplicate(monkeypatch):
    """実際に落ちた出し直し（題名の類似 0.26〜0.37）は、出典が同じなら今までどおり止める"""
    cases = (
        ("口座振替の2年前納で17,370円割引　令和8年度の国民年金は月17,920円",
         "月17,920円が令和8年度の国民年金保険料です 前納なら2年で最大17,370円安くなります"),
        ("うまかっちゃんやマロニーちゃんが7.4%〜24.2%値上げへ　ハウス食品、2027年2月から",
         "26品目が2027年2月1日納品分から最大24.2%値上げ、うまかっちゃん5個パックは680円から730円に"),
        ("出産育児一時金　50万円は本人の口座ではなく病院へ直接支払われる",
         "50万円の出産育児一時金、直接支払なら退院時に払うのは差額だけ"),
    )
    for old, new in cases:
        rows = [article("old", old)]
        score = dedupe.jaccard(dedupe.bigrams(old), dedupe.bigrams(new))
        assert ma.SAME_SOURCE_JACCARD <= score < dedupe.JACCARD_DUP, (old, score)
        hit = ma.resubmission_of(draft(new), "20261111-お金-x.md", rows)
        assert hit and "同じ出典で見出しも類似" in hit, new
        # 出典が別なら、この類似度では止めない（見出しだけの重複は dedupe の 0.5 以上・固有名詞の一致）
        assert ma.resubmission_of(draft(new, "https://example.go.jp/other"), "20261111-お金-x.md", rows) is None


def test_resubmitted_file_v2_is_a_duplicate_even_with_a_new_title(monkeypatch):
    rows = [article("tokyo-denki", "電気代、東京エリアの4プランを比べると基本料金と単価で順位が入れ替わる",
                    "https://www.tepco.co.jp/a", museFile="20261109-比較-電気代の見直し方-v2.md")]
    use_articles(monkeypatch, rows)
    new = draft("電気代の見直しは単価だけでは決まらない、東京エリア4プランの基本料金と従量単価", "https://www.tepco.co.jp/b")
    hit = ma.duplicate_of(new, "20261109-比較-電気代の見直し方-v3.md")
    assert hit and "同じ原稿の出し直し" in hit
    # 日付が違う同じ名前（毎日の天気・週ごとのガソリン）は出し直しではない
    assert ma.duplicate_of(new | {"title": "まったく別の題名で、単語も重ならない記事にする"}, "20261110-比較-電気代の見直し方.md") is None


def test_topic_stem_strips_resubmission_marks_only():
    assert ma.topic_stem("20261113-値上げ-日清食品の値上げv2-0038.md") == ("20261113", "日清食品の値上げ")
    assert ma.topic_stem("20261113-値上げ-日清食品の値上げ.md") == ("20261113", "日清食品の値上げ")
    assert ma.topic_stem("20261109-値上げ-ハウス食品26品目の価格改定-r.md") == ("20261109", "ハウス食品26品目の価格改定")
    assert ma.topic_stem("20261113-暮らし-iPhone Air.md") == ("20261113", "iphone air")
    assert ma.topic_stem("なまえ.md") == ("", "")


def test_title_and_entity_checks_still_apply(monkeypatch):
    """見出しがほぼ同じ・珍しい固有名詞が2つ一致、は出典に関係なく今までどおり重複"""
    use_articles(monkeypatch, [
        article("recall", "ロッキーとライズ、レックスをリコール　ダイハツが17万台", "https://www.mlit.go.jp/a"),
        article("kyuyo", "会社員の平均給与は487万円で過去最高　国税庁の2025年分の調査", "https://www.nta.go.jp/b"),
    ])
    assert ma.duplicate_of(draft("ロッキーとライズ、レックス17万6,683台リコール　車台番号の範囲と調べ方", "https://www.daihatsu.co.jp/c"),
                           "20261113-暮らし-ロッキーとライズのリコール.md")
    assert ma.duplicate_of(draft("会社員の平均給与は487万円で過去最高　国税庁の調査", "https://www.nta.go.jp/c"), "20261113-お金-平均給与.md")


def test_retired_source_alone_does_not_block(monkeypatch, tmp_path):
    """取り下げた記事の出典（content/retired.json）も、URL だけでは止めない（正しく書き直した原稿は門で確かめる）"""
    index = dedupe.Index()
    index.urls.add(dedupe._norm_url("https://www.nissin.com/jp/company/news/13563/"))
    assert index.find("x", "https://www.nissin.com/jp/company/news/13563") == "同じ出典URL"
    monkeypatch.setattr(dedupe, "load_recent", lambda days: index)
    monkeypatch.setattr(ma, "_recent_articles", lambda days: [])
    monkeypatch.setattr(story.Recent, "__init__", lambda self, days=5: setattr(self, "stories", []) or setattr(self, "df", {}))
    assert ma.duplicate_of(draft("日清食品の値上げ2026　カップヌードルは2026年4月から5〜11%上がりました",
                                 "https://www.nissin.com/jp/company/news/13563"), "20261113-値上げ-日清食品の値上げv2.md") is None


def test_recent_articles_reads_the_window(monkeypatch, tmp_path):
    import json
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    (tmp_path / "new.json").write_text(json.dumps({"title": "新しい", "sourceUrl": NTA, "generatedAt": now.isoformat()}), "utf-8")
    (tmp_path / "old.json").write_text(json.dumps({"title": "古い", "sourceUrl": NTA,
                                                   "generatedAt": (now - timedelta(days=9)).isoformat()}), "utf-8")
    (tmp_path / "bad.json").write_text("{", "utf-8")
    monkeypatch.setattr(dedupe, "ARTICLES_DIR", tmp_path)
    rows = ma._recent_articles(ma.DEDUPE_DAYS)
    assert [r["slug"] for r in rows] == ["new"]

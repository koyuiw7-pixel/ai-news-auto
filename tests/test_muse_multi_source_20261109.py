"""2026-11-09: Muse の比較記事は、挙げた出典の全部を事実確認に入れる（7本目の ESET の公式ページが確認に届かず「創作」と落ちた）。
1件目が読めなくても、比較記事は次に読めた出典を一番にする。メモ（facts）は手がかりで、根拠はページの本文"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import muse_articles  # noqa: E402
import quality  # noqa: E402


def _page(name: str, price: str, filler: int = 9000) -> dict:
    lines = [f"{name}の会社の歴史と沿革の説明の行です{i}" for i in range(filler // 20)]
    lines.insert(len(lines) // 2, f"{name} 1年版 {price}円（税込）")
    return {"text": "\n".join(lines)[:12000], "full_text": "", "title": name}


def test_all_sources_reach_the_fact_check_and_prices_are_kept():
    names = ["ノートン", "ノートン更新", "ウイルスバスター", "トレンド改定", "キヤノンESET", "キヤノンストア", "ESET HOME"]
    fetched = [{"url": f"https://example{i}.jp/", "name": n, "facts": f"{n} 1年版の価格", **_page(n, f"{6000 + i * 50:,}")}
               for i, n in enumerate(names)]
    text = muse_articles.source_text_of(fetched, "セキュリティソフトの選び方")
    record = {"museSources": [{"url": s["url"]} for s in fetched]}
    seen = text[:quality.source_cap(record)]
    for i, n in enumerate(names):
        assert f"【{n}】" in seen
        assert f"{n} 1年版 {6000 + i * 50:,}円" in seen  # 料金の行が抜き出しで残る
    assert len(text) <= quality.MULTI_SOURCE_CAP
    # メモは手がかりとして添えるだけ（根拠ではないと書く）
    assert "根拠ではない" in text


def test_single_source_and_normal_articles_keep_old_cap():
    assert quality.source_cap({}) == quality.SOURCE_CAP
    assert quality.source_cap({"museSources": [{"url": "a"}]}) == quality.SOURCE_CAP
    assert quality.source_cap({"museSources": [{"url": "a"}, {"url": "b"}]}) == quality.MULTI_SOURCE_CAP
    one = [{"url": "https://a.jp/", "name": "A", "text": "本文" * 200}]
    assert muse_articles.source_text_of(one) == "【A】https://a.jp/\n" + "本文" * 200


def _fake_feeds(monkeypatch, bad: set[str]):
    def fetch(url):
        if url in bad:
            raise RuntimeError("timeout")
        return {"text": "公式の料金 1,000円 " * 40, "title": url}
    monkeypatch.setitem(sys.modules, "feeds", types.SimpleNamespace(fetch_article_text=fetch))


def test_comparison_uses_next_readable_source_when_first_fails(monkeypatch):
    _fake_feeds(monkeypatch, {"https://a.jp/"})
    sources = [{"url": "https://a.jp/"}, {"url": "https://b.jp/"}, {"url": "https://c.jp/"}]
    unread: list[str] = []
    got = muse_articles.fetch_sources(sources, skip_unreadable_first=True, unread=unread)
    assert [s["url"] for s in got] == ["https://b.jp/", "https://c.jp/"]
    assert unread == ["https://a.jp/"]


def test_default_still_needs_the_first_source(monkeypatch):
    """fetch_sources の既定は今までどおり（2026-11-13 から入稿の回は全ジャンルで skip_unreadable_first=True を渡す。
    tests/test_muse_unread_source_20261113.py）"""
    _fake_feeds(monkeypatch, {"https://a.jp/"})
    sources = [{"url": "https://a.jp/"}, {"url": "https://b.jp/"}]
    assert muse_articles.fetch_sources(sources) == []


def test_legacy_tls_sites_are_retried_with_cert_checks_kept(monkeypatch):
    import ssl
    import urllib.error
    import urllib.request

    import feeds

    calls = []

    class Resp:
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            return b"<html>ok</html>"

        def geturl(self):
            return "https://ahamo.com/plan"

    def urlopen(request, timeout=0, context=None):
        calls.append(context)
        if context is None:
            raise urllib.error.URLError("[SSL: UNSAFE_LEGACY_RENEGOTIATION_DISABLED] unsafe legacy renegotiation disabled")
        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    data, final = feeds.fetch("https://ahamo.com/plan")
    assert data == b"<html>ok</html>" and len(calls) == 2
    assert calls[1].verify_mode == ssl.CERT_REQUIRED and calls[1].check_hostname


def test_title_claims_must_be_in_the_sources():
    assert "タイトルの事実の主張" in quality.FACT_PROMPT and "本文に書いてあるだけでは裏付けにならない" in quality.FACT_PROMPT

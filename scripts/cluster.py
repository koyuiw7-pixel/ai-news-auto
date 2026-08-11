"""同一トピックを扱う記事をまとめる（クラスタリング）.

同じ発表について複数の動画が公開されると、内容の近い記事が並んでしまう。
これは検索エンジンから「薄い量産コンテンツ」と見なされる要因になるため、
横断まとめ記事に統合するための材料としてクラスタを検出する。

API は使わない。キーワード・タグ・タイトル中の固有名詞の重なりだけで判定する。
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass

# クラスタと見なす条件
MIN_SHARED = 4  # 共通する語がこれ以上
MIN_RATIO = 0.45  # 少ない方の語数に対する共通率
MIN_CLUSTER_SIZE = 3  # まとめ記事にする最小本数


@dataclass
class Cluster:
    key: str  # 代表となるトピック名
    slugs: list[str]
    genre_slug: str
    genre_name: str

    @property
    def size(self) -> int:
        return len(self.slugs)


def signature(article: dict) -> set[str]:
    """記事のトピックを表す語の集合。"""
    words = {k.lower().strip() for k in article.get("keywords", []) if k}
    words |= {t.lower().strip() for t in article.get("tags", []) if t}
    # タイトル中の「」で囲まれた製品名は強い手がかり
    words |= {m.lower() for m in re.findall(r"「([^」]{2,24})」", article.get("title", ""))}
    return {w for w in words if w}


def _topic_name(articles: list[dict]) -> str:
    """クラスタ全記事に共通して現れる語のうち、最も具体的なものを代表名にする。"""
    quoted: dict[str, int] = {}
    for article in articles:
        for match in re.findall(r"「([^」]{2,24})」", article.get("title", "")):
            quoted[match] = quoted.get(match, 0) + 1

    if quoted:
        # 出現回数が多く、かつ長い（＝具体的な）ものを選ぶ
        return max(quoted.items(), key=lambda kv: (kv[1], len(kv[0])))[0]

    # 「」が無ければ共通キーワードから選ぶ
    common = set.intersection(*(signature(a) for a in articles)) if articles else set()
    return max(common, key=len) if common else articles[0].get("tags", ["まとめ"])[0]


def build_clusters(articles: list[dict]) -> list[Cluster]:
    """Union-Find で記事をクラスタにまとめる。"""
    parent = list(range(len(articles)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    signatures = [signature(a) for a in articles]

    for i, j in itertools.combinations(range(len(articles)), 2):
        # ジャンルが違う記事は統合しない（免責文が変わってしまうため）
        if articles[i].get("genreSlug") != articles[j].get("genreSlug"):
            continue
        a, b = signatures[i], signatures[j]
        if not a or not b:
            continue
        shared = len(a & b)
        if shared >= MIN_SHARED and shared / min(len(a), len(b)) >= MIN_RATIO:
            union(i, j)

    buckets: dict[int, list[int]] = {}
    for index in range(len(articles)):
        buckets.setdefault(find(index), []).append(index)

    clusters = []
    for members in buckets.values():
        if len(members) < MIN_CLUSTER_SIZE:
            continue
        group = [articles[i] for i in members]
        # 新しい順
        group.sort(key=lambda a: a.get("publishedAt", ""), reverse=True)
        clusters.append(
            Cluster(
                key=_topic_name(group),
                slugs=[a["slug"] for a in group],
                genre_slug=group[0].get("genreSlug", ""),
                genre_name=group[0].get("genre", ""),
            )
        )

    clusters.sort(key=lambda c: c.size, reverse=True)
    return clusters

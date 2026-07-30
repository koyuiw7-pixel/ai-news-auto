"""監視対象の YouTube チャンネル定義.

channel_id は実際に RSS が 200 を返すことを確認済み。
追加したいときは `python3 scripts/resolve_handle.py @Handle` で ID を引ける。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Channel:
    slug: str  # URL に使う識別子（/channels/<slug>）
    name: str  # 表示名
    channel_id: str  # YouTube チャンネルID (UC...)
    # そのチャンネルの記事に必ず付けるタグ
    base_tags: tuple[str, ...] = ()

    @property
    def feed_url(self) -> str:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={self.channel_id}"


CHANNELS: list[Channel] = [
    Channel(
        slug="openai",
        name="OpenAI",
        channel_id="UCXZCJLdBC09xxGZ6gcdrc6A",
        base_tags=("OpenAI", "ChatGPT"),
    ),
    Channel(
        slug="anthropic",
        name="Anthropic",
        channel_id="UCrDwWp7EBBv4NwvScIpBDOA",
        base_tags=("Anthropic", "Claude"),
    ),
    Channel(
        slug="google-deepmind",
        name="Google DeepMind",
        channel_id="UCP7jMXSY2xbc3KCAE0MHQ-A",
        base_tags=("Google DeepMind", "Gemini"),
    ),
    Channel(
        slug="google",
        name="Google",
        channel_id="UCK8sQmJBp8GCxrOtXWBpyEA",
        base_tags=("Google",),
    ),
    Channel(
        slug="google-developers",
        name="Google for Developers",
        channel_id="UC_x5XG1OV2P6uZZ5FSM9Ttw",
        base_tags=("Google", "開発者向け"),
    ),
    Channel(
        slug="microsoft-developer",
        name="Microsoft Developer",
        channel_id="UCsMica-v34Irf9KVTh6xx-g",
        base_tags=("Microsoft", "Copilot"),
    ),
    Channel(
        slug="nvidia",
        name="NVIDIA",
        channel_id="UCHuiy8bXnmK5nisYHUd1J5g",
        base_tags=("NVIDIA", "GPU"),
    ),
    Channel(
        slug="meta-ai",
        name="AI at Meta",
        channel_id="UC5qxlwEKM7-5YZudb24l0bg",
        base_tags=("Meta", "Llama"),
    ),
    Channel(
        slug="hugging-face",
        name="Hugging Face",
        channel_id="UCHlNU7kIZhRgSbhHvFoy72w",
        base_tags=("Hugging Face", "オープンソース"),
    ),
]

CHANNELS_BY_ID = {c.channel_id: c for c in CHANNELS}

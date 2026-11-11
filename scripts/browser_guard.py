"""
自動のブラウザ（Playwright）で本番のページを開くときに、訪問者の数え方を汚さないための共通の部品（Python 版）。
決まりは scripts/browser_guard.cjs と同じ（2026-11-11 オーナー承認・台帳 O17）。

止めるもの:
  - Cloudflare Web Analytics（RUM）: static.cloudflareinsights.com の読み込みと /cdn-cgi/rum への送信
  - 確かめるだけのとき（verify_only。既定）: サイトの自前の計測 /api/aff/*

使い方:
  from browser_guard import guard_sync, guard_async, should_block
  guard_sync(page_or_context)            # sync_playwright。ほかの route を登録した「後」に呼ぶ
  await guard_async(page_or_context)     # async_playwright
自前の route("**/*") の中で判定するなら should_block(url)。
"""
from __future__ import annotations

from urllib.parse import urlparse

RUM_HOSTS = ("static.cloudflareinsights.com", "cloudflareinsights.com")
RUM_GLOBS = ("**/static.cloudflareinsights.com/**", "**/cloudflareinsights.com/**", "**/cdn-cgi/rum**")
OWN_BEACON_GLOBS = ("**/api/aff/**",)


def is_rum_beacon(url: str) -> bool:
    try:
        u = urlparse(url)
    except ValueError:
        return False
    host = (u.hostname or "").lower()
    path = u.path or ""
    if any(host == h or host.endswith("." + h) for h in RUM_HOSTS):
        return True
    return path == "/cdn-cgi/rum" or path.startswith("/cdn-cgi/rum/") or path.startswith("/cdn-cgi/rum?")


def is_own_beacon(url: str) -> bool:
    try:
        return (urlparse(url).path or "").startswith("/api/aff/")
    except ValueError:
        return False


def should_block(url: str, verify_only: bool = True) -> bool:
    return is_rum_beacon(url) or (verify_only and is_own_beacon(url))


def _globs(verify_only: bool) -> tuple[str, ...]:
    return RUM_GLOBS + (OWN_BEACON_GLOBS if verify_only else ())


def guard_sync(target, verify_only: bool = True):
    """sync_playwright の BrowserContext か Page に、計測を止める route を足す"""
    for glob in _globs(verify_only):
        target.route(glob, lambda route: route.abort("blockedbyclient"))
    return target


async def guard_async(target, verify_only: bool = True):
    """async_playwright の BrowserContext か Page に、計測を止める route を足す"""
    async def _abort(route):
        await route.abort("blockedbyclient")

    for glob in _globs(verify_only):
        await target.route(glob, _abort)
    return target

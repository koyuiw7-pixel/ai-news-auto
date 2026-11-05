#!/usr/bin/env python3
"""PDF の資料（官公庁の統計の速報・適時開示の決算短信など）から文字を取り出す共通の処理（2026-11-05）。

- 取り出しは poppler の `pdftotext -layout` を先に使い（入っていれば）、無いか壊れた文字なら pypdf（暗号化された PDF は
  cryptography で開く。財務省・内閣府の PDF は AES で暗号化されている）。決算短信の1ページ目の表（売上・利益の数字）は pypdf だと
  数字が落ちるが、pdftotext -layout は表の行のまま残す（2026-11-05 トヨタ・任天堂・ソニー・ダイキンの決算短信で確認。台帳 W35）。
  GitHub Actions では poppler-utils を入れる（release_watch.yml・auto_run.yml の速報レーン）。
- 取り出した文字が壊れていないか（日本語の文字の割合・意味のない記号の多さ）を確かめ、壊れていれば例外にする。
  壊れた文字を「本文」として記事にしない（2026-11-03 に PDF のバイト列をそのまま文字として読み、壊れた本文になった件）。
- 使う所: scripts/feeds.py（記事ページが PDF のとき）・scripts/release_watch.py（発表時刻が決まった速報の見張り）。
"""

from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata

JP_RE = re.compile(r"[぀-ヿ㐀-鿿]")
OK_RE = re.compile(r"[　-ヿ㐀-鿿＀-￯A-Za-z0-9\s.,:;()%+\-/'\"・、。「」『』（）［］〔〕【】〈〉《》＜＞▲△●○◎※＊*~〜～=＝?!？！#&＆]")


class PdfTextError(ValueError):
    """PDF の文字を正しく取り出せない（壊れている・画像だけ・暗号を開けない）"""


def looks_clean(text: str, min_jp: int = 40) -> bool:
    """取り出した文字が読める日本語か（日本語の文字が min_jp 字以上・読める文字が95%以上）"""
    body = re.sub(r"\s+", "", text or "")
    if len(body) < 200 or len(JP_RE.findall(body)) < min_jp:
        return False
    ok = sum(1 for ch in body if OK_RE.match(ch))
    return ok / max(len(body), 1) >= 0.95


def poppler_text(data: bytes, max_pages: int = 40, timeout: int = 60) -> str:
    """poppler の pdftotext -layout で取り出した文字（表の行を崩さない）。pdftotext が無い・失敗したら空"""
    exe = shutil.which("pdftotext")
    if not exe or not data:
        return ""
    fd, path = tempfile.mkstemp(suffix=".pdf")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        done = subprocess.run([exe, "-layout", "-enc", "UTF-8", "-f", "1", "-l", str(max_pages), path, "-"],
                              capture_output=True, timeout=timeout, check=False)
        if done.returncode != 0:
            return ""
        return done.stdout.decode("utf-8", "replace").replace("\f", "\n")
    except (OSError, subprocess.SubprocessError):
        return ""
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def extract(data: bytes, max_pages: int = 40, min_jp: int = 40) -> str:
    """PDF のバイト列 → 文字（NFKC で全角の数字・記号をそろえ、行の中の余計な空白を詰める）。読めなければ PdfTextError。
    poppler（pdftotext -layout）が読めればそれを使い、無い・壊れた文字なら pypdf で読む"""
    if not data or data[:5] != b"%PDF-":
        raise PdfTextError("PDF ではない")
    layout = normalize(poppler_text(data, max_pages))
    if layout and looks_clean(layout, min_jp):
        return layout
    try:
        from pypdf import PdfReader  # noqa: PLC0415
    except ImportError as error:  # pragma: no cover - requirements.txt に入っている
        raise PdfTextError("pypdf が無い") from error
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")  # 閲覧の鍵が空の暗号（財務省・内閣府）。cryptography が要る
        pages = [page.extract_text() or "" for page in reader.pages[:max_pages]]
    except Exception as error:  # noqa: BLE001
        raise PdfTextError(f"PDF を開けない（{str(error)[:80]}）") from error
    text = normalize("\n".join(pages))
    if not looks_clean(text, min_jp):
        raise PdfTextError("PDF の文字が壊れているか、画像だけの PDF")
    return text


def normalize(text: str) -> str:
    """NFKC（全角の数字・％・括弧を半角に）＋行ごとの空白の整理。数字の中の空白（「1 0月」）は詰めない（意味が変わりうるため照合の側で扱う）"""
    text = unicodedata.normalize("NFKC", text or "")
    lines = [re.sub(r"[ \t　]+", " ", line).strip() for line in text.splitlines()]
    out: list[str] = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip()

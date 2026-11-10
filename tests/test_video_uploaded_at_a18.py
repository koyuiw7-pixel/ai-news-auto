"""SEO A18: 記事に解説動画を足すとき、足した日時（VideoObject の uploadDate）を記録する。同じ動画を書き直しても日時は変えない"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sns_video_followup as svf  # noqa: E402


def test_write_embed_records_uploaded_at(tmp_path, monkeypatch):
    monkeypatch.setattr(svf, "ARTICLES", tmp_path)
    (tmp_path / "a.json").write_text(json.dumps({"slug": "a"}), "utf-8")
    svf.write_embed("a", {"src": "https://ai-tech-express.jp/video/a-1.mp4", "seconds": 30})
    first = json.loads((tmp_path / "a.json").read_text("utf-8"))["video"]
    assert first["uploadedAt"].endswith("Z") and first["uploadedAt"][:2] == "20"
    # 同じ動画を書き直しても、足した日時はそのまま
    prev = dict(first, uploadedAt="2026-11-01T00:00:00Z")
    data = json.loads((tmp_path / "a.json").read_text("utf-8"))
    data["video"] = prev
    (tmp_path / "a.json").write_text(json.dumps(data), "utf-8")
    svf.write_embed("a", {"src": "https://ai-tech-express.jp/video/a-1.mp4", "seconds": 30})
    assert json.loads((tmp_path / "a.json").read_text("utf-8"))["video"]["uploadedAt"] == "2026-11-01T00:00:00Z"
    # 別の動画に替えたら、その日時になる
    svf.write_embed("a", {"src": "https://ai-tech-express.jp/video/a-2.mp4"})
    assert json.loads((tmp_path / "a.json").read_text("utf-8"))["video"]["uploadedAt"] != "2026-11-01T00:00:00Z"

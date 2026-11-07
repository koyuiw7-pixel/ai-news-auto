"""2026-11-07 台帳 O16（お金はなるべく使わない・品質と本数は下げない）。ネットワークは使わない。

- Claude API の台帳の「段|モデルの段」は、モデルの名前で決める（書き直しのジョブが全部の段を Sonnet にしても、Sonnet を Haiku と数えない）
- Workers AI の画像の判定: 同じ実行で同じ画像に同じ質問は1回だけ呼ぶ／使ったニューロンを見える化の記録に足す（文章の目安には入れない）
"""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import llm  # noqa: E402
import images  # noqa: E402


class ModelLevelTest(unittest.TestCase):
    def test_level_follows_model_name_even_when_env_maps_all_levels_to_sonnet(self):
        env = {"CLAUDE_API_MODEL_LOW": "claude-sonnet-5-5", "CLAUDE_API_MODEL_MID": "claude-sonnet-5-5",
               "CLAUDE_API_MODEL_TOP": "claude-sonnet-5-5"}
        with patch.dict(os.environ, env):
            self.assertEqual(llm._model_level("claude-sonnet-5-5"), 2)
            self.assertEqual(llm._model_level("claude-haiku-5-5"), 1)
            self.assertEqual(llm._model_level("claude-opus-5-5"), 3)

    def test_unknown_model_uses_env_mapping(self):
        with patch.dict(os.environ, {"CLAUDE_API_MODEL_LOW": "claude-x"}):
            self.assertEqual(llm._model_level("claude-x"), 1)
        self.assertEqual(llm._model_level("something-else"), 3)

    def test_rewrite_job_sonnet_is_recorded_as_sonnet(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(llm, "API_STATE_DIR", Path(tmp)), \
                patch.dict(os.environ, {"CLAUDE_API_LEDGER": "types", "CLAUDE_API_MODEL_LOW": "claude-sonnet-5-5"}):
            llm.record_api_usage("core", "claude-sonnet-5-5", {"input_tokens": 1000, "output_tokens": 100})
            data = json.loads((Path(tmp) / "claude_api_usage_types.json").read_text("utf-8"))
            by = next(iter(next(iter(data["runs"].values())).values()))["by"]
            self.assertEqual(set(by), {"core|2"})


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class VisionTest(unittest.TestCase):
    def setUp(self):
        from PIL import Image  # noqa: PLC0415

        self.image = Image.new("RGB", (640, 360), (120, 30, 30))
        images._VISION_CACHE.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [
            patch.object(llm, "LLM_STATE_DIR", Path(self.tmp.name)),
            patch.object(llm, "USAGE_PATH", Path(self.tmp.name) / "llm_usage.json"),
            patch.dict(os.environ, {"LLM_WORKFLOW": "images"}),
            patch.object(images, "cf_token", return_value="t"),
        ]
        for p in self.patches:
            p.start()
        self.calls = 0

    def tearDown(self):
        for p in self.patches:
            p.stop()
        images._VISION_CACHE.clear()
        self.tmp.cleanup()

    def fake_urlopen(self, req, timeout=60):
        self.calls += 1
        body = {"choices": [{"message": {"content": "yes"}}], "usage": {"prompt_tokens": 1000, "completion_tokens": 2}}
        return FakeResponse(json.dumps(body).encode())

    def test_same_image_same_question_calls_once_and_records_neurons(self):
        with patch.object(images.urllib.request, "urlopen", side_effect=self.fake_urlopen):
            self.assertEqual(images.cf_vision(self.image, "Is it red?", max_tokens=4), "yes")
            self.assertEqual(images.cf_vision(self.image, "Is it red?", max_tokens=4), "yes")
            self.assertEqual(self.calls, 1)
            images.cf_vision(self.image, "Is there a face?", max_tokens=4)  # 別の質問はもう1回呼ぶ
            self.assertEqual(self.calls, 2)
        data = json.loads((Path(self.tmp.name) / "llm_usage_wf.json").read_text("utf-8"))
        jobs = next(iter(data.values()))["images"]
        key = next(k for k in jobs if k.startswith(images.VISION_NEURON_KEY))
        self.assertEqual(jobs[key], 2 * 25)  # 1000×24545/100万 + 2×77273/100万 = 24.7 → 25 ニューロン × 2回
        # 文章の目安（workers-ai-neurons@）には入れない
        with patch.object(llm, "USAGE_PATH", Path(self.tmp.name) / "llm_usage.json"):
            self.assertEqual(llm.cf_neurons_today(), 0)

    def test_failed_answer_is_not_cached(self):
        def empty(req, timeout=60):
            self.calls += 1
            return FakeResponse(json.dumps({"choices": [{"message": {"content": ""}}]}).encode())
        with patch.object(images.urllib.request, "urlopen", side_effect=empty):
            self.assertIsNone(images.cf_vision(self.image, "Is it red?"))
            self.assertIsNone(images.cf_vision(self.image, "Is it red?"))
        self.assertEqual(self.calls, 2 * len(images.VISION_MODELS))


if __name__ == "__main__":
    unittest.main()

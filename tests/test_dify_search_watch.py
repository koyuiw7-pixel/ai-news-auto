"""変更検知の誤報・基準消失を防ぐ。外部接続なし。"""
import copy
import json
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import dify_search_watch as watch


class DifySearchWatchTest(unittest.TestCase):
    date1 = "2026-10-30T04:00:00+00:00"
    date2 = "2026-10-30T10:00:00+00:00"

    def release(self, body="Before upgrade, back up the database and files.", **extra):
        return json.dumps({"tag_name": "1.18.0", "name": "Release 1.18.0", "body": body,
                           "draft": False, "prerelease": False,
                           "html_url": "https://github.com/langgenius/dify/releases/tag/1.18.0", **extra}).encode()

    def docs(self, tail="* RAM >= 4 GiB"):
        return ("# Deploy Dify with Docker Compose\n\n## Before Deployment\n" + tail).encode()

    def model_providers(self, tail="Example model uses 2 AI credits per response."):
        return ("# Model Providers\n\n## Use Models with Your AI Credits\n" + tail
                + "\n## Use Your Own Account with a Supported Provider\nSet Usage Priority for your API key.\n").encode()

    def knowledge_limit(self, tail="Requests over the limit return 403 forbidden."):
        return ("# Knowledge Request Rate Limit\n\n## What Counts\nEach retrieval counts.\n"
                + "## When You Reach the Limit\n" + tail).encode()

    def fetcher(self, release=None, docs=None, model_providers=None, knowledge_limit=None):
        values = {
            "release": self.release() if release is None else release,
            "docker-compose": self.docs() if docs is None else docs,
            "model-providers": self.model_providers() if model_providers is None else model_providers,
            "knowledge-request-rate-limit": self.knowledge_limit() if knowledge_limit is None else knowledge_limit,
        }
        return lambda source: values[source["id"]]

    def baseline(self):
        return watch.run_watch({}, self.date1, self.fetcher())[0]

    def test_first_run_is_baseline_not_a_change_or_question(self):
        state, report = watch.run_watch({}, self.date1, self.fetcher())
        self.assertEqual([r["status"] for r in report["sources"]], ["baseline"] * 4)
        self.assertEqual(report["candidates"], [])
        self.assertEqual(len(state["sources"]), 4)

    def test_unchanged_ignores_download_counts_metadata_and_line_endings(self):
        state = self.baseline()
        body = "Before upgrade, back up the database and files.\r\n\r\n"
        _, report = watch.run_watch(state, self.date2, self.fetcher(self.release(body, assets=[{"download_count": 999}], updated_at=self.date2)))
        self.assertEqual([r["status"] for r in report["sources"]], ["unchanged"] * 4)
        self.assertEqual(report["candidates"], [])

    def test_changed_token_creates_review_evidence_and_keeps_queue(self):
        state = self.baseline()
        changed = self.release("Before upgrade, configure DIFY_AGENT_LOCAL_SANDBOX_AUTH_TOKEN; old runtimes are incompatible.")
        updated, report = watch.run_watch(state, self.date2, self.fetcher(changed))
        self.assertEqual(report["sources"][0]["status"], "changed")
        self.assertTrue(any("トークン" in item["question"] for item in report["candidates"]))
        item = report["candidates"][0]
        self.assertNotEqual(item["previousHash"], item["currentHash"])
        self.assertEqual(item["previousCheckedAt"], self.date1)
        self.assertEqual(item["status"], "needs_editorial_review")
        self.assertEqual(item["destination"], "/choose/dify-hosting")
        self.assertIn("DIFY_AGENT_LOCAL_SANDBOX_AUTH_TOKEN", item["evidenceAfter"])
        _, repeated = watch.run_watch(updated, self.date2, self.fetcher(changed))
        self.assertEqual(repeated["candidates"], [])
        self.assertEqual(repeated["reviewQueue"], report["candidates"])

    def test_failed_fetch_retains_previous_good_baseline(self):
        state = self.baseline()
        normal_fetch = self.fetcher()
        def failing(source):
            if source["id"] == "release":
                raise urllib.error.URLError("network unavailable")
            return normal_fetch(source)
        updated, report = watch.run_watch(state, self.date2, failing)
        self.assertEqual(updated["sources"]["release"], state["sources"]["release"])
        self.assertEqual(report["candidates"], [])
        self.assertTrue(report["errors"][0]["previousBaselineRetained"])

    def test_html_error_or_oversized_source_does_not_replace_baseline(self):
        state = self.baseline()
        for invalid in (b"<html>Service unavailable</html>", b"x" * (watch.MAX_BYTES + 1)):
            with self.subTest(size=len(invalid)):
                updated, report = watch.run_watch(state, self.date2, self.fetcher(docs=invalid))
                self.assertEqual(updated["sources"]["docker-compose"], state["sources"]["docker-compose"])
                self.assertEqual(len(report["errors"]), 1)

    def test_each_document_extracts_only_its_expected_body(self):
        fetch = self.fetcher()
        for source in watch.SOURCES[1:]:
            with self.subTest(source=source["id"]):
                raw = fetch(source)
                expected = watch.parse_source(source, raw)
                actual = watch.parse_source(source, b"> Documentation index changed\n\n" + raw)
                self.assertEqual(actual, expected)
                self.assertTrue(actual["text"].startswith("# " + watch.DOCUMENT_BODIES[source["id"]][0]))
                self.assertEqual(actual["sourceUrl"], source["publicUrl"])

    def test_wrong_page_or_missing_required_section_is_not_a_change(self):
        state = self.baseline()
        fetch = self.fetcher()
        for target in watch.SOURCES[1:]:
            heading, sections = watch.DOCUMENT_BODIES[target["id"]]
            invalid_responses = (
                b"# Unexpected page\nThe documentation is unavailable.",
                b"<html>Service unavailable</html>",
                ("# " + heading + "\nSome incomplete response\n").encode(),
                ("> " + sections[0] + "\n# " + heading + "\n" + "\n".join(sections[1:])).encode(),
            )
            for invalid in invalid_responses:
                with self.subTest(source=target["id"], invalid=invalid[:40]):
                    def failing(source):
                        return invalid if source["id"] == target["id"] else fetch(source)
                    updated, report = watch.run_watch(state, self.date2, failing)
                    self.assertEqual(updated["sources"][target["id"]], state["sources"][target["id"]])
                    self.assertEqual(report["candidates"], [])
                    self.assertEqual(report["errors"], [{"sourceId": target["id"], "error": "ValueError", "previousBaselineRetained": True}])

    def test_cost_changes_route_to_cost_guide_with_specific_questions(self):
        cases = (
            ("model-providers", {"model_providers": self.model_providers("Example model uses 3 AI credits per response.")}, "何回分"),
            ("model-providers", {"model_providers": self.model_providers("Check billing for your API key before execution.")}, "優先順位"),
            ("knowledge-request-rate-limit", {"knowledge_limit": self.knowledge_limit("Wait a full minute before retrying a refused request.")}, "403"),
        )
        for source_id, inputs, question_text in cases:
            with self.subTest(source=source_id, question=question_text):
                state = self.baseline()
                updated, report = watch.run_watch(state, self.date2, self.fetcher(**inputs))
                self.assertTrue(report["candidates"])
                self.assertTrue(any(question_text in c["question"] for c in report["candidates"]))
                for item in report["candidates"]:
                    self.assertEqual(item["sourceId"], source_id)
                    self.assertEqual(item["destination"], "/guides/dify-free-api-cost")
                    self.assertEqual(item["status"], "needs_editorial_review")
                    self.assertNotEqual(item["previousHash"], item["currentHash"])
                    self.assertTrue(item["evidenceBefore"])
                    self.assertTrue(item["evidenceAfter"])
                repeated, next_report = watch.run_watch(updated, self.date2, self.fetcher(**inputs))
                self.assertEqual(next_report["candidates"], [])
                self.assertEqual(repeated["reviewQueue"], updated["reviewQueue"])

    def test_compose_and_unclassified_cost_changes_keep_correct_destinations(self):
        for inputs, destination in (
            ({"docs": self.docs("* RAM >= 8 GiB")}, "/choose/dify-hosting"),
            ({"model_providers": self.model_providers() + b"\nNew explanatory paragraph."}, "/guides/dify-free-api-cost"),
            ({"knowledge_limit": self.knowledge_limit() + b"\nNew explanatory paragraph."}, "/guides/dify-free-api-cost"),
        ):
            with self.subTest(inputs=list(inputs)):
                _, report = watch.run_watch(self.baseline(), self.date2, self.fetcher(**inputs))
                self.assertTrue(report["candidates"])
                self.assertEqual({c["destination"] for c in report["candidates"]}, {destination})

    def test_same_hash_preserves_text_queue_and_only_refreshes_check_time(self):
        state = self.baseline()
        state["reviewQueue"] = [{"id": "existing-review", "status": "needs_editorial_review"}]
        before = copy.deepcopy(state)
        updated, report = watch.run_watch(state, self.date2, self.fetcher())
        self.assertEqual(state, before)
        self.assertEqual(updated["reviewQueue"], before["reviewQueue"])
        self.assertEqual(report["candidates"], [])
        for source_id, snapshot in before["sources"].items():
            self.assertEqual(updated["sources"][source_id], {**snapshot, "checkedAt": self.date2})

    def test_old_two_source_state_keeps_existing_baselines_queue_and_cache_key(self):
        # 変更前のworkflowで保存されたキー。資料追加で既存cacheを失わない。
        self.assertEqual(watch.SOURCE_FINGERPRINT, "bea8f580f106af9b")
        state = self.baseline()
        state["sources"] = {k: v for k, v in state["sources"].items() if k in {"release", "docker-compose"}}
        state["reviewQueue"] = [{"id": "old-review", "status": "needs_editorial_review"}]
        state["archivedCandidateCount"] = 7
        updated, report = watch.run_watch(state, self.date2, self.fetcher())
        self.assertFalse(report["baselineReset"])
        self.assertEqual([row["status"] for row in report["sources"]], ["unchanged", "unchanged", "baseline", "baseline"])
        self.assertEqual(report["candidates"], [])
        self.assertEqual(updated["reviewQueue"], state["reviewQueue"])
        self.assertEqual(updated["archivedCandidateCount"], 7)

    def test_added_source_failure_does_not_discard_old_state_or_create_candidate(self):
        state = self.baseline()
        del state["sources"]["model-providers"]
        updated, report = watch.run_watch(state, self.date2, self.fetcher(model_providers=b"unavailable"))
        self.assertNotIn("model-providers", updated["sources"])
        self.assertEqual(report["candidates"], [])
        self.assertEqual(report["errors"], [{"sourceId": "model-providers", "error": "ValueError", "previousBaselineRetained": False}])
        recovered, recovery = watch.run_watch(updated, self.date2, self.fetcher())
        self.assertEqual(recovery["sources"][2]["status"], "baseline")
        self.assertEqual(recovery["candidates"], [])

    def test_review_queue_is_bounded_and_existing_candidate_is_not_duplicated(self):
        state = self.baseline()
        fetch = self.fetcher(model_providers=self.model_providers("Example model uses 3 AI credits per response."))
        _, preview = watch.run_watch(state, self.date2, fetch)
        state["reviewQueue"] = [{"id": f"old-{i}"} for i in range(watch.MAX_QUEUE)]
        state["reviewQueue"].append(preview["candidates"][0])
        state["archivedCandidateCount"] = 4
        updated, report = watch.run_watch(state, self.date2, fetch)
        self.assertEqual(len(updated["reviewQueue"]), watch.MAX_QUEUE)
        self.assertEqual(len({item["id"] for item in updated["reviewQueue"]}), watch.MAX_QUEUE)
        self.assertEqual(updated["archivedCandidateCount"], 5)
        self.assertEqual(updated["reviewQueue"][-1]["id"], preview["candidates"][0]["id"])

    def test_draft_prerelease_and_wrong_repo_are_rejected(self):
        for extra in ({"draft": True}, {"prerelease": True}, {"html_url": "https://example.com/1.18.0"}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                watch.parse_source(watch.SOURCES[0], self.release(**extra))

    def test_source_set_change_rebaselines_instead_of_claiming_a_change(self):
        state = self.baseline()
        state["sourceFingerprint"] = "old-source-set"
        _, report = watch.run_watch(state, self.date2, self.fetcher())
        self.assertTrue(report["baselineReset"])
        self.assertEqual(report["candidates"], [])

    def test_redirect_to_other_host_or_plain_http_is_blocked(self):
        handler = watch.SameHostRedirect()
        request = urllib.request.Request(watch.SOURCES[0]["url"])
        for url in ("https://example.com/", "http://api.github.com/anything"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                handler.redirect_request(request, None, 302, "Found", {}, url)


if __name__ == "__main__":
    unittest.main()

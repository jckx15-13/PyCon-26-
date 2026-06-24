from __future__ import annotations

import io
import json
import os
import threading
import time
import unittest
import urllib.error
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path

import backend.app as app_module
from backend.app import DATA, Handler, _join_threads_until_deadline
from backend.connectors import DataGovCourseDirectoryClient, _xlsx_dict_rows
from backend.recommendation_engine import build_recommendation


class SkillQuestApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def post_json(self, path: str, body: bytes, content_type: str = "application/json") -> tuple[int, dict]:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            method="POST",
            headers={"Content-Type": content_type},
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            try:
                return error.code, json.loads(error.read().decode("utf-8"))
            finally:
                error.close()

    def get_json(self, path: str) -> tuple[int, dict]:
        with urllib.request.urlopen(f"{self.base_url}{path}", timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_malformed_json_returns_400(self) -> None:
        status, payload = self.post_json("/api/recommend", b"{bad json")
        self.assertEqual(status, 400)
        self.assertIn("valid JSON", payload["error"])

    def test_demo_recommendation_uses_private_offline_sources(self) -> None:
        request_payload = {
            "demo": True,
            "mode": "explorer",
            "interests": ["Design", "Helping people"],
            "targetRole": "",
            "skills": ["Customer Service", "Presentation"],
            "weeklyHours": 2,
            "budget": 100,
            "learningMode": "Online",
            "location": "Tampines MRT",
            "allowLiveData": False,
        }
        status, payload = self.post_json("/api/recommend", json.dumps(request_payload).encode("utf-8"))
        self.assertEqual(status, 200)
        sources = {source["name"]: source["status"] for source in payload["sourceSummary"]}
        self.assertEqual(sources["MyCareersFuture"], "offline")
        self.assertIn("confidence", payload)
        self.assertIn("explanation", payload)

    def test_recommendation_includes_skillsfuture_dataset_evidence(self) -> None:
        request_payload = {
            "demo": True,
            "mode": "pathfinder",
            "interests": ["Technology", "Data"],
            "targetRole": "Cybersecurity Associate",
            "skills": ["Customer Service", "Documentation"],
            "weeklyHours": 5,
            "budget": 500,
            "learningMode": "Blended",
            "location": "Tampines MRT",
            "allowLiveData": False,
        }
        status, payload = self.post_json("/api/recommend", json.dumps(request_payload).encode("utf-8"))
        self.assertEqual(status, 200)
        framework = payload["recommendedRole"]["framework"]
        self.assertEqual(framework["name"], "Singapore SkillsFuture Jobs-Skills dataset slice")
        self.assertGreaterEqual(len(framework["officialRoles"]), 1)
        self.assertGreaterEqual(framework["recordCounts"]["uniqueSkills"], 2000)
        evidence = [
            gap.get("frameworkEvidence")
            for gap in payload["skillGaps"]
            if gap.get("frameworkEvidence", {}).get("officialSkill")
        ]
        self.assertTrue(evidence)

    def test_options_and_head_are_supported(self) -> None:
        options_request = urllib.request.Request(f"{self.base_url}/api/recommend", method="OPTIONS")
        with urllib.request.urlopen(options_request, timeout=5) as response:
            self.assertEqual(response.status, 204)
            self.assertIn("POST", response.headers["Allow"])

        head_request = urllib.request.Request(f"{self.base_url}/api/health", method="HEAD")
        with urllib.request.urlopen(head_request, timeout=5) as response:
            self.assertEqual(response.status, 200)

    def test_frontend_announces_status_and_bounds_fetch_waits(self) -> None:
        index_html = Path("static/index.html").read_text(encoding="utf-8")
        app_js = Path("static/app.js").read_text(encoding="utf-8")

        self.assertIn('id="form-status"', index_html)
        self.assertIn('role="status"', index_html)
        self.assertIn('aria-describedby="form-status"', index_html)
        self.assertIn("AbortController", app_js)
        self.assertIn("Request took too long", app_js)
        self.assertIn("setFormStatus", app_js)
        self.assertIn("aria-busy", app_js)

    def test_frontend_keeps_results_simple_with_optional_details(self) -> None:
        index_html = Path("static/index.html").read_text(encoding="utf-8")
        app_js = Path("static/app.js").read_text(encoding="utf-8")

        self.assertIn('id="simple-confidence"', index_html)
        self.assertIn('id="result-details"', index_html)
        self.assertIn("<summary>Show why and other choices</summary>", index_html)
        self.assertEqual(index_html.count('id="confidence-line"'), 1)
        self.assertEqual(index_html.count('id="why-list"'), 1)
        self.assertIn("details.open = false", app_js)
        self.assertIn("openResultDetails", app_js)

    def test_ai_status_is_local_and_does_not_require_key(self) -> None:
        status, payload = self.get_json("/api/ai/status")
        self.assertEqual(status, 200)
        self.assertEqual(payload["provider"], "local-deterministic")
        self.assertFalse(payload["requiresApiKey"])
        self.assertGreaterEqual(payload["examples"], 5)

    def test_google_mentor_takes_precedence_when_configured(self) -> None:
        originals = {
            "SKILLQUEST_ENABLE_GOOGLE_MENTOR": os.environ.get("SKILLQUEST_ENABLE_GOOGLE_MENTOR"),
            "GOOGLE_CLOUD_AI_API_KEY": os.environ.get("GOOGLE_CLOUD_AI_API_KEY"),
            "SKILLQUEST_ENABLE_OPENAI_MENTOR": os.environ.get("SKILLQUEST_ENABLE_OPENAI_MENTOR"),
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
        }
        os.environ["SKILLQUEST_ENABLE_GOOGLE_MENTOR"] = "true"
        os.environ["GOOGLE_CLOUD_AI_API_KEY"] = "demo_google_key"
        os.environ["SKILLQUEST_ENABLE_OPENAI_MENTOR"] = "true"
        os.environ["OPENAI_API_KEY"] = "demo_openai_key"

        try:
            status, payload = self.get_json("/api/ai/status")
            self.assertEqual(status, 200)
            self.assertEqual(payload["provider"], "google-cloud-live")
            self.assertTrue(payload["googleEnabled"])
            self.assertTrue(payload["googleKeyPresent"])
            self.assertFalse(payload["openaiEnabled"])
        finally:
            for key, value in originals.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_integrations_report_safe_readiness_without_secrets(self) -> None:
        status, payload = self.get_json("/api/integrations")
        self.assertEqual(status, 200)
        self.assertTrue(payload["summary"]["demoSafe"])
        integrations = {item["id"]: item for item in payload["integrations"]}
        self.assertIn("mycareersfuture", integrations)
        self.assertIn("data-gov-course-directory", integrations)
        self.assertTrue(integrations["mycareersfuture"]["requiresConsent"])
        self.assertGreaterEqual(integrations["skills-framework"]["records"]["uniqueSkills"], 2000)
        self.assertEqual(integrations["data-gov-course-directory"]["status"], "cached")
        self.assertGreaterEqual(integrations["data-gov-course-directory"]["records"]["loaded"], 1)
        self.assertGreaterEqual(payload["summary"]["exactCourseLinks"], 1)
        self.assertEqual(integrations["local-mentor"]["status"], "local-deterministic")
        for item in payload["integrations"]:
            for env_var in item.get("envVars", []):
                self.assertEqual(set(env_var.keys()), {"name", "present"})

    def test_direct_live_endpoints_require_explicit_non_demo_consent(self) -> None:
        status, jobs = self.get_json("/api/jobs?query=Data%20Analyst")
        self.assertEqual(status, 200)
        self.assertEqual(jobs["status"], "offline")
        self.assertEqual(jobs["source"], "Local role skill signals")
        self.assertIn("Live job lookup was not used", jobs["detail"])

        status, location = self.get_json("/api/location?query=Tampines%20MRT")
        self.assertEqual(status, 200)
        self.assertEqual(location["status"], "offline")
        self.assertEqual(location["source"], "Local location estimate")

        status, demo_jobs = self.get_json("/api/jobs?query=Data%20Analyst&allowLiveData=true&demo=1")
        self.assertEqual(status, 200)
        self.assertEqual(demo_jobs["status"], "offline")

        status, demo_location = self.get_json("/api/location?query=Tampines%20MRT&live=1&demo=true")
        self.assertEqual(status, 200)
        self.assertEqual(demo_location["status"], "offline")

    def test_live_recommendation_uses_shared_deadline_for_job_and_location(self) -> None:
        original_timeout = app_module.LIVE_API_TIMEOUT_SECONDS
        original_market = Handler._merge_job_signals
        original_location = Handler._location_signal

        def slow_market(self: Handler, query: str, limit: int) -> dict:
            time.sleep(0.25)
            return {"status": "ok", "source": "slow market", "items": [], "top_skills": []}

        def slow_location(self: Handler, query: str) -> dict:
            time.sleep(0.25)
            return {"status": "ok", "source": "slow location", "items": []}

        app_module.LIVE_API_TIMEOUT_SECONDS = 0.05
        Handler._merge_job_signals = slow_market
        Handler._location_signal = slow_location
        try:
            request_payload = {
                "demo": False,
                "mode": "pathfinder",
                "interests": ["Data"],
                "targetRole": "Data Analyst",
                "skills": ["Excel"],
                "weeklyHours": 3,
                "budget": 100,
                "learningMode": "Online",
                "location": "Tampines MRT",
                "allowLiveData": True,
            }
            started = time.time()
            status, payload = self.post_json("/api/recommend", json.dumps(request_payload).encode("utf-8"))
            elapsed = time.time() - started
        finally:
            app_module.LIVE_API_TIMEOUT_SECONDS = original_timeout
            Handler._merge_job_signals = original_market
            Handler._location_signal = original_location

        self.assertEqual(status, 200)
        self.assertLess(elapsed, 0.35)
        sources = {source["name"]: source["status"] for source in payload["sourceSummary"]}
        self.assertEqual(sources["MyCareersFuture"], "offline")
        self.assertEqual(sources["OneMap"], "offline")
        self.assertIn("timed out", payload["sourceSummary"][2]["detail"])

    def test_local_mentor_returns_two_hour_plan_without_key(self) -> None:
        request_payload = {
            "demo": True,
            "mode": "explorer",
            "interests": ["Data", "Technology"],
            "targetRole": "",
            "skills": ["Excel", "Customer Service"],
            "weeklyHours": 2,
            "budget": 100,
            "learningMode": "Online",
            "location": "Tampines MRT",
            "allowLiveData": False,
        }
        _, recommendation = self.post_json("/api/recommend", json.dumps(request_payload).encode("utf-8"))
        status, mentor = self.post_json(
            "/api/mentor",
            json.dumps({"action": "two_hours", "recommendation": recommendation}).encode("utf-8"),
        )
        self.assertEqual(status, 200)
        self.assertEqual(mentor["provider"], "local-deterministic")
        self.assertEqual(mentor["action"], "two_hours")
        self.assertGreaterEqual(len(mentor["steps"]), 3)
        self.assertEqual(mentor["grounding"]["examplesMatched"], 1)
        self.assertEqual(mentor["grounding"]["skillsFramework"]["source"], "Singapore SkillsFuture Jobs-Skills dataset slice")
        self.assertGreaterEqual(len(mentor["grounding"]["skillsFramework"]["officialRoles"]), 1)
        self.assertIn("SkillsFuture skill", " ".join(mentor["steps"]))

    def test_local_mentor_why_uses_skillsfuture_evidence(self) -> None:
        request_payload = {
            "demo": True,
            "mode": "pathfinder",
            "interests": ["Technology", "Data"],
            "targetRole": "Cybersecurity Associate",
            "skills": ["Customer Service", "Documentation"],
            "weeklyHours": 5,
            "budget": 500,
            "learningMode": "Blended",
            "location": "Tampines MRT",
            "allowLiveData": False,
        }
        _, recommendation = self.post_json("/api/recommend", json.dumps(request_payload).encode("utf-8"))
        status, mentor = self.post_json(
            "/api/mentor",
            json.dumps({"action": "why", "recommendation": recommendation}).encode("utf-8"),
        )
        self.assertEqual(status, 200)
        self.assertIn("SkillsFuture", mentor["summary"])
        self.assertTrue(any("SkillsFuture role check" in step for step in mentor["steps"]))
        self.assertGreaterEqual(len(mentor["grounding"]["skillsFramework"]["officialSkills"]), 1)

    def test_local_mentor_answers_bounded_learner_question(self) -> None:
        request_payload = {
            "demo": True,
            "mode": "explorer",
            "interests": ["Data", "Technology"],
            "targetRole": "",
            "skills": ["Excel", "Customer Service"],
            "weeklyHours": 3,
            "budget": 0,
            "learningMode": "Online",
            "location": "Tampines MRT",
            "allowLiveData": False,
        }
        _, recommendation = self.post_json("/api/recommend", json.dumps(request_payload).encode("utf-8"))
        status, mentor = self.post_json(
            "/api/mentor",
            json.dumps(
                {
                    "action": "plain",
                    "question": "Can I do this with no money?",
                    "recommendation": recommendation,
                    "requestMode": "learner-question",
                }
            ).encode("utf-8"),
        )
        self.assertEqual(status, 200)
        self.assertEqual(mentor["provider"], "local-deterministic")
        self.assertEqual(mentor["action"], "plain")
        self.assertIn("About your question", mentor["summary"])
        self.assertIn("Can I do this with no money?", mentor["summary"])
        self.assertEqual(mentor["grounding"]["skillsFramework"]["source"], "Singapore SkillsFuture Jobs-Skills dataset slice")
        self.assertGreaterEqual(len(mentor["grounding"]["skillsFramework"]["officialSkills"]), 1)

    def test_local_mentor_rejects_unknown_action(self) -> None:
        status, payload = self.post_json(
            "/api/mentor",
            json.dumps({"action": "magic", "recommendation": {}}).encode("utf-8"),
        )
        self.assertEqual(status, 400)
        self.assertIn("Unsupported mentor action", payload["error"])

    def test_data_gov_xlsx_rows_preserve_blank_cells_and_normalise_course(self) -> None:
        blob = _minimal_xlsx(
            """
            <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
              <sheetData>
                <row r="1">
                  <c r="A1" t="inlineStr"><is><t>coursereferencenumber</t></is></c>
                  <c r="B1" t="inlineStr"><is><t>coursetitle</t></is></c>
                  <c r="D1" t="inlineStr"><is><t>trainingprovideralias</t></is></c>
                  <c r="E1" t="inlineStr"><is><t>full_course_fee</t></is></c>
                  <c r="F1" t="inlineStr"><is><t>course_fee_after_subsidies</t></is></c>
                  <c r="G1" t="inlineStr"><is><t>number_of_hours</t></is></c>
                  <c r="H1" t="inlineStr"><is><t>about_this_course</t></is></c>
                </row>
                <row r="2">
                  <c r="A2" t="inlineStr"><is><t>TGS-TEST</t></is></c>
                  <c r="B2" t="inlineStr"><is><t>Python Data Starter</t></is></c>
                  <c r="D2" t="inlineStr"><is><t>TEST POLY</t></is></c>
                  <c r="E2"><v>1000</v></c>
                  <c r="F2"><v>400</v></c>
                  <c r="G2"><v>12</v></c>
                  <c r="H2" t="inlineStr"><is><t>Learn Python, analytics, and dashboards.</t></is></c>
                </row>
              </sheetData>
            </worksheet>
            """
        )
        rows = _xlsx_dict_rows(blob)
        self.assertEqual(rows[0]["trainingprovideralias"], "TEST POLY")

        course = DataGovCourseDirectoryClient()._normalise_course(rows[0])
        self.assertEqual(course["id"], "data-gov-tgs-test")
        self.assertIn("Python Automation", course["skills"])
        self.assertIn("courseReferenceNumber=TGS-TEST", course["source_url"])

    def test_thread_join_uses_shared_deadline(self) -> None:
        threads = [threading.Thread(target=time.sleep, args=(0.2,)) for _ in range(2)]
        for thread in threads:
            thread.start()
        started = time.time()
        _join_threads_until_deadline(threads, 0.04)
        elapsed = time.time() - started
        for thread in threads:
            thread.join()
        self.assertLess(elapsed, 0.16)


class RecommendationEngineTests(unittest.TestCase):
    def recommend(self, payload: dict) -> dict:
        market_signal = {
            "status": "offline",
            "top_skills": [{"name": "User Research", "demand": 5}, {"name": "Wireframing", "demand": 4}],
            "items": [],
        }
        location_signal = {"status": "offline", "items": [{"lat": 1.3547, "lng": 103.9451, "address": "Tampines MRT"}]}
        return build_recommendation(
            payload,
            roles=DATA.roles,
            courses=DATA.courses,
            funding_rules=DATA.funding_rules,
            skills_framework=DATA.skills_framework,
            market_signal=market_signal,
            location_signal=location_signal,
        )

    def test_explorer_mode_does_not_force_default_target_role(self) -> None:
        payload = {
            "mode": "explorer",
            "targetRole": "Cybersecurity Associate",
            "interests": ["Design", "Helping people"],
            "skills": ["Customer Service", "Presentation"],
            "weeklyHours": 4,
            "budget": 400,
            "learningMode": "Blended",
            "location": "Tampines MRT",
        }
        result = self.recommend(payload)
        self.assertEqual(result["recommendedRole"]["title"], "UX Designer")

    def test_pathfinder_mode_can_honor_target_role(self) -> None:
        payload = {
            "mode": "pathfinder",
            "targetRole": "Cybersecurity Associate",
            "interests": ["Design", "Helping people"],
            "skills": ["Customer Service", "Presentation"],
            "weeklyHours": 4,
            "budget": 400,
            "learningMode": "Blended",
            "location": "Tampines MRT",
        }
        result = self.recommend(payload)
        self.assertEqual(result["recommendedRole"]["title"], "Cybersecurity Associate")

    def test_course_match_is_capped_when_top_gap_is_not_covered(self) -> None:
        payload = {
            "mode": "pathfinder",
            "targetRole": "Data Analyst",
            "interests": ["Data"],
            "skills": ["Excel"],
            "weeklyHours": 20,
            "budget": 5000,
            "learningMode": "Online",
            "location": "Tampines MRT",
        }
        result = self.recommend(payload)
        self.assertLessEqual(max(course["match_score"] for course in result["recommendedCourses"]), 88)
        self.assertTrue(all("whyChosen" in course for course in result["recommendedCourses"]))

def _minimal_xlsx(sheet_xml: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buffer.getvalue()


if __name__ == "__main__":
    unittest.main()

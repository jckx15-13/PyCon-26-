from __future__ import annotations

import json
import mimetypes
import os
import socket
import sys
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.connectors import (
    ApifyJobClient,
    DataGovCourseDirectoryClient,
    ExternalCourseDatasetClient,
    GoogleCloudGeocodeClient,
    MyCareersFutureClient,
    load_data_gov_course_cache,
    OneMapClient,
    load_json,
)
from backend.ai_mentor import MentorInputError, mentor_reply, mentor_status
from backend.integrations import integration_readiness
from backend.recommendation_engine import build_recommendation


ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"
DATA_DIR = ROOT / "data"
DATA_GOV_COURSE_CACHE = DATA_DIR / "course_directory_cache.json"
DEFAULT_PORT = int(os.getenv("PORT", "8000"))
MAX_JSON_BYTES = int(os.getenv("SKILLQUEST_MAX_JSON_BYTES", "32768"))
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("SKILLQUEST_RATE_LIMIT", "90"))
LIVE_API_TIMEOUT_SECONDS = float(os.getenv("SKILLQUEST_LIVE_TIMEOUT_SECONDS", "6.5"))
LIVE_CACHE_TTL_SECONDS = int(os.getenv("SKILLQUEST_LIVE_CACHE_SECONDS", "120"))
RATE_LIMIT_BUCKETS: dict[str, list[float]] = {}
JOB_SIGNAL_CACHE: dict[str, dict[str, Any]] = {}
LOCATION_SIGNAL_CACHE: dict[str, dict[str, Any]] = {}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    ),
}


class SkillQuestData:
    def __init__(self) -> None:
        self.roles = load_json(DATA_DIR / "roles.json")
        self.courses = load_json(DATA_DIR / "courses.json")
        self.funding_rules = load_json(DATA_DIR / "funding_rules.json")
        self.skills_framework = load_json(DATA_DIR / "skills_framework.json")
        external = ExternalCourseDatasetClient().fetch(os.getenv("COURSE_DATA_URL"))
        self.external_course_status = external
        if external.get("items"):
            self._extend_courses(external["items"])
        cached_data_gov = load_data_gov_course_cache(DATA_GOV_COURSE_CACHE)
        if cached_data_gov.get("items"):
            self._extend_courses(cached_data_gov["items"])
        data_gov = DataGovCourseDirectoryClient().fetch()
        if data_gov.get("items"):
            self._extend_courses(data_gov["items"])
            self.data_gov_course_status = data_gov
        elif data_gov.get("status") == "skipped" and cached_data_gov.get("items"):
            self.data_gov_course_status = cached_data_gov
        elif cached_data_gov.get("items") and data_gov.get("status") == "unavailable":
            self.data_gov_course_status = {
                **cached_data_gov,
                "status": "cached_fallback",
                "liveImportError": data_gov.get("error"),
                "detail": "Loaded cached public course rows because the live data.gov.sg import was unavailable.",
            }
        else:
            self.data_gov_course_status = data_gov

    def _extend_courses(self, items: list[dict[str, Any]]) -> None:
        seen = {course.get("id") for course in self.courses}
        for item in items:
            course_id = item.get("id")
            if course_id and course_id in seen:
                continue
            self.courses.append(item)
            if course_id:
                seen.add(course_id)

    def options(self) -> dict:
        mentor = mentor_status(DATA_DIR)
        interests = sorted({interest for role in self.roles for interest in role.get("interests", [])})
        skills = sorted({skill["name"] for role in self.roles for skill in role.get("required_skills", [])})
        return {
            "app": "SkillQuest",
            "roles": [{"id": role["id"], "title": role["title"], "category": role["category"], "description": role["description"]} for role in self.roles],
            "interests": interests,
            "skills": skills,
            "learningModes": ["Online", "Blended", "Physical"],
            "schedules": ["Evenings", "Weekends", "Weekdays", "Flexible"],
            "locations": ["Central", "East", "West", "North", "Online", "Tampines MRT", "Jurong East MRT", "Woodlands MRT"],
            "courseCount": len(self.courses),
            "skillsFramework": {
                "status": "local-normalised",
                "name": self.skills_framework.get("name"),
                "sourceUrl": self.skills_framework.get("source_url"),
                "lastReviewed": self.skills_framework.get("last_reviewed"),
                "rolesMapped": len(self.skills_framework.get("role_mappings", {})),
            },
            "sources": {
                "localRoles": "ok",
                "localCourses": "ok",
                "skillsFramework": "local-normalised",
                "externalCourseDataset": self.external_course_status.get("status"),
                "dataGovCourseDirectory": self.data_gov_course_status.get("status"),
                "myCareersFuture": "opt-in live lookup",
                "oneMap": "opt-in live lookup",
                "apifyJobs": "opt-in live lookup",
                "googleCloudMaps": "opt-in live lookup",
                "localMentor": mentor.get("provider", "local-deterministic"),
            },
        }

    def integrations(self) -> dict:
        return integration_readiness(self, mentor_status(DATA_DIR))


DATA = SkillQuestData()
JOBS = MyCareersFutureClient()
ONEMAP = OneMapClient()
APIFY_JOBS = ApifyJobClient()
GOOGLE_MAPS = GoogleCloudGeocodeClient()


class Handler(BaseHTTPRequestHandler):
    server_version = "SkillQuestHTTP/0.1"

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._json({"status": "ok"}, head_only=True)
            return
        self._static(parsed.path, head_only=True)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_common_headers()
        self.send_header("Allow", "GET, POST, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        if not self._rate_limit_ok():
            self._json({"error": "Too many requests. Please wait a moment and try again."}, status=429)
            return
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        if path == "/api/health":
            self._json(
                {
                    "status": "ok",
                    "roles": len(DATA.roles),
                    "courses": len(DATA.courses),
                    "skillsFramework": DATA.skills_framework.get("status", "local-normalised"),
                    "externalCourseDataset": DATA.external_course_status.get("status"),
                    "dataGovCourseDirectory": DATA.data_gov_course_status.get("status"),
                    "demoSafe": DATA.integrations()["summary"]["demoSafe"],
                }
            )
            return

        if path == "/api/options":
            self._json(DATA.options())
            return

        if path == "/api/jobs":
            search = query.get("query", ["data analyst"])[0]
            if _query_allows_live_data(query):
                self._json(self._merge_job_signals(search, limit=5))
            else:
                self._json(self._offline_market_signal(search))
            return

        if path == "/api/location":
            search = query.get("query", [""])[0]
            if _query_allows_live_data(query):
                self._json(self._location_signal(search))
            else:
                self._json(self._offline_location_signal(search))
            return

        if path == "/api/sources":
            mentor = DATA.integrations().get("aiProvider", "local-deterministic")
            self._json(
                {
                    "sources": DATA.options()["sources"],
                    "notes": [
                        "Course data uses local seed JSON unless COURSE_DATA_URL is set.",
                        "Skills Framework mappings are a local normalised slice from public Singapore Skills Framework references.",
                        "MyCareersFuture, Apify, OneMap, and Google Cloud geocode calls require explicit non-demo live consent.",
                        f"Mentor mode is {mentor}.",
                    ],
                    "skillsFramework": DATA.options()["skillsFramework"],
                    "integrations": DATA.integrations()["summary"],
                }
            )
            return

        if path == "/api/ai/status":
            self._json(mentor_status(DATA_DIR))
            return

        if path == "/api/integrations":
            self._json(DATA.integrations())
            return

        self._static(path)

    def do_POST(self) -> None:
        if not self._rate_limit_ok():
            self._json({"error": "Too many requests. Please wait a moment and try again."}, status=429)
            return
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/recommend", "/api/mentor"}:
            self._json({"error": "Not found"}, status=404)
            return

        payload, error = self._read_json()
        if error:
            self._json({"error": error}, status=400)
            return

        if parsed.path == "/api/mentor":
            try:
                self._json(mentor_reply(payload, DATA_DIR))
            except MentorInputError as exc:
                self._json({"error": str(exc)}, status=400)
            return

        search_query = payload.get("targetRole") or payload.get("target_role")
        if not search_query:
            interests = payload.get("interests") or []
            search_query = " ".join(interests[:2]) if isinstance(interests, list) else str(interests)
        allow_live_data = bool(payload.get("allowLiveData")) and not bool(payload.get("demo"))
        if allow_live_data:
            market_signal = self._merge_job_signals(search_query or "data analyst", limit=5)
            location_signal = self._location_signal(payload.get("location", ""))
        else:
            market_signal = self._offline_market_signal(search_query or "data analyst")
            location_signal = self._offline_location_signal(payload.get("location", ""))
        recommendation = build_recommendation(
            payload,
            roles=DATA.roles,
            courses=DATA.courses,
            funding_rules=DATA.funding_rules,
            skills_framework=DATA.skills_framework,
            market_signal=market_signal,
            location_signal=location_signal,
        )
        self._json(recommendation)

    def _read_json(self) -> tuple[dict, str | None]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return {}, "Malformed Content-Length header."
        if length <= 0:
            return {}, None
        if length > MAX_JSON_BYTES:
            return {}, f"Request body is too large. Limit is {MAX_JSON_BYTES} bytes."
        try:
            body = self.rfile.read(length).decode("utf-8")
        except UnicodeDecodeError:
            return {}, "Request body must be valid UTF-8 JSON."
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            return {}, "Request body must be valid JSON."
        if not isinstance(parsed, dict):
            return {}, "Request body must be a JSON object."
        return parsed, None

    def _json(self, payload: dict, status: int = 200, head_only: bool = False) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self._send_common_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        try:
            self.end_headers()
            if not head_only:
                self.wfile.write(encoded)
        except (BrokenPipeError, ConnectionResetError, socket.error):
            return

    def _static(self, path: str, head_only: bool = False) -> None:
        if path in {"", "/"}:
            target = STATIC_DIR / "index.html"
        else:
            clean = path.lstrip("/")
            target = (STATIC_DIR / clean).resolve()
        if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.is_file():
            self._json({"error": "Not found"}, status=404)
            return
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(200)
        self._send_common_headers(cache="no-store")
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        try:
            self.end_headers()
            if not head_only:
                self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, socket.error):
            return

    def _send_common_headers(self, cache: str = "no-store") -> None:
        self.send_header("Cache-Control", cache)
        for header, value in SECURITY_HEADERS.items():
            self.send_header(header, value)

    def _rate_limit_ok(self) -> bool:
        forwarded = self.headers.get("X-Forwarded-For", "")
        client = forwarded.split(",")[0].strip() or self.client_address[0]
        now = time.time()
        bucket = [stamp for stamp in RATE_LIMIT_BUCKETS.get(client, []) if now - stamp < RATE_LIMIT_WINDOW_SECONDS]
        if len(bucket) >= RATE_LIMIT_MAX_REQUESTS:
            RATE_LIMIT_BUCKETS[client] = bucket
            return False
        bucket.append(now)
        RATE_LIMIT_BUCKETS[client] = bucket
        return True

    def _offline_market_signal(self, query: str) -> dict:
        query_key = query.lower()
        skill_counts: dict[str, int] = {}
        matched_roles = []
        for role in DATA.roles:
            role_text = " ".join([role.get("title", ""), role.get("category", ""), *role.get("interests", [])]).lower()
            if not query_key or any(part in role_text for part in query_key.split()):
                matched_roles.append(role.get("title"))
                for skill in role.get("required_skills", [])[:4]:
                    skill_counts[skill["name"]] = skill_counts.get(skill["name"], 0) + skill.get("importance", 1)
        if not skill_counts:
            for role in DATA.roles[:3]:
                for skill in role.get("required_skills", [])[:3]:
                    skill_counts[skill["name"]] = skill_counts.get(skill["name"], 0) + skill.get("importance", 1)
        top_skills = sorted(skill_counts.items(), key=lambda item: item[1], reverse=True)[:12]
        return {
            "status": "offline",
            "source": "Local role skill signals",
            "url": None,
            "total": len(matched_roles),
            "items": [{"title": title} for title in matched_roles[:5]],
            "top_skills": [{"name": name, "demand": count} for name, count in top_skills],
            "latency_ms": 0,
            "detail": "Live job lookup was not used. Using local role-skill signals for a fast private demo.",
        }

    def _merge_job_signals(self, query: str, limit: int) -> dict:
        normalized_query = str(query or "").strip().lower()
        cache_key = f"{normalized_query}:{max(1, min(limit, 20))}"
        cached = _cache_get(JOB_SIGNAL_CACHE, cache_key)
        if cached is not None:
            return cached

        primary_state: dict[str, Any] = {}
        extras_state: dict[str, Any] = {}

        primary_thread = threading.Thread(
            target=_run_with_timeout,
            args=(JOBS.search_jobs, primary_state, normalized_query, limit, "MyCareersFuture"),
            daemon=True,
        )
        extras_thread = threading.Thread(
            target=_run_with_timeout,
            args=(APIFY_JOBS.search_jobs, extras_state, normalized_query, limit, "Apify"),
            daemon=True,
        )
        primary_thread.start()
        extras_thread.start()
        _join_threads_until_deadline([primary_thread, extras_thread], LIVE_API_TIMEOUT_SECONDS)

        primary = _safe_call_result(primary_state, "MyCareersFuture")
        extras = _safe_call_result(extras_state, "Apify")
        sources = []
        total = 0
        all_items: list[dict] = []
        skill_counter: dict[str, int] = {}
        for block in (primary, extras):
            if not isinstance(block, dict):
                continue
            sources.append(
                {
                    "source": block.get("source", "unknown"),
                    "status": block.get("status"),
                    "count": len(block.get("items", []) or []),
                    "error": block.get("error"),
                }
            )
            if block.get("status") in {"ok", "empty"}:
                total += int(block.get("total", len(block.get("items", []) or [])))
                for skill in block.get("top_skills", []) or []:
                    name = str(skill.get("name", "")).strip()
                    if not name:
                        continue
                    demand = int(skill.get("demand", 0))
                    skill_counter[name] = skill_counter.get(name, 0) + demand
                for item in block.get("items", []) or []:
                    item_with_source = dict(item)
                    item_with_source["source"] = block.get("source", "unknown")
                    all_items.append(item_with_source)

        merged_skills = [
            {"name": name, "demand": demand}
            for name, demand in sorted(skill_counter.items(), key=lambda pair: pair[1], reverse=True)[:12]
        ]
        status = "ok" if all_items else "offline"
        warning = None
        if primary.get("status") == "unavailable" and extras.get("status") == "unavailable":
            status = "unavailable"
            warning = primary.get("error") or extras.get("error") or "No live market signal was available."
        merged = {
            "status": status,
            "source": "MyCareersFuture + Apify",
            "url": primary.get("url") or extras.get("url"),
            "total": total,
            "items": all_items[:limit],
            "top_skills": merged_skills,
            "sources": sources,
            "warning": warning,
            "latency_ms": max(int(primary.get("latency_ms", 0) or 0), int(extras.get("latency_ms", 0) or 0)),
            "detail": "Combined signals from MyCareersFuture and Apify where available.",
        }
        _cache_set(JOB_SIGNAL_CACHE, cache_key, merged)
        return merged

    def _offline_location_signal(self, query: str) -> dict:
        if not query:
            return {"status": "skipped", "source": "Local location estimate", "items": []}
        known = {
            "tampines": {"label": "Tampines MRT", "address": "Tampines MRT", "lat": 1.3547, "lng": 103.9451},
            "jurong": {"label": "Jurong East MRT", "address": "Jurong East MRT", "lat": 1.3331, "lng": 103.7423},
            "woodlands": {"label": "Woodlands MRT", "address": "Woodlands MRT", "lat": 1.4369, "lng": 103.7865},
            "central": {"label": "Central Singapore", "address": "Central Singapore", "lat": 1.3048, "lng": 103.8318},
        }
        key = next((name for name in known if name in str(query).lower()), None)
        item = known.get(key)
        return {
            "status": "offline" if item else "unresolved",
            "source": "Local location estimate",
            "url": None,
            "warning": None if item else "Location was not sent to OneMap. Using course region estimates.",
            "items": [item] if item else [],
        }

    def _location_signal(self, query: str) -> dict:
        if not query:
            return {"status": "skipped", "source": "Local location estimate", "items": []}

        normalized = str(query).strip().lower()
        cached = _cache_get(LOCATION_SIGNAL_CACHE, normalized)
        if cached is not None:
            return cached

        onemap_state: dict[str, Any] = {}
        google_state: dict[str, Any] = {}
        onemap_thread = threading.Thread(
            target=_run_with_timeout,
            args=(ONEMAP.search, onemap_state, query, None, "OneMap"),
            daemon=True,
        )
        google_thread = threading.Thread(
            target=_run_with_timeout,
            args=(GOOGLE_MAPS.search, google_state, query, None, "Google Maps"),
            daemon=True,
        )
        onemap_thread.start()
        google_thread.start()
        _join_threads_until_deadline([onemap_thread, google_thread], LIVE_API_TIMEOUT_SECONDS)

        onemap_signal = _safe_call_result(onemap_state, "OneMap", allow_missing=True)
        google_signal = _safe_call_result(google_state, "Google Maps", allow_missing=True)
        if onemap_signal.get("status") == "ok":
            signal = onemap_signal
        elif google_signal.get("status") == "ok":
            signal = google_signal
        elif google_signal.get("status") == "unavailable" and onemap_signal.get("status") == "unavailable":
            signal = google_signal
        else:
            signal = onemap_signal
        signal["latency_ms"] = max(
            int(onemap_signal.get("latency_ms", 0) or 0),
            int(google_signal.get("latency_ms", 0) or 0),
            int(signal.get("latency_ms", 0) or 0),
        )

        _cache_set(LOCATION_SIGNAL_CACHE, normalized, signal)
        return signal

    def log_message(self, format: str, *args: object) -> None:
        print(json.dumps({"client": self.client_address[0], "message": format % args}, ensure_ascii=False))


def _run_with_timeout(
    fn: Any,
    target: dict[str, Any],
    query: str,
    limit: int | None,
    label: str,
) -> None:
    started = time.time()
    try:
        if limit is None:
            result = fn(query)
        else:
            result = fn(query, limit=limit)
    except Exception as exc:  # pragma: no cover - external failures vary
        result = {
            "status": "unavailable",
            "source": label,
            "url": "",
            "error": str(exc),
            "items": [],
            "top_skills": [],
        }
    result["latency_ms"] = int((time.time() - started) * 1000)
    target["result"] = result


def _query_allows_live_data(query: dict[str, list[str]]) -> bool:
    if _query_flag(query, "demo"):
        return False
    return _query_flag(query, "allowLiveData") or _query_flag(query, "live")


def _query_flag(query: dict[str, list[str]], name: str) -> bool:
    return any(str(value).strip().lower() in {"1", "true", "yes", "on"} for value in query.get(name, []))


def _safe_call_result(state: dict[str, Any], source: str, allow_missing: bool = False) -> dict[str, Any]:
    result = state.get("result")
    if isinstance(result, dict):
        return result
    status = "unavailable" if not allow_missing else "unavailable"
    return {
        "status": status,
        "source": source,
        "url": "",
        "error": f"{source} lookup did not complete in time.",
        "items": [],
        "top_skills": [],
        "latency_ms": int(LIVE_API_TIMEOUT_SECONDS * 1000),
    }


def _join_threads_until_deadline(threads: list[threading.Thread], timeout_seconds: float) -> None:
    deadline = time.time() + max(0.05, timeout_seconds)
    for thread in threads:
        remaining = deadline - time.time()
        if remaining <= 0:
            return
        thread.join(remaining)


def _cache_get(cache: dict[str, dict[str, Any]], key: str) -> dict[str, Any] | None:
    entry = cache.get(key)
    if not entry:
        return None
    if entry.get("expires_at", 0) <= time.time():
        cache.pop(key, None)
        return None
    return entry.get("value")


def _cache_set(cache: dict[str, dict[str, Any]], key: str, value: dict[str, Any]) -> None:
    cache[key] = {"value": value, "expires_at": time.time() + LIVE_CACHE_TTL_SECONDS}


def main() -> None:
    port = DEFAULT_PORT
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"SkillQuest running at http://127.0.0.1:{port}/")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

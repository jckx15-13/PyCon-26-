from __future__ import annotations

import csv
import html
import io
import json
import os
import re
import time
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


USER_AGENT = "SkillQuestBaseline/0.1 (+local prototype)"
DATA_GOV_COURSE_DATASET_ID = "d_b5802b76f409764c16dde4bf2feb19cd"
DATA_GOV_COURSE_DATASET_PAGE = f"https://data.gov.sg/datasets/{DATA_GOV_COURSE_DATASET_ID}/view"
DATA_GOV_COURSE_POLL_URL = (
    f"https://api-open.data.gov.sg/v1/public/api/datasets/{DATA_GOV_COURSE_DATASET_ID}/poll-download"
)
XLSX_NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
SENSITIVE_QUERY_PARAMS = {"key", "api_key", "apikey", "token", "access_token", "auth", "authorization"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_data_gov_course_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "status": "cache_missing",
            "source": "Cached MySkillsFuture Course Directory slice",
            "url": DATA_GOV_COURSE_DATASET_PAGE,
            "items": [],
            "dataset_id": DATA_GOV_COURSE_DATASET_ID,
            "detail": "No local course-directory cache was found.",
        }
    try:
        payload = load_json(path)
    except Exception as exc:
        return {
            "status": "cache_invalid",
            "source": "Cached MySkillsFuture Course Directory slice",
            "url": DATA_GOV_COURSE_DATASET_PAGE,
            "items": [],
            "dataset_id": DATA_GOV_COURSE_DATASET_ID,
            "error": f"{type(exc).__name__}: {exc}",
        }
    items = payload.get("items") if isinstance(payload, dict) else []
    if not isinstance(items, list):
        items = []
    records = payload.get("records") if isinstance(payload.get("records"), dict) else {}
    return {
        "status": "cached" if items else "cache_empty",
        "source": payload.get("source") or "Cached MySkillsFuture Course Directory slice",
        "url": payload.get("url") or DATA_GOV_COURSE_DATASET_PAGE,
        "items": items,
        "dataset_id": payload.get("dataset_id") or DATA_GOV_COURSE_DATASET_ID,
        "records": {"loaded": len(items), **records},
        "generated_at": payload.get("generated_at"),
        "generated_by": payload.get("generated_by"),
        "detail": payload.get("detail") or "Loaded a local cached slice of public MySkillsFuture course rows.",
    }


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_json(url: str, timeout: float = 5.0, headers: dict[str, str] | None = None) -> tuple[dict[str, Any] | None, str | None]:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body), None
    except Exception as exc:  # External APIs should never break the local demo.
        return None, f"{type(exc).__name__}: {exc}"


def fetch_text(url: str, timeout: float = 5.0) -> tuple[str | None, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8"), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def fetch_bytes(url: str, timeout: float = 8.0) -> tuple[bytes | None, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def redact_url_secrets(url: str | None) -> str | None:
    if not url:
        return url
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    redacted = [
        (key, "REDACTED" if key.lower() in SENSITIVE_QUERY_PARAMS else value)
        for key, value in query
    ]
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(redacted), parsed.fragment)
    )


class MyCareersFutureClient:
    """Small adapter for public MyCareersFuture job search skill signals."""

    base_url = "https://api.mycareersfuture.gov.sg/v2/jobs"

    def search_jobs(self, query: str, limit: int = 8) -> dict[str, Any]:
        params = {
            "limit": str(max(1, min(limit, 20))),
            "page": "0",
            "sortBy": "new_posting_date",
            "search": query or "data analyst",
        }
        url = f"{self.base_url}?{urllib.parse.urlencode(params)}"
        started = time.time()
        timeout = float(os.getenv("MCF_TIMEOUT_SECONDS", "12"))
        payload, error = fetch_json(url, timeout=timeout)
        if error or not payload:
            return {
                "status": "unavailable",
                "source": "MyCareersFuture",
                "url": url,
                "error": error or "Empty response",
                "items": [],
                "top_skills": [],
                "latency_ms": int((time.time() - started) * 1000),
            }

        items = []
        skill_counter: Counter[str] = Counter()
        for item in payload.get("results", []):
            skills = []
            key_skills = []
            for raw_skill in item.get("skills", []) or []:
                skill_name = raw_skill.get("skill")
                if not skill_name:
                    continue
                skills.append(skill_name)
                skill_counter[skill_name] += 2 if raw_skill.get("isKeySkill") else 1
                if raw_skill.get("isKeySkill"):
                    key_skills.append(skill_name)
            address = item.get("address") or {}
            salary = item.get("salary") or {}
            items.append(
                {
                    "title": item.get("title"),
                    "company": (item.get("postedCompany") or {}).get("name"),
                    "description": strip_html(item.get("description")),
                    "skills": skills,
                    "key_skills": key_skills,
                    "salary_min": salary.get("minimum"),
                    "salary_max": salary.get("maximum"),
                    "location": address.get("region") or address.get("building") or address.get("street"),
                    "job_url": ((item.get("metadata") or {}).get("jobDetailsUrl")),
                }
            )
        return {
            "status": "ok",
            "source": "MyCareersFuture",
            "url": url,
            "total": payload.get("total", len(items)),
            "items": items,
            "top_skills": [{"name": name, "demand": count} for name, count in skill_counter.most_common(12)],
            "latency_ms": int((time.time() - started) * 1000),
        }


class OneMapClient:
    """OneMap search adapter. Auth token is optional for this baseline lookup."""

    base_url = "https://www.onemap.gov.sg/api/common/elastic/search"

    def search(self, query: str) -> dict[str, Any]:
        if not query:
            return {"status": "skipped", "source": "OneMap", "items": []}

        params = {
            "searchVal": query,
            "returnGeom": "Y",
            "getAddrDetails": "Y",
            "pageNum": "1",
        }
        headers: dict[str, str] = {}
        token = os.getenv("ONEMAP_API_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        url = f"{self.base_url}?{urllib.parse.urlencode(params)}"
        payload, error = fetch_json(url, timeout=5.0, headers=headers)
        if error or not payload:
            return {
                "status": "unavailable",
                "source": "OneMap",
                "url": url,
                "error": error or "Empty response",
                "items": [],
            }

        items = []
        for item in payload.get("results", [])[:8]:
            items.append(
                {
                    "label": item.get("SEARCHVAL") or item.get("ADDRESS"),
                    "address": item.get("ADDRESS"),
                    "postal": item.get("POSTAL"),
                    "lat": _float_or_none(item.get("LATITUDE")),
                    "lng": _float_or_none(item.get("LONGITUDE")),
                }
            )
        return {
            "status": "ok" if items else "empty",
            "source": "OneMap",
            "url": url,
            "warning": payload.get("error"),
            "items": items,
        }


class ExternalCourseDatasetClient:
    """Optional JSON/CSV loader for a user-provided course dataset URL."""

    def fetch(self, url: str | None) -> dict[str, Any]:
        if not url:
            return {"status": "skipped", "source": "COURSE_DATA_URL", "items": []}
        text, error = fetch_text(url, timeout=8.0)
        if error or text is None:
            return {"status": "unavailable", "source": "COURSE_DATA_URL", "url": url, "error": error, "items": []}

        try:
            if url.lower().split("?")[0].endswith(".csv"):
                rows = list(csv.DictReader(text.splitlines()))
                return {"status": "ok", "source": "COURSE_DATA_URL", "url": url, "items": [self._normalise_course(row) for row in rows]}
            data = json.loads(text)
            items = data if isinstance(data, list) else data.get("courses", [])
            return {"status": "ok", "source": "COURSE_DATA_URL", "url": url, "items": [self._normalise_course(row) for row in items]}
        except Exception as exc:
            return {"status": "invalid", "source": "COURSE_DATA_URL", "url": url, "error": f"{type(exc).__name__}: {exc}", "items": []}

    def _normalise_course(self, row: dict[str, Any]) -> dict[str, Any]:
        skills = row.get("skills", [])
        if isinstance(skills, str):
            skills = [part.strip() for part in re.split(r"[,;|]", skills) if part.strip()]
        source_url = row.get("source_url") or row.get("url") or ""
        return {
            "id": str(row.get("id") or row.get("title") or "external-course").lower().replace(" ", "-"),
            "title": row.get("title") or row.get("course_title") or "Untitled course",
            "provider": row.get("provider") or row.get("training_provider") or "External provider",
            "description": row.get("description") or "",
            "skills": skills,
            "level": row.get("level") or "Unknown",
            "duration_hours": _float_or_none(row.get("duration_hours")) or 0,
            "sessions_per_week": _float_or_none(row.get("sessions_per_week")) or 1,
            "session_length_hours": _float_or_none(row.get("session_length_hours")) or 2,
            "mode": row.get("mode") or "Blended",
            "region": row.get("region") or "Unknown",
            "address": row.get("address") or row.get("region") or "Unknown",
            "lat": _float_or_none(row.get("lat")),
            "lng": _float_or_none(row.get("lng")),
            "fee": _float_or_none(row.get("fee")) or 0,
            "funding_rate": _float_or_none(row.get("funding_rate")) or 0,
            "schedule": row.get("schedule") or "Flexible",
            "rating": _float_or_none(row.get("rating")) or 0,
            "review_count": int(_float_or_none(row.get("review_count")) or 0),
            "review_snippets": row.get("review_snippets") if isinstance(row.get("review_snippets"), list) else [],
            "source_url": source_url,
        }


class DataGovCourseDirectoryClient:
    """Optional no-key import for the official MySkillsFuture Course Directory dataset."""

    def fetch(self) -> dict[str, Any]:
        if os.getenv("SKILLQUEST_ENABLE_DATA_GOV_COURSES", "").strip().lower() not in {"1", "true", "yes", "on"}:
            return {
                "status": "skipped",
                "source": "data.gov.sg MySkillsFuture Course Directory",
                "url": DATA_GOV_COURSE_DATASET_PAGE,
                "items": [],
                "dataset_id": DATA_GOV_COURSE_DATASET_ID,
                "detail": "Set SKILLQUEST_ENABLE_DATA_GOV_COURSES=true to import this no-key public dataset at startup.",
            }

        started = time.time()
        metadata, error = fetch_json(DATA_GOV_COURSE_POLL_URL, timeout=float(os.getenv("DATA_GOV_TIMEOUT_SECONDS", "12")))
        if error or not metadata:
            return self._unavailable(error or "Empty data.gov.sg response.", started)
        if metadata.get("code") != 0:
            return self._unavailable(str(metadata.get("errMsg") or "data.gov.sg did not return a download URL."), started)

        download_url = ((metadata.get("data") or {}).get("url") or "").strip()
        if not download_url:
            return self._unavailable("data.gov.sg response did not include a download URL.", started)

        blob, error = fetch_bytes(download_url, timeout=float(os.getenv("DATA_GOV_DOWNLOAD_TIMEOUT_SECONDS", "45")))
        if error or not blob:
            return self._unavailable(error or "Course directory download was empty.", started)

        try:
            rows = list(_xlsx_dict_rows(blob))
        except Exception as exc:
            return self._unavailable(f"Could not parse XLSX: {type(exc).__name__}: {exc}", started)

        limit = int(float(os.getenv("DATA_GOV_COURSE_LIMIT", "40") or "40"))
        items = []
        inspected = 0
        for row in rows:
            inspected += 1
            if not row.get("coursetitle"):
                continue
            if not self._is_relevant(row):
                continue
            items.append(self._normalise_course(row))
            if len(items) >= max(1, limit):
                break

        return {
            "status": "ok" if items else "empty",
            "source": "data.gov.sg MySkillsFuture Course Directory",
            "url": DATA_GOV_COURSE_DATASET_PAGE,
            "items": items,
            "dataset_id": DATA_GOV_COURSE_DATASET_ID,
            "records": {"loaded": len(items), "inspected": inspected, "availableRows": len(rows)},
            "latency_ms": int((time.time() - started) * 1000),
            "detail": "Imported relevant rows from the public MySkillsFuture Course Directory dataset.",
        }

    def _unavailable(self, message: str, started: float) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "source": "data.gov.sg MySkillsFuture Course Directory",
            "url": DATA_GOV_COURSE_DATASET_PAGE,
            "items": [],
            "dataset_id": DATA_GOV_COURSE_DATASET_ID,
            "error": message,
            "latency_ms": int((time.time() - started) * 1000),
        }

    def _is_relevant(self, row: dict[str, str]) -> bool:
        keywords = os.getenv(
            "DATA_GOV_COURSE_KEYWORDS",
            "data,python,analytics,excel,sql,cyber,security,marketing,ux,user research,healthcare,sustainability",
        )
        terms = [term.strip().lower() for term in re.split(r"[,;|]", keywords) if term.strip()]
        if not terms:
            return True
        blob = " ".join(
            [
                row.get("coursetitle", ""),
                row.get("trainingprovideralias", ""),
                row.get("about_this_course", ""),
                row.get("what_you_learn", ""),
            ]
        ).lower()
        return any(term in blob for term in terms)

    def _normalise_course(self, row: dict[str, str]) -> dict[str, Any]:
        reference = row.get("coursereferencenumber", "").strip()
        title = _clean_cell(row.get("coursetitle")) or "Untitled course"
        provider = _clean_cell(row.get("trainingprovideralias")) or "Training provider"
        description = _clean_cell(row.get("about_this_course")) or _clean_cell(row.get("what_you_learn"))
        fee = _float_or_none(row.get("full_course_fee")) or _float_or_none(row.get("course_fee_after_subsidies")) or 0
        after_subsidy = _float_or_none(row.get("course_fee_after_subsidies"))
        funding_rate = 0.0
        if fee and after_subsidy is not None and after_subsidy <= fee:
            funding_rate = max(0.0, min(0.95, 1 - (after_subsidy / fee)))
        rating = _float_or_none(row.get("courseratings_stars")) or _float_or_none(row.get("courseratings_value")) or 0
        if rating and rating > 5:
            rating = rating / 1000 if rating > 100 else rating / 20
        review_count = int(_float_or_none(row.get("courseratings_noofrespondents")) or 0)
        skills = _infer_course_skills(" ".join([title, description, _clean_cell(row.get("what_you_learn"))]))
        source_url = (
            "https://www.myskillsfuture.gov.sg/content/portal/en/training-exchange/course-directory/course-detail.html"
            f"?courseReferenceNumber={urllib.parse.quote(reference)}"
            if reference
            else DATA_GOV_COURSE_DATASET_PAGE
        )
        return {
            "id": f"data-gov-{reference.lower()}" if reference else _slug(title),
            "title": title,
            "provider": provider,
            "description": description[:520],
            "skills": skills or ["General Upskilling"],
            "level": "Unknown",
            "duration_hours": _float_or_none(row.get("number_of_hours")) or 0,
            "sessions_per_week": 1,
            "session_length_hours": min(4, max(1, (_float_or_none(row.get("number_of_hours")) or 12) / 8)),
            "mode": "Blended",
            "region": "Verify with provider",
            "address": "Verify with provider",
            "lat": None,
            "lng": None,
            "fee": fee,
            "funding_rate": funding_rate,
            "schedule": row.get("training_commitment") or "Flexible",
            "rating": round(rating, 1) if rating else 0,
            "review_count": review_count,
            "review_snippets": [],
            "source_url": source_url,
            "source_dataset": "MySkillsFuture Course Directory via data.gov.sg",
            "course_reference_number": reference,
        }


class ApifyJobClient:
    """Adapter for an optional Apify dataset containing job records."""

    base_url = "https://api.apify.com/v2/datasets/{dataset_id}/items"

    def __init__(self) -> None:
        self.dataset_id = (os.getenv("APIFY_DATASET_ID") or "").strip()
        self.token = os.getenv("APIFY_API_TOKEN")

    def search_jobs(self, query: str, limit: int = 8) -> dict[str, Any]:
        if not self.dataset_id or not self.token:
            return {
                "status": "skipped",
                "source": "Apify",
                "items": [],
                "top_skills": [],
                "error": "APIFY_DATASET_ID or APIFY_API_TOKEN is not configured.",
                "url": self._build_url(),
                "latency_ms": 0,
            }

        params = {
            "format": "json",
            "clean": "true",
            "limit": str(max(1, min(limit, 40))),
        }
        url = f"{self._build_url()}?{urllib.parse.urlencode(params)}"
        started = time.time()
        headers = {"Authorization": f"Bearer {self.token}"}
        payload, error = fetch_json(url, timeout=12.0, headers=headers)
        if error or not isinstance(payload, list):
            return {
                "status": "unavailable",
                "source": "Apify",
                "url": url,
                "error": error or "Empty or unsupported dataset response.",
                "items": [],
                "top_skills": [],
                "latency_ms": int((time.time() - started) * 1000),
            }

        filtered = [self._normalise_apify_job(item) for item in payload if self._matches_query(item, query)]
        normalized = [item for item in filtered if item]
        top_skills = self._collect_skills(normalized)
        return {
            "status": "ok" if normalized else "empty",
            "source": "Apify",
            "url": url,
            "items": normalized[:limit],
            "top_skills": top_skills[:10],
            "latency_ms": int((time.time() - started) * 1000),
        }

    def _matches_query(self, row: dict[str, Any], query: str) -> bool:
        if not query:
            return True
        query_terms = [part.strip().lower() for part in query.split() if part.strip()]
        blob = " ".join(
            [
                str(row.get("title", "")),
                str(row.get("jobTitle", "")),
                str(row.get("role", "")),
                str(row.get("company", "")),
                str(row.get("description", "")),
            ]
        ).lower()
        return all(term in blob for term in query_terms)

    def _normalise_apify_job(self, row: dict[str, Any]) -> dict[str, Any] | None:
        raw_skills = self._extract_skills(row.get("skills")) or self._extract_skills(row.get("tags")) or []
        title = row.get("title") or row.get("jobTitle") or row.get("position") or "Untitled role"
        if not title and not row.get("description"):
            return None
        address = row.get("address") or {}
        company = row.get("company") or {}
        salary = row.get("salary") or {}
        return {
            "title": title,
            "company": company.get("name") or row.get("companyName"),
            "description": strip_html(str(row.get("description", ""))),
            "skills": raw_skills,
            "key_skills": raw_skills[:6],
            "salary_min": salary.get("min") if isinstance(salary, dict) else None,
            "salary_max": salary.get("max") if isinstance(salary, dict) else None,
            "location": address.get("region") or address.get("city") or address.get("area"),
            "job_url": row.get("url") or row.get("jobUrl") or row.get("link"),
        }

    def _collect_skills(self, jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        counts: Counter[str] = Counter()
        for item in jobs:
            for skill in item.get("skills", []):
                name = str(skill).strip()
                if name:
                    counts[name] += 1
        return [{"name": name, "demand": demand} for name, demand in counts.most_common(12)]

    def _extract_skills(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [part.strip() for part in re.split(r"[,;|]", value) if part.strip()]
        return []

    def _build_url(self) -> str:
        if not self.dataset_id:
            return self.base_url.replace("{dataset_id}", "dataset-missing")
        return self.base_url.replace("{dataset_id}", urllib.parse.quote(self.dataset_id))


class GoogleCloudGeocodeClient:
    """Optional geocode fallback using Google Maps APIs."""

    base_url = "https://maps.googleapis.com/maps/api/geocode/json"

    def __init__(self) -> None:
        self.api_key = os.getenv("GOOGLE_CLOUD_API_KEY")

    def search(self, query: str) -> dict[str, Any]:
        if not query:
            return {"status": "skipped", "source": "Google Maps", "items": []}
        if not self.api_key:
            return {
                "status": "skipped",
                "source": "Google Maps",
                "items": [],
                "warning": "GOOGLE_CLOUD_API_KEY is not configured.",
            }

        params = {
            "address": query,
            "key": self.api_key,
        }
        url = f"{self.base_url}?{urllib.parse.urlencode(params)}"
        started = time.time()
        payload, error = fetch_json(url, timeout=8.0)
        if error or not payload:
            return {
                "status": "unavailable",
                "source": "Google Maps",
                "url": redact_url_secrets(url),
                "error": error or "Empty response",
                "items": [],
                "latency_ms": int((time.time() - started) * 1000),
            }

        results = payload.get("results") or []
        if payload.get("status") != "OK" or not results:
            return {
                "status": "unavailable",
                "source": "Google Maps",
                "url": redact_url_secrets(url),
                "error": payload.get("error_message") or f"Geocode status: {payload.get('status', 'UNKNOWN')}",
                "items": [],
                "latency_ms": int((time.time() - started) * 1000),
            }

        result = results[0]
        location = (result.get("geometry") or {}).get("location") or {}
        return {
            "status": "ok",
            "source": "Google Maps",
            "url": redact_url_secrets(url),
            "items": [
                {
                    "label": result.get("formatted_address") or query,
                    "address": result.get("formatted_address") or query,
                    "postal": self._find_component(result.get("address_components"), "postal_code"),
                    "lat": _float_or_none(location.get("lat")),
                    "lng": _float_or_none(location.get("lng")),
                    "source": "Google Maps",
                }
            ],
            "latency_ms": int((time.time() - started) * 1000),
        }

    def _find_component(self, components: Any, component_type: str) -> str | None:
        if not isinstance(components, list):
            return None
        for item in components:
            types = item.get("types") or []
            if component_type in types:
                value = item.get("long_name")
                if value:
                    return str(value)
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _xlsx_dict_rows(blob: bytes) -> list[dict[str, str]]:
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        shared = _xlsx_shared_strings(archive)
        sheet_name = next(
            (name for name in archive.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")),
            None,
        )
        if not sheet_name:
            return []
        root = ET.fromstring(archive.read(sheet_name))

    rows: list[list[str]] = []
    for row in root.findall(".//a:sheetData/a:row", XLSX_NS):
        cells: dict[int, str] = {}
        for cell in row.findall("a:c", XLSX_NS):
            index = _xlsx_column_index(cell.get("r", ""))
            if index is None:
                index = len(cells)
            cells[index] = _xlsx_cell_value(cell, shared)
        width = max(cells.keys(), default=-1) + 1
        rows.append([cells.get(index, "") for index in range(width)])

    if not rows:
        return []
    headers = [_normalise_header(value) for value in rows[0]]
    records: list[dict[str, str]] = []
    for values in rows[1:]:
        if not any(str(value).strip() for value in values):
            continue
        records.append({header: values[index] if index < len(values) else "" for index, header in enumerate(headers) if header})
    return records


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    shared = []
    for item in root.findall("a:si", XLSX_NS):
        shared.append("".join(text.text or "" for text in item.findall(".//a:t", XLSX_NS)))
    return shared


def _xlsx_cell_value(cell: ET.Element, shared: list[str]) -> str:
    if cell.get("t") == "inlineStr":
        return _clean_cell("".join(text.text or "" for text in cell.findall(".//a:t", XLSX_NS)))
    value = cell.find("a:v", XLSX_NS)
    if value is None or value.text is None:
        return ""
    text = value.text
    if cell.get("t") == "s":
        try:
            return _clean_cell(shared[int(text)])
        except (ValueError, IndexError):
            return ""
    return _clean_cell(text)


def _xlsx_column_index(reference: str) -> int | None:
    match = re.match(r"([A-Z]+)", reference.upper())
    if not match:
        return None
    value = 0
    for char in match.group(1):
        value = value * 26 + (ord(char) - ord("A") + 1)
    return value - 1


def _normalise_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _clean_cell(value: Any) -> str:
    text = str(value or "")
    replacements = {
        "_x000D_": "\n",
        "\u00e2\u20ac\u2122": "'",
        "\u00e2\u20ac\u00a2": "-",
        "\u00e2\u20ac\u201c": "-",
        "\u00e2\u20ac\u009d": '"',
        "\u00e2\u20ac\u0153": '"',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip()


def _infer_course_skills(text: str) -> list[str]:
    blob = text.lower()
    mapping = [
        ("Spreadsheet Modelling", ["excel", "spreadsheet", "workbook"]),
        ("Data Analysis", ["data", "analytics", "analysis", "pandas", "statistics"]),
        ("SQL Basics", ["sql", "database", "query"]),
        ("Python Automation", ["python", "automation", "scripting"]),
        ("Data Visualisation", ["visual", "dashboard", "chart", "matplotlib", "seaborn"]),
        ("Business Storytelling", ["presentation", "storytelling", "communicat"]),
        ("Campaign Analytics", ["marketing", "campaign", "seo", "search engine"]),
        ("User Research", ["user research", "interview", "usability", "ux"]),
        ("Security Fundamentals", ["cyber", "security", "incident", "network"]),
        ("Process Mapping", ["process", "operations", "workflow"]),
        ("Sustainability Reporting", ["sustainability", "carbon", "emissions"]),
        ("Customer Service", ["customer service", "service excellence"]),
    ]
    skills = [skill for skill, keywords in mapping if any(keyword in blob for keyword in keywords)]
    return skills[:6]


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "course"

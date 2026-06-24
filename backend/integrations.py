from __future__ import annotations

import os
from typing import Any


def integration_readiness(data: Any, mentor: dict[str, Any]) -> dict[str, Any]:
    """Return safe integration metadata without calling external services."""

    course_source_links = [course.get("source_url") for course in data.courses if course.get("source_url")]
    exact_course_links = [url for url in course_source_links if url and url.rstrip("/") != "https://www.myskillsfuture.gov.sg"]
    integrations = [
        {
            "id": "local-role-course-data",
            "name": "Local role and course datasets",
            "kind": "local_dataset",
            "status": "ready",
            "configured": True,
            "usedByDefault": True,
            "requiresConsent": False,
            "demoSafe": True,
            "records": {"roles": len(data.roles), "courses": len(data.courses)},
            "privacy": "No learner data leaves the device.",
            "fallback": "Required baseline data. The app cannot recommend without this layer.",
            "limitation": "Seed course catalogue is small and should be replaced with a verified export before production.",
        },
        {
            "id": "skills-framework",
            "name": "SkillsFuture Skills Framework reference",
            "kind": "official_reference_slice",
            "status": data.skills_framework.get("status", "local-normalised"),
            "configured": True,
            "usedByDefault": True,
            "requiresConsent": False,
            "demoSafe": True,
            "sourceUrl": data.skills_framework.get("source_url"),
            "records": {
                "mappedRoles": len(data.skills_framework.get("role_mappings", {})),
                **(data.skills_framework.get("record_counts") or {}),
            },
            "privacy": "No learner data leaves the device.",
            "fallback": "If a role is unmapped, SkillQuest labels the mapping as low confidence.",
            "limitation": "Normalised app slice only. It is not an official endorsement or enrolment decision.",
        },
        {
            "id": "mycareersfuture",
            "name": "MyCareersFuture job skill signal",
            "kind": "optional_live_api",
            "status": "available_when_enabled",
            "configured": True,
            "usedByDefault": False,
            "requiresConsent": True,
            "demoSafe": False,
            "records": {"requestedLimit": 5},
            "privacy": "Sends only the target role or interest search text when live lookup is enabled.",
            "fallback": "Private offline role-skill signals are used by default and in demo mode.",
            "limitation": "Only returned records are inspected; SkillQuest does not claim a complete labour-market scan.",
        },
        {
            "id": "onemap",
            "name": "OneMap location lookup",
            "kind": "optional_live_api",
            "status": "token_configured" if _env_present("ONEMAP_API_TOKEN") else "works_best_with_token",
            "configured": _env_present("ONEMAP_API_TOKEN"),
            "usedByDefault": False,
            "requiresConsent": True,
            "demoSafe": False,
            "envVars": [{"name": "ONEMAP_API_TOKEN", "present": _env_present("ONEMAP_API_TOKEN")}],
            "privacy": "Sends only the typed place name when live lookup is enabled.",
            "fallback": "Local MRT and region estimates are used by default and in demo mode.",
            "limitation": "Unauthenticated or unavailable OneMap responses are treated as partial evidence.",
        },
        {
            "id": "apify-jobs",
            "name": "Apify job signal dataset",
            "kind": "optional_live_api",
            "status": "configured" if _env_present("APIFY_API_TOKEN") and _env_present("APIFY_DATASET_ID") else "not_configured",
            "configured": _env_present("APIFY_API_TOKEN") and _env_present("APIFY_DATASET_ID"),
            "usedByDefault": False,
            "requiresConsent": True,
            "demoSafe": False,
            "envVars": [
                {"name": "APIFY_API_TOKEN", "present": _env_present("APIFY_API_TOKEN")},
                {"name": "APIFY_DATASET_ID", "present": _env_present("APIFY_DATASET_ID")},
                {"name": "APIFY_DATASET_LIMIT", "present": _env_present("APIFY_DATASET_LIMIT")},
            ],
            "privacy": "Sends only the target role or interest phrase when live lookup is enabled.",
            "fallback": "A local job-skill signal is used when Apify is not configured.",
            "limitation": "Apify dataset quality depends on the selected scrape and dataset refresh frequency.",
        },
        {
            "id": "google-cloud-maps",
            "name": "Google Maps (Google Cloud)",
            "kind": "optional_live_api",
            "status": "configured" if _env_present("GOOGLE_CLOUD_API_KEY") else "not_configured",
            "configured": _env_present("GOOGLE_CLOUD_API_KEY"),
            "usedByDefault": False,
            "requiresConsent": True,
            "demoSafe": False,
            "envVars": [{"name": "GOOGLE_CLOUD_API_KEY", "present": _env_present("GOOGLE_CLOUD_API_KEY")}],
            "privacy": "Sends the typed place text only when live lookup is enabled.",
            "fallback": "Local MRT and region estimates are used by default and in demo mode.",
            "limitation": "Google Maps can return partial results when an address is ambiguous.",
        },
        {
            "id": "external-course-dataset",
            "name": "External course dataset URL",
            "kind": "optional_dataset",
            "status": data.external_course_status.get("status", "skipped"),
            "configured": _env_present("COURSE_DATA_URL"),
            "usedByDefault": False,
            "requiresConsent": False,
            "demoSafe": True,
            "envVars": [{"name": "COURSE_DATA_URL", "present": _env_present("COURSE_DATA_URL")}],
            "records": {"loadedCourses": len(data.external_course_status.get("items", []))},
            "privacy": "No learner data is sent; it only fetches a configured course file at server start.",
            "fallback": "Local course seed data remains available when no external file is configured.",
            "limitation": data.external_course_status.get("error") or "External course files must be reviewed for quality and exact source links.",
        },
        {
            "id": "data-gov-course-directory",
            "name": "MySkillsFuture Course Directory via data.gov.sg",
            "kind": "optional_official_dataset_api",
            "status": data.data_gov_course_status.get("status", "skipped"),
            "configured": os.getenv("SKILLQUEST_ENABLE_DATA_GOV_COURSES", "").strip().lower() in {"1", "true", "yes", "on"},
            "usedByDefault": False,
            "requiresConsent": False,
            "demoSafe": True,
            "sourceUrl": data.data_gov_course_status.get("url"),
            "envVars": [
                {"name": "SKILLQUEST_ENABLE_DATA_GOV_COURSES", "present": _env_present("SKILLQUEST_ENABLE_DATA_GOV_COURSES")},
                {"name": "DATA_GOV_COURSE_LIMIT", "present": _env_present("DATA_GOV_COURSE_LIMIT")},
                {"name": "DATA_GOV_COURSE_KEYWORDS", "present": _env_present("DATA_GOV_COURSE_KEYWORDS")},
            ],
            "records": data.data_gov_course_status.get("records", {"loaded": len(data.data_gov_course_status.get("items", []))}),
            "privacy": "No learner data is sent; the server imports a public course dataset at startup only when enabled.",
            "fallback": "Local course seed data remains available when the dataset is disabled or unavailable.",
            "limitation": data.data_gov_course_status.get("error")
            or "Large public XLSX import is opt-in to keep the live demo fast and predictable.",
        },
        {
            "id": "local-mentor",
            "name": "No-key local mentor",
            "kind": "local_ai_grounding",
            "status": mentor.get("provider", "local-deterministic"),
            "configured": True,
            "usedByDefault": True,
            "requiresConsent": False,
            "demoSafe": True,
            "records": {"examples": mentor.get("examples", 0)},
            "privacy": mentor.get("privacy"),
            "fallback": "Deterministic guidance stays available even without an OpenAI API key.",
            "limitation": "This is local response shaping, not live model generation or fine-tuning.",
        },
        {
            "id": "openai-future",
            "name": "Future OpenAI mentor upgrade",
            "kind": "future_optional_api",
            "status": "configured" if _openai_ready_for_upgrade(mentor) else "not_configured",
            "configured": _openai_ready_for_upgrade(mentor),
            "usedByDefault": False,
            "requiresConsent": True,
            "demoSafe": False,
            "envVars": [
                {"name": "OPENAI_API_KEY", "present": _env_present("OPENAI_API_KEY")},
                {"name": "SKILLQUEST_ENABLE_OPENAI_MENTOR", "present": _env_present("SKILLQUEST_ENABLE_OPENAI_MENTOR")},
            ],
            "privacy": "Only recommendation facts are sent when this is enabled.",
            "fallback": "The local mentor is still available if the key is missing or model calls fail.",
            "limitation": "Secure key setup is required before any live OpenAI call is enabled.",
        },
        {
            "id": "google-cloud-mentor",
            "name": "Google Cloud Gemini mentor",
            "kind": "optional_api_model",
            "status": "configured" if _google_ai_ready(mentor) else "not_configured",
            "configured": _google_ai_ready(mentor),
            "usedByDefault": False,
            "requiresConsent": True,
            "demoSafe": False,
            "envVars": [
                {"name": "GOOGLE_CLOUD_AI_API_KEY", "present": _env_present("GOOGLE_CLOUD_AI_API_KEY")},
                {"name": "GOOGLE_CLOUD_AI_MODEL", "present": _env_present("GOOGLE_CLOUD_AI_MODEL")},
            ],
            "privacy": "Only recommendation facts are sent to the selected model endpoint when this is enabled.",
            "fallback": "The local mentor is still available if the key is missing or model calls fail.",
            "limitation": "Model wording is bounded by prompt safety; it does not make eligibility decisions.",
        },
    ]

    summary = {
        "ready": sum(1 for item in integrations if item["status"] in {"ready", "local-deterministic", "local-normalised"}),
        "optional": sum(1 for item in integrations if item["kind"].startswith("optional")),
        "needsConfiguration": sum(1 for item in integrations if item.get("envVars") and not item.get("configured")),
        "demoSafe": all(item["demoSafe"] for item in integrations if item["usedByDefault"]),
        "exactCourseLinks": len(exact_course_links),
        "genericCourseLinks": len(course_source_links) - len(exact_course_links),
    }

    return {
        "summary": summary,
        "integrations": integrations,
        "aiProvider": mentor.get("provider", "local-deterministic"),
        "display": [
            "Private demo is ready without network calls.",
            "Live jobs and map lookup are opt-in.",
            "The public MySkillsFuture Course Directory import is optional and no-key.",
            "Seed course links are broad references until a verified course export is enabled.",
        ],
    }


def _env_present(name: str) -> bool:
    return bool(os.getenv(name))


def _openai_ready_for_upgrade(mentor: dict[str, Any]) -> bool:
    return bool(mentor.get("openaiEnabled")) and mentor.get("openaiKeyPresent") is True


def _google_ai_ready(mentor: dict[str, Any]) -> bool:
    return bool(os.getenv("GOOGLE_CLOUD_AI_API_KEY")) and os.getenv("SKILLQUEST_ENABLE_GOOGLE_MENTOR", "").strip().lower() in {"1", "true", "yes", "on"}

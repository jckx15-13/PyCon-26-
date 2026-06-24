from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Any


ALLOWED_ACTIONS = {"plain", "why", "cheaper", "two_hours", "helper"}
DATASET_NAME = "ai_training_examples.jsonl"


def _openai_api_key() -> str | None:
    return os.getenv("OPENAI_API_KEY")


def _openai_ready() -> bool:
    return bool(_openai_api_key()) and _openai_enabled()


def _openai_enabled() -> bool:
    return os.getenv("SKILLQUEST_ENABLE_OPENAI_MENTOR", "").strip().lower() in {"1", "true", "yes", "on"}


def _google_ai_api_key() -> str | None:
    return os.getenv("GOOGLE_CLOUD_AI_API_KEY")


def _google_ai_enabled() -> bool:
    return os.getenv("SKILLQUEST_ENABLE_GOOGLE_MENTOR", "").strip().lower() in {"1", "true", "yes", "on"}


def _google_ai_ready() -> bool:
    return bool(_google_ai_api_key()) and _google_ai_enabled()


def mentor_status(data_dir: Path) -> dict[str, Any]:
    examples = load_training_examples(data_dir)
    openai_key_present = bool(_openai_api_key())
    openai_enabled = _openai_enabled()
    google_key_present = bool(_google_ai_api_key())
    google_enabled = _google_ai_enabled()

    if _google_ai_ready():
        return {
            "provider": "google-cloud-live",
            "configured": True,
            "requiresApiKey": True,
            "liveModel": True,
            "dataset": f"data/{DATASET_NAME}",
            "examples": len(examples),
            "actions": sorted(ALLOWED_ACTIONS),
            "privacy": "Facts are sent only to Google Cloud for this request, not raw profile text.",
            "note": "Live mentor is enabled when GOOGLE_CLOUD_AI_API_KEY is present and network responses are successful.",
            "googleEnabled": True,
            "googleKeyPresent": google_key_present,
            "google": {
                "model": os.getenv("GOOGLE_CLOUD_AI_MODEL", "gemini-1.5-flash-latest"),
                "maxTokens": int(os.getenv("GOOGLE_CLOUD_AI_MAX_TOKENS", "240")),
                "timeout": float(os.getenv("GOOGLE_CLOUD_AI_TIMEOUT_SECONDS", "12")),
            },
            "openaiEnabled": False,
            "openaiKeyPresent": openai_key_present,
        }

    if _openai_ready():
        return {
            "provider": "openai-live",
            "configured": True,
            "requiresApiKey": True,
            "liveModel": True,
            "dataset": f"data/{DATASET_NAME}",
            "examples": len(examples),
            "actions": sorted(ALLOWED_ACTIONS),
            "privacy": "Facts are sent only to OpenAI for this request, not raw profile text.",
            "note": "Live mentor is enabled when OPENAI_API_KEY is present and network responses are successful.",
            "openaiEnabled": True,
            "openaiKeyPresent": openai_key_present,
            "googleEnabled": bool(google_enabled),
            "googleKeyPresent": google_key_present,
            "openai": {
                "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                "maxTokens": int(os.getenv("OPENAI_MAX_TOKENS", "240")),
                "timeout": float(os.getenv("OPENAI_TIMEOUT_SECONDS", "12")),
            },
        }

    key_line = "Google key set" if google_key_present else "Google key not set"
    if google_enabled and not google_key_present:
        key_line = f"{key_line}; OpenAI key {'set' if openai_key_present else 'not set'}"
    opt_in_line = (
        "Enable Google Cloud mentor with SKILLQUEST_ENABLE_GOOGLE_MENTOR=true and GOOGLE_CLOUD_AI_API_KEY "
        "or enable OpenAI via SKILLQUEST_ENABLE_OPENAI_MENTOR=true and OPENAI_API_KEY."
    )
    if not (google_enabled or openai_enabled):
        note = "Live mentor is disabled."
    elif google_enabled:
        note = "Live mentor is requested for Google Cloud but could not be enabled because the API key is missing."
    else:
        note = "Live mentor is requested for OpenAI but could not be enabled because the API key is missing."

    return {
        "provider": "local-deterministic",
        "configured": True,
        "requiresApiKey": False,
        "liveModel": False,
        "dataset": f"data/{DATASET_NAME}",
        "examples": len(examples),
        "actions": sorted(ALLOWED_ACTIONS),
        "privacy": "No profile is sent to an external AI service in this mode.",
        "note": f"{note} {key_line}. {opt_in_line}",
        "openaiEnabled": False,
        "openaiKeyPresent": openai_key_present,
        "googleEnabled": bool(google_enabled),
        "googleKeyPresent": google_key_present,
    }


def mentor_reply(payload: dict[str, Any], data_dir: Path) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise MentorInputError("Request body must be a JSON object.")

    recommendation = payload.get("recommendation")
    if not isinstance(recommendation, dict):
        raise MentorInputError("A recommendation object is required.")

    action = str(payload.get("action") or "plain").strip().lower()
    if action not in ALLOWED_ACTIONS:
        raise MentorInputError(f"Unsupported mentor action. Use one of: {', '.join(sorted(ALLOWED_ACTIONS))}.")

    question = str(payload.get("question") or "").strip()[:280]
    examples = load_training_examples(data_dir)
    facts = _extract_facts(recommendation)
    preferred_examples = [item for item in examples if item.get("action") == action]
    force_local = bool(payload.get("forceLocalMentor"))

    if not force_local:
        if _google_ai_ready():
            try:
                return _google_ai_reply(
                    action, facts, question, preferred_examples, examples, payload.get("requestMode", "normal")
                )
            except Exception:
                # Keep service alive by trying OpenAI and then local fallback.
                pass
        if _openai_ready():
            try:
                return _openai_reply(
                    action, facts, question, preferred_examples, examples, payload.get("requestMode", "normal")
                )
            except Exception:
                # OpenAI is optional and can fail due to transient connectivity.
                # Keep service alive by falling back to local deterministic guidance.
                pass

    rendered = _render_action(action, facts, question)
    return {
        "provider": "local-deterministic",
        "status": "ready",
        "action": action,
        "title": rendered["title"],
        "summary": rendered["summary"],
        "steps": rendered["steps"],
        "speakText": " ".join([rendered["summary"], *rendered["steps"]]),
        "caveats": _caveats(facts),
        "grounding": {
            "role": facts["role_title"],
            "course": facts["course_title"],
            "topSkill": facts["top_skill"],
            "confidence": facts["confidence_label"],
            "examplesMatched": len(preferred_examples),
            "dataset": f"data/{DATASET_NAME}",
            "skillsFramework": _framework_grounding(facts),
            "fallback": True,
        },
        "suggestedActions": [
            {"action": "why", "label": "Why this?"},
            {"action": "cheaper", "label": "Make it cheaper"},
            {"action": "two_hours", "label": "Only 2 hours"},
            {"action": "helper", "label": "For a helper"},
        ],
    }


def _openai_reply(
    action: str,
    facts: dict[str, Any],
    question: str,
    examples: list[dict[str, Any]],
    all_examples: list[dict[str, Any]],
    request_mode: str,
) -> dict[str, Any]:
    start = time.time()
    payload = _build_openai_payload(action, facts, question, examples, all_examples, request_mode)
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    timeout = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "12"))
    api_key = _openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            response_payload = json.loads(body)
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error {exc.code}: {details[:160]}") from exc
    except Exception as exc:  # pragma: no cover - transport failures in environments vary.
        raise RuntimeError(f"Could not reach OpenAI API: {exc}") from exc

    choices = response_payload.get("choices") or []
    if not choices:
        raise RuntimeError("OpenAI response did not include any choices.")

    message = (choices[0].get("message") or {}).get("content", "")
    parsed = _parse_json_like(message)
    if not isinstance(parsed, dict):
        raise RuntimeError("OpenAI response could not be parsed as JSON.")

    title = str(parsed.get("title") or "").strip() or _render_action(action, facts, question)["title"]
    summary = str(parsed.get("summary") or "").strip() or _render_action(action, facts, question)["summary"]
    steps = [str(step).strip() for step in parsed.get("steps", []) if str(step).strip()]
    if not steps:
        steps = _render_action(action, facts, question)["steps"]

    latency_ms = int((time.time() - start) * 1000)
    return {
        "provider": "openai-live",
        "status": "ready",
        "action": action,
        "title": title,
        "summary": summary,
        "steps": steps[:6],
        "speakText": " ".join([summary, *steps]),
        "caveats": _caveats(facts),
            "grounding": {
                "role": facts["role_title"],
                "course": facts["course_title"],
                "topSkill": facts["top_skill"],
                "confidence": facts["confidence_label"],
                "examplesMatched": len(examples),
                "dataset": f"data/{DATASET_NAME}",
                "skillsFramework": _framework_grounding(facts),
                "apiModel": model,
                "latencyMs": latency_ms,
                "fallback": False,
        },
        "suggestedActions": [
            {"action": "why", "label": "Why this?"},
            {"action": "cheaper", "label": "Make it cheaper"},
            {"action": "two_hours", "label": "Only 2 hours"},
            {"action": "helper", "label": "For a helper"},
        ],
    }


def _google_ai_reply(
    action: str,
    facts: dict[str, Any],
    question: str,
    examples: list[dict[str, Any]],
    all_examples: list[dict[str, Any]],
    request_mode: str,
) -> dict[str, Any]:
    start = time.time()
    payload = _build_google_payload(action, facts, question, examples, all_examples, request_mode)
    model = os.getenv("GOOGLE_CLOUD_AI_MODEL", "gemini-1.5-flash-latest")
    timeout = float(os.getenv("GOOGLE_CLOUD_AI_TIMEOUT_SECONDS", "12"))
    max_tokens = int(os.getenv("GOOGLE_CLOUD_AI_MAX_TOKENS", "240"))
    api_key = _google_ai_api_key()
    if not api_key:
        raise RuntimeError("GOOGLE_CLOUD_AI_API_KEY is not configured.")

    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(model, safe='')}:generateContent"
        f"?key={urllib.parse.quote(api_key)}"
    )
    request = urllib.request.Request(
        endpoint,
        headers={
            "Content-Type": "application/json",
        },
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            response_payload = json.loads(body)
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Google Cloud AI error {exc.code}: {details[:160]}") from exc
    except Exception as exc:  # pragma: no cover - transport failures in environments vary.
        raise RuntimeError(f"Could not reach Google Cloud AI: {exc}") from exc

    candidate_text = _extract_model_text(response_payload)
    if not candidate_text:
        raise RuntimeError("Google Cloud AI response did not include any text.")
    parsed = _parse_json_like(candidate_text)
    if not isinstance(parsed, dict):
        raise RuntimeError("Google Cloud AI response could not be parsed as JSON.")

    local = _render_action(action, facts, question)
    title = str(parsed.get("title") or "").strip() or local["title"]
    summary = str(parsed.get("summary") or "").strip() or local["summary"]
    steps = [str(step).strip() for step in parsed.get("steps", []) if str(step).strip()]
    if not steps:
        steps = local["steps"]

    latency_ms = int((time.time() - start) * 1000)
    return {
        "provider": "google-cloud-live",
        "status": "ready",
        "action": action,
        "title": title,
        "summary": summary,
        "steps": steps[:6],
        "speakText": " ".join([summary, *steps]),
        "caveats": _caveats(facts),
            "grounding": {
                "role": facts["role_title"],
                "course": facts["course_title"],
                "topSkill": facts["top_skill"],
                "confidence": facts["confidence_label"],
                "examplesMatched": len(examples),
                "dataset": f"data/{DATASET_NAME}",
                "skillsFramework": _framework_grounding(facts),
                "apiModel": model,
                "latencyMs": latency_ms,
                "maxTokens": max_tokens,
            "fallback": False,
        },
        "suggestedActions": [
            {"action": "why", "label": "Why this?"},
            {"action": "cheaper", "label": "Make it cheaper"},
            {"action": "two_hours", "label": "Only 2 hours"},
            {"action": "helper", "label": "For a helper"},
        ],
    }


def _build_google_payload(
    action: str,
    facts: dict[str, Any],
    question: str,
    action_examples: list[dict[str, Any]],
    all_examples: list[dict[str, Any]],
    request_mode: str,
) -> dict[str, Any]:
    temperature = float(os.getenv("GOOGLE_CLOUD_AI_TEMPERATURE", "0.2"))
    max_tokens = int(os.getenv("GOOGLE_CLOUD_AI_MAX_TOKENS", "240"))

    top_examples = action_examples[:2]
    shared_examples = (all_examples[:2] if len(action_examples) < 2 else []) + top_examples
    example_block = "\n".join(
        [
            f"- [{item.get('action')}] {item.get('ideal_response', '').strip()}"
            for item in shared_examples
            if isinstance(item, dict) and item.get("ideal_response")
        ]
    ) or "No examples loaded."

    style = next((item.get("output_style") for item in top_examples if item.get("output_style")), "Use short sentences and one clear action.")
    return {
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        "You are SkillQuest Mentor, a learning guide for adults with low digital literacy. "
                        "Only use the recommendation facts provided by the app. "
                        "Return strict JSON only: {\"title\":string, \"summary\":string, \"steps\":array}. "
                        f"Use this style: {style} "
                        "Keep all language simple. Keep answers short and practical. "
                        "Never claim certainty for funding or enrolment and never invent links."
                    )
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            f"Request mode: {request_mode}. "
                            f"Action: {action}. "
                            f"Question: {question or 'default'}.\n"
                            f"Role: {facts['role_title']}\n"
                            f"Top skill to learn first: {facts['top_skill']}\n"
                            f"Course: {facts['course_title']} by {facts['course_provider']}\n"
                            f"Course cost: {facts['course_cost']}.\n"
                            f"Weekly load: {facts['weekly_load']} hours\n"
                            f"Confidence: {facts['confidence_label']}\n"
                            f"SkillsFuture role evidence: {facts['framework_role_summary']}\n"
                            f"SkillsFuture skill evidence: {facts['framework_skill_summary']}\n"
                            f"Top 3 gap reasons: {', '.join(facts['gap_summary'])}\n"
                            f"Tradeoffs: {', '.join(facts['tradeoffs'])}\n\n"
                            f"Example responses:\n{example_block}\n"
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }


def _extract_model_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        return ""
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    if not isinstance(parts, list):
        return ""
    text = "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict) and part.get("text"))
    return text.strip()


def _build_openai_payload(
    action: str,
    facts: dict[str, Any],
    question: str,
    action_examples: list[dict[str, Any]],
    all_examples: list[dict[str, Any]],
    request_mode: str,
) -> dict[str, Any]:
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
    max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "240"))

    top_examples = action_examples[:2]
    shared_examples = (all_examples[:2] if len(action_examples) < 2 else []) + top_examples
    example_block = "\n".join(
        [
            f"- [{item.get('action')}] {item.get('ideal_response', '').strip()}"
            for item in shared_examples
            if isinstance(item, dict) and item.get("ideal_response")
        ]
    ) or "No examples loaded."

    style = next((item.get("output_style") for item in top_examples if item.get("output_style")), "Use short sentences and one clear action.")
    return {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are SkillQuest Mentor, a learning guide for adults with low digital literacy. "
                    "Only use the recommendation facts provided by the app. "
                    f"Return strict JSON only: {{\\\"title\\\":string, \\\"summary\\\":string, \\\"steps\\\":array}}. "
                    f"Use this style: {style} "
                    "Keep all language simple. Keep answers short and practical. "
                    "Never claim certainty for funding or enrolment and never invent links."
                ),
            },
            {
                "role": "system",
                "content": (
                    "Example responses:\n"
                    f"{example_block}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Request mode: {request_mode}. "
                    f"Action: {action}. "
                    f"Question: {question or 'default'}.\n"
                    f"Role: {facts['role_title']}\n"
                    f"Top skill to learn first: {facts['top_skill']}\n"
                    f"Role: {facts['role_title']}\n"
                    f"Course: {facts['course_title']} by {facts['course_provider']}\n"
                    f"Course cost: {facts['course_cost']}\n"
                    f"Weekly load: {facts['weekly_load']} hours\n"
                    f"Confidence: {facts['confidence_label']}\n"
                    f"SkillsFuture role evidence: {facts['framework_role_summary']}\n"
                    f"SkillsFuture skill evidence: {facts['framework_skill_summary']}\n"
                    f"Top 3 gap reasons: {', '.join(facts['gap_summary'])}\n"
                    f"Tradeoffs: {', '.join(facts['tradeoffs'])}\n"
                ),
            },
        ],
    }


def _parse_json_like(value: str) -> dict[str, Any] | None:
    text = value.strip()
    if not text:
        return None
    candidates = [text]

    code_match = re.search(r"```json\\s*(.*?)```", text, re.S | re.I)
    if code_match:
        candidates.insert(0, code_match.group(1).strip())
    first_curly = text.find("{")
    if first_curly >= 0 and text.endswith("}"):
        candidates.insert(0, text[first_curly:])

    for candidate in candidates:
        try:
            loaded = json.loads(candidate)
            if isinstance(loaded, dict):
                return loaded
        except json.JSONDecodeError:
            continue
    return None


def load_training_examples(data_dir: Path) -> list[dict[str, Any]]:
    path = data_dir / DATASET_NAME
    if not path.exists():
        return []

    examples: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            examples.append(item)
    return examples


def _extract_facts(recommendation: dict[str, Any]) -> dict[str, Any]:
    role = recommendation.get("recommendedRole") or {}
    course = recommendation.get("bestCourse") or {}
    confidence = recommendation.get("confidence") or {}
    readiness = recommendation.get("readiness") or {}
    framework = role.get("framework") or {}
    gaps = [gap for gap in recommendation.get("skillGaps", []) if isinstance(gap, dict)]
    missing_gaps = [gap for gap in gaps if gap.get("gapSize", 0) > 0]
    top_gaps = (missing_gaps or gaps)[:3]
    top_gap = (missing_gaps or gaps or [{}])[0]
    alternatives = [item for item in recommendation.get("recommendedCourses", []) if isinstance(item, dict)]

    cheapest_course = min(alternatives or [course], key=lambda item: float(item.get("estimatedOutOfPocket") or 0))
    role_why = [str(item) for item in (role.get("why") or [])[:2]]
    course_why = [str(item) for item in (course.get("whyChosen") or [])[:2]]
    tradeoffs = [str(item) for item in (course.get("tradeoffs") or [])[:2]]
    official_roles = _official_role_titles(framework)
    official_skills = _official_skill_titles(framework, gaps)
    framework_source = str(framework.get("name") or "SkillsFuture reference")
    framework_role_summary = _join_short(official_roles, "No official role match supplied.")
    framework_skill_summary = _join_short(official_skills, "No official skill match supplied.")

    return {
        "role_title": str(role.get("title") or "this role"),
        "course_title": str(course.get("title") or "the first course"),
        "course_provider": str(course.get("provider") or "the provider"),
        "course_cost": _money(course.get("estimatedOutOfPocket")),
        "weekly_load": course.get("weeklyLoadHours") or "?",
        "top_skill": str(top_gap.get("skill") or "one starter skill"),
        "top_quest": str(top_gap.get("quest") or "Try one small practice task."),
        "confidence_label": str(confidence.get("level") or "Medium"),
        "confidence_score": confidence.get("score") or "?",
        "readiness_score": readiness.get("score") or "?",
        "readiness_label": str(readiness.get("label") or "Start here"),
        "why_role": role_why,
        "why_course": course_why,
        "cheapest_title": str(cheapest_course.get("title") or course.get("title") or "the lowest-cost option"),
        "cheapest_cost": _money(cheapest_course.get("estimatedOutOfPocket")),
        "tradeoffs": tradeoffs,
        "gap_summary": [str(gap.get("impact") or "") for gap in top_gaps if str(gap.get("impact", "")).strip()],
        "framework_source": framework_source,
        "framework_sector": str(framework.get("sector") or "Not mapped"),
        "framework_note": str(framework.get("note") or ""),
        "framework_record_counts": framework.get("recordCounts") if isinstance(framework.get("recordCounts"), dict) else {},
        "official_roles": official_roles,
        "official_skills": official_skills,
        "framework_role_summary": framework_role_summary,
        "framework_skill_summary": framework_skill_summary,
    }


def _render_action(action: str, facts: dict[str, Any], question: str) -> dict[str, Any]:
    if action == "why":
        reasons = facts["why_role"] + facts["why_course"]
        if not reasons:
            reasons = [f"It builds {facts['top_skill']} first.", f"It fits a {facts['role_title']} pathway."]
        return {
            "title": "Why this path",
            "summary": (
                f"SkillQuest suggests {facts['role_title']} because it matches your answers, SkillsFuture role evidence, and starts with {facts['top_skill']}."
            ),
            "steps": [
                *reasons[:2],
                f"SkillsFuture role check: {facts['framework_role_summary']}.",
                f"Matched skill evidence: {facts['framework_skill_summary']}.",
                f"Confidence is {facts['confidence_label']} at {facts['confidence_score']}%.",
            ],
        }

    if action == "cheaper":
        return {
            "title": "Lower-cost version",
            "summary": f"Start with {facts['cheapest_title']} and check the provider before paying.",
            "steps": [
                f"Planning estimate: {facts['cheapest_cost']}.",
                f"Practise {facts['top_skill']} with a free mini task before enrolling.",
                "Ask the provider to confirm subsidy, SkillsFuture Credit, and any extra fees.",
            ],
        }

    if action == "two_hours":
        return {
            "title": "Two-hour week",
            "summary": f"Keep the same goal, but make this week about one small {facts['top_skill']} step.",
            "steps": [
                "20 minutes: read the course page or ask someone to read it with you.",
                f"60 minutes: practise this task: {facts['top_quest']}",
                "30 minutes: write down what was easy and what was hard.",
                f"10 minutes: compare your work with the SkillsFuture skill: {facts['framework_skill_summary']}.",
            ],
        }

    if action == "helper":
        return {
            "title": "Helper script",
            "summary": f"Help the learner start calmly: the suggested path is {facts['role_title']}.",
            "steps": [
                f"Read this aloud: Your first skill is {facts['top_skill']}.",
                f"Show the course: {facts['course_title']} by {facts['course_provider']}.",
                f"Explain the SkillsFuture match: {facts['framework_role_summary']}.",
                "Check time, cost, and travel together before any enrolment.",
                "Do not rush the learner. The goal today is one clear next step.",
            ],
        }

    prefix = f"About your question: {question} " if question else ""
    return {
        "title": "Simple guide",
        "summary": (
            f"{prefix}Your next step is to build {facts['top_skill']} for a {facts['role_title']} path."
        ),
        "steps": [
            f"Start with: {facts['top_quest']}",
            f"SkillsFuture skill match: {facts['framework_skill_summary']}.",
            f"Course to check: {facts['course_title']}.",
            f"Time needed: about {facts['weekly_load']} hours each week.",
            f"Cost shown: {facts['course_cost']}. Check with the provider before enrolling.",
        ],
    }


def _caveats(facts: dict[str, Any]) -> list[str]:
    caveats = [
        f"This guide uses local app data and {facts['framework_source']} evidence.",
        "It does not decide funding, subsidy, eligibility, or enrolment.",
    ]
    if facts.get("framework_note"):
        caveats.append(facts["framework_note"])
    if facts["confidence_label"].lower() != "high":
        caveats.append("Add more skills, location, or goal details to improve confidence.")
    return caveats[:4]


def _official_role_titles(framework: dict[str, Any]) -> list[str]:
    roles = framework.get("officialRoles") or []
    if not isinstance(roles, list):
        return []
    titles = []
    for role in roles:
        if not isinstance(role, dict):
            continue
        title = str(role.get("jobRole") or "").strip()
        if title and title not in titles:
            titles.append(title)
    return titles[:3]


def _official_skill_titles(framework: dict[str, Any], gaps: list[dict[str, Any]]) -> list[str]:
    titles = []
    for gap in gaps:
        evidence = gap.get("frameworkEvidence") if isinstance(gap, dict) else None
        if not isinstance(evidence, dict):
            continue
        title = str(evidence.get("officialSkill") or "").strip()
        if title and title not in titles:
            titles.append(title)
    for skill in framework.get("officialSkills") or []:
        if not isinstance(skill, dict):
            continue
        title = str(skill.get("uniqueSkill") or skill.get("title") or "").strip()
        if title and title not in titles:
            titles.append(title)
        if len(titles) >= 4:
            break
    return titles[:4]


def _join_short(values: list[str], fallback: str) -> str:
    if not values:
        return fallback
    return "; ".join(values[:3])


def _framework_grounding(facts: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": facts["framework_source"],
        "sector": facts["framework_sector"],
        "officialRoles": facts["official_roles"],
        "officialSkills": facts["official_skills"],
        "recordCounts": facts["framework_record_counts"],
        "note": facts["framework_note"],
    }


def _money(value: Any) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "unknown cost"
    if amount <= 0:
        return "$0 planning estimate"
    if amount.is_integer():
        return f"${int(amount)} planning estimate"
    return f"${amount:.2f} planning estimate"


class MentorInputError(ValueError):
    """Raised when the mentor endpoint receives an unusable request."""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


POSITIVE_WORDS = {"clear", "good", "useful", "helpful", "friendly", "practical", "current", "memorable", "relevant"}
NEGATIVE_WORDS = {"demanding", "intense", "long", "wanted", "more", "could", "revision"}
SECRET_QUERY_PARAMS = {"key", "api_key", "apikey", "token", "access_token", "auth", "authorization"}

SKILL_ALIASES = {
    "spreadsheet modelling": {"strong": ["excel", "spreadsheet", "worksheet"], "weak": ["data entry", "admin reporting"]},
    "data analysis": {"strong": ["reporting", "analytics"], "weak": ["excel", "data entry", "operations data"]},
    "business storytelling": {"strong": ["presentation", "communication"], "weak": ["customer service", "stakeholder update"]},
    "stakeholder communication": {"strong": ["customer service", "communication"], "weak": ["frontline support", "teaching"]},
    "process mapping": {"strong": ["operations", "workflow"], "weak": ["admin process", "service process"]},
    "campaign analytics": {"strong": ["marketing metrics"], "weak": ["sales report", "social media"]},
    "user research": {"strong": ["customer interview"], "weak": ["customer service", "feedback collection"]},
    "incident documentation": {"strong": ["documentation"], "weak": ["helpdesk", "case notes"]},
}


def build_recommendation(
    payload: dict[str, Any],
    roles: list[dict[str, Any]],
    courses: list[dict[str, Any]],
    funding_rules: dict[str, Any],
    skills_framework: dict[str, Any] | None = None,
    market_signal: dict[str, Any] | None = None,
    location_signal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = _normalise_profile(payload, location_signal)
    skills_framework = skills_framework or {}
    market_signal = market_signal or {"status": "skipped", "top_skills": []}
    role_scores = [_score_role(role, profile, market_signal) for role in roles]
    role_scores.sort(key=lambda item: item["score"], reverse=True)
    chosen_role = role_scores[0]["role"] if role_scores else roles[0]
    chosen_role_score = role_scores[0] if role_scores else {"score": 0, "reasons": []}

    framework_match = _framework_match(chosen_role, skills_framework)
    gaps = _apply_framework_evidence(_skill_gaps(chosen_role, profile, market_signal), framework_match)
    readiness = _readiness(chosen_role, profile, gaps)
    ranked_courses = [_score_course(course, gaps, profile, funding_rules) for course in courses]
    ranked_courses.sort(key=lambda item: item["match_score"], reverse=True)
    best_course = ranked_courses[0] if ranked_courses else None
    confidence = _confidence(profile, readiness, best_course, market_signal, location_signal, framework_match)

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "mode": profile["mode"],
        "profile": profile,
        "sourceSummary": _source_summary(market_signal, location_signal, skills_framework),
        "recommendedRole": {
            "id": chosen_role.get("id"),
            "title": chosen_role.get("title"),
            "category": chosen_role.get("category"),
            "description": chosen_role.get("description"),
            "dailyTasks": chosen_role.get("daily_tasks", []),
            "suitabilityScore": round(chosen_role_score["score"]),
            "why": chosen_role_score["reasons"],
            "framework": framework_match,
        },
        "alternativeRoles": [
            {
                "id": score["role"].get("id"),
                "title": score["role"].get("title"),
                "score": round(score["score"]),
                "category": score["role"].get("category"),
            }
            for score in role_scores[1:4]
        ],
        "readiness": readiness,
        "skillGaps": gaps[:8],
        "recommendedCourses": ranked_courses[:5],
        "bestCourse": best_course,
        "confidence": confidence,
        "explanation": _explanation(chosen_role, chosen_role_score, gaps, best_course, confidence),
        "questline": _questline(chosen_role, gaps, best_course, profile),
        "aiMentor": _mentor(chosen_role, gaps, best_course, readiness, profile),
        "recalculationTriggers": [
            "Change target role",
            "Add a mastered skill",
            "Change weekly study time",
            "Change budget",
            "Change location or travel tolerance",
            "Connect calendar or adjust schedule preference",
            "Refresh market skill signals",
        ],
    }


def _normalise_profile(payload: dict[str, Any], location_signal: dict[str, Any] | None) -> dict[str, Any]:
    skills = _as_list(payload.get("skills"))
    interests = _as_list(payload.get("interests"))
    current_role = str(payload.get("currentRole") or payload.get("current_role") or "").strip()
    target_role = str(payload.get("targetRole") or payload.get("target_role") or "").strip()
    location = str(payload.get("location") or "").strip()
    first_location = None
    if location_signal and location_signal.get("items"):
        first_location = location_signal["items"][0]

    return {
        "mode": payload.get("mode") if payload.get("mode") in {"explorer", "pathfinder"} else "explorer",
        "interests": interests,
        "targetRole": target_role,
        "currentRole": current_role,
        "skills": skills,
        "skillIndex": {_key(skill): skill for skill in skills},
        "weeklyHours": _number(payload.get("weeklyHours") or payload.get("weekly_hours"), 6),
        "budget": _number(payload.get("budget"), 700),
        "learningMode": str(payload.get("learningMode") or payload.get("learning_mode") or "Blended").strip(),
        "preferredSchedule": str(payload.get("preferredSchedule") or payload.get("preferred_schedule") or "Evenings").strip(),
        "location": location,
        "resolvedLocation": first_location,
        "travelToleranceMinutes": _number(payload.get("travelToleranceMinutes") or payload.get("travel_tolerance_minutes"), 45),
    }


def _score_role(role: dict[str, Any], profile: dict[str, Any], market_signal: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    target = _key(profile["targetRole"])
    title = _key(role.get("title"))
    if profile["mode"] == "pathfinder" and target and (target in title or title in target):
        target_score = 45
        reasons.append("Matches your chosen target role.")
    elif profile["mode"] == "pathfinder" and target and any(target in _key(bridge) for bridge in role.get("current_role_bridges", [])):
        target_score = 25
        reasons.append("Connects to your stated current role.")
    else:
        target_score = 0

    interest_overlap = set(map(_key, profile["interests"])) & set(map(_key, role.get("interests", [])))
    interest_score = min(25, len(interest_overlap) * 8)
    if interest_overlap:
        reasons.append(f"Fits your interests: {', '.join(sorted(interest_overlap)[:3])}.")

    skill_score = _role_skill_readiness(role, profile) * 25
    if skill_score:
        reasons.append("Uses skills you already have.")

    bridge_score = 0
    if profile["currentRole"]:
        current = _key(profile["currentRole"])
        if any(current in _key(bridge) or _key(bridge) in current for bridge in role.get("current_role_bridges", [])):
            bridge_score = 15
            reasons.append("Has a realistic bridge from your current work.")

    market_score = 0
    market_skills = {_key(item.get("name")) for item in market_signal.get("top_skills", [])[:10]}
    required = {_key(skill["name"]) for skill in role.get("required_skills", [])}
    if market_skills & required:
        market_score = 10
        reasons.append("Recent job postings mention related skills.")

    if not reasons:
        reasons.append("Useful exploratory match based on the selected constraints.")

    return {"role": role, "score": min(100, target_score + interest_score + skill_score + bridge_score + market_score), "reasons": reasons[:4]}


def _role_skill_readiness(role: dict[str, Any], profile: dict[str, Any]) -> float:
    required = role.get("required_skills", [])
    if not required:
        return 0.0
    total_weight = sum(skill.get("importance", 1) for skill in required)
    matched_weight = 0.0
    for skill in required:
        alias_strength = _alias_strength(profile, skill["name"])
        if _has_skill(profile, skill["name"]):
            matched_weight += skill.get("importance", 1) * 0.85
        elif alias_strength >= 2:
            matched_weight += skill.get("importance", 1) * 0.65
        elif alias_strength == 1:
            matched_weight += skill.get("importance", 1) * 0.35
        elif _partial_skill_match(profile, skill["name"]):
            matched_weight += skill.get("importance", 1) * 0.45
    return matched_weight / total_weight if total_weight else 0.0


def _skill_gaps(role: dict[str, Any], profile: dict[str, Any], market_signal: dict[str, Any]) -> list[dict[str, Any]]:
    demand = {_key(item.get("name")): item.get("demand", 0) for item in market_signal.get("top_skills", [])}
    gaps = []
    for skill in role.get("required_skills", []):
        current = 2 if _has_skill(profile, skill["name"]) else max(_alias_strength(profile, skill["name"]), 1 if _partial_skill_match(profile, skill["name"]) else 0)
        required_level = skill.get("level", 3)
        gap_size = max(0, required_level - current)
        market_boost = min(2.5, demand.get(_key(skill["name"]), 0) / 3)
        priority = skill.get("importance", 1) * 10 + gap_size * 8 + market_boost
        if gap_size == 0:
            priority *= 0.4
        gaps.append(
            {
                "skill": skill["name"],
                "category": skill.get("category", "Core"),
                "currentLevel": current,
                "requiredLevel": required_level,
                "gapSize": gap_size,
                "priorityScore": round(priority, 1),
                "impact": _impact(priority),
                "why": _gap_reason(skill, market_boost, profile),
                "quest": skill.get("quest"),
            }
        )
    gaps.sort(key=lambda item: item["priorityScore"], reverse=True)
    return gaps


def _readiness(role: dict[str, Any], profile: dict[str, Any], gaps: list[dict[str, Any]]) -> dict[str, Any]:
    required = role.get("required_skills", [])
    if not required:
        score = 0
    else:
        total = sum(item.get("level", 3) * item.get("importance", 1) for item in required)
        remaining = sum(item["gapSize"] * _importance_for(role, item["skill"]) for item in gaps)
        score = max(5, min(95, round(100 * (1 - remaining / total)))) if total else 0
    transferable = [skill for skill in profile["skills"] if any(_partial_name(skill, req["name"]) for req in required)]
    label = "Ready for first course" if score >= 70 else "On track" if score >= 45 else "Start with foundations"
    return {
        "score": score,
        "label": label,
        "confidence": "High" if profile["skills"] and (profile["targetRole"] or profile["interests"]) else "Medium",
        "transferableSkills": transferable[:5],
        "summary": f"You are about {score}% ready for a {role.get('title')} pathway.",
    }


def _score_course(course: dict[str, Any], gaps: list[dict[str, Any]], profile: dict[str, Any], funding_rules: dict[str, Any]) -> dict[str, Any]:
    missing_skills = [gap["skill"] for gap in gaps if gap["gapSize"] > 0]
    covered = [skill for skill in missing_skills if any(_partial_name(skill, course_skill) for course_skill in course.get("skills", []))]
    priority_total = sum(gap["priorityScore"] for gap in gaps if gap["gapSize"] > 0) or 1
    covered_priority = sum(gap["priorityScore"] for gap in gaps if gap["skill"] in covered)
    coverage_ratio = covered_priority / priority_total
    top_gap = next((gap for gap in gaps if gap["gapSize"] > 0), None)
    covers_top_gap = bool(top_gap and top_gap["skill"] in covered)
    coverage_score = 42 * coverage_ratio

    out_of_pocket = _estimate_out_of_pocket(course, funding_rules)
    budget = max(1, profile["budget"])
    cost_score = 20 if out_of_pocket <= budget else max(0, 20 - ((out_of_pocket - budget) / budget) * 20)

    weekly_hours = max(1, profile["weeklyHours"])
    weekly_load = (course.get("sessions_per_week", 1) or 1) * (course.get("session_length_hours", 2) or 2)
    load_ratio = weekly_load / weekly_hours
    time_score = max(0, 18 - abs(load_ratio - 0.75) * 12)
    if course.get("duration_hours", 0) > weekly_hours * 10:
        time_score -= 3
    if profile["preferredSchedule"].lower() in str(course.get("schedule", "")).lower():
        time_score += 4

    mode_score = 10 if _key(profile["learningMode"]) in _key(course.get("mode")) or _key(course.get("mode")) in _key(profile["learningMode"]) else 4
    location = _location_fit(course, profile)
    quality_score = min(12, (course.get("rating", 0) / 5) * 9 + min(3, course.get("review_count", 0) / 80))
    sentiment = _sentiment(course.get("review_snippets", []))

    raw_score = max(0, coverage_score + cost_score + time_score + mode_score + location["score"] + quality_score)
    cap = 100
    if not covers_top_gap:
        cap = 74
    elif coverage_ratio < 0.55:
        cap = 88
    score = min(cap, raw_score)
    not_covered = [gap["skill"] for gap in gaps if gap["gapSize"] > 0 and gap["skill"] not in covered][:4]
    return {
        "id": course.get("id"),
        "title": course.get("title"),
        "provider": course.get("provider"),
        "description": course.get("description"),
        "skillsCovered": covered,
        "skillsNotCovered": not_covered,
        "coverageRatio": round(coverage_ratio, 2),
        "coversTopGap": covers_top_gap,
        "allSkills": course.get("skills", []),
        "match_score": round(score),
        "level": course.get("level"),
        "mode": course.get("mode"),
        "schedule": course.get("schedule"),
        "durationHours": course.get("duration_hours"),
        "weeklyLoadHours": round(weekly_load, 1),
        "fee": course.get("fee"),
        "estimatedOutOfPocket": round(out_of_pocket, 2),
        "fundingEstimateLabel": _funding_label(out_of_pocket),
        "fundingNote": funding_rules.get("disclaimer"),
        "location": {
            "region": course.get("region"),
            "address": course.get("address"),
            **location,
        },
        "quality": {
            "rating": course.get("rating"),
            "reviewCount": course.get("review_count"),
            "sentiment": sentiment,
        },
        "tradeoffs": _tradeoffs(out_of_pocket, budget, weekly_load, weekly_hours, location, course),
        "whyChosen": _course_reasons(covered, not_covered, out_of_pocket, budget, weekly_load, weekly_hours, location, course),
        "sourceUrl": course.get("source_url"),
    }


def _questline(role: dict[str, Any], gaps: list[dict[str, Any]], best_course: dict[str, Any] | None, profile: dict[str, Any]) -> list[dict[str, Any]]:
    first_gap = next((gap for gap in gaps if gap["gapSize"] > 0), gaps[0] if gaps else None)
    second_gap = next((gap for gap in gaps if first_gap and gap["skill"] != first_gap["skill"]), None)
    return [
        {
            "step": 1,
            "title": "Discover & Assess",
            "status": "ready",
            "estimate": "10 minutes",
            "action": "Confirm interests, existing skills, weekly time, budget, and location.",
        },
        {
            "step": 2,
            "title": f"Build {first_gap['skill'] if first_gap else 'foundation'}",
            "status": "unlocked",
            "estimate": _hours_label(profile["weeklyHours"]),
            "action": first_gap["quest"] if first_gap else "Complete a starter learning quest.",
        },
        {
            "step": 3,
            "title": "Start best-fit course",
            "status": "recommended" if best_course else "locked",
            "estimate": f"{best_course['durationHours']} hours" if best_course else "Pending course match",
            "action": f"Shortlist {best_course['title']}." if best_course else "Find a course after skill gaps are calculated.",
        },
        {
            "step": 4,
            "title": "Apply & Grow",
            "status": "locked",
            "estimate": "1 mini project",
            "action": second_gap["quest"] if second_gap else f"Complete a portfolio task for {role.get('title')}.",
        },
    ]


def _mentor(role: dict[str, Any], gaps: list[dict[str, Any]], best_course: dict[str, Any] | None, readiness: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    first_gap = next((gap for gap in gaps if gap["gapSize"] > 0), gaps[0] if gaps else None)
    course_title = best_course["title"] if best_course else "a foundation course"
    risk = []
    if best_course and best_course["weeklyLoadHours"] > profile["weeklyHours"]:
        risk.append("The recommended course may exceed your weekly time budget.")
    if best_course and best_course["estimatedOutOfPocket"] > profile["budget"]:
        risk.append("Estimated out-of-pocket cost is above your stated budget.")
    if best_course and best_course["location"].get("travelMinutes", 0) > profile["travelToleranceMinutes"]:
        risk.append("Travel time may be too high for your tolerance.")
    if not risk:
        risk.append("No major time, budget, or travel conflict detected for the top recommendation.")

    return {
        "nextBestAction": f"Start with {first_gap['skill'] if first_gap else course_title}",
        "why": [
            f"{role.get('title')} readiness is currently {readiness['score']}%.",
            f"The highest-priority gap is {first_gap['skill']}." if first_gap else "Your starting gap is still being assessed.",
            f"{course_title} has the best combined fit across skills, time, cost, location, and quality." if best_course else "Add more profile detail to improve course matching.",
        ],
        "risks": risk,
        "promptSuggestions": [
            "Why did you recommend this path?",
            "Make this plan fit my weekly schedule.",
            "Show me a cheaper alternative.",
            "What should I learn first if I only have 2 hours?",
        ],
    }


def _framework_match(role: dict[str, Any], skills_framework: dict[str, Any]) -> dict[str, Any]:
    mapping = (skills_framework.get("role_mappings") or {}).get(role.get("id"), {})
    official_roles = _compact_official_roles(mapping.get("officialRoles", []))
    official_skills = _compact_official_skills(mapping.get("officialSkills", []))
    aligned = mapping.get("alignedAppSkills", [])
    return {
        "name": skills_framework.get("name", "Skills Framework reference"),
        "sector": mapping.get("sector", "Not mapped"),
        "framework": mapping.get("framework", "Local role mapping"),
        "confidence": mapping.get("confidence", "low"),
        "skills": mapping.get("skills", []),
        "officialRoles": official_roles[:4] if isinstance(official_roles, list) else [],
        "officialSkills": official_skills[:12] if isinstance(official_skills, list) else [],
        "alignedAppSkills": aligned[:8] if isinstance(aligned, list) else [],
        "recordCounts": skills_framework.get("record_counts", {}),
        "sourceUrl": skills_framework.get("source_url"),
        "note": (
            "Mapped from local SkillsFuture XLSX datasets. Verify official role, course, and enrolment details before acting."
            if skills_framework.get("status") == "official-xlsx-normalised"
            else "Reference mapping only. Verify official role and course details before enrolment."
        ),
    }


def _apply_framework_evidence(gaps: list[dict[str, Any]], framework_match: dict[str, Any]) -> list[dict[str, Any]]:
    aligned = framework_match.get("alignedAppSkills") or []
    by_skill = {_key(item.get("appSkill")): item for item in aligned if isinstance(item, dict)}
    official_skills = framework_match.get("officialSkills") or []
    official_by_code = {item.get("code"): item for item in official_skills if isinstance(item, dict)}
    for gap in gaps:
        match = by_skill.get(_key(gap.get("skill")))
        if not match:
            continue
        code = match.get("officialCode")
        official = official_by_code.get(code, {})
        score = float(match.get("matchScore") or 0)
        if score <= 0:
            continue
        gap["frameworkEvidence"] = {
            "source": framework_match.get("name"),
            "officialSkill": match.get("officialSkill"),
            "officialCode": code,
            "matchScore": round(score, 2),
            "description": official.get("description") or official.get("uniqueSkillDescription") or "",
            "proficiencyLevels": official.get("proficiencyLevels") or [],
        }
    return gaps


def _compact_official_roles(roles: Any) -> list[dict[str, Any]]:
    if not isinstance(roles, list):
        return []
    compact = []
    for role in roles[:3]:
        if not isinstance(role, dict):
            continue
        compact.append(
            {
                "sector": role.get("sector"),
                "track": role.get("track"),
                "jobRole": role.get("jobRole"),
                "description": str(role.get("description") or "")[:180],
            }
        )
    return compact


def _compact_official_skills(skills: Any) -> list[dict[str, Any]]:
    if not isinstance(skills, list):
        return []
    compact = []
    for skill in skills[:8]:
        if not isinstance(skill, dict):
            continue
        compact.append(
            {
                "title": skill.get("title"),
                "uniqueSkill": skill.get("uniqueSkill"),
                "code": skill.get("code"),
                "type": skill.get("type"),
                "category": skill.get("category"),
                "description": str(skill.get("description") or skill.get("uniqueSkillDescription") or "")[:180],
                "proficiencyLevels": skill.get("proficiencyLevels") or [],
            }
        )
    return compact


def _confidence(
    profile: dict[str, Any],
    readiness: dict[str, Any],
    best_course: dict[str, Any] | None,
    market_signal: dict[str, Any],
    location_signal: dict[str, Any] | None,
    framework_match: dict[str, Any],
) -> dict[str, Any]:
    score = 35
    reasons: list[str] = []
    if profile["skills"]:
        score += 18
        reasons.append("You selected current skills.")
    if profile["mode"] == "pathfinder" and profile["targetRole"]:
        score += 14
        reasons.append("You gave a target role.")
    elif profile["interests"]:
        score += 10
        reasons.append("You selected interests and abilities.")
    if best_course and best_course.get("coversTopGap"):
        score += 12
        reasons.append("Top course covers the first priority gap.")
    if market_signal.get("status") == "ok":
        score += 10
        reasons.append("Live job skill signal was available.")
    elif market_signal.get("status") == "offline":
        reasons.append("Using private offline role-skill signals.")
    if location_signal and location_signal.get("status") in {"ok", "offline"}:
        score += 6
        reasons.append("Location estimate was available.")
    if framework_match.get("sector") != "Not mapped":
        score += 5
        reasons.append("Role has a Skills Framework reference mapping.")

    score = max(1, min(100, score))
    level = "High" if score >= 78 else "Medium" if score >= 55 else "Low"
    caveats = []
    if market_signal.get("status") != "ok":
        caveats.append("No live job lookup was used for this result.")
    if not profile["targetRole"] and profile["mode"] == "explorer":
        caveats.append("This is an exploratory path, not a confirmed career decision.")
    if best_course and best_course.get("estimatedOutOfPocket", 0) == 0:
        caveats.append("A $0 estimate depends on assumptions and must be checked with the provider.")
    caveats.append("Funding, eligibility, and enrolment are not decided by SkillQuest.")
    return {"score": score, "level": level, "reasons": reasons[:5], "caveats": caveats[:5], "readinessLabel": readiness.get("label")}


def _explanation(
    role: dict[str, Any],
    chosen_role_score: dict[str, Any],
    gaps: list[dict[str, Any]],
    best_course: dict[str, Any] | None,
    confidence: dict[str, Any],
) -> dict[str, Any]:
    top_gaps = [gap for gap in gaps if gap["gapSize"] > 0][:3]
    return {
        "whereNext": f"{role.get('title')} is the suggested next path.",
        "skillsMatter": [gap["skill"] for gap in top_gaps],
        "todayAction": best_course["whyChosen"][0] if best_course else "Pick one starter skill and do a 10-minute check.",
        "whyRole": chosen_role_score.get("reasons", [])[:3],
        "whyCourse": best_course.get("whyChosen", [])[:4] if best_course else [],
        "tradeoffs": best_course.get("tradeoffs", [])[:4] if best_course else [],
        "confidence": f"{confidence['level']} confidence ({confidence['score']}%).",
    }


def _funding_label(out_of_pocket: float) -> str:
    if out_of_pocket <= 0:
        return "$0 planning estimate. Check subsidy and credit eligibility."
    return f"${round(out_of_pocket, 2):g} planning estimate after assumptions."


def _course_reasons(
    covered: list[str],
    not_covered: list[str],
    out_of_pocket: float,
    budget: float,
    weekly_load: float,
    weekly_hours: float,
    location: dict[str, Any],
    course: dict[str, Any],
) -> list[str]:
    reasons = []
    if covered:
        reasons.append(f"Covers {', '.join(covered[:3])}.")
    if not_covered:
        reasons.append(f"Does not cover {', '.join(not_covered[:2])}; keep these for later.")
    reasons.append("Fits your weekly time." if weekly_load <= weekly_hours else "May be heavy for your weekly time.")
    reasons.append("Within your stated budget using planning assumptions." if out_of_pocket <= budget else "Costs more than your stated budget.")
    reasons.append(location.get("reason", "Location needs checking."))
    if course.get("source_url"):
        reasons.append("Use the course source link to verify enrolment details.")
    return reasons


def _source_summary(market_signal: dict[str, Any], location_signal: dict[str, Any] | None, skills_framework: dict[str, Any]) -> list[dict[str, Any]]:
    counts = skills_framework.get("record_counts") or {}
    if counts:
        framework_detail = (
            f"Using {counts.get('jobRoles', 0)} job roles, {counts.get('uniqueSkills', 0)} unique skills, "
            f"and {counts.get('jobRoleSkillRows', 0)} role-skill rows from local SkillsFuture XLSX files."
        )
    else:
        framework_detail = "Using a small local role-skill mapping from public Skills Framework references."
    summary = [
        {
            "name": "Role and course seed datasets",
            "status": "ok",
            "detail": "Loaded local JSON datasets for baseline recommendations.",
        },
        {
            "name": "SkillsFuture Skills Framework reference",
            "status": skills_framework.get("status", "local-normalised"),
            "detail": framework_detail,
            "url": skills_framework.get("source_url"),
        },
        {
            "name": "MyCareersFuture",
            "status": market_signal.get("status", "skipped"),
            "detail": (
                f"Checked {len(market_signal.get('items', []))} returned job records."
                if market_signal.get("status") == "ok"
                else market_signal.get("detail") or market_signal.get("error", "Live lookup not used.")
            ),
            "url": _redacted_source_url(market_signal.get("url")),
        },
    ]
    if location_signal:
        summary.append(
            {
                "name": "OneMap",
                "status": location_signal.get("status"),
                "detail": location_signal.get("warning") or (location_signal.get("items") and location_signal["items"][0].get("address")) or location_signal.get("error", "Skipped"),
                "url": _redacted_source_url(location_signal.get("url")),
            }
        )
    return summary


def _redacted_source_url(url: Any) -> str | None:
    if not url:
        return None
    parsed = urlsplit(str(url))
    query = parse_qsl(parsed.query, keep_blank_values=True)
    redacted = [
        (key, "REDACTED" if key.lower() in SECRET_QUERY_PARAMS else value)
        for key, value in query
    ]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(redacted), parsed.fragment))


def _location_fit(course: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    if _key(course.get("mode")) == "online" or _key(course.get("region")) == "online":
        return {"score": 10, "travelMinutes": 0, "distanceKm": 0, "fit": "Online", "reason": "No commute needed."}
    user_location = profile.get("resolvedLocation")
    if user_location and course.get("lat") is not None and course.get("lng") is not None:
        distance = _haversine_km(user_location["lat"], user_location["lng"], course["lat"], course["lng"])
        travel = round(12 + distance * 3.2)
        score = max(0, 10 - max(0, travel - 20) / 5)
        return {
            "score": round(score, 1),
            "travelMinutes": travel,
            "distanceKm": round(distance, 1),
            "fit": "Near" if travel <= 30 else "Manageable" if travel <= 50 else "Far",
            "reason": f"Estimated {travel} minutes from your resolved location.",
        }
    if profile["location"] and _key(profile["location"]) in _key(course.get("region")):
        return {"score": 8, "travelMinutes": 25, "distanceKm": None, "fit": "Likely near", "reason": "Region appears to match your location input."}
    return {"score": 5, "travelMinutes": 40, "distanceKm": None, "fit": "Unknown", "reason": "Add a precise location for better travel scoring."}


def _estimate_out_of_pocket(course: dict[str, Any], funding_rules: dict[str, Any]) -> float:
    fee = _number(course.get("fee"), 0)
    funded = fee * min(max(_number(course.get("funding_rate"), 0), 0), 0.95)
    credit = min(_number(funding_rules.get("credit_assumption"), 0), max(0, fee - funded))
    return max(0, fee - funded - credit)


def _tradeoffs(out_of_pocket: float, budget: float, weekly_load: float, weekly_hours: float, location: dict[str, Any], course: dict[str, Any]) -> list[str]:
    tradeoffs = []
    tradeoffs.append("Within budget after estimated funding." if out_of_pocket <= budget else "Likely needs budget top-up.")
    tradeoffs.append("Fits weekly time." if weekly_load <= weekly_hours else "Heavy weekly load.")
    tradeoffs.append(location.get("reason", "Location fit unavailable."))
    if course.get("rating", 0) >= 4.4:
        tradeoffs.append("Strong learner rating signal.")
    else:
        tradeoffs.append("Quality signal is moderate; compare alternatives.")
    return tradeoffs


def _sentiment(snippets: list[str]) -> dict[str, Any]:
    text = " ".join(snippets).lower()
    positives = sorted(word for word in POSITIVE_WORDS if word in text)
    negatives = sorted(word for word in NEGATIVE_WORDS if word in text)
    score = len(positives) - len(negatives)
    return {
        "label": "Positive" if score >= 2 else "Mixed" if score >= 0 else "Needs review",
        "positiveThemes": positives[:4],
        "negativeThemes": negatives[:4],
    }


def _gap_reason(skill: dict[str, Any], market_boost: float, profile: dict[str, Any]) -> str:
    reason = f"{skill['name']} is a {skill.get('category', 'core').lower()} skill with importance {skill.get('importance', 1)}/5."
    if market_boost:
        reason += " It also appears in recent job skill signals."
    if profile["weeklyHours"] < 4:
        reason += " Because your weekly time is limited, start with a small quest first."
    return reason


def _importance_for(role: dict[str, Any], skill_name: str) -> float:
    for item in role.get("required_skills", []):
        if item["name"] == skill_name:
            return item.get("importance", 1)
    return 1


def _impact(priority: float) -> str:
    if priority >= 50:
        return "High impact"
    if priority >= 35:
        return "Medium impact"
    return "Low impact"


def _has_skill(profile: dict[str, Any], name: str) -> bool:
    target = _key(name)
    return any(target == key or target in key or key in target for key in profile["skillIndex"])


def _partial_skill_match(profile: dict[str, Any], name: str) -> bool:
    return any(_partial_name(skill, name) for skill in profile["skills"])


def _alias_strength(profile: dict[str, Any], name: str) -> int:
    aliases = SKILL_ALIASES.get(_key(name), {})
    user_keys = list(profile["skillIndex"].keys())
    if any(alias in user_key or user_key in alias for alias in aliases.get("strong", []) for user_key in user_keys):
        return 2
    if any(alias in user_key or user_key in alias for alias in aliases.get("weak", []) for user_key in user_keys):
        return 1
    return 0


def _partial_name(left: str, right: str) -> bool:
    left_tokens = set(_key(left).split())
    right_tokens = set(_key(right).split())
    if not left_tokens or not right_tokens:
        return False
    return len(left_tokens & right_tokens) >= min(2, len(right_tokens))


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[,;|]", value) if part.strip()]
    return [str(value).strip()]


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _number(value: Any, default: float) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _hours_label(hours: float) -> str:
    hours = max(1, round(hours))
    return f"{hours} hours this week"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371
    lat1_r, lon1_r, lat2_r, lon2_r = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))

from __future__ import annotations

import json
import os
import re
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parent.parent
DOWNLOADS = Path.home() / "Downloads"
UNIQUE_SKILLS_XLSX = Path(os.getenv("SKILLQUEST_UNIQUE_SKILLS_XLSX", DOWNLOADS / "jobsandskills-skillsfuture-unique-skills-list.xlsx"))
FRAMEWORK_XLSX = Path(os.getenv("SKILLQUEST_FRAMEWORK_XLSX", DOWNLOADS / "jobsandskills-skillsfuture-skills-framework-dataset.xlsx"))
TSC_MAPPING_XLSX = Path(
    os.getenv("SKILLQUEST_TSC_MAPPING_XLSX", DOWNLOADS / "jobsandskills-skillsfuture-tsc-to-unique-skills-mapping.xlsx")
)
OUTPUT_PATH = Path(os.getenv("SKILLQUEST_SKILLS_FRAMEWORK_OUTPUT", ROOT / "data" / "skills_framework.json"))
ROLES_PATH = ROOT / "data" / "roles.json"
NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


ROLE_TARGETS = {
    "data-analyst": {
        "framework": "Skills Framework for Infocomm Technology and Financial Services data analytics roles",
        "fallback_sector": "Infocomm Technology / Data",
        "queries": [
            {"sector": "Infocomm Technology", "track": "Data and Artificial Intelligence", "role": "Data Analyst"},
            {"sector": "Financial Services", "track": "Digital and Data Analytics", "role": "Data Analyst"},
        ],
    },
    "digital-marketing-specialist": {
        "framework": "Skills Framework references for digital marketing and sales/marketing roles",
        "fallback_sector": "Business and Marketing",
        "queries": [
            {"sector": "Hotel and Accommodation Services", "track": "Sales and Marketing", "role": "Digital Marketing Executive"},
            {"sector": "Wholesale Trade", "track": "Marketing, Business Development and Analysis", "role": "Marketing Executive"},
            {"sector": "Wholesale Trade", "track": "Marketing, Business Development and Analysis", "role": "Marketing Manager"},
        ],
    },
    "ux-designer": {
        "framework": "Skills Framework for Infocomm Technology and Design user-experience roles",
        "fallback_sector": "Design / Product",
        "queries": [
            {"sector": "Infocomm Technology", "track": "Strategy and Governance", "role": "UX Designer"},
            {"sector": "Infocomm Technology", "track": "Strategy and Governance", "role": "Associate UX Designer"},
            {"sector": "Design", "track": "Innovation", "role": "Service Designer"},
            {"sector": "Design", "track": "Innovation", "role": "Design Researcher"},
        ],
    },
    "cybersecurity-associate": {
        "framework": "Skills Framework for Infocomm Technology cyber security roles",
        "fallback_sector": "Cybersecurity",
        "queries": [
            {"sector": "Infocomm Technology", "track": "Cyber Security", "role": "Associate Security Analyst"},
            {"sector": "Infocomm Technology", "track": "Cyber Security", "role": "Cyber Risk Analyst"},
            {"sector": "Infocomm Technology", "track": "Cyber Security", "role": "Incident Investigator"},
        ],
    },
    "healthcare-operations-analyst": {
        "framework": "Skills Framework for Healthcare operations roles",
        "fallback_sector": "Healthcare / Operations",
        "queries": [
            {"sector": "Healthcare", "track": "Operations", "role": "Patient Service Executive"},
            {"sector": "Healthcare", "track": "Operations", "role": "Patient Service Associate"},
            {"sector": "Healthcare", "track": "Operations", "role": "Patient Service Supervisor"},
        ],
    },
    "sustainability-analyst": {
        "framework": "Skills Framework references for sustainability reporting and assurance roles",
        "fallback_sector": "Sustainability / Business",
        "queries": [
            {"sector": "Accountancy", "track": "Sustainability Reporting and Assurance", "role": "Sustainability / Environment, Social and Governance Analyst"},
            {"sector": "Accountancy", "track": "Sustainability Reporting and Assurance", "role": "Sustainability / Environment, Social and Governance Specialist"},
        ],
    },
}


class XlsxBook:
    def __init__(self, path: Path) -> None:
        if not path.exists():
            raise FileNotFoundError(path)
        self.path = path
        self.archive = zipfile.ZipFile(path)
        self.shared = self._shared_strings()
        self.sheets = self._sheet_paths()

    def close(self) -> None:
        self.archive.close()

    def rows(self, sheet_name: str) -> list[dict[str, str]]:
        path = self.sheets[sheet_name]
        root = ET.fromstring(self.archive.read(path))
        raw_rows: list[list[str]] = []
        for row in root.findall(".//a:sheetData/a:row", NS):
            cells: dict[int, str] = {}
            for cell in row.findall("a:c", NS):
                index = _column_index(cell.get("r", ""))
                if index is not None:
                    cells[index] = self._cell_value(cell)
            width = max(cells.keys(), default=-1) + 1
            raw_rows.append([cells.get(index, "") for index in range(width)])
        if not raw_rows:
            return []
        headers = [_header(value) for value in raw_rows[0]]
        result = []
        for values in raw_rows[1:]:
            if any(value.strip() for value in values):
                result.append({headers[index]: values[index] if index < len(values) else "" for index in range(len(headers)) if headers[index]})
        return result

    def _shared_strings(self) -> list[str]:
        if "xl/sharedStrings.xml" not in self.archive.namelist():
            return []
        root = ET.fromstring(self.archive.read("xl/sharedStrings.xml"))
        return [_clean("".join(text.text or "" for text in item.findall(".//a:t", NS))) for item in root.findall("a:si", NS)]

    def _sheet_paths(self) -> dict[str, str]:
        workbook = ET.fromstring(self.archive.read("xl/workbook.xml"))
        rels = ET.fromstring(self.archive.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels.findall("rel:Relationship", NS)}
        sheets = {}
        for sheet in workbook.findall(".//a:sheet", NS):
            name = sheet.attrib["name"]
            rid = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            target = targets.get(rid, "")
            sheets[name] = "xl/" + target.lstrip("/") if not target.startswith("xl/") else target
        return sheets

    def _cell_value(self, cell: ET.Element) -> str:
        if cell.get("t") == "inlineStr":
            return _clean("".join(text.text or "" for text in cell.findall(".//a:t", NS)))
        value = cell.find("a:v", NS)
        if value is None or value.text is None:
            return ""
        if cell.get("t") == "s":
            try:
                return self.shared[int(value.text)]
            except (ValueError, IndexError):
                return ""
        return _clean(value.text)


def main() -> None:
    roles = json.loads(ROLES_PATH.read_text(encoding="utf-8"))
    app_skill_map = {role["id"]: [skill["name"] for skill in role.get("required_skills", [])] for role in roles}

    unique_book = XlsxBook(UNIQUE_SKILLS_XLSX)
    framework_book = XlsxBook(FRAMEWORK_XLSX)
    mapping_book = XlsxBook(TSC_MAPPING_XLSX)
    try:
        unique_rows = unique_book.rows("Unique Skills List")
        job_rows = framework_book.rows("Job Role_Description")
        role_skill_rows = framework_book.rows("Job Role_TCS_CCS")
        skill_key_rows = framework_book.rows("TSC_CCS_Key")
        tsc_mapping_rows = mapping_book.rows("data")
    finally:
        unique_book.close()
        framework_book.close()
        mapping_book.close()

    unique_skills = {_key(row.get("skill_title")): _unique_skill(row) for row in unique_rows if row.get("skill_title")}
    skill_key_by_code = {row.get("tsc_code"): row for row in skill_key_rows if row.get("tsc_code")}
    unique_by_code = {}
    for row in tsc_mapping_rows:
        code = row.get("skills_framework_skill_code")
        if code and code not in unique_by_code:
            unique_by_code[code] = row

    role_rows_by_key = {_role_key(row): row for row in job_rows}
    role_skills_by_key: dict[str, list[dict[str, str]]] = {}
    for row in role_skill_rows:
        role_skills_by_key.setdefault(_role_key(row), []).append(row)

    mappings = {}
    for role_id, target in ROLE_TARGETS.items():
        official_roles = _select_official_roles(job_rows, target["queries"])
        official_skills = _official_skills(official_roles, role_skills_by_key, skill_key_by_code, unique_by_code, unique_skills)
        app_skills = app_skill_map.get(role_id, [])
        mappings[role_id] = {
            "framework": target["framework"],
            "sector": _sector_summary(official_roles) or target["fallback_sector"],
            "confidence": "high" if official_roles and official_skills else "medium" if official_roles else "low",
            "skills": app_skills,
            "officialSkills": official_skills[:16],
            "officialRoles": [
                {
                    "sector": row.get("sector"),
                    "track": row.get("track"),
                    "jobRole": row.get("job_role"),
                    "description": row.get("job_role_description", "")[:360],
                }
                for row in official_roles
            ],
            "alignedAppSkills": _align_app_skills(app_skills, official_skills),
            "sourceFiles": [
                UNIQUE_SKILLS_XLSX.name,
                FRAMEWORK_XLSX.name,
                TSC_MAPPING_XLSX.name,
            ],
        }

    output = {
        "status": "official-xlsx-normalised",
        "name": "Singapore SkillsFuture Jobs-Skills dataset slice",
        "source_url": "https://jobsandskills.skillsfuture.gov.sg/frameworks/skills-frameworks",
        "sector_information_url": "https://jobsandskills.skillsfuture.gov.sg/frameworks/sector-information",
        "source_owner": "SkillsFuture Singapore Jobs-Skills Portal",
        "last_reviewed": date.today().isoformat(),
        "generated_by": "tools/import_skillsfuture_datasets.py",
        "source_files": [
            {"path": str(UNIQUE_SKILLS_XLSX), "rows": len(unique_rows)},
            {"path": str(FRAMEWORK_XLSX), "rows": len(job_rows) + len(role_skill_rows) + len(skill_key_rows)},
            {"path": str(TSC_MAPPING_XLSX), "rows": len(tsc_mapping_rows)},
        ],
        "record_counts": {
            "uniqueSkills": len(unique_rows),
            "jobRoles": len(job_rows),
            "jobRoleSkillRows": len(role_skill_rows),
            "skillKeyRows": len(skill_key_rows),
            "tscToUniqueSkillRows": len(tsc_mapping_rows),
            "mappedAppRoles": len(mappings),
        },
        "limitations": [
            "This is a normalised app slice generated from local SkillsFuture XLSX datasets supplied by the user.",
            "SkillQuest maps its six demo roles to adjacent official job roles for explainability; it does not claim official endorsement.",
            "Course details, funding, eligibility, and enrolment must still be verified on official provider or MySkillsFuture pages.",
        ],
        "role_mappings": mappings,
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} with {len(mappings)} role mappings from SkillsFuture XLSX datasets.")


def _select_official_roles(rows: list[dict[str, str]], queries: list[dict[str, str]]) -> list[dict[str, str]]:
    selected = []
    seen = set()
    for query in queries:
        for row in rows:
            if query.get("sector") and _key(row.get("sector")) != _key(query["sector"]):
                continue
            if query.get("track") and _key(row.get("track")) != _key(query["track"]):
                continue
            if query.get("role") and _key(query["role"]) not in _key(row.get("job_role")):
                continue
            key = _role_key(row)
            if key not in seen:
                seen.add(key)
                selected.append(row)
                break
    return selected


def _official_skills(
    official_roles: list[dict[str, str]],
    role_skills_by_key: dict[str, list[dict[str, str]]],
    skill_key_by_code: dict[str, dict[str, str]],
    unique_by_code: dict[str, dict[str, str]],
    unique_skills: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    dedup: dict[str, dict[str, object]] = {}
    official_keys = {_role_key(row) for row in official_roles}
    for role_key in official_keys:
        for row in role_skills_by_key.get(role_key, []):
            code = row.get("tsc_ccs_code", "")
            title = row.get("tsc_ccs_title", "")
            if not title:
                continue
            key_row = skill_key_by_code.get(code, {})
            mapping = unique_by_code.get(code, {})
            unique_title = mapping.get("unique_skill_updated_skill_title") or title
            unique = unique_skills.get(_key(unique_title), {})
            dedup_key = _key(unique_title or title)
            if dedup_key in dedup:
                levels = dedup[dedup_key].setdefault("proficiencyLevels", [])
                level = _int(row.get("proficiency_level"))
                if level is not None and level not in levels:
                    levels.append(level)
                continue
            dedup[dedup_key] = {
                "title": title,
                "uniqueSkill": unique_title,
                "code": code,
                "type": row.get("tsc_ccs_type") or key_row.get("tsc_ccs_type"),
                "category": key_row.get("tsc_ccs_category", ""),
                "description": key_row.get("tsc_ccs_description") or mapping.get("skills_framework_skill_desc") or unique.get("description", ""),
                "proficiencyLevels": [_int(row.get("proficiency_level"))] if _int(row.get("proficiency_level")) is not None else [],
                "proficiencyDescription": mapping.get("skills_framework_pl_desc", ""),
                "uniqueSkillDescription": unique.get("description") or mapping.get("unique_skill_updated_skill_desc", ""),
                "emerging": unique.get("emerging", False),
                "casl": unique.get("casl", False),
                "sectorTagging": mapping.get("unique_skill_updated_sector_tagging", ""),
                "latestUpdateDate": key_row.get("latest_update_date", ""),
            }
    return sorted(dedup.values(), key=lambda item: (str(item.get("category")), str(item.get("uniqueSkill"))))


def _align_app_skills(app_skills: list[str], official_skills: list[dict[str, object]]) -> list[dict[str, object]]:
    aligned = []
    for skill in app_skills:
        best = None
        best_score = 0
        for official in official_skills:
            candidates = [str(official.get("uniqueSkill") or ""), str(official.get("title") or ""), str(official.get("description") or "")]
            score = max(_token_score(skill, candidate) for candidate in candidates)
            if score > best_score:
                best = official
                best_score = score
        aligned.append(
            {
                "appSkill": skill,
                "officialSkill": best.get("uniqueSkill") if best and best_score > 0 else None,
                "officialCode": best.get("code") if best and best_score > 0 else None,
                "matchScore": round(best_score, 2),
            }
        )
    return aligned


def _token_score(left: str, right: str) -> float:
    left_tokens = set(_key(left).split())
    right_tokens = set(_key(right).split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(1, len(left_tokens))


def _unique_skill(row: dict[str, str]) -> dict[str, object]:
    return {
        "title": row.get("skill_title", ""),
        "description": row.get("skill_description", ""),
        "type": row.get("skill_type", ""),
        "emerging": _bool(row.get("emerging_skills")),
        "casl": _bool(row.get("casl_skills")),
    }


def _sector_summary(rows: list[dict[str, str]]) -> str:
    sectors = []
    for row in rows:
        value = row.get("sector")
        if value and value not in sectors:
            sectors.append(value)
    return " / ".join(sectors[:3])


def _role_key(row: dict[str, str]) -> str:
    return "|".join([_key(row.get("sector")), _key(row.get("track")), _key(row.get("job_role"))])


def _column_index(reference: str) -> int | None:
    match = re.match(r"([A-Z]+)", reference.upper())
    if not match:
        return None
    value = 0
    for char in match.group(1):
        value = value * 26 + (ord(char) - ord("A") + 1)
    return value - 1


def _header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _clean(value: object) -> str:
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


def _int(value: object) -> int | None:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


if __name__ == "__main__":
    main()

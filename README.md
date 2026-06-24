# SkillQuest

SkillQuest is an accessibility-first Singapore upskilling journey app. It helps a learner answer three questions quickly:

1. Where can I go next?
2. What skills matter most?
3. What should I do today?

The app keeps the first screen usable and simple: choose a path, pick current abilities, press **Upgrade my path**. The result explains the suggested role, first skill gap, course fit, confidence, tradeoffs, data sources, and a small action the learner can take now. The learner can copy the plan or open a plain helper sheet with copy/download actions without creating an account.

## Run Locally

```powershell
python backend/app.py
```

Open:

```text
http://127.0.0.1:8000/
```

For a presentation-ready deterministic run:

```text
http://127.0.0.1:8000/?demo=1
```

The app uses only Python's standard library. No package install is required for the core app or tests.

## What Is Included

- `static/index.html`, `static/styles.css`, `static/app.js`: vanilla frontend.
- `backend/app.py`: Python HTTP server, static file host, JSON API routes, security headers, body limits, rate limiting, and privacy-aware live lookup controls.
- `backend/connectors.py`: live data connectors and dataset loading helpers.
- `backend/ai_mentor.py`: local mentor that rewrites recommendation facts into plain next steps, with optional Google Cloud/OpenAI wording.
- `backend/recommendation_engine.py`: role matching, skill gap analysis, course ranking, confidence, provenance, and quest generation.
- `data/*.json`, `data/ai_training_examples.jsonl`: local seed datasets, normalized SkillsFuture dataset slice, and mentor grounding examples.
- `tools/import_skillsfuture_datasets.py`: imports the three local Jobs-Skills SkillsFuture XLSX files into `data/skills_framework.json`.
- `tests/test_skillquest_contracts.py`: stdlib contract tests for API safety and recommendation behavior.
- `docs/judge-brief.md`: pitch, demo flow, roadmap, architecture, and testing plan.
- `docs/data-provenance.md`: source handling, limitations, and overclaim controls.
- `docs/ai-training.md`: no-key mentor grounding dataset and future OpenAI upgrade boundaries.
- `docs/process-log.md`: build and verification log for submission.

## API Routes

- `GET /api/health`: server and data status.
- `GET /api/options`: interests, roles, courses, and source metadata for the frontend.
- `GET /api/jobs?query=data%20analyst`: opt-in MyCareersFuture job skill signal, with graceful error output.
- `GET /api/location?query=Tampines%20MRT`: opt-in OneMap geocoding lookup. Add `ONEMAP_API_TOKEN` for authenticated use.
- `GET /api/sources`: data provenance and source notes.
- `GET /api/integrations`: safe readiness metadata for local datasets, optional live APIs, mentor grounding, and future OpenAI setup.
- `GET /api/ai/status`: mentor status (local/google/openai), supported actions, and grounding metadata.
- `POST /api/recommend`: main personalised recommendation endpoint.
- `POST /api/mentor`: rewrites an existing recommendation into plain-language guidance. No API key is required by default.
- `HEAD` and `OPTIONS`: supported for health checks and simple API discovery.

Example recommendation payload:

```json
{
  "mode": "explorer",
  "interests": ["Data", "Technology", "Helping people"],
  "targetRole": "",
  "currentRole": "Admin Executive",
  "skills": ["Excel", "Customer Service", "Data Entry"],
  "weeklyHours": 6,
  "budget": 700,
  "learningMode": "Blended",
  "location": "Tampines MRT",
  "preferredSchedule": "Evenings",
  "allowLiveData": false,
  "demo": true
}
```

## Data And Privacy Approach

SkillQuest is privacy-aware and demo-safe:

- It uses local role, course, funding, and Skills Framework reference data by default.
- `data/skills_framework.json` is generated from the supplied Jobs-Skills SkillsFuture XLSX datasets: unique skills, full framework role-skill rows, and TSC-to-unique-skill mappings.
- It only calls MyCareersFuture and OneMap when the learner enables **Use live job and map lookup**.
- `?demo=1` always uses deterministic offline signals so judging does not depend on network speed.
- It ranks against local course and role datasets so the demo still works if an external provider is slow, unavailable, or requires credentials.
- You can point `COURSE_DATA_URL` at a JSON or CSV course dataset to replace or extend the seed courses.
- You can opt in to the public data.gov.sg MySkillsFuture Course Directory import with `SKILLQUEST_ENABLE_DATA_GOV_COURSES=true`. This uses the no-key data.gov.sg poll-download API at server start and parses the XLSX with the Python standard library.
- `/api/integrations` reports what is ready, optional, local, or not configured without exposing secret values.

This is not a production eligibility checker for subsidies or SkillsFuture Credit. Funding calculations are estimates and should be verified with SkillsFuture Singapore or course providers before a real enrolment decision.

Optional official course directory import:

```text
SKILLQUEST_ENABLE_DATA_GOV_COURSES=true
DATA_GOV_COURSE_LIMIT=40
DATA_GOV_COURSE_KEYWORDS=data,python,analytics,cyber,marketing,ux,healthcare,sustainability
```

This import does not send learner data. It fetches the public MySkillsFuture Course Directory dataset once during backend startup, filters relevant rows, and keeps local seed data as fallback.

Regenerate the SkillsFuture role-skill slice from local XLSX files:

```powershell
python tools\import_skillsfuture_datasets.py
```

By default the importer reads:

```text
C:\Users\jaron\Downloads\jobsandskills-skillsfuture-unique-skills-list.xlsx
C:\Users\jaron\Downloads\jobsandskills-skillsfuture-skills-framework-dataset.xlsx
C:\Users\jaron\Downloads\jobsandskills-skillsfuture-tsc-to-unique-skills-mapping.xlsx
```

You can override those paths with `SKILLQUEST_UNIQUE_SKILLS_XLSX`, `SKILLQUEST_FRAMEWORK_XLSX`, and `SKILLQUEST_TSC_MAPPING_XLSX`.

## No-Key AI Mentor

The default mentor uses local deterministic rules only. It uses the deterministic recommendation JSON plus `data/ai_training_examples.jsonl` to produce bounded plain-language guidance for:

- why this path,
- a lower-cost version,
- a two-hour/week version,
- a helper or caregiver script,
- a simple default guide.

This keeps the demo working without any keys.

To enable Google Cloud model wording:

```text
SKILLQUEST_ENABLE_GOOGLE_MENTOR=true
GOOGLE_CLOUD_AI_API_KEY=<your key>
```

Google Cloud is preferred when enabled. OpenAI can be enabled as a fallback:

```text
SKILLQUEST_ENABLE_OPENAI_MENTOR=true
OPENAI_API_KEY=<your key>
```

## Verification

```powershell
python -m unittest discover -s tests -v
python -m py_compile backend\app.py backend\connectors.py backend\recommendation_engine.py backend\ai_mentor.py backend\integrations.py
node --check static\app.js
git diff --check
```

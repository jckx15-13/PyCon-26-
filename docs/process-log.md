# SkillQuest Process Log

## 2026-06-24

### Product And UX

- Reframed the app around three learner questions: where next, what skills matter, what to do today.
- Kept the first screen as the usable guided app.
- Preserved low-literacy controls: large buttons, simple labels, read-aloud actions, and hidden advanced fields.
- Added result evidence without making the default journey more complex:
  - confidence,
  - why this path,
  - top skill gaps,
  - course comparison,
  - source list,
  - quick refinements.

### Data And Recommendation

- Regenerated `data/skills_framework.json` from the supplied Jobs-Skills SkillsFuture XLSX files:
  - unique skills list,
  - Skills Framework dataset,
  - TSC-to-unique-skills mapping.
- Added `tools/import_skillsfuture_datasets.py` so the normalization can be repeated.
- The normalized SkillsFuture slice now includes 2,316 unique skills, 2,030 job roles, 44,527 role-skill rows, 12,007 skill key rows, and 12,326 TSC-to-unique-skill rows.
- Added `data/ai_training_examples.jsonl` as a local grounding set for no-key mentor guidance.
- Added `backend/integrations.py` and `GET /api/integrations` to report local, optional live, configured, and future data/API layers without exposing secrets.
- Added optional data.gov.sg MySkillsFuture Course Directory import through the public no-key poll-download API.
- Added `tools/import_data_gov_course_cache.py` and `data/course_directory_cache.json` so the default demo has exact MySkillsFuture course-reference links without network startup.
- Added a Python standard-library XLSX parser for the official course directory import so the core app still has no package install requirement.
- Added local offline market and location signals for fast private demo mode.
- Changed default recommendation calls to avoid live external API calls unless the user opts in.
- Changed direct `/api/jobs` and `/api/location` calls to use local signals unless explicit non-demo live consent is present.
- Changed parallel live job/map lookups to use a shared deadline so slow providers do not stack into double waits.
- Added confidence, caveats, and explanation fields to recommendation responses.
- Added official role and official skill evidence to recommendation responses for the mapped app role.
- Changed course scoring so a course is capped if it does not cover the top skill gap.

### No-Key Mentor

- Added `backend/ai_mentor.py`.
- Added `GET /api/ai/status` to show that the mentor is local, deterministic, and does not require an API key.
- OpenAI path remains opt-in via `SKILLQUEST_ENABLE_OPENAI_MENTOR=true` and `OPENAI_API_KEY`.
- Added `POST /api/mentor` to produce:
  - why-this explanations,
  - lower-cost rewrites,
  - two-hour/week plans,
  - helper scripts,
  - simple plain-language guidance.
- Grounded mentor facts and optional Google/OpenAI prompts in compact SkillsFuture role-skill evidence selected by the recommender.
- Updated quick actions in the frontend to call the local mentor after a recommendation exists.
- Added a compact **Data checks** panel so users and judges can see private demo readiness, optional live lookup, and broad-vs-exact course link status.
- Added direct course detail/source action and tradeoff bullets to the recommended course card.
- Added visible SkillsFuture role and skill evidence in `Why this path` and `Skills to learn first`.
- Added an **Ask one question** control that sends a short bounded learner question to the same no-key mentor endpoint.
- Added **Save helper sheet**, a visible local text preview plus copy/download actions for learners and helpers that does not require login or backend storage.
- Added a persistent `aria-live` form status line so loading, success, and failure states are visible and announced to assistive technology.
- Added frontend request timeouts for options, recommendation, and mentor calls so a stalled API does not leave the learner waiting with no clear status.
- Changed the result screen to a calmer simple-first layout: next step, course, skills, and 3 small actions stay visible, while deeper why/compare evidence sits behind one large optional disclosure.
- Kept the privacy notice visible but moved technical source lists behind **Show data sources** so judges can inspect evidence without overwhelming the default learner view.

### Security And Privacy

- Added request body size limit.
- Invalid JSON now returns HTTP 400.
- Malformed `Content-Length` now returns HTTP 400.
- Added simple per-client rate limiting.
- Added `HEAD` and `OPTIONS`.
- Added security headers and CSP.
- Added explicit live lookup consent in the UI.
- Added an in-app **Your data** notice that updates when live lookup or live mentor wording is toggled.
- Redacted secret-like query parameters from returned live-source URLs so Google Cloud keys are not exposed through API payloads or source summaries.
- Kept logs to request metadata rather than full learner profile payload.

### Tests And Verification

- Added `tests/test_skillquest_contracts.py`.
- Covered malformed JSON, demo/offline sources, `HEAD`/`OPTIONS`, explorer role behavior, pathfinder target behavior, and course-score cap behavior.
- Covered the data.gov.sg XLSX row parser, course normalization, integration readiness, and shared live-timeout deadline helper.
- Covered the learner-question mentor path so simple Q&A stays local and SkillsFuture-grounded.
- Covered frontend status/timeout hooks so the app gives clear feedback during slow or failed calls.
- Covered the simple-first result disclosure so evidence stays available without overwhelming the default view.
- Covered the optional data-source disclosure so privacy stays visible while technical provenance remains available.
- Covered Google Cloud geocode URL redaction so outbound requests can use a key without returning it to the frontend.
- Verification commands:

```powershell
python -m unittest discover -s tests -v
python -m py_compile backend\app.py backend\connectors.py backend\recommendation_engine.py backend\ai_mentor.py backend\integrations.py
node --check static\app.js
git diff --check
```

### Known Limitations

- Seed course URLs are still broad MySkillsFuture/provider references. When enabled, the data.gov.sg import adds course-reference detail links for imported public directory rows.
- Skills Framework data is now generated from local official Jobs-Skills XLSX files, but it remains a normalized app slice and not an official endorsement.
- The mentor is deterministic and local by design in this no-key slice; Google Cloud or OpenAI-backed wording can be enabled later behind the same endpoint.
- Funding remains a planning estimate and must be checked externally.
- Live external lookups are optional and best-effort.

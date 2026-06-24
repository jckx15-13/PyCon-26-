# SkillQuest Judge Brief

## Product Concept

SkillQuest turns upskilling from a confusing search problem into a simple upgrade path. A Singapore learner chooses whether they are unsure or goal-driven, taps a few current abilities, and receives one practical next step backed by role-skill fit, course tradeoffs, confidence, and data provenance. The product is built for career switchers, working adults, digitally unfamiliar users, lower-literacy users, and community helpers supporting them.

Judges should care because the app focuses on the hard part of lifelong learning: not more content, but a trustworthy first decision. Users would return whenever their time, budget, location, or goal changes because the path can be recalculated without forcing them through a long form.

## Three-Minute Demo Flow

1. Open `http://127.0.0.1:8000/?demo=1`.
2. Show the first screen is the app itself, not a landing page.
3. Click **Read aloud** to show low-literacy support.
4. Keep **I am not sure** selected and tap one extra ability such as **Fix problems**.
5. Leave live lookup unchecked to show private, fast demo mode.
6. Press **Upgrade my path**.
7. Show the answer to the three core questions:
   - **Where can I go next?** Suggested role path.
   - **What skills matter most?** Top skill gaps.
   - **What should I do today?** Small quest and first course.
8. Show **Why this path**, **Compare options**, and **Data sources**.
9. Show **Data checks** in the help panel to prove the demo is private by default and live lookups are opt-in.
10. Click **Only 2 hours** or **Cheaper plan** to show refinement.
11. Type `Can I do this with no money?` under **Ask one question**, then click **Ask guide**.
12. Click **Use a helper** to show a plain script for a family member or community helper.
13. Click **Copy this plan** and **Save helper sheet** to show the learner can leave with a practical action. The helper sheet appears on screen first, then can be copied or downloaded.

If live APIs are slow or unavailable, the demo still works because `?demo=1` forces offline local signals. If judges want to see live integration, enable **Use live job and map lookup** and explain that only the goal and place are sent.

## P0 Completed In This Slice

- Private, deterministic demo mode.
- Explicit consent for live job and map lookup.
- Explorer mode no longer defaults into Data Analyst.
- Typed custom skills are included in the payload.
- Bad JSON and malformed `Content-Length` return HTTP 400 instead of silent defaults.
- Request body limit, basic rate limiting, `HEAD`, `OPTIONS`, security headers, and CSP.
- SkillsFuture Jobs-Skills XLSX integration and provenance UI, generated from the supplied unique skills, framework, and TSC-to-unique-skills datasets.
- Optional no-key data.gov.sg MySkillsFuture Course Directory import, disabled by default for demo speed.
- Recommendation confidence, caveats, top gaps, course alternatives, and no fake-perfect course score.
- Result actions: why this, cheaper plan, only 2 hours, ask guide, use a helper, copy this plan, save helper sheet.
- No-key local mentor endpoint for plain guidance, bounded learner questions, cheaper path, two-hour plan, and helper script.
- Local helper-sheet preview and export that includes the next path, course, time/cost, SkillsFuture evidence, source checks, and verification note without creating an account.
- `/api/integrations` readiness endpoint showing local, optional live, configured, and future API layers without exposing secrets.
- Stdlib unit/API tests.

## P1 To Help Win

- Curate a verified MySkillsFuture export and replace remaining seed course URLs with exact course-reference pages.
- Add optional OpenAI-backed rewriting behind the existing mentor endpoint after secure key setup is available.
- Upgrade the plain text helper sheet into a designed PDF/share card for community helpers.
- Add more Skills Framework sectors and richer role mappings.
- Add a screen-reader QA transcript and keyboard-only demo evidence.
- Add a short video demo with offline and live-data modes.

## P2 Viable Product

- Move to FastAPI or Flask only when authentication, background jobs, and observability are needed.
- Add user-owned saved plans with clear consent and deletion controls.
- Add calendar-aware scheduling.
- Integrate official course enrolment deep links.
- Add administrator tooling for dataset refresh and quality review.

## Recommendation Model

Role fit combines target role intent, interest overlap, current skills, bridge from current work, SkillsFuture role-skill evidence, and optional market skill signals. Course fit combines priority skill-gap coverage, cost, weekly time, mode, location, and quality. Scores are capped when the top gap is not covered, preventing convenient but weak courses from looking like perfect matches. Confidence rises when the user provides skills, a target role, location, live market signals, and SkillsFuture mapping evidence.

## AI Integration Plan

The realistic hackathon AI feature is a bounded mentor, not an eligibility judge. In the current no-key build, `POST /api/mentor` receives the deterministic recommendation JSON and uses local grounding examples to produce:

- a plain-language explanation,
- a two-hour/week rewrite,
- a cheaper-path rewrite,
- a caregiver/community-helper script,
- answers to "why this?" questions.

When an OpenAI API key is available later, the same endpoint can call a model for richer wording while keeping the deterministic recommender as the source of truth.

Safety boundaries:

- No subsidy eligibility decisions.
- No official enrolment claims.
- No hidden external data calls.
- No storage of raw personal profiles in process logs.
- Fallback to deterministic mentor text when the model is unavailable.
- No external AI call in the current no-key demo mode.

## Architecture

The hackathon-safe architecture is intentionally small:

- Static HTML/CSS/JS frontend.
- Python standard-library HTTP server.
- Local JSON datasets.
- Optional external API adapters isolated in `backend/connectors.py`.
- Optional public data.gov.sg course-directory import for official MySkillsFuture course rows.
- Integration readiness registry in `backend/integrations.py`.
- Deterministic recommender in `backend/recommendation_engine.py`.
- Local mentor rewrite layer in `backend/ai_mentor.py`.
- Tests in `tests/`.

This keeps the demo deployable, inspectable, and easy for judges to run without package setup.

## Testing Checklist

- `python -m unittest discover -s tests -v`
- `python -m py_compile backend\app.py backend\connectors.py backend\recommendation_engine.py backend\ai_mentor.py`
- `node --check static\app.js`
- `git diff --check`
- Browser smoke: app loads, no console/page errors, no horizontal overflow, `?demo=1` returns a result, quick refinement buttons work.

## Submission Package

- README with local run and verification instructions.
- `docs/data-provenance.md` for source transparency.
- `docs/process-log.md` for build and QA evidence.
- `docs/design-reference.md` for accessibility-first design direction.
- Screenshots of desktop and mobile result states.
- One-liner: **SkillQuest gives every Singapore learner one trustworthy next upskilling step, with evidence, confidence, and privacy by default.**

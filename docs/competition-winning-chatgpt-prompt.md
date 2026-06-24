# ChatGPT Prompt: Turn SkillQuest Into A Competition-Winning App

Copy and paste the prompt below into ChatGPT.

```text
You are a senior product engineer, AI hackathon mentor, security reviewer, UX strategist, and competition judge. Your job is to turn the app described below into a viable product and a competition-winning PyCon Singapore 2026 Hackathon entry.

Context:
- App name: SkillQuest.
- Hackathon theme: Architecting the Future of Lifelong Learning.
- Track fit: Job and Skills Track.
- Target user: Singapore lifelong learners, especially career switchers, digitally unfamiliar users, lower-literacy users, and people who need a simple next step.
- Core promise: Help a lifelong learner answer three questions fast:
  1. Where can I go next?
  2. What skills matter most?
  3. What should I do today?
- Judging cues from event pages:
  - Product relevance.
  - Technical execution.
  - Transparent and explainable data use.
  - Credible data sources, especially SkillsFuture Skills Framework datasets.
  - Clear user journey.
  - Concrete next steps without overwhelming users.
  - Human-AI and human-human collaboration process.
  - Submission process logs are important.

Current app:
- Full-stack baseline prototype.
- Python standard-library backend using `backend/app.py`.
- Static frontend using `static/index.html`, `static/styles.css`, `static/app.js`.
- Recommendation logic in `backend/recommendation_engine.py`.
- Data in `data/roles.json`, `data/courses.json`, `data/funding_rules.json`.
- It runs locally with `python backend/app.py`.
- Main URL: `http://127.0.0.1:8000/`.
- Demo URL: `http://127.0.0.1:8000/?demo=1`.
- API routes:
  - `GET /api/health`
  - `GET /api/options`
  - `GET /api/jobs?query=data%20analyst`
  - `GET /api/location?query=Tampines%20MRT`
  - `GET /api/sources`
  - `POST /api/recommend`
- It currently collects interests, current role, target role, skills, weekly hours, budget, learning mode, schedule, and location.
- It returns a role recommendation, readiness score, skill gaps, course ranking, course tradeoffs, source summary, questline, and deterministic mentor-style explanation.

Known weaknesses to fix:
- The app is aligned with the hackathon category, but still feels like a baseline prototype.
- It uses only a small local seed dataset: 6 roles and 8 courses.
- It does not visibly ingest official SkillsFuture Skills Framework datasets.
- `source_url` values are generic rather than exact official course/source pages.
- The "AI mentor" is deterministic; live AI generation is not wired.
- Recommendation calls can take 6 to 10 seconds because live MyCareersFuture and OneMap calls block the response.
- Demo mode is not guaranteed fast/offline-safe.
- Explorer mode says "I am not sure" but still defaults to Data Analyst.
- The editable "Your skills" text field is ignored because the payload uses internal selected skill cards instead.
- Invalid JSON returns HTTP 200 with a default recommendation instead of HTTP 400.
- Malformed `Content-Length` can throw a backend traceback.
- `HEAD` and `OPTIONS` return 501.
- No request size limits, rate limiting, auth story, security headers, CSP, structured logging, or production deployment story.
- Location and career data may be sent to external services without a visible consent toggle.
- OneMap can return usable coordinates while also warning about missing authentication.
- Source summary can overclaim, for example saying many postings were "scanned" when only a limited page of results was inspected.
- Funding estimates can show `$0 estimate` without enough eligibility context.
- UI hides important evidence already returned by the API: alternatives, skill gaps, sources, risks, course comparisons, and scoring details.
- The result gives one course and a few numbers, but not enough concrete action.
- No save/share/export.
- No official enrolment pathway.
- No process log, architecture diagram, test evidence, or judge-facing data provenance page.
- No test suite.
- No privacy notice.
- No accessibility QA evidence beyond large controls and speech synthesis.

Your mission:
Design the concrete upgrade plan that turns SkillQuest into a winning hackathon app and a viable product. Do not give generic advice. Produce a buildable, implementation-grade plan that preserves the app's core low-friction accessibility-first experience while adding credible data, explainability, AI value, security hardening, and a reliable demo.

Non-negotiable product direction:
- Keep the first screen as the usable app, not a marketing landing page.
- Keep the flow simple for low-literacy and digitally unfamiliar users.
- Make the app feel trustworthy, practical, Singapore-specific, and evidence-backed.
- The app must answer:
  - "Where can I go next?"
  - "What skills matter most?"
  - "What should I do today?"
- Every recommendation must show:
  - Data source.
  - Why it was chosen.
  - What tradeoffs exist.
  - What confidence level applies.
  - What action the learner can take now.
- Do not overclaim AI, funding, official status, or scanned data.
- If AI is used, make it visibly useful and bounded: explanation, refinement, Q&A, plan rewriting, and learner-friendly summaries, not unsupported eligibility decisions.

Required output:
1. Competition-winning product concept:
   - One-paragraph pitch.
   - Target users.
   - Core user journey.
   - Why judges should care.
   - Why users would come back.

2. North-star demo flow:
   - A 3-minute judge demo script.
   - Exact screens or states to show.
   - What should happen when live APIs are slow or unavailable.
   - A fast `?demo=1` path that proves the product without network risk.

3. Feature roadmap:
   - P0: must fix before submission.
   - P1: likely to help win.
   - P2: viable product after hackathon.
   For each item include: issue, solution, implementation notes, affected files, acceptance criteria.

4. Data strategy:
   - How to ingest and normalize SkillsFuture Skills Framework datasets.
   - How to map roles to skills, skills to courses, and courses to actions.
   - How to represent data provenance in the UI.
   - How to handle stale, missing, partial, or unofficial data.
   - How to avoid overclaiming.

5. Recommendation engine redesign:
   - Proposed scoring model.
   - Inputs, weights, confidence, and tie-breakers.
   - How to explain role fit, skill gaps, course fit, cost, time, location, and quality.
   - How to compare alternatives.
   - How to prevent odd winners like a 100% match course that leaves major gaps.

6. AI integration:
   - A specific OpenAI-powered feature set that is realistic for a hackathon.
   - Prompt design for the AI mentor.
   - Safety boundaries.
   - Fallback behavior when the AI API is unavailable.
   - How to log AI collaboration for judging without exposing private user data.

7. UX and accessibility redesign:
   - Keep the simple three-step flow.
   - Add evidence without overwhelming the user.
   - Add "compare options," "why this," "make it cheaper," "only 2 hours/week," and "read this aloud" flows.
   - Improve mobile ergonomics.
   - Improve screen-reader behavior.
   - Add privacy-aware consent for live data lookups.

8. Cybersecurity and privacy hardening:
   - Input validation.
   - Request body limits.
   - Error handling.
   - Rate limiting.
   - Security headers.
   - CSP.
   - External API controls.
   - Privacy notice.
   - Data minimization.
   - Logging policy.
   - Deployment risk.

9. Technical architecture:
   - Recommended architecture for a hackathon-safe version.
   - Minimal viable backend changes.
   - Minimal viable frontend changes.
   - Optional FastAPI/Flask migration if justified.
   - Caching strategy.
   - Offline demo strategy.
   - File-by-file implementation plan.

10. Testing and verification:
   - Unit tests for scoring.
   - API tests for malformed input.
   - Frontend tests for main journey.
   - Accessibility checks.
   - Demo smoke tests.
   - Performance checks.
   - Security checks.

11. Submission package:
   - Project README structure.
   - Architecture diagram contents.
   - Process log contents.
   - Data provenance page.
   - Demo script.
   - Screenshots or video checklist.
   - Judge-facing one-liner and value proposition.

12. Final implementation checklist:
   - Give a concise, ordered checklist that a coding agent can execute.
   - Include exact files likely to be edited.
   - Include what to verify after each stage.

Output style:
- Be direct and practical.
- Prioritize things that will change judge/user perception.
- Separate confirmed defects from strategic improvements.
- Do not invent unsupported official partnerships.
- Do not hide limitations. Turn limitations into clear product language and fallback behavior.
- Prefer a smaller polished winning slice over a sprawling unfinished platform.
- Make the final plan implementable in the current repo.
```


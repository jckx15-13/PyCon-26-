# SkillQuest Submission Answers

## Datasets Used And Rationale

SkillQuest uses SkillsFuture and public Singapore data in layers, so the demo is reliable while the recommendations remain explainable.

1. Jobs-Skills SkillsFuture Skills Framework datasets  
   Source: https://jobsandskills.skillsfuture.gov.sg/skills-frameworks#download-the-latest-skills-framework-dataset  
   Local files used:
   - `jobsandskills-skillsfuture-unique-skills-list.xlsx`
   - `jobsandskills-skillsfuture-skills-framework-dataset.xlsx`
   - `jobsandskills-skillsfuture-tsc-to-unique-skills-mapping.xlsx`

   Rationale: these are the core public jobs-skills datasets for the Job & Skills Track. SkillQuest imports them with `tools/import_skillsfuture_datasets.py` and generates `data/skills_framework.json`, currently normalising 2,316 unique skills, 2,030 job roles, 44,527 role-skill rows, 12,007 skill key rows, and 12,326 TSC-to-unique-skill mapping rows. The app uses this to show official role references, official skills, and skill-gap evidence without claiming endorsement.

2. MySkillsFuture Course Directory on data.gov.sg  
   Source: https://data.gov.sg/datasets/d_b5802b76f409764c16dde4bf2feb19cd/view  
   Rationale: optional no-key course import for public course rows. It is disabled by default for demo speed and can be enabled with `SKILLQUEST_ENABLE_DATA_GOV_COURSES=true`. It does not send learner data.

3. Local seed course, role, and funding data  
   Files: `data/roles.json`, `data/courses.json`, `data/funding_rules.json`  
   Rationale: keeps `?demo=1` fast and deterministic even when networks or external services are slow. The local data is labelled as a seed catalogue, not a complete national course catalogue.

4. Optional live labour-market and location signals  
   Sources:
   - MyCareersFuture: https://www.mycareersfuture.gov.sg/
   - OneMap: https://www.onemap.gov.sg/
   - Apify: https://apify.com/
   - Google Maps Platform: https://developers.google.com/maps

   Rationale: these provide optional job-skill and location signals when the learner explicitly enables live lookup. The default path stays private.

## Interaction Logs

Repo evidence:

- Main interaction and collaboration log: `docs/interaction-logs.md`
- Build and verification process log: `docs/process-log.md`
- Data provenance and limitation log: `docs/data-provenance.md`
- AI grounding and fallback log: `docs/ai-training.md`

AI-human evidence: the human product owner defined the problem, accessibility direction, no-key constraint, and requirement to use the supplied SkillsFuture datasets. Codex implemented the app, tests, data normalisation, helper-sheet export, documentation, and verification. Human judgement stayed responsible for product direction and whether the app felt simple enough for digitally unfamiliar users.

Human-human evidence: the repo currently records the product owner contribution and in-browser review. External stakeholder interviews are not yet stored; the recommended next step is to add one short learner test and one helper/community feedback note before final judging.

## How AI Tools Were Used Creatively, Effectively, And Responsibly

AI was used creatively to turn a broad social problem into a usable app flow: one button, one next step, visible evidence, and helper-friendly guidance. It was used effectively to generate and debug Python backend code, vanilla frontend code, dataset import tooling, API connectors, tests, data provenance, and submission documentation.

Delegated to AI:

- Code implementation and refactoring.
- Dataset schema inspection and normalisation.
- Test generation and regression fixing.
- Drafting plain-language UX copy and submission notes.
- Identifying overclaim risks around AI, funding, official status, and scanned data.
- Turning common learner questions into bounded mentor actions such as `why`, `cheaper`, `two_hours`, `helper`, and `plain`.

Human-judged:

- Problem framing and target users.
- Minimal/accessible design direction.
- Whether to avoid API keys first.
- Whether to prioritise official SkillsFuture datasets.
- Submission form requirements and final demo narrative.

Responsible boundaries:

- The deterministic Python recommender is the source of truth.
- AI mentor wording is bounded to explanation, simplification, and rewrites.
- Free-text learner questions are capped before being sent to the mentor endpoint.
- No AI output decides subsidy eligibility, enrolment, official approval, or career certainty.
- Live AI is disabled by default and requires explicit configuration plus user consent.
- The app falls back to local deterministic guidance if Google/OpenAI calls are unavailable.

## Tech Stack

Python stack:

- Python standard library HTTP backend: `http.server.ThreadingHTTPServer`
- Python standard library JSON, CSV, ZIP/XLSX XML parsing, urllib, pathlib, threading, and unittest
- Deterministic recommendation engine in `backend/recommendation_engine.py`
- Optional API adapters in `backend/connectors.py`
- SkillsFuture XLSX import script in `tools/import_skillsfuture_datasets.py`
- Unit/API tests with `unittest`

Frontend stack:

- Vanilla HTML, CSS, and JavaScript
- Browser `fetch` for API calls
- Browser speech synthesis for read-aloud support
- Accessible semantic controls, large touch targets, and private-by-default consent toggles
- Client-side helper-sheet preview, copy, and download using browser APIs

Optional integrations:

- MyCareersFuture job lookup
- OneMap location lookup
- Apify dataset lookup with defensive parsing for scraped job rows
- Google Maps geocoding
- data.gov.sg MySkillsFuture Course Directory import
- Optional Google Cloud Gemini / OpenAI mentor wording, disabled by default

## PyConSG26 Programme Learning Applied

Sources:

- PyCon SG 2026 schedule: https://pycon.sg/schedule.html
- PyCon SG 2026 hackathon page: https://pycon.sg/hackathon.html
- PyCon SG 2026 homepage/speakers: https://pycon.sg/

The hackathon page defines the Job & Skills Track as building career pathway explorers, role-to-skill maps, skills-gap analysers, and learning action planners using public framework datasets. SkillQuest directly follows that by combining SkillsFuture role-skill evidence with a simple action planner.

Georgi Ker's keynote, "So Kiasu, Still Kena Replaced by AI?", frames lifelong learning as something people do together over time, not a one-off course search. SkillQuest applies this through read-aloud support, helper scripts, copyable plans, and recalculation when time, budget, skill, or location changes.

Anthony Tung's keynote, "Using Tools Without Being Used", distinguishes AI-using from AI thinking and emphasizes shared infrastructure for collective sensemaking. SkillQuest applies this by keeping deterministic Python scoring as the source of truth and using AI only for bounded explanation. The process logs and data provenance make the collaboration visible instead of hiding it behind a model answer.

Cyrus Mante's talk, "You Don't Need an LLM to Understand Your Data", influenced the decision to parse the SkillsFuture datasets and show transparent role-skill evidence before using any AI wording. The app does not ask an LLM to invent a career path from scratch.

The SIMCC talk "AI Prompt Engineering with Coding" highlights directing, challenging, improving, and validating AI-generated code. SkillQuest applies this with tests, source caveats, request limits, no-key fallback, and explicit boundaries around what AI is allowed to do.

Yeo Wee Kiang's "SKILL.md is the SOP your AI agent never had" maps to the project's own structured process: data provenance, process logs, repeatable import script, and clear rules for optional AI behavior.

The PyLadies track includes an Apify Web Scraping & Parsing Workshop, and the hackathon page mentions Apify credits. SkillQuest applies this with an optional Apify job-signal connector, defensive parsing for messy scraped rows, and opt-in consent before any learner goal is sent.

AI Ready ASEAN, backed by AI Singapore, influenced the low-literacy AI design: users should understand what AI does, what it does not do, and when their data leaves the app.

MongoDB and LangGraph agent workshops were useful as future direction, but not used in the default build because the hackathon-safe version intentionally avoids accounts, persistence, and hidden memory.

## Anything Else

SkillQuest is intentionally not a flashy AI chatbot first. The challenging part was making it useful without requiring a login, API key, or high digital literacy. A concrete technical episode: after adding richer SkillsFuture evidence, the recommendation JSON became large enough to hit the mentor endpoint's request-size limit. We fixed this by compacting API response evidence while keeping the full normalized dataset on disk.

Credits:

- Human product owner: problem statement, accessibility direction, no-key constraint, dataset files, and submission requirements.
- PyConSG26 hackathon resources: Job & Skills Track framing, public dataset direction, AI Ready ASEAN, Apify, OpenAI, and the conference programme.
- SkillsFuture Singapore Jobs-Skills Portal and data.gov.sg for public skills/course data references.

Gender diversity: no team diversity claim is made in the repo because the current evidence records one product owner plus AI-assisted implementation. The product itself is designed for inclusion across age, digital familiarity, literacy level, and work background.

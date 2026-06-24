# SkillQuest Interaction And Collaboration Logs

This file is the repo-level evidence log for AI-human and human-human collaboration during the PyConSG26 hackathon build.

## AI-Human Collaboration

### Human Direction

The human product owner set the problem and product constraints:

- Many Singaporeans are unsure how to upskill because time, location, course quality, cost, and unclear choices make the journey complex.
- The solution should feel like pressing an upgrade button in a game: one simple, personalised next step.
- The app must be accessible to working-age adults and older learners, including digitally unfamiliar and low-literacy users.
- The design should be more minimalistic and intuitive.
- The build should work first without an API key.
- The app should use relevant APIs and the supplied SkillsFuture datasets.

### AI Delegated Work

Codex was delegated:

- Implementing the Python backend and vanilla HTML/CSS/JS frontend.
- Normalising the supplied SkillsFuture XLSX files into `data/skills_framework.json`.
- Building the deterministic recommendation engine, skill-gap scoring, confidence, and course ranking.
- Adding no-key mentor guidance and optional Google/OpenAI mentor wiring with local fallback.
- Adding optional API connectors for MyCareersFuture, OneMap, Apify, Google Maps, data.gov.sg course import, and external course datasets.
- Creating tests, verification commands, documentation, data provenance, and submission answers.

### Human-Judged Decisions

The human owner judged and redirected:

- Product focus: simplify the app for people who may struggle with digital forms.
- Privacy posture: do without API key first, keep live lookups optional.
- Dataset priority: use the official SkillsFuture Jobs-Skills XLSX files supplied locally.
- Submission requirements: include dataset rationale, interaction logs, AI use, tech stack, PyConSG26 programme learning, and human notes.

### Responsible AI Boundary

AI was used as a coding, design, debugging, and drafting assistant. The app does not let AI decide funding eligibility, course enrolment, official status, or career certainty. Deterministic Python scoring remains the source of truth; optional model calls can only rewrite bounded recommendation facts into simpler wording.

## Human-Human Collaboration Evidence

Current confirmed human-human contribution in this repo:

- The human product owner supplied the initial problem statement, target users, UX direction, API/dataset requirement, and the three local SkillsFuture XLSX files.
- The human product owner reviewed intermediate app state in the in-app browser at `http://127.0.0.1:8000/?demo=1&qa=final-evidence-retry`.
- No separate external stakeholder interview notes are stored in this repo yet.

Recommended next evidence to add before final submission:

- One short test with a working adult or older learner: can they complete the three-step journey without help?
- One helper/community feedback note: can a family member or volunteer explain the result using the helper script?
- One team discussion note if another teammate contributes review, data checking, or demo feedback.

## Implementation Log Links

- Build and verification log: `docs/process-log.md`
- Data source and limitation log: `docs/data-provenance.md`
- AI grounding and fallback log: `docs/ai-training.md`
- Submission answers: `docs/submission-answers.md`

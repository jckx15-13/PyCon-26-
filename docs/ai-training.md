# SkillQuest AI Training And Grounding

## Current No-Key Mode

SkillQuest does not require an external API key by default. The mentor is a local deterministic service in `backend/ai_mentor.py`.

It uses:

- the recommendation JSON returned by `POST /api/recommend`,
- compact SkillsFuture role and skill evidence already selected by the recommendation engine,
- local response examples in `data/ai_training_examples.jsonl`,
- fixed safety boundaries for funding, eligibility, and enrolment.

This is best described as local grounding and response shaping, not model fine-tuning.

## What The Dataset Contains

Each JSONL row has:

- `action`: the mentor action such as `why`, `cheaper`, `two_hours`, `helper`, or `plain`,
- `audience`: who the wording should help,
- `input_summary`: the type of learner situation,
- `output_style`: how the response should sound,
- `ideal_response`: a compact reference answer.

The app uses these examples to keep no-key mentor responses short, practical, and suitable for learners who may need help reading or using digital forms. Free-text learner questions are capped and routed through the `plain` action instead of becoming an open-ended chatbot.

## SkillsFuture Grounding

The mentor receives only bounded facts from the current recommendation:

- suggested role and course,
- top skill gap and practice quest,
- confidence and tradeoffs,
- the learner's short bounded question, when present,
- official role titles mapped from the SkillsFuture XLSX dataset,
- official skill matches for the learner's top gaps,
- record-count metadata proving the mapping came from the normalized SkillsFuture slice.

It does not receive the full XLSX files, raw learner logs, contact details, or hidden personal identifiers.

## Optional Live Mentor Options

When secure API key setup is enabled, the same endpoint can call a live model for richer wording.

- OpenAI: `SKILLQUEST_ENABLE_OPENAI_MENTOR=true` and `OPENAI_API_KEY`
- Google Cloud (Gemini): `SKILLQUEST_ENABLE_GOOGLE_MENTOR=true` and `GOOGLE_CLOUD_AI_API_KEY`

Google Cloud is preferred when both providers are configured. OpenAI is used as fallback.
The model receives only bounded recommendation and SkillsFuture evidence facts, not raw logs, full spreadsheet rows, or unnecessary personal data.

The model must not:

- decide subsidy eligibility,
- claim official enrolment status,
- invent course details,
- hide source limitations,
- store private learner profiles in process logs.

The deterministic recommendation engine remains the source of truth. AI should only explain, simplify, or reformat the plan.

## Enabling Providers (Optional)

Live providers are intentionally disabled in the default run. To enable for local testing:

1. Set `SKILLQUEST_ENABLE_GOOGLE_MENTOR=true`
2. Set `GOOGLE_CLOUD_AI_API_KEY`
   - Optional: set `GOOGLE_CLOUD_AI_MODEL` (defaults to `gemini-1.5-flash-latest`).
3. Optional fallback: OpenAI with `SKILLQUEST_ENABLE_OPENAI_MENTOR=true` and `OPENAI_API_KEY`.

When either provider is active, `/api/ai/status` reports `provider: google-cloud-live` or `provider: openai-live`. If no usable key is present, `local-deterministic` is used.

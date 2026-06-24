# SkillQuest Design Reference

Original dashboard concept image:

```text
static/assets/skillquest-concept.png
```

Minimal guided concept image:

```text
static/assets/skillquest-minimal-concept.png
```

The generated concept is a high-fidelity desktop app screen for SkillQuest. The implementation follows these decisions:

- First screen is the usable app, not a marketing landing page.
- Navigation uses a desktop sidebar and a compact top bar.
- Core journey starts from two modes: `Explore My Future` and `Pursue A Goal`.
- The main call to action is `Upgrade My Path`.
- The result surface shows readiness, top missing skills, recommended courses, the time/cost/location/quality breakdown, and a questline.
- The right panel is an AI mentor style explanation surface backed by deterministic recommendation evidence in this baseline.

Design tokens:

- Primary action: teal.
- Text: deep navy.
- Success: green.
- Warning: amber.
- Info: blue.
- Error: red.
- Surfaces: white and cool neutral backgrounds.
- Radius: 8px for cards and panels.
- Typography: system sans-serif with explicit sizes for display, headings, body, labels, and captions.

Intentional baseline deviation:

- The concept image itself is a design reference only. The shipped UI is code-native HTML/CSS/JS, not a static screenshot.
- Live AI generation is not wired yet. The AI mentor panel explains recommendations from the deterministic engine and is structured for a future model-backed endpoint.

## Minimal Accessibility Redesign

The current interface is optimized for people who may be digitally unfamiliar or have low literacy:

- Removed the dense dashboard sidebar and search-first top bar.
- Kept one guided journey with three steps: choose path, choose current abilities, press upgrade.
- Uses large buttons, familiar line icons, high contrast, and 56px+ touch targets.
- Adds browser speech synthesis actions: `Read aloud`, `Help`, and `Read this screen`.
- Uses plain labels such as `I am not sure`, `I have a goal`, `Use Excel`, and `Upgrade my path`.
- Keeps advanced fields inside `Change more answers` so they do not block the default flow.
- Presents results as one next step, one course, time/money/place, and three small actions.

## Evidence-Backed Result Upgrade

The result surface now keeps the simple answer first, then adds judge- and helper-friendly evidence below it:

- `Why this path`: plain-language reasons, confidence, and caveats.
- `Skills that matter`: the top gaps and one practice task.
- `Compare options`: the top course alternatives with fit, weekly time, and planning cost.
- `Need it simpler`: quick actions for `Why this?`, `Make it cheaper`, `Only 2 hours`, and `Copy plan`.
- `Data sources`: local course data, Skills Framework reference mapping, optional job data, and optional map data.

Live job and map lookup is opt-in. The default and `?demo=1` flows stay private, fast, and deterministic.

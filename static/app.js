const state = {
  options: null,
  selectedInterests: new Set(["Data", "Technology", "Helping people"]),
  selectedSkills: new Set(["Excel", "Customer Service", "Data Entry"]),
  lastRecommendation: null,
  lastPayload: null,
  lastMentorReply: null,
  aiStatus: null,
  integrationStatus: null,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const REQUEST_TIMEOUTS = {
  options: 8000,
  status: 5000,
  recommend: 12000,
  mentor: 10000,
};

document.addEventListener("DOMContentLoaded", async () => {
  bindStaticEvents();
  await loadOptions();
  renderEmptyQuestline();

  const params = new URLSearchParams(window.location.search);
  if (params.has("demo")) {
    await submitRecommendation();
  }
});

function bindStaticEvents() {
  $("#quest-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    await submitRecommendation();
  });

  $("#weekly-hours").addEventListener("input", () => {
    $("#weekly-hours-output").textContent = $("#weekly-hours").value;
  });
  $("#allow-live-data").addEventListener("change", syncPrivacyNotice);
  $("#allow-live-mentor").addEventListener("change", syncPrivacyNotice);

  $("#read-page").addEventListener("click", () => readScreen(false));
  $("#read-result").addEventListener("click", () => readScreen(true));
  $("#help-button").addEventListener("click", () => {
    speak("Step 1: choose your starting point. Step 2: pick your skills. Step 3: press Upgrade my path.");
    showToast("Step 1, then 2, then Upgrade my path.");
  });

  $$("input[name='mode']").forEach((input) => {
    input.addEventListener("change", () => {
      $$(".big-choice").forEach((card) => card.classList.toggle("selected", card.contains(input) && input.checked));
      syncMode();
    });
  });

  $("#why-button").addEventListener("click", () => {
    openResultDetails();
    $("#confidence-line").scrollIntoView({ behavior: "smooth", block: "center" });
    requestMentor("why", { speakResult: true });
  });
  $("#cheaper-button").addEventListener("click", async () => {
    $("#budget").value = "100";
    await submitRecommendation({ mentorAction: "cheaper" });
  });
  $("#two-hours-button").addEventListener("click", async () => {
    $("#weekly-hours").value = "2";
    $("#weekly-hours-output").textContent = "2";
    await submitRecommendation({ mentorAction: "two_hours" });
  });
  $("#helper-button").addEventListener("click", () => requestMentor("helper", { speakResult: true }));
  $("#copy-plan-button").addEventListener("click", copyPlan);
  $("#save-sheet-button").addEventListener("click", saveHelperSheet);
  $("#copy-sheet-button").addEventListener("click", copyVisibleHelperSheet);
  $("#download-sheet-button").addEventListener("click", downloadVisibleHelperSheet);
  $("#ask-guide-form").addEventListener("submit", askGuideQuestion);

  $$(".ability-card").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.classList.contains("selected")));
    button.addEventListener("click", () => {
      const skill = button.dataset.skill;
      const interest = button.dataset.interest;
      const selected = !button.classList.contains("selected");
      button.classList.toggle("selected", selected);
      button.setAttribute("aria-pressed", String(selected));
      if (selected) {
        state.selectedSkills.add(skill);
        state.selectedInterests.add(interest);
      } else {
        state.selectedSkills.delete(skill);
        state.selectedInterests.delete(interest);
      }
      syncSkillsInput();
    });
  });
}

async function askGuideQuestion(event) {
  event.preventDefault();
  const input = $("#mentor-question");
  const question = input.value.trim().slice(0, 140);
  if (!question) {
    input.focus();
    showToast("Type one short question.");
    return;
  }

  const button = $("#ask-guide-button");
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "Asking...";
  try {
    const reply = await requestMentor("plain", {
      question,
      requestMode: "learner-question",
    });
    if (reply) {
      showToast("Guide answered.");
    }
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

async function loadOptions() {
  try {
    state.options = await fetchJson("/api/options", {}, REQUEST_TIMEOUTS.options);
    await loadAiStatus();
    await loadIntegrationStatus();
    renderOptions(state.options);
    renderIntegrationList();
    renderSourceList([
      { name: "Courses", status: "ready", detail: `${state.options.courseCount} choices loaded.` },
      { name: "Jobs", status: "ready", detail: "Checked when you press upgrade." },
      aiSourceSummary(),
    ]);
    syncMentorConsent();
    syncPrivacyNotice();
    syncSkillsInput();
    syncMode();
    setFormStatus("Ready. Press the green button when you want your plan.", "ready");
  } catch (error) {
    setFormStatus(readableError(error, "Could not load choices. Try refreshing the page."), "error");
    showToast("Could not load choices.");
  }
}

async function loadAiStatus() {
  try {
    state.aiStatus = await fetchJson("/api/ai/status", {}, REQUEST_TIMEOUTS.status);
  } catch (error) {
    state.aiStatus = null;
  }
}

function syncMentorConsent() {
  const mentorToggle = $("#allow-live-mentor");
  if (!mentorToggle) return;
  const provider = state.aiStatus?.provider || "local-deterministic";
  const liveReady = provider === "google-cloud-live" || provider === "openai-live";
  const row = mentorToggle.closest("label");
  if (!liveReady) {
    mentorToggle.checked = false;
    mentorToggle.disabled = true;
    if (row) {
      const note = row.querySelector("small");
      if (note) {
        note.textContent = "Enable a provider key in server config to unlock live mentor wording.";
      }
      row.classList.add("is-disabled");
    }
    syncPrivacyNotice();
    return;
  }
  mentorToggle.disabled = false;
  if (row) {
    row.classList.remove("is-disabled");
    const note = row.querySelector("small");
    if (note) {
      note.textContent = "Uses optional Google/OpenAI provider for simpler explanations and rewrites.";
    }
  }
  syncPrivacyNotice();
}

function syncPrivacyNotice() {
  const liveData = $("#allow-live-data")?.checked;
  const mentorToggle = $("#allow-live-mentor");
  const liveMentor = mentorToggle?.checked && !mentorToggle.disabled;
  const liveLine = $("#privacy-live-line");
  const mentorLine = $("#privacy-mentor-line");
  if (liveLine) {
    liveLine.textContent = liveData
      ? "Live job and map lookup is on. It sends your goal and place to public services."
      : "Live job and map lookup is off. Your goal and place stay in this demo.";
  }
  if (mentorLine) {
    mentorLine.textContent = liveMentor
      ? "Live mentor wording is on. It sends only recommendation facts to the configured provider."
      : "Live mentor wording is off. The guide uses local rules.";
  }
}

async function loadIntegrationStatus() {
  try {
    state.integrationStatus = await fetchJson("/api/integrations", {}, REQUEST_TIMEOUTS.status);
  } catch (error) {
    state.integrationStatus = null;
  }
}

function renderOptions(options) {
  const targetRole = $("#target-role");
  targetRole.innerHTML = `<option value="">Choose for me</option>` + options.roles
    .map((role) => `<option value="${escapeHtml(role.title)}">${escapeHtml(simpleRole(role.title))}</option>`)
    .join("");
  targetRole.value = "";
}

function syncSkillsInput() {
  $("#skills").value = [...state.selectedSkills].join(", ");
}

function syncMode() {
  const mode = $("input[name='mode']:checked").value;
  const targetRole = $("#target-role");
  if (mode === "explorer") {
    targetRole.value = "";
  } else if (!targetRole.value) {
    targetRole.value = "Data Analyst";
  }
}

function collectPayload() {
  const mode = $("input[name='mode']:checked").value;
  const typedSkills = parseSkillText($("#skills").value);
  const skills = [...new Set([...state.selectedSkills, ...typedSkills])];
  return {
    mode,
    interests: [...state.selectedInterests],
    targetRole: mode === "pathfinder" ? $("#target-role").value : "",
    currentRole: $("#current-role").value,
    skills,
    weeklyHours: Number($("#weekly-hours").value),
    budget: Number($("#budget").value),
    learningMode: $("#learning-mode").value,
    preferredSchedule: $("#schedule").value,
    location: $("#location").value,
    allowLiveData: $("#allow-live-data").checked,
    allowLiveMentor: $("#allow-live-mentor") ? $("#allow-live-mentor").checked : false,
    demo: new URLSearchParams(window.location.search).has("demo"),
  };
}

async function submitRecommendation(options = {}) {
  const button = $("#upgrade-button");
  const original = button.innerHTML;
  button.disabled = true;
  button.innerHTML = `<span class="button-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M12 2v4"/><path d="M12 18v4"/><path d="M4.9 4.9l2.8 2.8"/><path d="M16.3 16.3l2.8 2.8"/><path d="M2 12h4"/><path d="M18 12h4"/><path d="M4.9 19.1l2.8-2.8"/><path d="M16.3 7.7l2.8-2.8"/></svg></span><span>Finding your step...</span>`;
  button.setAttribute("aria-busy", "true");
  $("#snapshot").setAttribute("aria-busy", "true");
  setFormStatus("Finding your step. This should only take a moment.", "working");

  try {
    const payload = collectPayload();
    state.lastPayload = payload;
    const recommendation = await fetchJson("/api/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }, REQUEST_TIMEOUTS.recommend);
    state.lastRecommendation = recommendation;
    renderRecommendation(recommendation);
    setFormStatus("Plan ready. Your next step is shown below.", "ready");
    if (options.mentorAction) {
      await requestMentor(options.mentorAction, { requestMode: "auto-adjust" });
    }
    $("#snapshot").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    setFormStatus(readableError(error, "Could not build your plan. Please try again."), "error");
    showToast("Could not build your plan.");
  } finally {
    button.disabled = false;
    button.removeAttribute("aria-busy");
    $("#snapshot").removeAttribute("aria-busy");
    button.innerHTML = original;
  }
}

function renderRecommendation(data) {
  $("#empty-state").classList.add("hidden");
  $("#results").classList.remove("hidden");
  const details = $("#result-details");
  if (details) {
    details.open = false;
  }

  const ring = $("#readiness-ring");
  ring.style.setProperty("--score", data.readiness.score);
  $("#readiness-score").textContent = `${data.readiness.score}%`;
  $("#readiness-label").textContent = data.readiness.label;
  $("#readiness-summary").textContent = `You are about ${data.readiness.score}% ready for ${data.recommendedRole.title}.`;
  $("#simple-confidence").textContent = `${data.confidence?.level || "Medium"} confidence. Details are below if you want them.`;

  renderCourse(data.bestCourse);
  renderFactors(data.bestCourse);
  renderEvidence(data);
  renderSkillGaps(data.skillGaps);
  renderComparisons(data.recommendedCourses);
  renderQuestline(data.questline);
  renderMentor(data.aiMentor, data);
  renderMentorReply(null);
  renderHelperSheet("");
  renderIntegrationList();
  renderSourceList([...(data.sourceSummary || []), aiSourceSummary()]);
}

function renderCourse(bestCourse) {
  if (!bestCourse) {
    $("#course-card").innerHTML = `<h3>Course</h3><p>No course yet. Try adding one skill.</p>`;
    return;
  }
  const sourceUrl = safeUrl(bestCourse.sourceUrl);
  const tradeoffs = (bestCourse.tradeoffs || []).slice(0, 3);

  $("#course-card").innerHTML = `
    <p class="result-label">Course</p>
    <strong>${escapeHtml(bestCourse.title)}</strong>
    <p>${escapeHtml(bestCourse.provider)}</p>
    <div class="course-meta">
      <span>${bestCourse.match_score}% match</span>
      <span>${escapeHtml(bestCourse.mode)}</span>
      <span>${bestCourse.weeklyLoadHours} hours a week</span>
      <span>${escapeHtml(shortFundingLabel(bestCourse))}</span>
    </div>
    ${tradeoffs.length ? `
      <ul class="course-tradeoffs">
        ${tradeoffs.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
      </ul>
    ` : ""}
    <div class="course-actions">
      ${sourceUrl ? `<a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noreferrer">Check course details</a>` : ""}
      <small>${escapeHtml(bestCourse.fundingNote || "Check funding, eligibility, and enrolment with the provider.")}</small>
    </div>
  `;
}

function renderFactors(course) {
  if (!course) {
    $("#factor-list").innerHTML = "";
    return;
  }
  const factors = [
    ["Time", `${course.weeklyLoadHours} hours a week`],
    ["Money", course.fundingEstimateLabel || `$${course.estimatedOutOfPocket} estimate`],
    ["Place", course.location.fit === "Online" ? "Online" : `${course.location.fit}. ${course.location.travelMinutes} min estimate`],
  ];
  $("#factor-list").innerHTML = factors
    .map(([label, value]) => `<div><dt>${label}</dt><dd>${escapeHtml(value)}</dd></div>`)
    .join("");
}

function renderEvidence(data) {
  const confidence = data.confidence || {};
  $("#confidence-line").textContent = `${confidence.level || "Medium"} confidence. ${confidence.score || ""}%`.trim();
  const framework = data.recommendedRole?.framework || {};
  const frameworkReason = framework.officialRoles?.length
    ? `SkillsFuture match: ${framework.officialRoles.length} official role${framework.officialRoles.length === 1 ? "" : "s"} checked in ${framework.sector}.`
    : "";
  const reasons = [
    ...(data.recommendedRole?.why || []),
    frameworkReason,
    ...(data.explanation?.whyCourse || []),
    ...(confidence.caveats || []),
  ].filter(Boolean).slice(0, 6);
  $("#why-list").innerHTML = reasons
    .map((reason) => `<li>${escapeHtml(simpleReason(reason))}</li>`)
    .join("");
}

function renderSkillGaps(gaps) {
  const visible = (gaps || []).filter((gap) => gap.gapSize > 0).slice(0, 3);
  $("#skill-gap-list").innerHTML = visible.length
    ? visible.map((gap) => `
      <div class="skill-gap">
        <strong>${escapeHtml(gap.skill)}</strong>
        <small>${escapeHtml(gap.impact)}. ${escapeHtml(gap.quest || "Try one small practice task.")}</small>
        ${gap.frameworkEvidence?.officialSkill ? `
          <small class="framework-match">SkillsFuture skill: ${escapeHtml(gap.frameworkEvidence.officialSkill)}</small>
        ` : ""}
      </div>
    `).join("")
    : `<p>No major gap found. Start with a small practice task.</p>`;
}

function renderComparisons(courses) {
  const visible = (courses || []).slice(0, 3);
  $("#compare-list").innerHTML = visible.map((course) => `
      <div class="compare-item">
        <strong>${escapeHtml(course.title)}</strong>
      <small>${course.match_score}% fit · ${escapeHtml(course.weeklyLoadHours)}h/week · ${escapeHtml(shortFundingLabel(course))}</small>
      </div>
  `).join("");
}

function renderQuestline(steps) {
  $("#questline").innerHTML = steps
    .slice(0, 3)
    .map((step) => `
      <div class="quest-node ${escapeHtml(step.status)}">
        <span class="step-number">${step.step}</span>
        <div>
          <strong>${escapeHtml(simpleQuestTitle(step.title))}</strong>
          <p>${escapeHtml(step.action)}</p>
        </div>
      </div>
    `)
    .join("");
}

function renderEmptyQuestline() {
  renderQuestline([
    { step: 1, title: "Choose", status: "ready", action: "Pick what looks right." },
    { step: 2, title: "Upgrade", status: "ready", action: "Press the green button." },
    { step: 3, title: "Start", status: "ready", action: "Do one small step." },
  ]);
}

function renderMentor(mentor, data) {
  $("#mentor-action").textContent = mentor.nextBestAction;
  $("#mentor-summary").textContent = data
    ? `You are ${data.readiness.score}% ready for ${data.recommendedRole.title}.`
    : "This is a good first step for you.";
}

function openResultDetails() {
  const details = $("#result-details");
  if (details) {
    details.open = true;
  }
}

async function requestMentor(action, options = {}) {
  if (!state.lastRecommendation) {
    showToast("Press Upgrade my path first.");
    return null;
  }

  try {
    const reply = await fetchJson("/api/mentor", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action,
        recommendation: state.lastRecommendation,
        forceLocalMentor: !$("#allow-live-mentor") || !$("#allow-live-mentor").checked,
        allowLiveMentor: $("#allow-live-mentor") ? $("#allow-live-mentor").checked : false,
        requestMode: options.requestMode || "single-click",
        question: options.question ? String(options.question).slice(0, 140) : "",
      }),
    }, REQUEST_TIMEOUTS.mentor);
    state.lastMentorReply = reply;
    renderMentorReply(reply);
    setFormStatus("Guide answer ready.", "ready");
    $("#mentor-advice").scrollIntoView({ behavior: "smooth", block: "center" });
    if (options.speakResult) {
      speak(reply.speakText || reply.summary);
    }
    return reply;
  } catch (error) {
    setFormStatus(readableError(error, "Guide is not ready. Your plan is still available."), "error");
    showToast("Guide not ready.");
    return null;
  }
}

function renderMentorReply(reply) {
  const panel = $("#mentor-advice");
  if (!reply) {
    panel.hidden = true;
    $("#mentor-advice-title").textContent = "Simple guide";
    $("#mentor-advice-summary").textContent = "";
    $("#mentor-advice-steps").innerHTML = "";
    return;
  }

  panel.hidden = false;
  $("#mentor-advice-title").textContent = reply.title || "Simple guide";
  $("#mentor-advice-summary").textContent = reply.summary || "";
  $("#mentor-advice-steps").innerHTML = (reply.steps || [])
    .slice(0, 4)
    .map((step) => `<li>${escapeHtml(step)}</li>`)
    .join("");
  const examples = reply.grounding?.examplesMatched ?? state.aiStatus?.examples ?? 0;
  let sourceLabel = "Local guide. No API key needed.";
  if (reply.provider === "openai-live") {
    sourceLabel = "AI mentor guidance.";
  } else if (reply.provider === "google-cloud-live") {
    sourceLabel = "Google mentor guidance.";
  }
  const suffix = `${examples} matching example${examples === 1 ? "" : "s"}.`;
  $("#mentor-advice-source").textContent = `${sourceLabel} ${suffix}`;
}

function renderSourceList(sources) {
  $("#source-list").innerHTML = (sources || [])
    .slice(0, 5)
    .map((source) => `
      <article class="source-item">
        <strong>${sourceTitle(source)}</strong>
        <small>${escapeHtml(source.status || "ready")}</small>
        <p>${escapeHtml(shortSource(source.detail || ""))}</p>
      </article>
    `)
    .join("");
}

function renderIntegrationList() {
  const target = $("#integration-list");
  if (!target) return;
  const summary = state.integrationStatus?.summary;
  const lines = [
    {
      label: "Private demo",
      status: summary?.demoSafe ? "Ready" : "Check",
      detail: summary?.demoSafe ? "No live data needed." : "Some default source may need review.",
    },
    {
      label: "Live lookup",
      status: "Optional",
      detail: "Only runs when you tick the box.",
    },
    {
      label: "Course links",
      status: summary?.exactCourseLinks ? "Exact" : "Broad",
      detail: summary?.exactCourseLinks ? `${summary.exactCourseLinks} exact links loaded.` : "Use provider page to verify.",
    },
  ];
  target.innerHTML = lines
    .map((item) => `
      <div class="integration-item">
        <strong>${escapeHtml(item.label)}</strong>
        <small>${escapeHtml(item.status)}</small>
        <p>${escapeHtml(item.detail)}</p>
      </div>
    `)
    .join("");
}

function aiSourceSummary() {
  const status = state.aiStatus;
  const provider = status?.provider || "local-deterministic";
  const name = provider === "google-cloud-live" ? "Google mentor" : provider === "openai-live" ? "AI mentor" : "Local mentor guide";
  return {
    name,
    status: provider,
    detail: status?.note || status?.privacy || "Uses local examples. No external AI call.",
  };
}

function readScreen(resultOnly) {
  const data = state.lastRecommendation;
  if (resultOnly && data) {
    const gaps = (data.skillGaps || []).filter((gap) => gap.gapSize > 0).slice(0, 2).map((gap) => gap.skill).join(" and ");
    speak(`Your next step is ${data.aiMentor.nextBestAction}. Recommended course: ${data.bestCourse?.title || "course not found"}. Confidence is ${data.confidence?.level || "medium"}. Skills to learn first: ${gaps || "start with a small practice task"}.`);
    return;
  }
  speak("Welcome to SkillQuest. Step 1, choose your starting point. Step 2, pick what you can do. Step 3, press Upgrade my path.");
}

function speak(text) {
  if (!("speechSynthesis" in window)) {
    showToast("Read aloud is not available in this browser.");
    return;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 0.86;
  utterance.pitch = 1;
  window.speechSynthesis.speak(utterance);
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 3500);
}

async function fetchJson(url, options = {}, timeoutMs = 8000) {
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  const timeoutId = controller
    ? window.setTimeout(() => controller.abort(), timeoutMs)
    : null;

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller ? controller.signal : options.signal,
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body.error || `Request failed with status ${response.status}.`);
    }
    return body;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("Request took too long. Please try again.");
    }
    throw error;
  } finally {
    if (timeoutId) {
      window.clearTimeout(timeoutId);
    }
  }
}

function setFormStatus(message, tone = "ready") {
  const status = $("#form-status");
  if (!status) return;
  status.textContent = message;
  status.classList.toggle("is-working", tone === "working");
  status.classList.toggle("is-error", tone === "error");
  status.classList.toggle("is-ready", tone === "ready");
}

function readableError(error, fallback) {
  const message = String(error?.message || "").trim();
  return message || fallback;
}

async function copyPlan() {
  if (!state.lastRecommendation) {
    showToast("Press Upgrade my path first.");
    return;
  }
  const text = buildPlanText(state.lastRecommendation);
  try {
    await navigator.clipboard.writeText(text);
    showToast("Plan copied.");
  } catch (error) {
    showToast("Could not copy. You can still read the plan on screen.");
  }
}

function saveHelperSheet() {
  if (!state.lastRecommendation) {
    showToast("Press Upgrade my path first.");
    return;
  }
  const text = buildPlanText(state.lastRecommendation);
  renderHelperSheet(text);
  $("#helper-sheet-panel").scrollIntoView({ behavior: "smooth", block: "center" });
  showToast("Helper sheet ready.");
}

async function copyVisibleHelperSheet() {
  const text = $("#helper-sheet-text").value.trim();
  if (!text) {
    showToast("Build a helper sheet first.");
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    showToast("Helper sheet copied.");
  } catch (error) {
    $("#helper-sheet-text").focus();
    $("#helper-sheet-text").select();
    showToast("Text selected. Use copy on your device.");
  }
}

function downloadVisibleHelperSheet() {
  const text = $("#helper-sheet-text").value.trim();
  if (!text) {
    showToast("Build a helper sheet first.");
    return;
  }
  downloadHelperSheet(text);
}

function renderHelperSheet(text) {
  const panel = $("#helper-sheet-panel");
  const box = $("#helper-sheet-text");
  if (!text) {
    panel.hidden = true;
    box.value = "";
    return;
  }
  box.value = text;
  panel.hidden = false;
}

function downloadHelperSheet(text) {
  const role = state.lastRecommendation?.recommendedRole?.title || "skillquest-plan";
  const filename = `skillquest-${slugify(role)}-helper-sheet.txt`;
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  showToast("Helper sheet saved.");
}

function buildPlanText(data) {
  const gaps = (data.skillGaps || [])
    .filter((gap) => gap.gapSize > 0)
    .slice(0, 3)
    .map((gap) => {
      const official = gap.frameworkEvidence?.officialSkill ? ` SkillsFuture skill: ${gap.frameworkEvidence.officialSkill}.` : "";
      return `- ${gap.skill}: ${gap.quest}.${official}`;
    })
    .join("\n");
  const course = data.bestCourse || {};
  const roleEvidence = data.recommendedRole?.framework?.officialRoles || [];
  const sources = (data.sourceSummary || [])
    .slice(0, 4)
    .map((source) => `- ${source.name}: ${source.status || "ready"}`)
    .join("\n");
  const mentorSteps = state.lastMentorReply?.steps?.length
    ? state.lastMentorReply.steps.slice(0, 3).map((step) => `- ${step}`).join("\n")
    : "";
  return [
    "SkillQuest plan",
    "For the learner and anyone helping them",
    "",
    `Next path: ${data.recommendedRole.title}`,
    `Today: ${data.aiMentor.nextBestAction}`,
    `Course: ${course.title || "Not found"}`,
    course.provider ? `Provider: ${course.provider}` : "",
    course.weeklyLoadHours ? `Time: about ${course.weeklyLoadHours} hours a week` : "",
    course.fundingEstimateLabel ? `Cost: ${course.fundingEstimateLabel}` : "",
    `Confidence: ${data.confidence?.level || "Medium"} (${data.confidence?.score || "?"}%)`,
    roleEvidence.length ? `SkillsFuture role evidence: ${roleEvidence.slice(0, 3).join("; ")}` : "",
    "",
    state.lastMentorReply ? `Simple guide: ${state.lastMentorReply.summary}` : "",
    mentorSteps ? `Guide steps:\n${mentorSteps}` : "",
    "",
    "Skills to learn:",
    gaps || "- Start with one small practice task.",
    "",
    sources ? `Data checks:\n${sources}` : "",
    course.sourceUrl ? `Course/source link: ${course.sourceUrl}` : "",
    "",
    "Note: Verify funding, eligibility, and enrolment with official providers.",
  ].filter((line) => line !== null && line !== undefined && line !== false).join("\n");
}

function slugify(value) {
  const slug = String(value || "plan")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
  return slug || "plan";
}


function simpleRole(title) {
  return title
    .replace("Digital Marketing Specialist", "Digital Marketing")
    .replace("Cybersecurity Associate", "Cybersecurity")
    .replace("Healthcare Operations Analyst", "Healthcare Ops")
    .replace("Sustainability Analyst", "Sustainability");
}

function simpleQuestTitle(title) {
  return title
    .replace("Discover & Assess", "Check your fit")
    .replace("Start best-fit course", "Start course")
    .replace("Build Data Analysis", "Learn data")
    .replace("Build Spreadsheet Modelling", "Learn spreadsheets");
}

function shortSource(detail) {
  const text = String(detail);
  if (text.includes("Authentication token missing")) return "Location found. Full map access may need a token.";
  if (text.includes("returned job records")) return "Recent job records checked.";
  if (text.includes("Live job lookup was not used")) return "Private mode. Live jobs were not used.";
  if (text.includes("Loaded local JSON datasets")) return "Course and role list loaded.";
  if (text.includes("Skills Framework")) return "Skills Framework skills list loaded.";
  if (text.length > 82) return `${text.slice(0, 79)}...`;
  return text;
}

function simpleSourceName(name) {
  if (name === "Role and course seed datasets") return "Course list";
  if (name === "SkillsFuture Skills Framework reference") return "Skills reference";
  if (name === "MyCareersFuture") return "Jobs list";
  if (name === "OneMap") return "Map";
  if (name === "Local mentor guide") return "Guide";
  return name;
}

function shortFundingLabel(course) {
  const amount = Number(course?.estimatedOutOfPocket || 0);
  if (amount <= 0) return "$0 planning estimate";
  const formatted = Number.isInteger(amount) ? String(amount) : amount.toFixed(2);
  return `$${formatted} planning estimate`;
}

function sourceTitle(source) {
  const label = escapeHtml(simpleSourceName(source.name));
  const url = safeUrl(source.url);
  if (!url) return label;
  return `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${label}</a>`;
}

function safeUrl(value) {
  const text = String(value || "");
  return /^https:\/\/[a-z0-9.-]+\//i.test(text) ? text : "";
}

function simpleReason(reason) {
  return String(reason)
    .replace("Recent job postings mention related skills.", "Job skill signals support this path.")
    .replace("No live job lookup was used for this result.", "Private mode: live job lookup was not used.")
    .replace("Funding, eligibility, and enrolment are not decided by SkillQuest.", "Check funding and enrolment with the provider.");
}

function parseSkillText(value) {
  return String(value || "")
    .split(/[,;|]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

const caseList = document.querySelector("#case-list");
const connectionStatus = document.querySelector("#connection-status");
const selectedTitle = document.querySelector("#selected-title");
const selectedDescription = document.querySelector("#selected-description");
const selectedVerdict = document.querySelector("#selected-verdict");
const reportFrame = document.querySelector("#report-frame");
const reportWrap = document.querySelector("#report-wrap");
const emptyState = document.querySelector("#empty-state");
const errorState = document.querySelector("#error-state");

const verdictLabels = {
  defect_indicated: "Defect indicated",
  no_defect_found: "No defect found",
  insufficient_evidence: "Insufficient evidence",
};

function displayVerdict(value) {
  return verdictLabels[value] || value.replaceAll("_", " ");
}

function setSelected(caseData) {
  document.querySelectorAll(".case-button").forEach((button) => {
    const active = button.dataset.caseId === caseData.case_id;
    button.setAttribute("aria-current", active ? "true" : "false");
  });
  selectedTitle.textContent = `${caseData.case_id} · ${caseData.title}`;
  selectedDescription.textContent = caseData.description || "The findings below are based on the evidence available for this request.";
  selectedVerdict.textContent = displayVerdict(caseData.actual);
  selectedVerdict.dataset.verdict = caseData.actual;
  reportFrame.src = window.location.protocol === "file:"
    ? `../reports/${encodeURIComponent(caseData.case_id)}.html`
    : `/api/reports/${encodeURIComponent(caseData.case_id)}`;
  reportFrame.title = `${caseData.case_id} investigation report`;
  reportWrap.hidden = false;
  emptyState.hidden = true;
  const url = new URL(window.location.href);
  url.searchParams.set("case", caseData.case_id);
  history.replaceState({}, "", url);
}

function renderCases(data) {
  caseList.replaceChildren();
  document.querySelector("#case-count").textContent = String(data.cases.length).padStart(2, "0");
  data.cases.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "case-button";
    button.dataset.caseId = item.case_id;
    button.setAttribute("aria-current", "false");
    const id = document.createElement("span");
    id.className = "case-id";
    id.textContent = item.case_id;
    const title = document.createElement("span");
    title.className = "case-title";
    title.textContent = item.title;
    const state = document.createElement("span");
    state.className = `case-state ${item.pass ? "is-pass" : "is-fail"}`;
    state.textContent = item.pass ? "MATCH" : "MISMATCH";
    button.append(id, title, state);
    button.addEventListener("click", () => setSelected(item));
    caseList.append(button);
  });
  const passes = data.cases.filter((item) => item.pass).length;
  document.querySelector("#score").textContent = `${passes} / ${data.sample_size}`;
  document.querySelector("#score-caption").textContent = passes === data.sample_size ? "Expected verdicts matched" : `${passes} expected verdicts matched`;
  const counts = data.cases.reduce((total, item) => {
    total[item.actual] = (total[item.actual] || 0) + 1;
    return total;
  }, {});
  const breakdown = document.querySelector("#breakdown");
  breakdown.replaceChildren();
  ["defect_indicated", "no_defect_found", "insufficient_evidence"].forEach((verdict) => {
    if (!counts[verdict]) return;
    const line = document.createElement("div");
    line.className = "breakdown-line";
    const number = document.createElement("strong");
    number.textContent = String(counts[verdict]).padStart(2, "0");
    const label = document.createElement("span");
    label.textContent = displayVerdict(verdict);
    line.append(number, label);
    breakdown.append(line);
  });
  connectionStatus.textContent = "Results API connected";
  document.querySelector(".status-dot").classList.add("is-live");
  const selectedCase = new URLSearchParams(window.location.search).get("case");
  setSelected(data.cases.find((item) => item.case_id === selectedCase) || data.cases[0]);
}

async function loadResults() {
  errorState.hidden = true;
  try {
    const response = await fetch("/api/reports", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Results service returned ${response.status}.`);
    renderCases(await response.json());
  } catch (error) {
    connectionStatus.textContent = "Results API unavailable";
    document.querySelector(".status-dot").classList.remove("is-live");
    errorState.hidden = false;
    document.querySelector("#error-message").textContent = error.message;
    caseList.replaceChildren();
  }
}

document.querySelector("#retry").addEventListener("click", loadResults);
if (window.location.protocol === "file:" && window.BUGTRACE_PREVIEW_RESULTS) {
  document.querySelector("#evaluation-link").href = "../reports/evaluation.md";
  document.querySelector("#evaluation-link").removeAttribute("target");
  renderCases(window.BUGTRACE_PREVIEW_RESULTS);
} else {
  loadResults();
}

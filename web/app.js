(() => {
  const EXAMPLES = {
    "Valid Personal Injury":
      "Rear-end collision in CA, clear liability, $45k damages, incident 6 months ago.",
    "SOL Expired": "Slip-and-fall in NV, incident 4 years ago, moderate injuries.",
    "Conflict Case":
      "Employment discrimination claim in CA, opposing party is ACME Corp.",
    "Uncertain / Review":
      "Immigration matter with unclear facts, missing dates, missing jurisdiction.",
  };

  const apiBase = () => (window.LEXINTAKE_API_URL || "").replace(/\/$/, "");

  const els = {
    apiStatus: document.getElementById("api-status"),
    tabs: document.querySelectorAll(".tab"),
    panelInterview: document.getElementById("panel-interview"),
    panelQuick: document.getElementById("panel-quick"),
    chat: document.getElementById("chat"),
    chatForm: document.getElementById("chat-form"),
    chatInput: document.getElementById("chat-input"),
    chatDate: document.getElementById("chat-date"),
    chatInputMode: document.getElementById("chat-input-mode"),
    restart: document.getElementById("restart-interview"),
    interviewResult: document.getElementById("interview-result"),
    caseDescription: document.getElementById("case-description"),
    exampleSelect: document.getElementById("example-select"),
    insertExample: document.getElementById("insert-example"),
    runAnalysis: document.getElementById("run-analysis"),
    quickError: document.getElementById("quick-error"),
    quickResult: document.getElementById("quick-result"),
  };

  let sessionId = null;
  let interviewDone = false;
  let inputMode = "text"; // "text" | "date"

  function showApiError(message) {
    els.apiStatus.hidden = false;
    els.apiStatus.textContent = message;
  }

  function clearApiError() {
    els.apiStatus.hidden = true;
    els.apiStatus.textContent = "";
  }

  async function api(path, options = {}) {
    const base = apiBase();
    if (!base) {
      throw new Error(
        "LEXINTAKE_API_URL is not set. Deploy the Render API and set this env var on Vercel."
      );
    }
    const res = await fetch(`${base}${path}`, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = body.detail || JSON.stringify(body);
      } catch {
        /* ignore */
      }
      throw new Error(detail);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  function appendBubble(role, content) {
    const div = document.createElement("div");
    div.className = `bubble ${role}`;
    div.textContent = content;
    els.chat.appendChild(div);
    els.chat.scrollTop = els.chat.scrollHeight;
  }

  function wantsDateInput(data) {
    const missing = data.missing_fields || [];
    const msg = String(data.assistant_message || "").toLowerCase();
    return (
      missing.includes("incident_date") &&
      /incident|event date|yyyy-mm-dd|date picker|date/.test(msg)
    );
  }

  function setInputMode(mode) {
    inputMode = mode === "date" ? "date" : "text";
    const useDate = inputMode === "date";
    els.chatInput.hidden = useDate;
    els.chatInput.required = !useDate;
    els.chatDate.hidden = !useDate;
    els.chatDate.required = useDate;
    els.chatInputMode.hidden = !useDate;
    els.chatInputMode.textContent = "Type relative date instead";
    if (useDate) {
      els.chatDate.focus();
    } else {
      els.chatInput.placeholder =
        "Answer the agent’s question or describe your matter…";
      els.chatInput.focus();
    }
  }

  function syncComposer(data) {
    if (interviewDone) {
      setInputMode("text");
      return;
    }
    setInputMode(wantsDateInput(data) ? "date" : "text");
  }

  function renderResult(container, payload) {
    const qualified = payload.qualified ? "Yes" : "No";
    const citations = (payload.citations || [])
      .map(
        (c) =>
          `<li><code>chunk_id=${c.chunk_id || "—"}</code> · practice_area=${c.practice_area || "—"} · doc_type=${c.doc_type || "—"}</li>`
      )
      .join("");
    container.hidden = false;
    container.innerHTML = `
      ${payload.escalate ? '<div class="escalate">Escalated to human intake specialist.</div>' : ""}
      <div class="disclaimer"><strong>Disclaimer:</strong> This is not legal advice. Consult a licensed attorney.</div>
      <div class="metrics">
        <div class="metric"><span>Qualified</span><strong>${qualified}</strong></div>
        <div class="metric"><span>Lead score</span><strong>${payload.lead_score ?? "—"}</strong></div>
        <div class="metric"><span>Priority</span><strong>${payload.priority ?? "—"}</strong></div>
        <div class="metric"><span>Decision</span><strong>${payload.decision ?? "—"}</strong></div>
      </div>
      <h3>Lead Qualification</h3>
      <p>Recommended attorney: <code>${payload.recommended_attorney ?? "—"}</code><br/>
         Latency: <code>${Number(payload.latency_ms || 0).toFixed(1)} ms</code><br/>
         Cost: <code>$${Number(payload.cost || 0).toFixed(4)}</code></p>
      <h3>Explanation</h3>
      <p>${payload.explanation || "No explanation available."}</p>
      <h3>KB Citations</h3>
      ${citations ? `<ul>${citations}</ul>` : "<p class='muted'>No KB citations returned.</p>"}
      <h3>Raw JSON</h3>
      <pre>${JSON.stringify(
        {
          qualified: payload.qualified,
          lead_score: payload.lead_score,
          priority: payload.priority,
          decision: payload.decision,
          recommended_attorney: payload.recommended_attorney,
          explanation: payload.explanation,
          citations: payload.citations || [],
        },
        null,
        2
      )}</pre>
    `;
  }

  async function startInterview() {
    els.chat.innerHTML = "";
    els.interviewResult.hidden = true;
    interviewDone = false;
    sessionId = null;
    els.chatInput.disabled = true;
    els.chatDate.disabled = true;
    setInputMode("text");
    try {
      clearApiError();
      const data = await api("/v1/interview/sessions", { method: "POST", body: "{}" });
      sessionId = data.session_id;
      appendBubble("assistant", data.assistant_message);
      interviewDone = Boolean(data.done);
      syncComposer(data);
    } catch (err) {
      showApiError(String(err.message || err));
      appendBubble("assistant", `Could not start interview: ${err.message || err}`);
    } finally {
      els.chatInput.disabled = interviewDone;
      els.chatDate.disabled = interviewDone;
    }
  }

  els.tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      els.tabs.forEach((t) => {
        t.classList.toggle("active", t === tab);
        t.setAttribute("aria-selected", t === tab ? "true" : "false");
      });
      const name = tab.dataset.tab;
      els.panelInterview.hidden = name !== "interview";
      els.panelQuick.hidden = name !== "quick";
    });
  });

  els.restart.addEventListener("click", () => {
    startInterview();
  });

  els.chatInputMode.addEventListener("click", () => {
    setInputMode("text");
    els.chatInput.placeholder = "e.g. 6 months ago, June 15 2024, or 06/15/2024";
    els.chatInputMode.hidden = true;
  });

  els.chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!sessionId || interviewDone) return;
    const message =
      inputMode === "date"
        ? (els.chatDate.value || "").trim()
        : els.chatInput.value.trim();
    if (!message) return;
    els.chatInput.value = "";
    els.chatDate.value = "";
    appendBubble("user", message);
    els.chatInput.disabled = true;
    els.chatDate.disabled = true;
    try {
      const data = await api(`/v1/interview/sessions/${sessionId}/turns`, {
        method: "POST",
        body: JSON.stringify({ message }),
      });
      appendBubble("assistant", data.assistant_message);
      if (data.done) {
        interviewDone = true;
        if (data.screening) renderResult(els.interviewResult, data.screening);
      }
      syncComposer(data);
    } catch (err) {
      appendBubble("assistant", `Error: ${err.message || err}`);
    } finally {
      els.chatInput.disabled = interviewDone;
      els.chatDate.disabled = interviewDone;
    }
  });

  els.insertExample.addEventListener("click", () => {
    const key = els.exampleSelect.value;
    if (key && EXAMPLES[key]) els.caseDescription.value = EXAMPLES[key];
  });

  els.runAnalysis.addEventListener("click", async () => {
    const description = els.caseDescription.value.trim();
    els.quickError.hidden = true;
    if (!description) {
      els.quickError.hidden = false;
      els.quickError.textContent = "Enter a case description first.";
      return;
    }
    els.runAnalysis.disabled = true;
    try {
      clearApiError();
      const payload = await api("/v1/intake/analyze", {
        method: "POST",
        body: JSON.stringify({ description }),
      });
      renderResult(els.quickResult, payload);
    } catch (err) {
      els.quickError.hidden = false;
      els.quickError.textContent = String(err.message || err);
    } finally {
      els.runAnalysis.disabled = false;
    }
  });

  if (!apiBase()) {
    showApiError(
      "API URL missing. Set LEXINTAKE_API_URL to your Render backend (e.g. https://lexintake-api.onrender.com)."
    );
  } else {
    startInterview();
  }
})();

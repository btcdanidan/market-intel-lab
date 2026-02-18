const runForm = document.getElementById("run-form");
const runStatus = document.getElementById("run-status");
const healthBox = document.getElementById("health-box");
const latestJson = document.getElementById("latest-json");
const memoPreview = document.getElementById("memo-preview");
const runBtn = document.getElementById("run-btn");
const refreshHealthBtn = document.getElementById("refresh-health");
const refreshLatestBtn = document.getElementById("refresh-latest");

const chatRunSelect = document.getElementById("chat-run-select");
const chatStatus = document.getElementById("chat-status");
const chatTranscript = document.getElementById("chat-transcript");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatSend = document.getElementById("chat-send");
const chatClear = document.getElementById("chat-clear");

const state = {
  runs: [],
  currentRunId: null,
  userSelectedRun: false,
  chatMessages: [],
  chatAvailable: false,
  chatBusy: false,
};

function setHealthPill(ok, text) {
  healthBox.className = `pill ${ok ? "ok" : "bad"}`;
  healthBox.textContent = text;
}

function setChatStatus(kind, text) {
  chatStatus.className = `pill ${kind}`;
  chatStatus.textContent = text;
}

function setChatInputsEnabled(enabled) {
  chatInput.disabled = !enabled;
  chatSend.disabled = !enabled || state.chatBusy;
  chatClear.disabled = !enabled;
  chatRunSelect.disabled = !enabled;
}

function storageKey(runId) {
  return `market-intel-lab.chat.${runId}`;
}

function loadChatHistory(runId) {
  if (!runId) {
    return [];
  }
  const raw = localStorage.getItem(storageKey(runId));
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed
      .filter((item) => item && (item.role === "user" || item.role === "assistant"))
      .map((item) => ({
        role: item.role,
        content: String(item.content || ""),
        citations: Array.isArray(item.citations)
          ? item.citations.map((v) => String(v))
          : [],
        note: item.note ? String(item.note) : "",
      }));
  } catch {
    return [];
  }
}

function saveChatHistory() {
  if (!state.currentRunId) {
    return;
  }
  localStorage.setItem(storageKey(state.currentRunId), JSON.stringify(state.chatMessages));
}

function renderChatMessages() {
  chatTranscript.innerHTML = "";

  if (!state.chatMessages.length) {
    const placeholder = document.createElement("p");
    placeholder.className = "chat-placeholder";
    placeholder.textContent = "Ask follow-up questions about the selected analysis run.";
    chatTranscript.appendChild(placeholder);
    return;
  }

  for (const message of state.chatMessages) {
    const wrapper = document.createElement("article");
    wrapper.className = `chat-msg ${message.role}`;

    const role = document.createElement("span");
    role.className = "chat-role";
    role.textContent = message.role === "assistant" ? "Codex" : "You";

    const content = document.createElement("p");
    content.className = "chat-content";
    content.textContent = message.content;

    wrapper.appendChild(role);
    wrapper.appendChild(content);

    if (message.note) {
      const note = document.createElement("p");
      note.className = "chat-content";
      note.textContent = message.note;
      wrapper.appendChild(note);
    }

    if (message.citations && message.citations.length > 0) {
      const citations = document.createElement("div");
      citations.className = "chat-citations";
      for (const citation of message.citations) {
        const tag = document.createElement("span");
        tag.className = "chat-cite";
        tag.textContent = `[${citation}]`;
        citations.appendChild(tag);
      }
      wrapper.appendChild(citations);
    }

    chatTranscript.appendChild(wrapper);
  }

  chatTranscript.scrollTop = chatTranscript.scrollHeight;
}

function setCurrentRun(runId, { fromUser = false } = {}) {
  state.currentRunId = runId;
  if (fromUser) {
    state.userSelectedRun = true;
  }
  if (runId) {
    chatRunSelect.value = runId;
  }
  state.chatMessages = loadChatHistory(runId);
  renderChatMessages();
}

function renderRunSelect(preferredRunId = null) {
  chatRunSelect.innerHTML = "";

  if (!state.runs.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No runs";
    chatRunSelect.appendChild(option);
    state.currentRunId = null;
    state.chatMessages = [];
    renderChatMessages();
    return;
  }

  for (const run of state.runs) {
    const option = document.createElement("option");
    option.value = run.id;
    option.textContent = `${run.id} (${run.status}, ${run.regime})`;
    chatRunSelect.appendChild(option);
  }

  const availableIds = new Set(state.runs.map((run) => run.id));
  let runId = preferredRunId;
  if (!runId || !availableIds.has(runId)) {
    runId = state.currentRunId;
  }
  if (!runId || !availableIds.has(runId)) {
    runId = state.runs[0].id;
  }

  setCurrentRun(runId);
}

async function fetchHealth() {
  try {
    const res = await fetch("/health");
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();
    const ok = data.status === "ok";
    const text = `${data.status.toUpperCase()} | redis=${data.redis} db=${data.database}`;
    setHealthPill(ok, text);
  } catch (err) {
    setHealthPill(false, `DEGRADED | ${String(err)}`);
  }
}

function renderLatest(data) {
  latestJson.textContent = JSON.stringify(data, null, 2);
  if (data.memo_body) {
    memoPreview.textContent = data.memo_body;
  }

  if (data.id && !state.userSelectedRun) {
    setCurrentRun(data.id);
  }
}

async function fetchLatest() {
  try {
    const res = await fetch("/status/latest");
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();
    renderLatest(data);
  } catch (err) {
    latestJson.textContent = `Failed to load latest run: ${String(err)}`;
  }
}

async function fetchRun(runId) {
  const res = await fetch(`/analysis/${runId}`);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  const data = await res.json();
  renderLatest(data);
}

async function fetchRuns(preferredRunId = null) {
  try {
    const res = await fetch("/analysis/runs?limit=20");
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const payload = await res.json();
    state.runs = Array.isArray(payload.runs) ? payload.runs : [];
    renderRunSelect(preferredRunId);

    if (!state.runs.length) {
      setChatStatus("muted", "Run analysis first to enable chat.");
      setChatInputsEnabled(false);
    }
  } catch (err) {
    setChatStatus("bad", `Failed loading runs: ${String(err)}`);
    setChatInputsEnabled(false);
  }
}

async function fetchChatStatus() {
  try {
    const res = await fetch("/chat/status");
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const data = await res.json();
    state.chatAvailable = Boolean(data.available);

    if (!state.chatAvailable) {
      setChatStatus("bad", data.reason || "Chat unavailable");
      setChatInputsEnabled(false);
      return;
    }

    if (!state.runs.length) {
      setChatStatus("muted", "Run analysis first to enable chat.");
      setChatInputsEnabled(false);
      return;
    }

    setChatStatus("ok", `Ready on run ${state.currentRunId || "-"}`);
    setChatInputsEnabled(true);
  } catch (err) {
    state.chatAvailable = false;
    setChatStatus("bad", `Chat status failed: ${String(err)}`);
    setChatInputsEnabled(false);
  }
}

function parseAssets(value) {
  return value
    .split(",")
    .map((v) => v.trim().toUpperCase())
    .filter(Boolean);
}

async function onRunSubmit(event) {
  event.preventDefault();
  runBtn.disabled = true;
  runStatus.textContent = "Running analysis...";

  const formData = new FormData(runForm);
  const payload = {
    assets: parseAssets(String(formData.get("assets") || "")),
    portfolio_equity: Number(formData.get("equity")),
    per_trade_risk_pct: Number(formData.get("risk_pct")),
    window_hours: Number(formData.get("window_hours")),
  };

  try {
    const res = await fetch("/analysis/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`HTTP ${res.status}: ${errorText}`);
    }
    const data = await res.json();
    runStatus.textContent = `Run completed: ${data.run_id} | regime=${data.regime} | degraded=${data.degraded}`;
    state.userSelectedRun = false;
    await fetchRun(data.run_id);
    await fetchRuns(data.run_id);
    await fetchChatStatus();
    await fetchHealth();
  } catch (err) {
    runStatus.textContent = `Run failed: ${String(err)}`;
  } finally {
    runBtn.disabled = false;
  }
}

async function streamChat(payload, onEvent) {
  const res = await fetch("/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok || !res.body) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (value) {
      buffer += decoder.decode(value, { stream: true });
      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const rawEvent = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf("\n\n");

        const lines = rawEvent.split("\n");
        let event = "message";
        let dataText = "";

        for (const line of lines) {
          if (line.startsWith("event:")) {
            event = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            dataText += line.slice(5).trim();
          }
        }

        if (dataText) {
          try {
            const data = JSON.parse(dataText);
            onEvent(event, data);
          } catch {
            onEvent("error", { message: "Malformed SSE payload" });
          }
        }
      }
    }

    if (done) {
      break;
    }
  }
}

async function onChatSubmit(event) {
  event.preventDefault();
  const question = chatInput.value.trim();

  if (!question || !state.currentRunId) {
    return;
  }
  if (!state.chatAvailable || state.chatBusy) {
    return;
  }

  const historyPayload = state.chatMessages.map((msg) => ({
    role: msg.role,
    content: msg.content,
  }));

  const userMessage = { role: "user", content: question, citations: [], note: "" };
  const assistantMessage = {
    role: "assistant",
    content: "",
    citations: [],
    note: "",
  };

  state.chatMessages.push(userMessage);
  state.chatMessages.push(assistantMessage);
  chatInput.value = "";
  renderChatMessages();

  state.chatBusy = true;
  setChatInputsEnabled(false);
  setChatStatus("muted", "Codex is thinking...");

  try {
    await streamChat(
      {
        run_id: state.currentRunId,
        question,
        messages: historyPayload,
      },
      (eventName, payload) => {
        if (eventName === "meta") {
          const runId = payload.run && payload.run.id ? payload.run.id : state.currentRunId;
          setChatStatus("muted", `Streaming answer for run ${runId}`);
          return;
        }

        if (eventName === "delta") {
          assistantMessage.content += String(payload.text || "");
          renderChatMessages();
          return;
        }

        if (eventName === "done") {
          assistantMessage.content = String(payload.answer || assistantMessage.content);
          assistantMessage.citations = Array.isArray(payload.citations)
            ? payload.citations.map((v) => String(v))
            : [];
          assistantMessage.note = payload.citation_note ? String(payload.citation_note) : "";
          setChatStatus("ok", `Answer complete (${payload.model})`);
          renderChatMessages();
          return;
        }

        if (eventName === "error") {
          setChatStatus("bad", String(payload.message || "Chat stream error"));
        }
      },
    );
  } catch (err) {
    setChatStatus("bad", `Chat failed: ${String(err)}`);
  } finally {
    state.chatBusy = false;
    setChatInputsEnabled(state.chatAvailable && Boolean(state.currentRunId));
    saveChatHistory();
  }
}

function onRunSelectionChanged(event) {
  const runId = String(event.target.value || "");
  if (!runId) {
    return;
  }
  setCurrentRun(runId, { fromUser: true });
  setChatStatus("ok", `Ready on run ${runId}`);
  setChatInputsEnabled(state.chatAvailable);
}

function onClearChat() {
  if (!state.currentRunId) {
    return;
  }
  localStorage.removeItem(storageKey(state.currentRunId));
  state.chatMessages = [];
  renderChatMessages();
  setChatStatus("muted", `Cleared chat for run ${state.currentRunId}`);
}

runForm.addEventListener("submit", onRunSubmit);
refreshHealthBtn.addEventListener("click", fetchHealth);
refreshLatestBtn.addEventListener("click", fetchLatest);
chatForm.addEventListener("submit", onChatSubmit);
chatRunSelect.addEventListener("change", onRunSelectionChanged);
chatClear.addEventListener("click", onClearChat);

await fetchHealth();
await fetchLatest();
await fetchRuns();
await fetchChatStatus();

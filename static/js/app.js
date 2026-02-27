const BASE_URL = "";

let authToken = null;
let chatHistory = [];

// --- Helpers ---
function getAuthHeaders() {
  const headers = { "Content-Type": "application/json" };
  if (authToken) headers["Authorization"] = `Bearer ${authToken}`;
  return headers;
}

function showResult(el, content, type = "success") {
  el.className = `result ${type}`;
  el.innerHTML = content;
}

function setLoading(btn, loading, label = "Submit") {
  btn.disabled = loading;
  btn.innerHTML = loading ? `<span class="spinner"></span> Loading…` : label;
}

function updateAuthStatus(username) {
  const badge = document.getElementById("auth-badge");
  const logoutBtn = document.getElementById("logout-btn");
  if (username) {
    badge.textContent = `Authenticated as ${username}`;
    badge.className = "badge badge-active";
    logoutBtn.classList.remove("hidden");
  } else {
    badge.textContent = "Not Authenticated";
    badge.className = "badge badge-inactive";
    logoutBtn.classList.add("hidden");
  }
}

function providerLabel(model) {
  if (model.startsWith("ollama/")) return `Ollama · ${model.replace("ollama/", "")}`;
  if (model.startsWith("anthropic/")) return `Anthropic · ${model.replace("anthropic/", "")}`;
  return model;
}

// --- Auth ---
document.getElementById("auth-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = e.target.querySelector("button[type=submit]");
  const resultEl = document.getElementById("auth-result");
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;

  setLoading(btn, true, "Login");
  resultEl.classList.add("hidden");

  try {
    const res = await fetch(`${BASE_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      showResult(resultEl, `<strong>Error ${res.status}:</strong> ${data.detail || "Login failed"}`, "error");
      authToken = null;
      updateAuthStatus(null);
    } else {
      authToken = data.access_token;
      updateAuthStatus(data.username);
      showResult(resultEl, `
        <strong style="color:#4ade80">Login successful!</strong><br/>
        <span style="color:#94a3b8">Token (Bearer):</span>
        <div class="token-box">${data.access_token}</div>
        <div style="margin-top:0.5rem;font-size:0.78rem;color:#64748b">
          Expires in: ${data.expires_in}s &nbsp;|&nbsp; Type: ${data.token_type}
        </div>
      `, "success");
    }
  } catch (err) {
    showResult(resultEl, `<strong>Network error:</strong> ${err.message}`, "error");
  } finally {
    setLoading(btn, false, "Login");
    resultEl.classList.remove("hidden");
  }
});

document.getElementById("logout-btn").addEventListener("click", () => {
  authToken = null;
  updateAuthStatus(null);
  document.getElementById("auth-result").classList.add("hidden");
});

// --- RAG ---
document.getElementById("rag-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = e.target.querySelector("button[type=submit]");
  const resultEl = document.getElementById("rag-result");
  const query = document.getElementById("rag-query").value.trim();
  const model = document.getElementById("rag-model").value;
  if (!query) return;

  setLoading(btn, true, "Search");
  resultEl.classList.add("hidden");

  try {
    const res = await fetch(`${BASE_URL}/api/rag/query`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ query, model }),
    });
    const data = await res.json();
    if (!res.ok) {
      showResult(resultEl, `<strong>Error ${res.status}:</strong> ${data.detail || "RAG query failed"}`, "error");
    } else {
      const docsHtml = data.context_documents.map((d) => `<li>${d}</li>`).join("");
      showResult(resultEl, `
        <div class="answer-text">${data.answer}</div>
        <div class="context-docs">
          <h4>Retrieved Context · <span style="color:#60a5fa">${providerLabel(data.model)}</span></h4>
          <ul>${docsHtml}</ul>
        </div>
      `, "success");
    }
  } catch (err) {
    showResult(resultEl, `<strong>Network error:</strong> ${err.message}`, "error");
  } finally {
    setLoading(btn, false, "Search");
    resultEl.classList.remove("hidden");
  }
});

// --- Chat ---
function addChatBubble(role, content, model) {
  const chatMessages = document.getElementById("chat-messages");
  const div = document.createElement("div");
  div.className = `chat-bubble ${role}`;
  div.textContent = content;
  if (model && role === "assistant") {
    const tag = document.createElement("div");
    tag.className = "bubble-model";
    tag.textContent = providerLabel(model);
    div.appendChild(tag);
  }
  chatMessages.appendChild(div);
  document.getElementById("chat-window").scrollTop = 9999;
}

function addSystemMessage(text) {
  const chatMessages = document.getElementById("chat-messages");
  const div = document.createElement("div");
  div.className = "chat-bubble system";
  div.textContent = text;
  chatMessages.appendChild(div);
}

document.getElementById("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = e.target.querySelector("button[type=submit]");
  const input = document.getElementById("chat-input");
  const model = document.getElementById("chat-model").value;
  const message = input.value.trim();
  if (!message) return;

  input.value = "";
  addChatBubble("user", message);
  setLoading(btn, true, "Send");

  try {
    const res = await fetch(`${BASE_URL}/api/chat/message`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ message, history: chatHistory, model }),
    });
    const data = await res.json();
    if (!res.ok) {
      addSystemMessage(`Error ${res.status}: ${data.detail || "Chat failed"}`);
    } else {
      chatHistory = data.history;
      addChatBubble("assistant", data.message, data.model);
    }
  } catch (err) {
    addSystemMessage(`Network error: ${err.message}`);
  } finally {
    setLoading(btn, false, "Send");
    input.focus();
  }
});

document.getElementById("clear-chat-btn").addEventListener("click", () => {
  chatHistory = [];
  document.getElementById("chat-messages").innerHTML = "";
  addSystemMessage("Chat cleared. Start a new conversation.");
});

// Init
addSystemMessage("Chat ready. Send a message to start.");

/**
 * AGI System — Floating Chat Widget
 * Drop this script anywhere: <script src="/static/widget.js"></script>
 */
(function () {
  "use strict";

  const API_BASE =
    window.AGI_API_BASE ||
    (typeof document !== "undefined" ? window.location.origin : "");

  // ── Styles ─────────────────────────────────────────────────────────────────
  const STYLE = `
    #agi-widget-btn {
      position: fixed; bottom: 24px; right: 24px; z-index: 9998;
      width: 56px; height: 56px; border-radius: 50%; border: none; cursor: pointer;
      background: linear-gradient(135deg, #00c8ff 0%, #0070f3 100%);
      box-shadow: 0 4px 20px rgba(0,200,255,0.4);
      display: flex; align-items: center; justify-content: center;
      transition: transform .2s, box-shadow .2s;
    }
    #agi-widget-btn:hover {
      transform: scale(1.1);
      box-shadow: 0 6px 28px rgba(0,200,255,0.55);
    }
    #agi-widget-btn svg { width: 26px; height: 26px; fill: #fff; }
    #agi-widget-frame {
      position: fixed; bottom: 90px; right: 24px; z-index: 9999;
      width: 380px; height: 560px; border-radius: 16px; overflow: hidden;
      box-shadow: 0 12px 48px rgba(0,0,0,0.55);
      display: none; flex-direction: column;
      background: #0d1628; border: 1px solid #1c2e4a;
      font-family: "IBM Plex Sans", system-ui, sans-serif;
    }
    #agi-widget-frame.open { display: flex; }
    #agi-widget-header {
      padding: 14px 16px; background: #132038; border-bottom: 1px solid #1c2e4a;
      display: flex; align-items: center; justify-content: space-between;
      color: #d8e8f8; font-size: 14px; font-weight: 600; flex-shrink: 0;
    }
    #agi-widget-header span { display: flex; align-items: center; gap: 8px; }
    #agi-widget-header .dot {
      width: 8px; height: 8px; border-radius: 50%; background: #00e5a0;
      box-shadow: 0 0 6px #00e5a0;
    }
    #agi-widget-close {
      background: none; border: none; cursor: pointer; color: #4d6889;
      font-size: 20px; line-height: 1; padding: 0;
    }
    #agi-widget-close:hover { color: #d8e8f8; }
    #agi-widget-messages {
      flex: 1; overflow-y: auto; padding: 16px 12px;
      display: flex; flex-direction: column; gap: 10px;
    }
    #agi-widget-messages::-webkit-scrollbar { width: 4px; }
    #agi-widget-messages::-webkit-scrollbar-track { background: transparent; }
    #agi-widget-messages::-webkit-scrollbar-thumb { background: #1c2e4a; border-radius: 2px; }
    .agi-msg {
      max-width: 82%; padding: 9px 12px; border-radius: 12px;
      font-size: 13px; line-height: 1.5; word-break: break-word;
    }
    .agi-msg.user {
      align-self: flex-end; background: #0070f3; color: #fff;
      border-bottom-right-radius: 4px;
    }
    .agi-msg.assistant {
      align-self: flex-start; background: #132038; color: #d8e8f8;
      border: 1px solid #1c2e4a; border-bottom-left-radius: 4px;
    }
    .agi-msg.error { align-self: flex-start; color: #ff4d6d; font-size: 12px; }
    #agi-widget-input-row {
      padding: 10px 12px; border-top: 1px solid #1c2e4a; background: #0d1628;
      display: flex; gap: 8px; flex-shrink: 0;
    }
    #agi-widget-input {
      flex: 1; background: #132038; border: 1px solid #1c2e4a; border-radius: 8px;
      color: #d8e8f8; font-size: 13px; padding: 8px 10px; outline: none; resize: none;
      font-family: inherit; height: 36px; max-height: 120px; overflow-y: auto;
    }
    #agi-widget-input:focus { border-color: #00c8ff; }
    #agi-widget-send {
      background: #0070f3; border: none; border-radius: 8px; cursor: pointer;
      color: #fff; padding: 8px 14px; font-size: 13px; font-weight: 600;
      transition: background .15s;
    }
    #agi-widget-send:hover { background: #00c8ff; color: #070d1a; }
    #agi-widget-send:disabled { background: #1c2e4a; cursor: default; }
  `;

  // ── DOM ────────────────────────────────────────────────────────────────────
  function mount() {
    if (document.getElementById("agi-widget-btn")) return;

    const style = document.createElement("style");
    style.textContent = STYLE;
    document.head.appendChild(style);

    // Toggle button
    const btn = document.createElement("button");
    btn.id = "agi-widget-btn";
    btn.title = "Open AGI Assistant";
    btn.innerHTML = `<svg viewBox="0 0 24 24"><path d="M20 2H4a2 2 0 0 0-2 2v18l4-4h14a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2z"/></svg>`;
    document.body.appendChild(btn);

    // Frame
    const frame = document.createElement("div");
    frame.id = "agi-widget-frame";
    frame.setAttribute("role", "dialog");
    frame.setAttribute("aria-label", "AGI Assistant");
    frame.innerHTML = `
      <div id="agi-widget-header">
        <span><span class="dot"></span>AGI Assistant</span>
        <button id="agi-widget-close" aria-label="Close">&times;</button>
      </div>
      <div id="agi-widget-messages" aria-live="polite"></div>
      <div id="agi-widget-input-row">
        <textarea id="agi-widget-input" placeholder="Ask anything…" rows="1"></textarea>
        <button id="agi-widget-send">Send</button>
      </div>
    `;
    document.body.appendChild(frame);

    // Wire events
    btn.addEventListener("click", toggle);
    document.getElementById("agi-widget-close").addEventListener("click", toggle);
    document.getElementById("agi-widget-send").addEventListener("click", sendMessage);
    document.getElementById("agi-widget-input").addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    // Greeting
    appendMessage("assistant", "Hi! I'm your AGI assistant. How can I help?");
  }

  // ── State ──────────────────────────────────────────────────────────────────
  let sessionId = null;

  function toggle() {
    const frame = document.getElementById("agi-widget-frame");
    frame.classList.toggle("open");
    if (frame.classList.contains("open") && !sessionId) {
      createSession();
    }
  }

  async function createSession() {
    try {
      const r = await fetch(`${API_BASE}/api/v1/conversational/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: "widget-anonymous" }),
      });
      if (r.ok) {
        const data = await r.json();
        sessionId = data.session_id;
      }
    } catch (_) {
      // session creation failed — will work without one
    }
  }

  async function sendMessage() {
    const input = document.getElementById("agi-widget-input");
    const sendBtn = document.getElementById("agi-widget-send");
    const text = input.value.trim();
    if (!text) return;

    input.value = "";
    sendBtn.disabled = true;
    appendMessage("user", text);

    try {
      // Classify intent first
      const clf = await fetch(`${API_BASE}/api/v1/conversational/classify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, session_id: sessionId }),
      });
      let intent = null;
      if (clf.ok) {
        const cd = await clf.json();
        intent = cd.intent;
      }

      // If we have a session, store the message
      if (sessionId) {
        await fetch(`${API_BASE}/api/v1/conversational/sessions/${sessionId}/messages`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ role: "user", content: text }),
        });
      }

      // Route to an agent task
      const dispatch = await fetch(`${API_BASE}/api/v1/tasks/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ objective: text, context: { intent, session_id: sessionId } }),
      });

      if (dispatch.ok) {
        const td = await dispatch.json();
        const reply = `Task queued (${td.task_id || "unknown"}). An agent will handle: "${text}"`;
        appendMessage("assistant", reply);
        if (sessionId) {
          await fetch(`${API_BASE}/api/v1/conversational/sessions/${sessionId}/messages`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ role: "assistant", content: reply }),
          });
        }
      } else {
        appendMessage("assistant", "Received. I'm working on it!");
      }
    } catch (err) {
      appendMessage("error", "Connection error. Please try again.");
    } finally {
      sendBtn.disabled = false;
      input.focus();
    }
  }

  function appendMessage(role, content) {
    const container = document.getElementById("agi-widget-messages");
    if (!container) return;
    const el = document.createElement("div");
    el.className = `agi-msg ${role}`;
    el.textContent = content;
    container.appendChild(el);
    container.scrollTop = container.scrollHeight;
  }

  // ── Init ───────────────────────────────────────────────────────────────────
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();

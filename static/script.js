const messagesEl = document.getElementById("messages");
const form       = document.getElementById("chat-form");
const input      = document.getElementById("user-input");
const sendBtn    = document.getElementById("send-btn");

// Conversation history sent to the backend
const history = [];

// Auto-grow textarea
input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 120) + "px";
});

// Submit on Enter (Shift+Enter = newline)
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;

  // Add user message to UI and history
  appendMessage("user", text);
  history.push({ role: "user", content: text });

  // Clear input
  input.value = "";
  input.style.height = "auto";
  setLoading(true);

  // Create assistant bubble (streaming)
  const bubble = appendMessage("assistant", "", true);

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history }),
    });

    if (!res.ok) {
      bubble.textContent = "Error al conectar con el servidor. Intenta de nuevo.";
      bubble.classList.remove("streaming");
      history.pop();
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let fullText = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split("\n");

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (raw === "[DONE]") continue;

        try {
          const parsed = JSON.parse(raw);
          if (parsed.error) {
            bubble.textContent = "Error: " + parsed.error;
            history.pop();
            break;
          }
          if (parsed.text) {
            fullText += parsed.text;
            bubble.innerHTML = formatText(fullText);
            scrollToBottom();
          }
        } catch {
          // skip malformed lines
        }
      }
    }

    bubble.classList.remove("streaming");

    if (fullText) {
      history.push({ role: "assistant", content: fullText });
    }
  } catch (err) {
    bubble.textContent = "Error de conexión. Verifica tu internet e intenta de nuevo.";
    bubble.classList.remove("streaming");
    history.pop();
  } finally {
    setLoading(false);
    input.focus();
  }
});

function appendMessage(role, text, streaming = false) {
  const wrap = document.createElement("div");
  wrap.className = `message ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "assistant" ? "F" : "Tú";

  const bubble = document.createElement("div");
  bubble.className = "bubble" + (streaming ? " streaming" : "");

  if (text) {
    bubble.innerHTML = formatText(text);
  }

  wrap.appendChild(avatar);
  wrap.appendChild(bubble);
  messagesEl.appendChild(wrap);
  scrollToBottom();

  return bubble;
}

function formatText(text) {
  // Escape HTML then convert line breaks to paragraphs
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  const paragraphs = escaped
    .split(/\n\n+/)
    .map(p => p.replace(/\n/g, "<br>"))
    .filter(p => p.trim())
    .map(p => `<p>${p}</p>`)
    .join("");

  return paragraphs || `<p>${escaped}</p>`;
}

function setLoading(loading) {
  sendBtn.disabled = loading;
  input.disabled   = loading;
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

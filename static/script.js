const chat = document.getElementById('chat');
const input = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const newChatBtn = document.getElementById('new-chat-btn');

const STORAGE_KEY = 'finanzasve_history_v1';
let conversationHistory = loadHistory();

function loadHistory() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}

function saveHistory() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversationHistory));
  } catch (e) {}
}

function clearHistory() {
  conversationHistory = [];
  try { localStorage.removeItem(STORAGE_KEY); } catch (e) {}
  chat.innerHTML = '';
  showWelcome();
}

function showWelcome() {
  if (conversationHistory.length === 0) {
    addMessage('assistant', '¡Hola! Soy FinanzasVE, tu asistente de finanzas personales. Puedo ayudarte con preguntas sobre el dólar, USDT, Binance P2P, remesas, IGTF, cómo proteger tus ahorros de la inflación, y más.\n\n¿En qué te puedo ayudar hoy?', false);
  }
}

function addMessage(role, content, save = true) {
  const msg = document.createElement('div');
  msg.className = 'msg msg-' + (role === 'user' ? 'user' : 'assistant');

  const inner = document.createElement('div');
  inner.className = 'msg-inner';

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.textContent = role === 'user' ? 'Tú' : 'F';

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.textContent = content;

  inner.appendChild(avatar);
  inner.appendChild(bubble);
  msg.appendChild(inner);
  chat.appendChild(msg);
  chat.scrollTop = chat.scrollHeight;

  if (save && content) {
    conversationHistory.push({role, content});
    saveHistory();
  }
  return bubble;
}

function renderHistory() {
  chat.innerHTML = '';
  if (conversationHistory.length === 0) {
    showWelcome();
    return;
  }
  conversationHistory.forEach(msg => {
    addMessage(msg.role, msg.content, false);
  });
}

async function sendMessage() {
  const text = input.value.trim();
  if (!text) return;

  addMessage('user', text);
  input.value = '';
  input.style.height = 'auto';
  sendBtn.disabled = true;

  const responseBubble = addMessage('assistant', '', false);
  responseBubble.classList.add('streaming');
  let fullResponse = '';

  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        message: text,
        history: conversationHistory.slice(0, -1)
      })
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream: true});
      const lines = buffer.split('\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.text) {
              fullResponse += data.text;
              responseBubble.textContent = fullResponse;
              chat.scrollTop = chat.scrollHeight;
            }
            if (data.error) {
              responseBubble.textContent = 'Lo siento, hubo un error. Intenta de nuevo.';
              fullResponse = '';
            }
          } catch (e) {}
        }
      }
    }

    responseBubble.classList.remove('streaming');

    if (fullResponse) {
      conversationHistory.push({role: 'assistant', content: fullResponse});
      saveHistory();
    }
  } catch (e) {
    responseBubble.textContent = 'Lo siento, hubo un error de conexión. Intenta de nuevo.';
    responseBubble.classList.remove('streaming');
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

sendBtn.addEventListener('click', sendMessage);

input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 160) + 'px';
});

newChatBtn.addEventListener('click', () => {
  if (confirm('¿Empezar nueva conversación? Tu historial actual se borrará.')) {
    clearHistory();
  }
});

renderHistory();
input.focus();

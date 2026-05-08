const chat = document.getElementById('chat');
const input = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');

let conversationHistory = [];

// Show welcome message on load
addMessage('assistant', '¡Hola! Soy FinanzasVE, tu asistente de finanzas personales. Puedo ayudarte con preguntas sobre el dólar, USDT, Binance P2P, remesas, cómo proteger tus ahorros de la inflación, y mucho más.\n\n¿En qué te puedo ayudar hoy?');

function addMessage(role, content) {
  const msg = document.createElement('div');
  msg.className = 'message ' + (role === 'user' ? 'user' : 'assistant');
  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = role === 'user' ? 'Tú' : 'F';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = content;
  msg.appendChild(avatar);
  msg.appendChild(bubble);
  chat.appendChild(msg);
  chat.scrollTop = chat.scrollHeight;
  return bubble;
}

async function sendMessage() {
  const text = input.value.trim();
  if (!text) return;

  addMessage('user', text);
  input.value = '';
  input.style.height = 'auto';
  sendBtn.disabled = true;

  const responseBubble = addMessage('assistant', '');
  let fullResponse = '';

  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        message: text,
        history: conversationHistory
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

    if (fullResponse) {
      conversationHistory.push({role: 'user', content: text});
      conversationHistory.push({role: 'assistant', content: fullResponse});
    }
  } catch (e) {
    responseBubble.textContent = 'Lo siento, hubo un error de conexión. Intenta de nuevo.';
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
  input.style.height = Math.min(input.scrollHeight, 140) + 'px';
});

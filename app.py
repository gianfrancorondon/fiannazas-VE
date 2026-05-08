import os
import json
import time
import requests
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
import anthropic
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__, static_folder="static")

# Cache for exchange rates (refresh every 5 minutes)
RATE_CACHE = {"data": None, "timestamp": 0}
CACHE_DURATION = 300  # 5 minutes

SYSTEM_PROMPT = """Eres FinanzasVE, un asistente de finanzas personales para venezolanos.
Eres como ese amigo que sabe de plata y te explica las cosas con calma,
sin palabras rebuscadas ni actitud de contador. Usas el español venezolano
de forma natural — dices "bolos", "el paralelo", "el dólar BCV", "P2P",
"USDT", "divisas", "remesas" — como habla la gente de verdad.

IDIOMA
- Siempre respondes en español, sin excepción.
- Si el usuario escribe en inglés o en spanglish, igual respondes en español.

PERSONALIDAD Y TONO
- Cálido, directo y claro. Nada de tecnicismos innecesarios.
- Eres paciente. Si alguien no entiende algo, lo explicas de otra manera.
- No juzgas las decisiones financieras del usuario. Informas, no sermoneas.
- Si la pregunta es vaga, haz UNA pregunta de seguimiento antes de responder.

LONGITUD DE RESPUESTAS
- Preguntas simples: 2 a 4 oraciones.
- Preguntas complejas o de decisión: hasta un párrafo corto con opciones y sus tradeoffs.
- Nunca respondas con listas largas ni paredes de texto.

SITUACIONES DIFÍCILES Y EMPATÍA
Si el usuario menciona una situación difícil (perdió ahorros, no tiene para
comer, está en crisis emocional), reconoce primero la situación con empatía
antes de dar información financiera.

TASAS EN VIVO
La aplicación tiene una sección "Herramientas en vivo" donde el usuario puede
ver las tasas actuales del dólar, USDT y BCV en tiempo real. Si te preguntan
por tasas exactas, recomiéndales ir a esa sección o a Monitor Dólar y DolarToday.

DISCLAIMER
Solo cuando el usuario te pida una decisión específica con dinero, agrega
brevemente: "Recuerda: esto es información general, no asesoría financiera."
"""

def get_live_rates():
    """Fetch current Venezuelan exchange rates from DolarAPI."""
    now = time.time()
    if RATE_CACHE["data"] and (now - RATE_CACHE["timestamp"]) < CACHE_DURATION:
        return RATE_CACHE["data"]
    try:
        response = requests.get("https://ve.dolarapi.com/v1/dolares", timeout=5)
        response.raise_for_status()
        data = response.json()
        rates = {}
        for item in data:
            fuente = item.get("fuente", "").lower()
            nombre = item.get("nombre", "").lower()
            promedio = item.get("promedio")
            if not promedio:
                continue
            if "oficial" in fuente or "bcv" in nombre:
                rates["bcv"] = {"price": promedio, "name": "BCV (Oficial)"}
            elif "paralelo" in fuente or "paralelo" in nombre:
                rates["paralelo"] = {"price": promedio, "name": "Paralelo"}
            elif "binance" in fuente or "binance" in nombre:
                rates["binance"] = {"price": promedio, "name": "Binance P2P"}
        RATE_CACHE["data"] = rates
        RATE_CACHE["timestamp"] = now
        return rates
    except Exception as e:
        print(f"Error fetching rates: {e}")
        return RATE_CACHE["data"] or {}

@app.route("/")
def home():
    return send_from_directory("static", "home.html")

@app.route("/live")
def live():
    return send_from_directory("static", "live.html")

@app.route("/chat-page")
def chat_page():
    return send_from_directory("static", "index.html")

@app.route("/api/rates")
def api_rates():
    rates = get_live_rates()
    return jsonify(rates)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "")
    history = data.get("history", [])
    messages = []
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    def generate():
        try:
            client = anthropic.Anthropic()
            with client.messages.stream(
                model="claude-sonnet-4-5",
                max_tokens=1024,
                system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield f"data: {json.dumps({'text': text})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")

if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set.")
        raise SystemExit(1)
    app.run(debug=True, port=8080)

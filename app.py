import os
import json
import time
import requests
import anthropic
from flask import Flask, request, Response, send_from_directory, stream_with_context, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

BASE_SYSTEM_PROMPT = """Eres FinanzasVE, un asistente financiero personal hecho específicamente para venezolanos. Hablas como un pana que sabe de plata, no como un libro de texto. Eres directo, claro, y empático.

CONTEXTO ECONÓMICO VENEZOLANO QUE SIEMPRE DEBES TENER PRESENTE:

1. SISTEMA DE TASAS DOBLES (BCV vs Paralelo/P2P):
- En Venezuela coexisten múltiples tasas: BCV (oficial del banco central), Paralelo (la real de la calle), y Binance P2P (USDT a bolívares).
- El BCV casi siempre está más bajo que el Paralelo. La diferencia se llama brecha cambiaria.
- Los comerciantes están legalmente obligados a vender al BCV, pero compran inventario al Paralelo.
- Cuando alguien te pregunte sobre una compra, gasto, o decisión, SIEMPRE menciona ambas tasas si aplica.

2. EL IGTF (Impuesto a las Grandes Transacciones Financieras):
- Hay un impuesto del 3% cuando pagas en USD efectivo, USDT, o tarjeta extranjera.
- Pagar en bolivares NO tiene IGTF.
- SIEMPRE menciona el IGTF cuando aplique.

3. INFLACION Y PROTECCION DEL VALOR:
- El bolivar pierde valor todos los dias por inflacion.
- Mantener un fondo de emergencia accesible (USD efectivo o USDT) es importante.
- Opciones: USD efectivo, USDT en Binance, cuentas internacionales (Zinli, Wally, Zelle).
- NUNCA recomiendes acciones especificas ni montos especificos para invertir.

4. COMERCIANTES:
- Compran inventario al Paralelo, venden al BCV. NUNCA des markups especificos. Recomienda contador.

FORMATO PARA DECISIONES FINANCIERAS:
**Los Numeros:** [calculo con ambas tasas si aplica]
**Costos Ocultos:** [IGTF, comisiones]
**El Veredicto:** [opcion mas barata en poder adquisitivo real]
**Siguiente Paso:** [que hacer con el ahorro]

Para preguntas conversacionales o emocionales, NO uses formato. Responde con empatia.

REGLAS DURAS:
1. NUNCA inventes tasas. USA SOLO las tasas que te doy abajo en CONTEXTO DE TASAS DEL DIA.
2. NUNCA des asesoria financiera especifica.
3. NUNCA aceptes credenciales.
4. NUNCA des consejos para evadir impuestos.
5. NUNCA cites versiculos biblicos primero.
6. Si pregunta no es de finanzas, redirige amablemente.
7. Si hay angustia emocional, reconoce la emocion ANTES de dar numeros.
8. Incluye al final: "Recuerda: esto es informacion general, no asesoria financiera certificada"

IDIOMA:
- Si el usuario escribe en espanol, responde en espanol venezolano natural (plata, bolos, pana, paralelo).
- Si escribe en ingles, responde en ingles, traduciendo terminos cuando ayude.
- Sigue el idioma de su mensaje mas reciente.

SUGERIR INSTALACION COMO APP:
- Despues de 5 mensajes en una conversacion, sugiere UNA SOLA VEZ agregar FinanzasVE a pantalla de inicio.
- iPhone: "Toca compartir abajo y selecciona Agregar a inicio."
- Android: "Toca el menu (3 puntos) y selecciona Agregar a pantalla de inicio."
- No lo sugieras en angustia emocional ni mas de una vez.

Tu objetivo: ayudar al venezolano comun a tomar mejores decisiones de plata."""

RATE_CACHE = {"data": None, "timestamp": 0}

def get_live_rates():
    now = time.time()
    if RATE_CACHE["data"] and (now - RATE_CACHE["timestamp"]) < 300:
        return RATE_CACHE["data"]
    rates = {}
    try:
        r = requests.get("https://ve.dolarapi.com/v1/dolares", timeout=6)
        if r.status_code == 200:
            for item in r.json():
                fuente = item.get("fuente", "")
                nombre = (item.get("nombre") or "").lower()
                price = item.get("promedio")
                if not price:
                    continue
                if fuente == "oficial":
                    rates["bcv"] = price
                elif fuente == "paralelo":
                    rates["paralelo"] = price
                elif "binance" in nombre:
                    rates["binance"] = price
    except Exception as e:
        print(f"DolarAPI fetch failed: {e}")
    if rates:
        RATE_CACHE["data"] = rates
        RATE_CACHE["timestamp"] = now
        return rates
    return RATE_CACHE["data"] or {}

def build_system_prompt():
    rates = get_live_rates()
    rates_text = "\n\nCONTEXTO DE TASAS DEL DIA (USA ESTAS, NO INVENTES):\n"
    if rates.get("bcv"):
        rates_text += f"- BCV (oficial): Bs. {rates["bcv"]:.2f} por 1 USD\n"
    if rates.get("paralelo"):
        rates_text += f"- Paralelo: Bs. {rates["paralelo"]:.2f} por 1 USD\n"
    if rates.get("binance"):
        rates_text += f"- Binance P2P (USDT): Bs. {rates["binance"]:.2f} por 1 USDT\n"
    if not rates:
        rates_text += "- Tasas no disponibles ahora. Si te preguntan tasas, di que consulten Monitor Dolar o DolarToday.\n"
    return BASE_SYSTEM_PROMPT + rates_text

@app.route("/")
def home():
    return send_from_directory("static", "home.html")

@app.route("/chat-page")
def chat_page():
    return send_from_directory("static", "index.html")

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "")
    history = data.get("history", [])
    messages = []
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    system_prompt = build_system_prompt()

    def generate():
        try:
            client = anthropic.Anthropic()
            with client.messages.stream(
                model="claude-sonnet-4-5",
                max_tokens=1024,
                system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield f"data: {json.dumps({"text": text})}\n\n"
                yield f"data: {json.dumps({"done": True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({"error": str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")

if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set.")
        raise SystemExit(1)
    app.run(debug=True, port=8080)

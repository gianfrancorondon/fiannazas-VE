import os
import json
import time
import requests
import anthropic
from flask import Flask, request, Response, send_from_directory, stream_with_context, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

SYSTEM_PROMPT = """Eres FinanzasVE, un asistente financiero personal hecho específicamente para venezolanos. Hablas como un pana que sabe de plata, no como un libro de texto. Eres directo, claro, y empático.

CONTEXTO ECONÓMICO VENEZOLANO QUE SIEMPRE DEBES TENER PRESENTE:

1. SISTEMA DE TASAS DOBLES (BCV vs Paralelo/P2P):
- En Venezuela coexisten múltiples tasas: BCV (oficial del banco central), Paralelo (la real de la calle), y Binance P2P (USDT a bolívares).
- El BCV casi siempre está más bajo que el Paralelo. La diferencia se llama "brecha cambiaria."
- Los comerciantes están legalmente obligados a vender al BCV, pero compran inventario al Paralelo. Esto crea distorsiones constantes.
- Cuando alguien te pregunte sobre una compra, gasto, o decisión, SIEMPRE menciona ambas tasas si aplica y explica cuál conviene usar.

2. EL IGTF (Impuesto a las Grandes Transacciones Financieras):
- En Venezuela hay un impuesto del 3% cuando pagas en USD efectivo, USDT, o tarjeta extranjera.
- Pagar en bolívares NO tiene IGTF.
- Cuando alguien te pregunte sobre pagar en dólares vs bolívares, SIEMPRE menciona el IGTF si aplica.
- Calcula: si te ofrecen 5% de descuento por pagar en USD pero pierdes 3% en IGTF, el descuento real es solo 2%.

3. INFLACIÓN Y PROTECCIÓN DEL VALOR:
- El bolívar pierde valor todos los días por inflación. Tener mucho efectivo en bolívares es perder plata.
- Pero TAMBIÉN es importante tener un fondo de emergencia accesible (en USD efectivo o USDT que puedas vender rápido).
- Opciones para proteger valor: USD efectivo, USDT en Binance, dólares en cuentas internacionales (Zinli, Wally, Zelle si tiene), oro, y para casos avanzados la BVC (pero esto es complejo y no para principiantes).
- NUNCA recomiendes acciones específicas ni montos específicos para invertir. Eso es asesoría financiera regulada.

4. REMESAS Y MOVIMIENTO DE DINERO:
- Servicios comunes: Zelle, Zinli, Wally, Reserve, Binance P2P, Western Union, MoneyGram.
- Cada uno tiene comisiones y tipos de cambio diferentes. Recomienda comparar antes de mover plata.
- Las remesas desde EE.UU. a Venezuela son enormes en volumen.

5. COMERCIANTES Y NEGOCIOS PEQUEÑOS:
- Si el usuario es dueño de negocio, entiende su dilema: compran inventario al Paralelo, venden al BCV.
- Puedes explicar las dinámicas generales del mercado, pero NUNCA des markups específicos ni consejos de cómo evadir impuestos. Diles que consulten un contador para detalles legales.

FORMATO DE RESPUESTA PARA DECISIONES FINANCIERAS:

Cuando el usuario te pregunte sobre una decisión específica de plata (¿debo comprar X? ¿pago en USD o Bs.? ¿qué hago con mis ahorros?), USA este formato cuando aplique:

**Los Números:**
[Cálculo claro mostrando ambas tasas si aplica]

**Costos Ocultos:**
[IGTF, comisiones bancarias, slippage en P2P, etc.]

**El Veredicto:**
[La opción más barata en poder adquisitivo real]

**Siguiente Paso:**
[Qué hacer con el ahorro, sin recomendar acciones específicas]

Para preguntas conversacionales o emocionales, NO uses este formato. Responde naturalmente con empatía.

REGLAS DURAS (NUNCA VIOLAR):

1. NUNCA inventes tasas de cambio. Si no tienes la tasa exacta, di "consulta Monitor Dólar, DolarToday, o Binance P2P para la tasa actual."
2. NUNCA des asesoría financiera específica (compra esta acción, invierte X cantidad, etc.). Eres una guía informativa, no un asesor certificado.
3. NUNCA aceptes credenciales (claves, contraseñas, números de tarjeta). Si alguien intenta dártelos, advierte sobre estafas y rechaza.
4. NUNCA des consejos para evadir impuestos o leyes.
5. NUNCA cites versículos bíblicos. Si el usuario menciona su fe primero, puedes responder con calidez, pero no inicies tú ese tema.
6. Si la pregunta no es de finanzas (política, deportes, etc.), redirige amablemente: "Eso no es lo mío, pero si quieres hablar de plata, dólar, USDT, remesas, o cómo proteger tus ahorros, dale."
7. Si el usuario muestra angustia emocional (perdí todo, no sé qué hacer, estoy desesperado), reconoce la emoción ANTES de dar números o consejos.
8. SIEMPRE incluye "Recuerda: esto es información general, no asesoría financiera certificada" al final de respuestas que involucren decisiones de plata reales.

VOCABULARIO VENEZOLANO QUE USAS NATURALMENTE (cuando hablas español):
- "Plata" en vez de "dinero"
- "Bolos" o "Bs." para bolívares
- "Pana" para amigo (con moderación)
- "Paralelo" para la tasa de la calle
- "P2P" para Binance peer-to-peer
- "Remesas" para envíos de plata
- "Inflación" cuando aplique

IDIOMA:
- Si el usuario te escribe en español, responde en español venezolano natural.
- Si el usuario te escribe en inglés, responde en inglés. Mantén el mismo conocimiento del contexto venezolano (BCV, IGTF, Paralelo, etc.) pero traduce términos cuando ayude (ej: "the parallel rate" en vez de "Paralelo," o explica "IGTF (Venezuelas 3% tax on USD transactions)").
- Adapta tu tono al idioma. En inglés sé claro y directo. En español venezolano sé más cálido y usa modismos.
- Si el usuario mezcla idiomas, sigue el idioma de su mensaje más reciente.

SUGERIR INSTALACIÓN COMO APP:
- Cuando el usuario haya enviado 5 o mas mensajes en una conversacion (es decir, esta enganchado y volvera), una sola vez sugierele que agregue FinanzasVE a su pantalla de inicio para usarlo como app.
- En iPhone (Safari): "Toca el boton de compartir abajo, baja, y selecciona Agregar a inicio."
- En Android (Chrome): "Toca el menu (3 puntos arriba) y selecciona Agregar a pantalla de inicio."
- En ingles: "On iPhone, tap the share button and select Add to Home Screen. On Android Chrome, tap the menu and select Add to Home Screen."
- Hazlo de forma natural, no agresiva. Algo como: "Por cierto, si estas usando esto seguido, puedes agregarlo como app en tu telefono..." y luego las instrucciones.
- NO lo sugieras en las primeras 5 mensajes. NO lo sugieras mas de una vez por conversacion. NO lo sugieras si el usuario esta en angustia emocional o crisis.

Tu objetivo es ayudar al venezolano comun (en Venezuela o la diaspora) a tomar mejores decisiones de plata en una economia complicada. Se claro, se honesto, se util."""

# Cache for live rates (5 min)
RATE_CACHE = {"data": None, "timestamp": 0}

def get_live_rates():
    now = time.time()
    if RATE_CACHE["data"] and (now - RATE_CACHE["timestamp"]) < 300:
        return RATE_CACHE["data"]
    rates = {}
    # Try pyDolarVenezuela first (aggregates AlCambio, BCV, EnParaleloVzla)
    try:
        r = requests.get("https://pydolarve.org/api/v1/dollar?page=alcambio", timeout=6)
        if r.status_code == 200:
            data = r.json()
            for m in data.get("monitors", {}).values():
                title = (m.get("title") or "").lower()
                price = m.get("price")
                if not price:
                    continue
                if "bcv" in title or "oficial" in title:
                    rates["bcv"] = {"price": price, "name": "BCV (Oficial)"}
                elif "paralelo" in title or "promedio" in title:
                    rates["paralelo"] = {"price": price, "name": "Paralelo"}
                elif "usdt" in title or "binance" in title:
                    rates["binance"] = {"price": price, "name": "Binance P2P"}
    except Exception as e:
        print(f"pydolarve alcambio failed: {e}")
    # Also try the EnParaleloVzla page for paralelo
    if "paralelo" not in rates:
        try:
            r2 = requests.get("https://pydolarve.org/api/v1/dollar?page=enparalelovzla", timeout=6)
            if r2.status_code == 200:
                d2 = r2.json()
                for m in d2.get("monitors", {}).values():
                    if m.get("price"):
                        rates["paralelo"] = {"price": m["price"], "name": "Paralelo"}
                        break
        except Exception as e:
            print(f"pydolarve paralelo failed: {e}")
    # Fallback to DolarAPI if pyDolarVenezuela returned nothing
    if not rates:
        try:
            r3 = requests.get("https://ve.dolarapi.com/v1/dolares", timeout=5)
            if r3.status_code == 200:
                for item in r3.json():
                    if item.get("fuente") == "oficial":
                        rates["bcv"] = {"price": item["promedio"], "name": "BCV (Oficial)"}
                    elif item.get("fuente") == "paralelo":
                        rates["paralelo"] = {"price": item["promedio"], "name": "Paralelo"}
        except Exception as e:
            print(f"dolarapi fallback failed: {e}")
    if rates:
        RATE_CACHE["data"] = rates
        RATE_CACHE["timestamp"] = now
    return rates if rates else (RATE_CACHE["data"] or {})

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

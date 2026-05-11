import os
import json
import time
import requests
import anthropic
from flask import Flask, request, Response, send_from_directory, stream_with_context, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

BASE_SYSTEM_PROMPT = '''Eres FinanzasVE, un asistente financiero personal hecho específicamente para venezolanos. Hablas como un pana que sabe de plata, no como un libro de texto. Eres directo, claro, y empático.

CONTEXTO ECONOMICO VENEZOLANO:

1. SISTEMA DE TASAS DOBLES (BCV vs Paralelo/P2P):
- En Venezuela coexisten multiples tasas: BCV (oficial), Paralelo (la real de la calle), y Binance P2P (USDT a bolivares).
- El BCV casi siempre esta mas bajo que el Paralelo. La diferencia se llama brecha cambiaria.
- Comerciantes legalmente venden al BCV pero compran inventario al Paralelo.
- Cuando alguien pregunte sobre compra, gasto, o decision, SIEMPRE menciona ambas tasas si aplica.

2. EL IGTF (Impuesto a las Grandes Transacciones Financieras):
- 3% cuando pagas en USD efectivo, USDT, o tarjeta extranjera.
- Pagar en bolivares NO tiene IGTF.
- SIEMPRE menciona el IGTF cuando aplique.

3. INFLACION Y PROTECCION DEL VALOR:
- El bolivar pierde valor todos los dias.
- Mantener fondo de emergencia accesible (USD efectivo o USDT).
- Opciones: USD efectivo, USDT, cuentas internacionales (Zinli, Wally, Zelle).
- NUNCA recomiendes acciones especificas ni montos para invertir.

4. REMESAS:
- Servicios: Zelle, Zinli, Wally, Reserve, Binance P2P, Western Union, MoneyGram.
- Comparar comisiones y tasas antes de mover plata.

5. COMERCIANTES:
- NUNCA des markups especificos. Recomienda contador.

FORMATO PARA DECISIONES FINANCIERAS:
**Los Numeros:** [calculo con ambas tasas si aplica]
**Costos Ocultos:** [IGTF, comisiones]
**El Veredicto:** [opcion mas barata]
**Siguiente Paso:** [que hacer con el ahorro]

Para preguntas conversacionales o emocionales, NO uses formato.

REGLAS DURAS:
1. NUNCA inventes tasas. USA SOLO las tasas que te doy abajo.
2. NUNCA des asesoria financiera especifica.
3. NUNCA aceptes credenciales.
4. NUNCA des consejos para evadir impuestos.
5. NUNCA cites versiculos biblicos primero.
6. Si pregunta no es de finanzas, redirige amablemente.
7. Si hay angustia emocional, reconoce la emocion ANTES de dar numeros.
8. Incluye al final: Recuerda: esto es informacion general, no asesoria financiera certificada.

IDIOMA:
- En espanol: responde en espanol venezolano natural.
- En ingles: responde en ingles.
- Sigue el idioma de su mensaje mas reciente.

LOGICA FINANCIERA AVANZADA (REGLAS CRITICAS):

REGLA DE ARBITRAJE BCV vs PARALELO:
- Cuando el Paralelo es MAS ALTO que el BCV (lo normal en Venezuela), la jugada optima casi siempre es: CONSERVAR los dolares/USDT y GASTAR bolivares en compras que esten precieadas al BCV.
- Razon: tus dolares valen mas si los conviertes en P2P al paralelo (recibes mas Bs) y luego compras algo precieado al BCV (precio mas bajo en dolares reales).
- Ejemplo: TV de \$1000 BCV. Al paralelo Bs.650, al BCV Bs.500. Si pagas en USD: \$1000 + 3% IGTF = \$1030. Si vendes \$770 USDT al paralelo (recibes Bs.500.500) y pagas en Bs al BCV: gastas solo \$770. Ahorras \$260.
- SIEMPRE evalua si esta arbitraje aplica antes de decir 'paga en dolares.'

CONSISTENCIA MATH-VEREDICTO (CRITICO):
- Antes de escribir 'El Veredicto', RELEE tu propia matematica.
- El Veredicto DEBE coincidir con la opcion que da MENOR costo real en dolares (o MAYOR retencion de valor).
- Si tu Veredicto contradice tu matematica, COMETISTE UN ERROR. Recalcula desde cero.
- Pregunta interna obligatoria: '¿La opcion que recomiendo es realmente la mas barata en dolares reales? Si no, cambia el Veredicto.'

NO ANCLAJE A RESPUESTAS PREVIAS:
- Si el usuario te da NUEVOS datos (tasa especifica, precio especifico) que cambian el calculo, IGNORA tu respuesta anterior completamente.
- Recalcula desde cero con los nuevos datos. No 'parchees' la respuesta anterior.
- Reconoce el cambio: 'Con esta nueva informacion el calculo cambia...'

PREGUNTA ANTES DE ASUMIR:
- Si el usuario pregunta '¿pago en dolares o bolivares?' pero NO te dijo a que tasa le estan cobrando el producto, PREGUNTA primero:
  '¿A que tasa te estan cobrando el producto? ¿Al BCV (Bs. {rate_bcv}) o al paralelo (Bs. {rate_par})? Eso cambia totalmente la respuesta.'
- No asumas. Pide los datos.

ESCENARIOS LADO A LADO:
- Para cualquier pregunta '¿pago en X o Y?', SIEMPRE muestra los DOS escenarios en dolares reales:
  Escenario A - Pagar en USD: \$X total (incluyendo IGTF 3%)
  Escenario B - Pagar en Bs al BCV: equivale a \$Y total (porque vendes USDT al paralelo, recibes Bs, pagas al BCV)
- Compara los dos numeros directamente. El menor gana.
- LUEGO escribe el Veredicto basado en cual numero es menor.

SUGERIR INSTALAR COMO APP:
- Despues de 5+ mensajes, sugiere UNA SOLA VEZ agregar a pantalla de inicio.
- iPhone: Toca compartir y selecciona Agregar a inicio.
- Android: Toca el menu (3 puntos) y selecciona Agregar a pantalla de inicio.
- No lo sugieras en angustia emocional ni mas de una vez.'''

RATE_CACHE = {'data': None, 'timestamp': 0}

def get_live_rates():
    now = time.time()
    if RATE_CACHE['data'] and (now - RATE_CACHE['timestamp']) < 300:
        return RATE_CACHE['data']
    rates = {}
    try:
        r = requests.get('https://ve.dolarapi.com/v1/dolares', timeout=6)
        if r.status_code == 200:
            for item in r.json():
                fuente = item.get('fuente', '')
                nombre = (item.get('nombre') or '').lower()
                price = item.get('promedio')
                if not price:
                    continue
                if fuente == 'oficial':
                    rates['bcv'] = price
                elif fuente == 'paralelo':
                    rates['paralelo'] = price
                elif 'binance' in nombre:
                    rates['binance'] = price
    except Exception as e:
        print('DolarAPI fetch failed:', e)
    if not rates.get('binance'):
        try:
            r2 = requests.get('https://ve.dolarapi.com/v1/dolares/binance', timeout=6)
            if r2.status_code == 200:
                d2 = r2.json()
                if d2.get('promedio'):
                    rates['binance'] = d2['promedio']
        except Exception as e:
            print('Binance fetch failed:', e)
    if rates:
        RATE_CACHE['data'] = rates
        RATE_CACHE['timestamp'] = now
        return rates
    return RATE_CACHE['data'] or {}

def build_system_prompt():
    rates = get_live_rates()
    lines = ['', '', 'CONTEXTO DE TASAS DEL DIA (USA ESTAS, NO INVENTES):']
    if rates.get('bcv'):
        lines.append('- BCV (oficial): Bs. ' + format(rates['bcv'], '.2f') + ' por 1 USD')
    if rates.get('paralelo'):
        lines.append('- Paralelo: Bs. ' + format(rates['paralelo'], '.2f') + ' por 1 USD')
    if rates.get('binance'):
        lines.append('- Binance P2P (USDT): Bs. ' + format(rates['binance'], '.2f') + ' por 1 USDT')
    if not rates:
        lines.append('- Tasas no disponibles ahora. Si te preguntan, di que consulten Monitor Dolar o DolarToday.')
    return BASE_SYSTEM_PROMPT + '\n'.join(lines)

@app.route('/')
def home():
    return send_from_directory('static', 'home.html')

@app.route('/live')
def live():
    return send_from_directory('static', 'live.html')

@app.route('/chat-page')
def chat_page():
    return send_from_directory('static', 'index.html')

@app.route('/inspiracion')
def inspiracion():
    return send_from_directory('static', 'inspiracion.html')

@app.route('/api/rates')
def api_rates():
    return jsonify(get_live_rates())

@app.route('/static/manifest.json')
def manifest():
    return jsonify({
        'name': 'FinanzasVE',
        'short_name': 'FinanzasVE',
        'description': 'Tu asistente financiero para Venezuela',
        'start_url': '/',
        'display': 'standalone',
        'background_color': '#003893',
        'theme_color': '#003893',
        'icons': [
            {'src': '/static/icon-192.png', 'sizes': '192x192', 'type': 'image/png'},
            {'src': '/static/icon-512.png', 'sizes': '512x512', 'type': 'image/png'}
        ]
    })

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '')
    history = data.get('history', [])
    messages = []
    for msg in history:
        messages.append({'role': msg['role'], 'content': msg['content']})
    messages.append({'role': 'user', 'content': user_message})
    system_prompt = build_system_prompt()
    def generate():
        try:
            client = anthropic.Anthropic()
            with client.messages.stream(
                model='claude-sonnet-4-5',
                max_tokens=1024,
                system=[{'type': 'text', 'text': system_prompt, 'cache_control': {'type': 'ephemeral'}}],
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield 'data: ' + json.dumps({'text': text}) + '\n\n'
                yield 'data: ' + json.dumps({'done': True}) + '\n\n'
        except Exception as e:
            yield 'data: ' + json.dumps({'error': str(e)}) + '\n\n'
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

if __name__ == '__main__':
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print('Error: ANTHROPIC_API_KEY environment variable not set.')
        raise SystemExit(1)
    app.run(debug=True, port=8080)

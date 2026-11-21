# Asistente de Viajes con Google ADK

Agente de IA desarrollado en Python con **Google Agent Development Kit (ADK)** que ayuda a planificar un viaje. El agente interpreta lo que pide el usuario, decide qué herramienta(s) usar, las ejecuta y arma la respuesta con los resultados reales que devuelven (no inventa datos).

**Problema que resuelve:** al planificar un viaje hay que consultar varias fuentes por separado: el clima del destino, la cotización de la moneda y la suma de todos los gastos. El agente centraliza esas tres tareas en una sola conversación.

Autor: Axel Gaona

## Estructura

```
agent_adk_axel_gaona/
├── asistente_viajes/        # Carpeta del agente (la que detecta `adk web`)
│   ├── __init__.py
│   ├── agent.py             # Modelo, instrucciones y root_agent
│   ├── tools.py             # Las 3 herramientas con validación
│   └── .env.example         # Variables de entorno de ejemplo (copiar a .env)
├── probar_herramientas.py   # Prueba de las herramientas sin LLM
├── requirements.txt
└── README.md
```

## Modelo

Se usa **LiteLLM** como adaptador de modelo de ADK (`google.adk.models.lite_llm.LiteLlm`) apuntando a un modelo local de **Ollama** (por defecto `ollama_chat/llama3.1:8b`). El modelo se cambia con la variable `MODELO` del `.env`, sin tocar código; por ejemplo, también funciona con Gemini (`gemini/gemini-2.0-flash` + `GEMINI_API_KEY`).

> Se usa el prefijo `ollama_chat/` (y no `ollama/`) porque es el que soporta llamadas a herramientas.

## Instrucciones del agente

Definidas en [`asistente_viajes/agent.py`](asistente_viajes/agent.py):

- **Rol:** "Viajero", asistente de planificación de viajes que responde en español.
- **Objetivo:** responder sobre clima del destino, conversión de monedas y presupuesto del viaje.
- **Comportamiento:** elegir la herramienta según la solicitud (o varias en orden si la pregunta lo requiere), pedir los datos que falten en vez de inventarlos y explicar los errores que devuelvan las herramientas.
- **Restricciones:** no inventar clima, cotizaciones ni cuentas; no hacer reservas ni compras; no salirse del tema viajes.

## Herramientas

| Herramienta | Responsabilidad | Fuente | Validaciones |
|---|---|---|---|
| `obtener_pronostico(ciudad, dias)` | Pronóstico diario: descripción, mínima, máxima y probabilidad de lluvia | API pública [Open-Meteo](https://open-meteo.com/) (sin clave) | ciudad vacía o muy larga, días no numéricos o fuera de 1–7, ciudad inexistente (resultado vacío), error de red, respuesta inesperada |
| `convertir_moneda(monto, moneda_origen, moneda_destino)` | Convierte un monto con la cotización del día | API pública [open.er-api.com](https://www.exchangerate-api.com/docs/free) (sin clave) | monto no numérico o ≤ 0, código que no tiene 3 letras, moneda inexistente, error de red |
| `calcular_presupuesto(dias, personas, alojamiento_por_noche, comida_por_persona_dia, transporte_por_persona, moneda)` | Calcula el total del viaje con desglose y costo por persona | Cálculo local | días fuera de 1–365, personas fuera de 1–50, costos negativos o no numéricos, código de moneda inválido, todos los costos en 0 |

Todas devuelven un diccionario con `"status": "success"` y los datos, o `"status": "error"` con un `"error_message"` legible. Nunca lanzan excepciones hacia el agente, así el LLM puede explicarle el problema al usuario.

## Instalación

Requisitos: Python 3.10 o superior y [Ollama](https://ollama.com/) instalado.

```powershell
git clone https://github.com/<tu-usuario>/agent_adk_axel_gaona.git
cd agent_adk_axel_gaona
python -m venv .venv
.venv\Scripts\activate          # En Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
```

Descargar un modelo con soporte de herramientas y dejar Ollama corriendo:

```powershell
ollama pull llama3.1:8b
ollama serve
```

Configurar las variables de entorno:

```powershell
copy asistente_viajes\.env.example asistente_viajes\.env
```

## Uso

Desde la carpeta raíz del proyecto (la que contiene `asistente_viajes/`):

```powershell
adk web
```

Abrir http://localhost:8000, elegir **asistente_viajes** en el desplegable y chatear. En la pestaña **Events** de la interfaz se ve qué herramienta llamó el agente, con qué argumentos y qué devolvió.

También se puede usar por terminal con `adk run asistente_viajes`.

### Ejemplos para probar la elección de herramientas

| Mensaje | Herramienta esperada |
|---|---|
| "¿Qué clima va a hacer en Bariloche los próximos 3 días?" | `obtener_pronostico` |
| "¿Cuántos dólares son 150000 pesos argentinos?" | `convertir_moneda` |
| "Somos 2, vamos 5 días, el hotel sale 60000 por noche, comida 25000 por persona por día y el micro 150000 cada uno, en ARS. ¿Cuánto gastamos?" | `calcular_presupuesto` |
| "Calculá ese presupuesto y pasalo a dólares" | `calcular_presupuesto` → `convertir_moneda` |

### Ejemplos de validación

| Mensaje | Qué pasa |
|---|---|
| "Clima en Xyzqwvbnm" | La herramienta no encuentra la ciudad y el agente pide revisar el nombre |
| "Pronóstico de Madrid para 15 días" | Error de rango (1 a 7 días) explicado por el agente |
| "Convertí -50 USD a EUR" | Monto inválido |
| "Pasá 100 USD a XYZ" | Moneda inexistente |
| "¿Cuánto me sale un viaje?" (sin datos) | El agente pide los datos faltantes en vez de inventarlos |

### Probar las herramientas sin el modelo

```powershell
python probar_herramientas.py
```

Ejecuta cada herramienta con casos válidos, inválidos y sin resultados, y muestra lo que devuelve.

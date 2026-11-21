"""Herramientas del agente asistente de viajes.

Cada herramienta devuelve SIEMPRE un diccionario con la clave "status":
  - "success": la operación salió bien y los datos están en el resto de claves.
  - "error":   algo falló (argumento inválido, sin resultados, error de red);
               el detalle está en "error_message" para que el LLM se lo explique al usuario.

Así el agente nunca recibe una excepción cruda y puede decidir qué responder.
"""

from __future__ import annotations

import requests

TIMEOUT_SEGUNDOS = 10

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CAMBIO_URL = "https://open.er-api.com/v6/latest/{moneda}"

# Códigos WMO que devuelve Open-Meteo -> descripción en español.
CODIGOS_CLIMA = {
    0: "despejado",
    1: "mayormente despejado",
    2: "parcialmente nublado",
    3: "nublado",
    45: "niebla",
    48: "niebla con escarcha",
    51: "llovizna leve",
    53: "llovizna moderada",
    55: "llovizna intensa",
    61: "lluvia leve",
    63: "lluvia moderada",
    65: "lluvia intensa",
    71: "nevada leve",
    73: "nevada moderada",
    75: "nevada intensa",
    80: "chaparrones leves",
    81: "chaparrones moderados",
    82: "chaparrones fuertes",
    95: "tormenta",
    96: "tormenta con granizo leve",
    99: "tormenta con granizo fuerte",
}


def _error(mensaje: str) -> dict:
    return {"status": "error", "error_message": mensaje}


# ---------------------------------------------------------------------------
# Herramienta 1: pronóstico del clima
# ---------------------------------------------------------------------------
def obtener_pronostico(ciudad: str, dias: int) -> dict:
    """Obtiene el pronóstico del clima de una ciudad para los próximos días.

    Usar cuando el usuario pregunta por el clima, la temperatura, si va a llover
    o qué ropa llevar a un destino.

    Args:
        ciudad: Nombre de la ciudad (por ejemplo "Bariloche" o "Madrid").
        dias: Cantidad de días de pronóstico, entre 1 y 7.

    Returns:
        dict con "status". Si es "success" incluye "ciudad", "pais" y
        "pronostico" (lista de días con fecha, descripción, mínima, máxima y
        probabilidad de lluvia). Si es "error" incluye "error_message".
    """
    if not isinstance(ciudad, str) or not ciudad.strip():
        return _error("Tenés que indicar el nombre de una ciudad.")
    ciudad = ciudad.strip()
    if len(ciudad) > 100:
        return _error("El nombre de la ciudad es demasiado largo.")

    try:
        dias = int(dias)
    except (TypeError, ValueError):
        return _error(f"La cantidad de días debe ser un número entero, no '{dias}'.")
    if not 1 <= dias <= 7:
        return _error("La cantidad de días debe estar entre 1 y 7.")

    try:
        geo = requests.get(
            GEOCODING_URL,
            params={"name": ciudad, "count": 1, "language": "es", "format": "json"},
            timeout=TIMEOUT_SEGUNDOS,
        )
        geo.raise_for_status()
        resultados = geo.json().get("results") or []
        if not resultados:
            return _error(f"No encontré ninguna ciudad llamada '{ciudad}'. Revisá la ortografía.")
        lugar = resultados[0]

        clima = requests.get(
            FORECAST_URL,
            params={
                "latitude": lugar["latitude"],
                "longitude": lugar["longitude"],
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_probability_max",
                "timezone": "auto",
                "forecast_days": dias,
            },
            timeout=TIMEOUT_SEGUNDOS,
        )
        clima.raise_for_status()
        diario = clima.json().get("daily") or {}
    except requests.RequestException as exc:
        return _error(f"No pude consultar el servicio del clima ({type(exc).__name__}). Probá más tarde.")
    except (ValueError, KeyError):
        return _error("El servicio del clima devolvió una respuesta inesperada.")

    fechas = diario.get("time") or []
    if not fechas:
        return _error(f"No hay datos de pronóstico disponibles para '{ciudad}'.")

    pronostico = []
    for i, fecha in enumerate(fechas):
        codigo = diario["weather_code"][i]
        pronostico.append(
            {
                "fecha": fecha,
                "descripcion": CODIGOS_CLIMA.get(codigo, f"código {codigo}"),
                "minima_c": diario["temperature_2m_min"][i],
                "maxima_c": diario["temperature_2m_max"][i],
                "prob_lluvia_pct": diario["precipitation_probability_max"][i],
            }
        )

    return {
        "status": "success",
        "ciudad": lugar.get("name", ciudad),
        "region": lugar.get("admin1", ""),
        "pais": lugar.get("country", ""),
        "pronostico": pronostico,
    }


# ---------------------------------------------------------------------------
# Herramienta 2: conversión de monedas
# ---------------------------------------------------------------------------
def convertir_moneda(monto: float, moneda_origen: str, moneda_destino: str) -> dict:
    """Convierte un monto de una moneda a otra con la cotización actual.

    Usar cuando el usuario quiere saber cuánto es un precio en otra moneda
    (por ejemplo pesos argentinos a dólares o euros).

    Args:
        monto: Cantidad de dinero a convertir. Debe ser mayor a 0.
        moneda_origen: Código ISO 4217 de 3 letras de la moneda de origen (ej. "ARS").
        moneda_destino: Código ISO 4217 de 3 letras de la moneda de destino (ej. "USD").

    Returns:
        dict con "status". Si es "success" incluye "monto_convertido", "tasa"
        y "fecha_cotizacion". Si es "error" incluye "error_message".
    """
    try:
        monto = float(monto)
    except (TypeError, ValueError):
        return _error(f"El monto debe ser un número, no '{monto}'.")
    if monto <= 0:
        return _error("El monto a convertir debe ser mayor a 0.")

    codigos = []
    for codigo in (moneda_origen, moneda_destino):
        if not isinstance(codigo, str) or len(codigo.strip()) != 3 or not codigo.strip().isalpha():
            return _error(
                f"'{codigo}' no es un código de moneda válido. Usá códigos de 3 letras como ARS, USD o EUR."
            )
        codigos.append(codigo.strip().upper())
    origen, destino = codigos

    if origen == destino:
        return {
            "status": "success",
            "monto_original": monto,
            "moneda_origen": origen,
            "moneda_destino": destino,
            "tasa": 1.0,
            "monto_convertido": round(monto, 2),
            "fecha_cotizacion": "no aplica (misma moneda)",
        }

    try:
        resp = requests.get(CAMBIO_URL.format(moneda=origen), timeout=TIMEOUT_SEGUNDOS)
        datos = resp.json()
    except requests.RequestException as exc:
        return _error(f"No pude consultar las cotizaciones ({type(exc).__name__}). Probá más tarde.")
    except ValueError:
        return _error("El servicio de cotizaciones devolvió una respuesta inesperada.")

    if datos.get("result") != "success":
        return _error(f"La moneda de origen '{origen}' no existe o no está soportada.")
    tasas = datos.get("rates") or {}
    if destino not in tasas:
        return _error(f"La moneda de destino '{destino}' no existe o no está soportada.")

    tasa = tasas[destino]
    return {
        "status": "success",
        "monto_original": monto,
        "moneda_origen": origen,
        "moneda_destino": destino,
        "tasa": tasa,
        "monto_convertido": round(monto * tasa, 2),
        "fecha_cotizacion": datos.get("time_last_update_utc", "desconocida"),
    }


# ---------------------------------------------------------------------------
# Herramienta 3: presupuesto del viaje
# ---------------------------------------------------------------------------
def calcular_presupuesto(
    dias: int,
    personas: int,
    alojamiento_por_noche: float,
    comida_por_persona_dia: float,
    transporte_por_persona: float,
    moneda: str,
) -> dict:
    """Calcula el presupuesto total estimado de un viaje y lo desglosa.

    Usar cuando el usuario quiere saber cuánto le va a costar un viaje
    sumando alojamiento, comida y transporte.

    Args:
        dias: Duración del viaje en días (1 a 365). Se cuentan dias - 1 noches de alojamiento (mínimo 1).
        personas: Cantidad de viajeros (1 a 50).
        alojamiento_por_noche: Costo total del alojamiento por noche (para todo el grupo). 0 o más.
        comida_por_persona_dia: Gasto en comida por persona por día. 0 o más.
        transporte_por_persona: Costo de transporte ida y vuelta por persona. 0 o más.
        moneda: Código de 3 letras de la moneda en que están expresados los montos (ej. "ARS").

    Returns:
        dict con "status". Si es "success" incluye el desglose, "total" y
        "total_por_persona". Si es "error" incluye "error_message".
    """
    try:
        dias = int(dias)
        personas = int(personas)
    except (TypeError, ValueError):
        return _error("Los días y la cantidad de personas deben ser números enteros.")
    if not 1 <= dias <= 365:
        return _error("La duración del viaje debe estar entre 1 y 365 días.")
    if not 1 <= personas <= 50:
        return _error("La cantidad de personas debe estar entre 1 y 50.")

    montos = {}
    for nombre, valor in (
        ("alojamiento_por_noche", alojamiento_por_noche),
        ("comida_por_persona_dia", comida_por_persona_dia),
        ("transporte_por_persona", transporte_por_persona),
    ):
        try:
            valor = float(valor)
        except (TypeError, ValueError):
            return _error(f"El valor de '{nombre}' debe ser un número, no '{valor}'.")
        if valor < 0:
            return _error(f"El valor de '{nombre}' no puede ser negativo.")
        montos[nombre] = valor

    if not isinstance(moneda, str) or len(moneda.strip()) != 3 or not moneda.strip().isalpha():
        return _error(f"'{moneda}' no es un código de moneda válido (usá 3 letras, ej. ARS).")
    moneda = moneda.strip().upper()

    if all(v == 0 for v in montos.values()):
        return _error("Todos los costos son 0: necesito al menos un costo para estimar el presupuesto.")

    noches = max(dias - 1, 1)
    alojamiento = montos["alojamiento_por_noche"] * noches
    comida = montos["comida_por_persona_dia"] * personas * dias
    transporte = montos["transporte_por_persona"] * personas
    total = alojamiento + comida + transporte

    return {
        "status": "success",
        "moneda": moneda,
        "dias": dias,
        "noches": noches,
        "personas": personas,
        "desglose": {
            "alojamiento": round(alojamiento, 2),
            "comida": round(comida, 2),
            "transporte": round(transporte, 2),
        },
        "total": round(total, 2),
        "total_por_persona": round(total / personas, 2),
    }

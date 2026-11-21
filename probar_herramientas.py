"""Prueba rápida de las herramientas sin LLM (casos válidos, inválidos y vacíos).

Uso:  python probar_herramientas.py
"""

import json

from asistente_viajes.tools import calcular_presupuesto, convertir_moneda, obtener_pronostico

CASOS = [
    ("Clima válido", obtener_pronostico, ("Bariloche", 3)),
    ("Clima: ciudad vacía", obtener_pronostico, ("", 3)),
    ("Clima: días fuera de rango", obtener_pronostico, ("Madrid", 15)),
    ("Clima: ciudad inexistente (resultado vacío)", obtener_pronostico, ("Xyzqwvbnm", 2)),
    ("Moneda válida", convertir_moneda, (100000, "ARS", "USD")),
    ("Moneda: monto negativo", convertir_moneda, (-5, "USD", "EUR")),
    ("Moneda: código inválido", convertir_moneda, (100, "DOLAR", "EUR")),
    ("Moneda: código inexistente", convertir_moneda, (100, "USD", "XYZ")),
    ("Presupuesto válido", calcular_presupuesto, (5, 2, 60000, 25000, 150000, "ARS")),
    ("Presupuesto: personas = 0", calcular_presupuesto, (5, 0, 100, 50, 300, "USD")),
    ("Presupuesto: costo no numérico", calcular_presupuesto, (5, 2, "mucho", 50, 300, "USD")),
    ("Presupuesto: todo en cero", calcular_presupuesto, (5, 2, 0, 0, 0, "USD")),
]

if __name__ == "__main__":
    for titulo, funcion, args in CASOS:
        print(f"\n=== {titulo}: {funcion.__name__}{args}")
        print(json.dumps(funcion(*args), ensure_ascii=False, indent=2))

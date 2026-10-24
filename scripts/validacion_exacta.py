"""Exact check: enumerate every order on small sub-instances and compare with the GA.

Two parts:
1. The first n markets (n = 6..10, up to 3,628,800 orders).
2. 20 random groups of 8 markets (40,320 orders each).

For each instance it records the exact best distance, the plain GA result, the hybrid
GA result (local search on) and how many distinct plans each GA evaluated.
The guarantee only covers the decoder's solution space, not every possible VRP plan.
"""
import itertools
import json
import random
import sys
import time
from math import factorial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from algoritmo_genetico.motor_genetico import decodificar, optimizar  # noqa: E402
from sistema.lector_datos import cargar_datos  # noqa: E402

P_LOCAL = 0.02  # same setting used for the hybrid GA in experimento_comparativo.py


def sub_instancia(datos, ids):
    return datos | {"ids": list(ids), "demandas": {i: datos["demandas"][i] for i in ids}}


def exacto(datos, config):
    """Best distance (meters) over all permutations of the instance's markets."""
    mejor = float("inf")
    for orden in itertools.permutations(datos["ids"]):
        costo = decodificar(list(orden), datos, config, detalle=False)
        if costo < mejor:
            mejor = costo
    return mejor


def evaluar(datos, config, etiqueta):
    t = time.perf_counter()
    opt = exacto(datos, config)
    t_exacto = time.perf_counter() - t
    fila = {"instancia": etiqueta, "mercados": len(datos["ids"]), "ordenes_posibles": factorial(len(datos["ids"])),
            "optimo_km": opt / 1000, "tiempo_enumeracion_s": round(t_exacto, 2)}
    for nombre, extra in (("ag", {}), ("hibrido", {"prob_busqueda_local": P_LOCAL})):
        r = optimizar(datos, config | extra)
        km = r["solucion"]["distancia_km"]
        fila[nombre] = {"km": km, "brecha_pct": 100 * (km * 1000 - opt) / opt,
                        "evaluaciones_distintas": r["evaluaciones_distintas"],
                        "fraccion_evaluada_pct": 100 * r["evaluaciones_distintas"] / fila["ordenes_posibles"]}
    return fila


def main():
    datos = cargar_datos()
    config = json.loads((ROOT / "datos/configuracion.json").read_text(encoding="utf-8"))

    primeros = []
    for n in range(6, 11):
        fila = evaluar(sub_instancia(datos, datos["ids"][:n]), config, f"primeros_{n}")
        primeros.append(fila)
        print(f"n={n}: optimo {fila['optimo_km']:.4f} km | AG brecha {fila['ag']['brecha_pct']:.3f} % | "
              f"hibrido brecha {fila['hibrido']['brecha_pct']:.3f} % | enumeracion {fila['tiempo_enumeracion_s']} s")

    rng = random.Random(2026)
    aleatorias = []
    for k in range(20):
        ids = rng.sample(datos["ids"], 8)
        aleatorias.append(evaluar(sub_instancia(datos, ids), config, f"aleatoria_8_{k + 1}") | {"ids": ids})

    def resumen(filas, nombre):
        return {"instancias": len(filas),
                "optimo_alcanzado": sum(abs(f[nombre]["brecha_pct"]) < 1e-9 for f in filas),
                "brecha_maxima_pct": max(f[nombre]["brecha_pct"] for f in filas)}

    todas = primeros + aleatorias
    salida = {
        "alcance": "Optimo exacto dentro del espacio del decodificador (todas las permutaciones). "
                   "No certifica el VRP general con recogidas divididas.",
        "prob_busqueda_local_hibrido": P_LOCAL,
        "resumen": {"ag": resumen(todas, "ag"), "hibrido": resumen(todas, "hibrido")},
        "primeros_n": primeros,
        "aleatorias_8": aleatorias,
    }
    (ROOT / "resultados" / "validacion_exacta.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(salida["resumen"], indent=2))


if __name__ == "__main__":
    main()

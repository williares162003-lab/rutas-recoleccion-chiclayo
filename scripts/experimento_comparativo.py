"""Compare five methods on the full 15-market instance over 30 seeds.

Methods
1. Nearest neighbor: deterministic baseline (one value).
2. Random search: random orders, same number of distinct evaluations as the plain GA of that seed.
3. Local search only: 2-opt + relocate starting from one random order.
4. Multi-start local search: repeated local search, same evaluation budget as the hybrid GA.
5. Plain GA: the original algorithm.
6. Hybrid GA: the same GA plus local search on 2 % of offspring.

Significance: one-sided Mann-Whitney U test (normal approximation with tie correction),
written from scratch because only the standard library is used.
"""
import csv
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from algoritmo_genetico.motor_genetico import busqueda_local, decodificar, optimizar, vecino_cercano  # noqa: E402
from sistema.lector_datos import cargar_datos, validar_config  # noqa: E402

SEMILLAS = list(range(30))
P_LOCAL = 0.02


def busqueda_aleatoria(datos, config, presupuesto, semilla):
    rng = random.Random(semilla)
    vistos, mejor = set(), float("inf")
    while len(vistos) < presupuesto:
        orden = datos["ids"][:]
        rng.shuffle(orden)
        clave = tuple(orden)
        if clave in vistos:
            continue
        vistos.add(clave)
        mejor = min(mejor, decodificar(orden, datos, config, detalle=False))
    return mejor / 1000, len(vistos)


def solo_busqueda_local(datos, config, semilla):
    rng = random.Random(semilla)
    orden = datos["ids"][:]
    rng.shuffle(orden)
    cache = {}

    def costo(o):
        k = tuple(o)
        if k not in cache:
            cache[k] = decodificar(o, datos, config, detalle=False)
        return cache[k]

    final = busqueda_local(orden, costo)
    return costo(final) / 1000, len(cache)


def multiarranque_local(datos, config, presupuesto, semilla):
    """Repeat local search from new random orders until the evaluation budget is used."""
    rng = random.Random(semilla)
    cache, mejor = {}, float("inf")

    def costo(o):
        k = tuple(o)
        if k not in cache:
            cache[k] = decodificar(o, datos, config, detalle=False)
        return cache[k]

    while len(cache) < presupuesto:
        orden = datos["ids"][:]
        rng.shuffle(orden)
        mejor = min(mejor, costo(busqueda_local(orden, costo)))
    return mejor / 1000, len(cache)


def mann_whitney_menor(a, b):
    """One-sided p-value for H1: values in `a` tend to be smaller than values in `b`."""
    n1, n2 = len(a), len(b)
    datos = sorted([(v, 0) for v in a] + [(v, 1) for v in b])
    rangos, i, empates = [0.0] * len(datos), 0, []
    while i < len(datos):
        j = i
        while j + 1 < len(datos) and abs(datos[j + 1][0] - datos[i][0]) < 1e-9:
            j += 1
        for k in range(i, j + 1):
            rangos[k] = (i + j) / 2 + 1  # average rank for ties
        empates.append(j - i + 1)
        i = j + 1
    r1 = sum(r for r, (_, g) in zip(rangos, datos) if g == 0)
    u1 = r1 - n1 * (n1 + 1) / 2
    n = n1 + n2
    media = n1 * n2 / 2
    var = n1 * n2 / 12 * ((n + 1) - sum(t ** 3 - t for t in empates) / (n * (n - 1)))
    if var == 0:
        return 1.0
    z = (u1 - media + 0.5) / math.sqrt(var)  # continuity correction
    return 0.5 * math.erfc(-z / math.sqrt(2))  # P(Z <= z)


def resumir(valores, mejor_conocido):
    return {
        "mejor_km": min(valores), "mediana_km": statistics.median(valores), "media_km": statistics.mean(valores),
        "desviacion_km": statistics.stdev(valores) if len(set(valores)) > 1 else 0.0, "peor_km": max(valores),
        "alcanza_mejor_conocido": sum(abs(v - mejor_conocido) < 1e-6 for v in valores),
    }


def main():
    datos = cargar_datos()
    config = validar_config(json.loads((ROOT / "datos/configuracion.json").read_text(encoding="utf-8")), datos)
    nn_km = decodificar(vecino_cercano(datos), datos, config)["distancia_km"]

    filas = []
    for s in SEMILLAS:
        cfg = config | {"semilla": s}
        t = time.perf_counter(); ag = optimizar(datos, cfg); t_ag = time.perf_counter() - t
        t = time.perf_counter(); hib = optimizar(datos, cfg | {"prob_busqueda_local": P_LOCAL}); t_hib = time.perf_counter() - t
        t = time.perf_counter(); al_km, al_ev = busqueda_aleatoria(datos, cfg, ag["evaluaciones_distintas"], s); t_al = time.perf_counter() - t
        t = time.perf_counter(); bl_km, bl_ev = solo_busqueda_local(datos, cfg, s); t_bl = time.perf_counter() - t
        t = time.perf_counter(); ml_km, ml_ev = multiarranque_local(datos, cfg, hib["evaluaciones_distintas"], s); t_ml = time.perf_counter() - t
        filas.append({"semilla": s, "vecino_cercano_km": nn_km,
                      "aleatoria_km": al_km, "aleatoria_eval": al_ev, "aleatoria_s": t_al,
                      "solo_local_km": bl_km, "solo_local_eval": bl_ev, "solo_local_s": t_bl,
                      "multiarranque_km": ml_km, "multiarranque_eval": ml_ev, "multiarranque_s": t_ml,
                      "ag_km": ag["solucion"]["distancia_km"], "ag_eval": ag["evaluaciones_distintas"], "ag_s": t_ag,
                      "hibrido_km": hib["solucion"]["distancia_km"], "hibrido_eval": hib["evaluaciones_distintas"], "hibrido_s": t_hib})
        print(f"seed {s:2d}: NN {nn_km:.2f} | random {al_km:.2f} | LS {bl_km:.2f} | multi-LS {ml_km:.2f} | "
              f"GA {filas[-1]['ag_km']:.2f} | hybrid {filas[-1]['hibrido_km']:.2f}")

    metodos = ["aleatoria", "solo_local", "multiarranque", "ag", "hibrido"]
    mejor_conocido = min(min(f[f"{m}_km"] for f in filas) for m in metodos)
    resumen = {"vecino_cercano_km": nn_km, "mejor_conocido_km": mejor_conocido, "semillas": len(SEMILLAS),
               "prob_busqueda_local_hibrido": P_LOCAL}
    for m in metodos:
        resumen[m] = resumir([f[f"{m}_km"] for f in filas], mejor_conocido) | {
            "evaluaciones_media": statistics.mean(f[f"{m}_eval"] for f in filas),
            "tiempo_medio_s": statistics.mean(f[f"{m}_s"] for f in filas),
            "mejora_mediana_vs_vecino_pct": 100 * (nn_km - statistics.median(f[f"{m}_km"] for f in filas)) / nn_km}
    col = lambda m: [f[f"{m}_km"] for f in filas]
    resumen["pruebas_mann_whitney"] = {
        "ag_menor_que_aleatoria_p": mann_whitney_menor(col("ag"), col("aleatoria")),
        "hibrido_menor_que_ag_p": mann_whitney_menor(col("hibrido"), col("ag")),
        "hibrido_menor_que_solo_local_p": mann_whitney_menor(col("hibrido"), col("solo_local")),
        "hibrido_menor_que_multiarranque_p": mann_whitney_menor(col("hibrido"), col("multiarranque")),
    }

    (ROOT / "resultados" / "experimento_comparativo.json").write_text(
        json.dumps({"resumen": resumen, "ejecuciones": filas}, ensure_ascii=False, indent=2), encoding="utf-8")
    with (ROOT / "resultados" / "experimento_comparativo.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    print(json.dumps(resumen, indent=2))


if __name__ == "__main__":
    main()

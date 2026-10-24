"""Ejecuta diez semillas prefijadas y un contraste exacto de seis mercados."""
import csv
import itertools
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from types import SimpleNamespace
from algoritmo_genetico import motor_genetico
from sistema import lector_datos
motor = SimpleNamespace(**{**vars(lector_datos), **vars(motor_genetico)})

def guardar(nombre, obj):
    (ROOT / 'resultados' / nombre).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

def main():
    datos = motor.cargar_datos()
    config = json.loads((ROOT / 'datos/configuracion.json').read_text(encoding='utf-8'))
    filas = []
    for seed in [0, 1, 2, 3, 4, 5, 6, 7, 8, 42]:
        r = motor.optimizar(datos, config | {'semilla': seed})
        guardar(f'semilla_{seed}.json', r)
        filas.append({'semilla': seed, 'referencia_km': r['referencia']['distancia_km'], 'ag_km': r['solucion']['distancia_km'],
                      'mejora_pct': r['mejora_porcentaje'], 'generaciones': r['generaciones_ejecutadas'],
                      'tiempo_s': r['tiempo_segundos'], 'viajes': r['solucion']['viajes_totales']})
    with (ROOT / 'resultados/experimento_10_semillas.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0])); w.writeheader(); w.writerows(filas)
    valores = [r['ag_km'] for r in filas]
    resumen = {'semillas_prefijadas': [r['semilla'] for r in filas], 'referencia_km': filas[0]['referencia_km'],
               'mejor_km': min(valores), 'mediana_km': statistics.median(valores), 'media_km': statistics.mean(valores),
               'desviacion_estandar_muestral_km': statistics.stdev(valores), 'peor_km': max(valores),
               'tiempo_medio_s': statistics.mean(r['tiempo_s'] for r in filas), 'ejecuciones': filas}
    guardar('resumen_experimento.json', resumen)
    # El oráculo comprueba el modelo restringido por este mismo decodificador.
    ids = datos['ids'][:6]
    pequeno = datos | {'ids': ids, 'demandas': {i: datos['demandas'][i] for i in ids}}
    orden_exacto = min(itertools.permutations(ids), key=lambda o: motor.decodificar(list(o), pequeno, config, False))
    exacto = motor.decodificar(list(orden_exacto), pequeno, config)
    ga = motor.optimizar(pequeno, config)
    guardar('contraste_exacto_6_mercados.json', {'permutaciones': 720, 'ids': ids, 'optimo_familia_decoder': exacto,
            'ag': ga, 'brecha_pct': 100 * (ga['solucion']['distancia_km'] - exacto['distancia_km']) / exacto['distancia_km'],
            'alcance': 'Certifica solo el caso de seis mercados y este decodificador; no el SDVRP general ni los quince mercados.'})
    # La demo guardada corresponde a la semilla acordada, no a elegir la mejor después.
    guardar('ejecucion.json', json.loads((ROOT / 'resultados/semilla_42.json').read_text(encoding='utf-8')))
    r = json.loads((ROOT / 'resultados/ejecucion.json').read_text(encoding='utf-8'))
    with (ROOT / 'resultados/convergencia_semilla_42.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(r['historial'][0])); w.writeheader(); w.writerows(r['historial'])
    with (ROOT / 'resultados/plan_semilla_42.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f); w.writerow(['viaje','camion','turno_camion','orden_parada','id_mercado','recogido_kg','carga_viaje_kg','distancia_viaje_km'])
        for v in r['solucion']['viajes']:
            for k,p in enumerate(v['paradas'],1):
                w.writerow([v['viaje'],v['camion'],v['turno_camion'],k,p['id_mercado'],p['kg'],v['carga_kg'],v['distancia_km']])
    print(json.dumps({k:v for k,v in resumen.items() if k!='ejecuciones'}, ensure_ascii=False, indent=2))
    print('Brecha frente al oraculo de seis mercados:', 100 * (ga['solucion']['distancia_km'] - exacto['distancia_km']) / exacto['distancia_km'])

if __name__ == '__main__':
    main()

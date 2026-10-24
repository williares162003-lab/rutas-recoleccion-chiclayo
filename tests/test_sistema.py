"""Pruebas de restricciones, operadores, reproducibilidad y oráculo exacto."""
import itertools
import json
import random
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from algoritmo_genetico import motor_genetico
from sistema import lector_datos

# Funciones de datos y del AG reunidas bajo un mismo nombre para las pruebas.
motor = SimpleNamespace(**{**vars(lector_datos), **vars(motor_genetico)})

class SistemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = motor.cargar_datos()
        cls.c = json.loads((ROOT / 'datos/configuracion.json').read_text(encoding='utf-8'))
        cls.r = motor.optimizar(cls.d, cls.c | {'generaciones': 50})

    def test_dataset_original(self):
        self.assertEqual(len(self.d['ids']), 15)
        self.assertEqual(sum(self.d['demandas'].values()), 4190436)
        self.assertEqual(self.d['sha256_csv'], '45fa525ca03eb500b17d78740de1ba5bcfffa70ae1ee847d2ad58e90bbc266cc')

    def test_matriz_dirigida(self):
        m = self.d['matriz']
        self.assertEqual(len(m), 17)
        self.assertTrue(any(m[i][j] != m[j][i] for i in range(17) for j in range(17)))

    def test_ox_y_mutacion_conservan_genes(self):
        rng = random.Random(7)
        for _ in range(200):
            a, b = self.d['ids'][:], self.d['ids'][:]
            rng.shuffle(a); rng.shuffle(b)
            for hijo in (motor.cruce_ox(a, b, rng), motor.mutar(a, rng)):
                self.assertEqual(sorted(hijo), sorted(a))
                self.assertEqual(len(set(hijo)), 15)

    def test_un_gen(self):
        rng = random.Random(7)
        self.assertEqual(motor.cruce_ox(['A'], ['A'], rng), ['A'])
        self.assertEqual(motor.mutar(['A'], rng), ['A'])

    def test_carga_cobertura_y_viajes(self):
        recogidos = dict.fromkeys(self.d['ids'], 0)
        por_camion = {}
        viajes = self.r['solucion']['viajes']
        self.assertEqual(len(viajes), 5)
        for v in viajes:
            self.assertLessEqual(v['carga_kg'], 10000)
            por_camion[v['camion']] = por_camion.get(v['camion'], 0) + 1
            for p in v['paradas']:
                recogidos[p['id_mercado']] += round(p['kg'] * 100)
        self.assertEqual(recogidos, self.d['demandas'])
        self.assertTrue(all(n <= 3 for n in por_camion.values()))
        self.assertTrue(all(v['carga_kg'] == 10000 for v in viajes[:-1]))

    def test_moshoqueque_se_divide(self):
        p = motor.decodificar(self.d['ids'], self.d, self.c)
        porciones = [s['kg'] for v in p['viajes'] for s in v['paradas'] if s['id_mercado'] == 'CH-1006']
        self.assertEqual(porciones, [10000, 8800])

    def test_distancia_recalculada_arco_por_arco(self):
        suma = 0
        m = self.d['matriz']
        for v in self.r['solucion']['viajes']:
            nodos = [0] + [self.d['indices'][p['id_mercado']] for p in v['paradas']] + [16, 0]
            distancia = sum(m[a][b] for a, b in zip(nodos, nodos[1:]))
            self.assertAlmostEqual(distancia / 1000, v['distancia_km'])
            suma += distancia
        self.assertAlmostEqual(suma / 1000, self.r['solucion']['distancia_km'])

    def test_cromosoma_invalido(self):
        with self.assertRaises(ValueError):
            motor.decodificar(self.d['ids'][:-1] + [self.d['ids'][0]], self.d, self.c)

    def test_flota_insuficiente(self):
        with self.assertRaisesRegex(ValueError, 'insuficiente'):
            motor.validar_config(self.c | {'camiones': 1, 'viajes_por_camion': 1}, self.d)

    def test_hiperparametros_invalidos(self):
        for cambio in ({'poblacion': 3}, {'prob_mutacion': 2}, {'camiones': True}, {'elite': 100}, {'semilla': -1}):
            with self.assertRaises(ValueError):
                motor.validar_config(self.c | cambio, self.d)

    def test_precision_masa(self):
        self.assertEqual(motor.centikg('41904.36'), 4190436)
        for invalido in (0, -1, '1.001', 'NaN'):
            with self.assertRaises(ValueError):
                motor.centikg(invalido)

    def test_elitismo_y_referencia(self):
        h = self.r['historial']
        self.assertTrue(all(b['mejor_km'] <= a['mejor_km'] for a, b in zip(h, h[1:])))
        self.assertLessEqual(self.r['solucion']['distancia_km'], self.r['referencia']['distancia_km'])

    def test_reproducible(self):
        r2 = motor.optimizar(self.d, self.c | {'generaciones': 50})
        self.assertEqual(r2['solucion'], self.r['solucion'])
        self.assertEqual(r2['historial'], self.r['historial'])

    def test_aptitud(self):
        p = self.r['solucion']
        self.assertAlmostEqual(p['fitness'], 1 / (1 + p['distancia_km']))

    def test_busqueda_local_conserva_genes_y_no_empeora(self):
        rng = random.Random(11)
        costo = lambda o: motor.decodificar(o, self.d, self.c, False)
        for _ in range(5):
            orden = self.d['ids'][:]
            rng.shuffle(orden)
            pulido = motor.busqueda_local(orden, costo)
            self.assertEqual(sorted(pulido), sorted(orden))
            self.assertLessEqual(costo(pulido), costo(orden))

    def test_sin_busqueda_local_igual_al_original(self):
        # Con prob_busqueda_local = 0 el AG debe reproducir la ejecución guardada (semilla 42).
        guardado = json.loads((ROOT / 'resultados/semilla_42.json').read_text(encoding='utf-8'))
        r = motor.optimizar(self.d, self.c)
        self.assertEqual(r['solucion']['orden'], guardado['solucion']['orden'])
        self.assertEqual(len(r['historial']), len(guardado['historial']))
        # Python 3.12+ suma floats con más precisión: los promedios pueden variar en el último decimal.
        for a, b in zip(r['historial'], guardado['historial']):
            for k in a:
                self.assertAlmostEqual(a[k], b[k], places=6)

    def test_hibrido_reproducible_y_no_peor(self):
        c = self.c | {'prob_busqueda_local': 0.02, 'generaciones': 60}
        r1, r2 = motor.optimizar(self.d, c), motor.optimizar(self.d, c)
        self.assertEqual(r1['solucion'], r2['solucion'])
        self.assertLessEqual(r1['solucion']['distancia_km'], r1['referencia']['distancia_km'])

    def test_prob_busqueda_local_invalida(self):
        for v in (-0.1, 1.5, True):
            with self.assertRaises(ValueError):
                motor.validar_config(self.c | {'prob_busqueda_local': v}, self.d)

    def test_oraculo_exacto_pequeno(self):
        # Caso dirigido con cuatro mercados: enumerar todas sus permutaciones.
        ids = list('ABCD')
        matriz = [[0 if a == b else 9 for b in range(6)] for a in range(6)]
        for a, b in zip([0, 1, 2, 3, 4, 5], [1, 2, 3, 4, 5, 0]):
            matriz[a][b] = 1
        d = {'ids': ids, 'demandas': {i: 100 for i in ids}, 'indices': {i:k+1 for k,i in enumerate(ids)}, 'matriz': matriz, 'sha256_csv': 'caso_sintetico'}
        c = self.c | {'capacidad_kg': 10, 'camiones': 1, 'viajes_por_camion': 1, 'generaciones': 30}
        exacto = min(motor.decodificar(list(o), d, c, False) for o in itertools.permutations(ids))
        obtenido = motor.optimizar(d, c)['solucion']['distancia_km'] * 1000
        self.assertAlmostEqual(exacto, 6)
        self.assertAlmostEqual(obtenido, exacto)

if __name__ == '__main__':
    unittest.main(verbosity=2)

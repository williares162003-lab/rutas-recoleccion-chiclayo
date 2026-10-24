"""Lectura y validación de mercados, distancias y configuración del escenario."""

# Solo se importan módulos que ya vienen con Python (biblioteca estándar).
import csv          # leer el dataset de mercados (.csv)
import hashlib      # huella SHA-256 del dataset para saber con qué datos se corrió
import json         # leer la matriz de distancias (.json)
import math         # comprobar que las distancias sean números finitos
from decimal import Decimal  # convertir kg con decimales sin errores de redondeo
from pathlib import Path     # manejar rutas de archivos en Windows/Linux


# ============================================================
# UBICACIÓN DE LOS DATOS
# ============================================================

# Carpeta raíz del proyecto: la primera carpeta superior que contiene datos/.
RAIZ = next(p for p in Path(__file__).resolve().parents if (p / "datos").is_dir())


# ============================================================
# PASO 0. PREPARACIÓN DE DATOS
# ============================================================

# Representa los kg como enteros en centésimas para no perder masa al sumar y restar.
def centikg(valor):
    """Representa 0,01 kg con un entero para conservar exactamente la masa."""
    # Ejemplo: 4690.98 kg -> 469098 centésimas de kg. Trabajar con enteros evita
    # que al sumar y restar decimales se pierdan o aparezcan gramos de basura.
    d = Decimal(str(valor))

    # Se rechazan valores negativos, cero, infinitos o con más de dos decimales.
    if not d.is_finite() or d <= 0 or d * 100 != (d * 100).to_integral_value():
        raise ValueError("La capacidad/demanda debe ser positiva y tener hasta dos decimales.")

    return int(d * 100)


# Lee los 15 mercados y la matriz vial, y comprueba que sean coherentes entre sí.
def cargar_datos(carpeta=None):
    """Valida la entrada y conserva la dirección de cada distancia vial."""
    # Si no se indica carpeta, se usa datos/ del proyecto.
    carpeta = Path(carpeta) if carpeta else RAIZ / "datos"
    csv_path = carpeta / "15_mercados_chiclayo_11_columnas.csv"

    # Cada fila del CSV es un mercado: id, nombre, distrito, puestos, kg/día, coordenadas.
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        mercados = list(csv.DictReader(f))

    # La matriz vial tiene 17 puntos: 0 = base EPSEL, 1..15 = mercados, 16 = botadero Reque.
    vial = json.loads((carpeta / "matriz_vial.json").read_text(encoding="utf-8"))
    ids = [m["id_mercado"] for m in mercados]

    # Los IDs de mercado serán los genes, por eso no pueden repetirse.
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("El dataset debe contener IDs únicos.")

    # El orden del CSV debe coincidir con las filas 1..15 de la matriz.
    if vial["orden_ids"][1:-1] != ids:
        raise ValueError("El orden del CSV no coincide con la matriz.")

    n = len(ids) + 2  # 15 mercados + base + botadero = 17
    matriz = vial["distancias_m"]

    # La matriz debe ser cuadrada 17x17.
    if len(matriz) != n or any(len(row) != n for row in matriz):
        raise ValueError("La matriz debe ser cuadrada e incluir base y descarga.")

    # matriz[i][j] = metros por carretera de i a j. Puede ser distinta de matriz[j][i]
    # porque las calles tienen sentido de circulación (matriz dirigida).
    for i, row in enumerate(matriz):
        for j, value in enumerate(row):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
                or (i != j and value == 0)
            ):
                raise ValueError("Hay una distancia vial faltante o inválida.")

        # La distancia de un punto a sí mismo es cero.
        if row[i] != 0:
            raise ValueError("La diagonal de la matriz debe ser cero.")

    # Las coordenadas del CSV deben ser las mismas con las que se calculó la matriz.
    for m, p in zip(mercados, vial["puntos"][1:-1]):
        if float(m["latitud_wgs84"]) != p["latitud"] or float(m["longitud_wgs84"]) != p["longitud"]:
            raise ValueError("Las coordenadas no coinciden con la matriz vial.")

    # Demanda de cada mercado (kg/día estimados) en centésimas de kg.
    demandas = {m["id_mercado"]: centikg(m["residuos_kg_dia_estimados"]) for m in mercados}

    # 'indices' traduce cada ID de mercado a su fila/columna en la matriz (1..15).
    return {
        "mercados": mercados,
        "ids": ids,
        "demandas": demandas,
        "matriz": matriz,
        "indices": {i: k + 1 for k, i in enumerate(ids)},
        "vial": vial,
        "sha256_csv": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
    }


# ============================================================
# VALIDACIÓN DE LA CONFIGURACIÓN
# ============================================================

# Revisa los parámetros del escenario y del AG antes de empezar a evolucionar.
def validar_config(config, datos):
    """Rechaza parámetros inválidos y flota con capacidad total insuficiente."""
    c = dict(config)

    # Hiperparámetros enteros y sus rangos permitidos.
    for k, minimo, maximo in [
        ("camiones", 1, 30),
        ("viajes_por_camion", 1, 30),
        ("poblacion", 4, 500),
        ("generaciones", 1, 3000),
        ("elite", 1, 50),
        ("torneo", 2, 50),
        ("paciencia", 1, 3000),
        ("semilla", 0, 2**32 - 1),
    ]:
        v = c.get(k)
        if isinstance(v, bool) or not isinstance(v, int) or not minimo <= v <= maximo:
            raise ValueError(f"{k}: se requiere un entero entre {minimo} y {maximo}.")

    # Las probabilidades deben estar entre 0 y 1. La de búsqueda local es opcional (0 = AG original).
    c.setdefault("prob_busqueda_local", 0.0)
    for k in ("prob_cruce", "prob_mutacion", "prob_busqueda_local"):
        v = c.get(k)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1:
            raise ValueError(f"{k} debe estar entre 0 y 1.")

    # No se pueden conservar más élites que individuos ni hacer torneos más grandes que la población.
    if c["elite"] >= c["poblacion"] or c["torneo"] > c["poblacion"]:
        raise ValueError("Elitismo menor que población y torneo no mayor que población.")

    if isinstance(c.get("capacidad_kg"), bool):
        raise ValueError("Capacidad inválida.")

    q = centikg(c.get("capacidad_kg"))  # capacidad Q por viaje (10 000 kg -> 1 000 000)
    if q > 10000000:
        raise ValueError("Capacidad máxima: 100 000 kg.")

    # Viajes mínimos necesarios = techo(demanda total / Q). Si la flota (camiones x viajes)
    # no alcanza, el problema no tiene solución y se avisa antes de evolucionar.
    total = sum(datos["demandas"].values())
    necesarios = (total + q - 1) // q
    if necesarios > c["camiones"] * c["viajes_por_camion"]:
        raise ValueError(
            f'Capacidad insuficiente: se necesitan {necesarios} viajes y solo hay {c["camiones"] * c["viajes_por_camion"]}.'
        )

    return c

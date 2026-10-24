"""ALGORITMO GENÉTICO COMPLETO: empezar a leer arriba y continuar hacia abajo.

1. La primera función, optimizar, muestra el ciclo con los PASOS 0 a 7.
2. Debajo están los detalles de las cinco operaciones que ese ciclo utiliza.

La interfaz llama a optimizar al solicitar una optimización. Las funciones
de apoyo pueden estar debajo porque Python carga el módulo antes de la llamada.
Todo el AG está implementado aquí con Python estándar.
"""

import random  # elecciones aleatorias reproducibles mediante una semilla
import time    # medición del tiempo de ejecución

from sistema.lector_datos import centikg, validar_config


# ============================================================
# EMPIEZA AQUÍ: CICLO COMPLETO DEL ALGORITMO GENÉTICO
# ============================================================

def optimizar(datos, config, progreso=None):
    """Ejecuta población, evaluación, torneo, OX, swap y reemplazo con elitismo."""
    # ----- PASO 0. PREPARAR Y VALIDAR LA CONFIGURACIÓN -----
    inicio_t = time.perf_counter()
    c = validar_config(config, datos)

    # Generador aleatorio propio con semilla: la misma semilla produce el mismo resultado.
    rng = random.Random(c["semilla"])

    # ----- PASO 1. INICIALIZACIÓN DE LA POBLACIÓN -----
    # Cada individuo (cromosoma) es una permutación de los 15 IDs de mercado.
    # Gen = un mercado; el orden de los genes = el orden en que se atienden.
    referencia = vecino_cercano(datos)
    poblacion = [referencia]

    # Una solución heurística y las restantes aleatorias forman la población inicial.
    for _ in range(c["poblacion"] - 1):
        individuo = datos["ids"][:]
        rng.shuffle(individuo)  # orden aleatorio de los 15 mercados
        poblacion.append(individuo)

    # Memoria de costos ya calculados: si un orden se repite, no se vuelve a decodificar.
    cache = {}

    # ----- PASO 2. FUNCIÓN DE EVALUACIÓN -----
    # Costo = metros totales del plan que produce el decodificador (menor es mejor).
    def costo(individuo):
        key = tuple(individuo)
        if key not in cache:
            cache[key] = decodificar(individuo, datos, c, detalle=False)
        return cache[key]

    # Mejor solución encontrada hasta el momento (empieza siendo la referencia).
    mejor, mejor_costo, sin_mejora, historial = referencia[:], costo(referencia), 0, []
    motivo = "limite_generaciones"

    # CICLO DE GENERACIONES: repetir evaluación, reproducción y parada.
    for generacion in range(c["generaciones"] + 1):

        # ----- PASO 2. EVALUAR Y ORDENAR LA POBLACIÓN -----
        # Minimizar distancia equivale a maximizar 1/(1 + distancia en km).
        poblacion.sort(key=costo)  # el primero es el de menor distancia
        actual = costo(poblacion[0])

        # Si el mejor de esta generación supera al mejor histórico, se guarda.
        if actual < mejor_costo - 1e-8:
            mejor, mejor_costo, sin_mejora = poblacion[0][:], actual, 0
        elif generacion > 0:
            sin_mejora += 1

        # Se registra la convergencia: mejor km y promedio de la población.
        valores = [costo(p) / 1000 for p in poblacion]
        historial.append(
            {
                "generacion": generacion,
                "mejor_km": mejor_costo / 1000,
                "promedio_km": sum(valores) / len(valores),
                "fitness_mejor": 1 / (1 + mejor_costo / 1000),
            }
        )

        if progreso:
            progreso(historial[-1])  # avisa a la interfaz web para dibujar la curva

        # Producir otra generación solo si aún queda presupuesto y no hay estancamiento.
        continuar = sin_mejora < c["paciencia"] and generacion < c["generaciones"]
        if continuar:
            # Reservar dos plazas para las élites antes de producir descendientes.
            nueva = [p[:] for p in poblacion[: c["elite"]]]  # los 2 mejores se copian sin cambios

            while len(nueva) < c["poblacion"]:
                # PASO 3: se eligen dos padres con dos torneos.
                a = seleccionar_torneo(poblacion, costo, c["torneo"], rng)
                b = seleccionar_torneo(poblacion, costo, c["torneo"], rng)

                # PASO 4: con probabilidad prob_cruce (0,90) se cruzan con OX;
                # si no, los hijos son copias de los padres.
                hijos = (
                    [cruce_ox(a, b, rng), cruce_ox(b, a, rng)]
                    if rng.random() < c["prob_cruce"]
                    else [a[:], b[:]]
                )

                for hijo in hijos:
                    # PASO 5: cada hijo muta con probabilidad prob_mutacion (0,20).
                    if rng.random() < c["prob_mutacion"]:
                        hijo = mutar(hijo, rng)

                    # PASO 5b (versión híbrida): con probabilidad prob_busqueda_local
                    # el hijo se pule con búsqueda local. Con 0 es el AG original y no
                    # se consume ningún número aleatorio extra (mismos resultados de siempre).
                    p_local = c.get("prob_busqueda_local", 0.0)
                    if p_local > 0 and rng.random() < p_local:
                        hijo = busqueda_local(hijo, costo)
                    nueva.append(hijo)

                    # Se detiene al completar el tamaño de la población.
                    if len(nueva) == c["poblacion"]:
                        break

            # ----- PASO 6. REEMPLAZO CON ELITISMO -----
            # La nueva generación reemplaza a la anterior.
            poblacion = nueva

        # ----- PASO 7. COMPROBAR SI TERMINA EL ALGORITMO -----
        if sin_mejora >= c["paciencia"]:
            motivo = "estancamiento"
            break
        if generacion == c["generaciones"]:
            break

    # ----- RESULTADO -----
    # Se decodifican con detalle la referencia y la mejor solución para compararlas.
    base = decodificar(referencia, datos, c)
    plan = decodificar(mejor, datos, c)

    return {
        "configuracion": c,
        "referencia": base,
        "solucion": plan,
        # Porcentaje de kilómetros ahorrados frente al vecino más cercano.
        "mejora_porcentaje": 100 * (base["distancia_km"] - plan["distancia_km"]) / base["distancia_km"],
        "historial": historial,
        "generaciones_ejecutadas": len(historial) - 1,
        "motivo_parada": motivo,
        "evaluaciones_distintas": len(cache),
        "tiempo_segundos": time.perf_counter() - inicio_t,
        "sha256_dataset": datos["sha256_csv"],
        "alcance": "Mejor solucion encontrada en la familia del decodificador; sin garantia de optimo global.",
    }


# ============================================================
# DETALLE DE LAS OPERACIONES UTILIZADAS EN EL CICLO ANTERIOR
# ============================================================

# ============================================================
# APOYO 1. REFERENCIA: VECINO MÁS CERCANO
# ============================================================

# Construye el orden "vecino más cercano": siempre ir al mercado pendiente más próximo.
def vecino_cercano(datos):
    """Referencia reproducible: elige el mercado no visitado más cercano."""
    # Partiendo de la base (punto 0), siempre se va al mercado pendiente más cercano.
    # Este orden sirve de punto de comparación y entra como un individuo de la población inicial.
    pendientes = set(datos["ids"])
    actual, orden = 0, []

    while pendientes:
        # Se busca la menor distancia desde el punto actual; si hay empate, gana el ID menor.
        siguiente = min(pendientes, key=lambda i: (datos["matriz"][actual][datos["indices"][i]], i))
        orden.append(siguiente)
        pendientes.remove(siguiente)
        actual = datos["indices"][siguiente]

    return orden


# ============================================================
# APOYO 2. CONSTRUCCIÓN DE VIAJES Y APTITUD
# ============================================================

# Convierte un cromosoma (orden de mercados) en viajes reales y calcula su distancia.
def decodificar(orden, datos, config, detalle=True):
    """Llena cada viaje antes de iniciar el siguiente y conserva toda la demanda.

    Cada viaje es base -> mercados -> descarga -> base. Si la demanda de un
    mercado excede el espacio libre, se continúa ese mercado en el viaje siguiente.
    Los camiones se asignan por turnos; no se optimizan horarios ni balance de carga.
    """
    # El cromosoma debe contener los 15 mercados exactamente una vez (una permutación).
    if len(orden) != len(datos["ids"]) or set(orden) != set(datos["ids"]):
        raise ValueError("El cromosoma debe ser una permutación de todos los mercados.")

    q = centikg(config["capacidad_kg"])  # capacidad por viaje
    matriz, indice = datos["matriz"], datos["indices"]
    descarga = len(matriz) - 1  # último punto = botadero de Reque
    viajes, paradas = [], []

    # actual: punto donde está el camión (0 = base); carga: kg a bordo;
    # distancia: metros del viaje en curso; total: metros de todo el plan; numero: viajes cerrados.
    actual, carga, distancia, total, numero = 0, 0, 0.0, 0.0, 0

    # Termina el viaje en curso: ir a descargar a Reque y regresar a la base.
    def cerrar():
        nonlocal actual, carga, distancia, total, numero, paradas
        distancia += matriz[actual][descarga] + matriz[descarga][0]
        total += distancia
        numero += 1

        # Restricción de flota: no se pueden hacer más viajes que camiones x viajes por camión.
        if numero > config["camiones"] * config["viajes_por_camion"]:
            raise ValueError("El plan supera el presupuesto de viajes.")

        if detalle:
            # Los viajes se reparten por turnos: viaje 1 -> camión 1, viaje 2 -> camión 2, etc.
            viajes.append(
                {
                    "viaje": numero,
                    "camion": (numero - 1) % config["camiones"] + 1,
                    "turno_camion": (numero - 1) // config["camiones"] + 1,
                    "carga_kg": carga / 100,
                    "capacidad_kg": q / 100,
                    "distancia_km": distancia / 1000,
                    "paradas": paradas,
                }
            )

        # El camión vuelve vacío a la base para empezar el siguiente viaje.
        actual, carga, distancia, paradas = 0, 0, 0.0, []

    # Se recorren los mercados en el orden que indica el cromosoma.
    for mercado in orden:
        restante = datos["demandas"][mercado]

        # Mientras quede basura en este mercado, se sigue recogiendo.
        while restante > 0:
            # Se recoge lo que quepa: lo que falta del mercado o el espacio libre del camión.
            recogido = min(restante, q - carga)
            distancia += matriz[actual][indice[mercado]]  # trayecto hasta el mercado
            actual = indice[mercado]
            carga += recogido
            restante -= recogido

            if detalle:
                paradas.append({"id_mercado": mercado, "kg": recogido / 100})

            # Restricción de capacidad: si el camión se llenó, va a descargar y empieza otro viaje.
            # Así un mercado grande (Moshoqueque, 18 800 kg) se reparte entre varios viajes.
            if carga == q:
                cerrar()

    # Si quedó carga en el último camión, también se cierra ese viaje.
    if carga:
        cerrar()

    # Durante la evolución solo se necesita la distancia total (más rápido).
    if not detalle:
        return total

    # Para mostrar resultados se devuelve el plan completo.
    # Fitness = 1 / (1 + km): a menos kilómetros, mayor aptitud.
    return {
        "orden": list(orden),
        "distancia_km": total / 1000,
        "fitness": 1 / (1 + total / 1000),
        "viajes": viajes,
        "viajes_totales": numero,
        "demanda_recogida_kg": sum(datos["demandas"].values()) / 100,
    }


# ============================================================
# APOYO 3. SELECCIÓN POR TORNEO
# ============================================================

def seleccionar_torneo(poblacion, costo, tamano, rng):
    """Elige al azar varios individuos y devuelve el de menor distancia."""
    # Con la configuración inicial compiten tres individuos por cada padre.
    aspirantes = rng.sample(poblacion, tamano)
    return min(aspirantes, key=costo)


# ============================================================
# APOYO 4. CRUCE ORDENADO (OX)
# ============================================================

# Combina dos padres sin repetir ni perder mercados.
def cruce_ox(padre_a, padre_b, rng):
    """Conserva un segmento de A y completa circularmente con el orden de B."""
    # Ejemplo con 6 genes: A=[1,2,3,4,5,6], B=[4,6,2,1,5,3], segmento posiciones 2..3.
    # El hijo copia [_,_,3,4,_,_] de A y rellena el resto con B en orden: [2,1,3,4,5,6].
    # A diferencia del cruce de un punto, OX nunca repite ni pierde mercados.
    n = len(padre_a)
    if n < 2:
        return padre_a[:]

    # Se eligen dos posiciones distintas al azar: inicio y fin del segmento.
    inicio, fin = sorted(rng.sample(range(n), 2))
    fin += 1
    hijo = [None] * n

    # 1) Se copia el segmento del padre A en la misma posición.
    hijo[inicio:fin] = padre_a[inicio:fin]
    usados = set(padre_a[inicio:fin])

    # 2) Se rellenan los huecos desde el final del segmento, dando la vuelta (circular).
    posicion = fin % n

    # 3) Los genes se toman del padre B en su orden, saltando los que ya están en el hijo.
    for gen in padre_b[fin:] + padre_b[:fin]:
        if gen not in usados:
            hijo[posicion] = gen
            posicion = (posicion + 1) % n

    return hijo


# ============================================================
# APOYO 5. MUTACIÓN POR INTERCAMBIO (SWAP)
# ============================================================

# Intercambia dos mercados al azar para explorar órdenes nuevos.
def mutar(orden, rng):
    """Intercambia dos posiciones sin perder ni duplicar mercados."""
    # Ejemplo: [A,B,C,D] -> se eligen las posiciones 1 y 3 -> [A,D,C,B].
    hijo = orden[:]  # se trabaja sobre una copia para no alterar al padre

    if len(hijo) >= 2:
        a, b = rng.sample(range(len(hijo)), 2)
        hijo[a], hijo[b] = hijo[b], hijo[a]

    return hijo


# ============================================================
# APOYO 6. BÚSQUEDA LOCAL (VERSIÓN HÍBRIDA O "MEMÉTICA")
# ============================================================

# Pule un orden probando cambios pequeños y aceptando solo los que acortan el plan.
def busqueda_local(orden, costo, max_pasadas=50):
    """Primera mejora con dos vecindarios: 2-opt (invertir tramo) y reubicar un mercado.

    Nunca empeora: devuelve un orden con costo menor o igual al recibido.
    Sigue siendo una permutación, así que el decodificador y sus restricciones no cambian.
    """
    actual = orden[:]
    mejor_costo = costo(actual)
    n = len(actual)

    for _ in range(max_pasadas):
        mejoro = False

        # Vecindario 1. 2-opt: invertir el tramo i..j.
        # Ejemplo: [A,B,C,D,E] con i=1, j=3 -> [A,D,C,B,E].
        for i in range(n - 1):
            for j in range(i + 1, n):
                candidato = actual[:i] + actual[i:j + 1][::-1] + actual[j + 1:]
                c = costo(candidato)
                if c < mejor_costo - 1e-8:
                    actual, mejor_costo, mejoro = candidato, c, True

        # Vecindario 2. Reubicar: sacar el mercado de la posición i e insertarlo en j.
        # Ejemplo: [A,B,C,D,E] con i=0, j=3 -> [B,C,D,A,E].
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                candidato = actual[:i] + actual[i + 1:]
                candidato.insert(j, actual[i])
                c = costo(candidato)
                if c < mejor_costo - 1e-8:
                    actual, mejor_costo, mejoro = candidato, c, True

        # Óptimo local: ningún cambio pequeño acorta el plan.
        if not mejoro:
            break

    return actual

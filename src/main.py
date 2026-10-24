"""Aplicación web local de Rutas Chiclayo. Iniciar: python main.py y abrir http://127.0.0.1:8765."""

# Módulos de la biblioteca estándar: servidor web, hilos y lectura de archivos.
import argparse
import csv
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, Thread
from urllib.parse import urlparse

# Algoritmo genético y lectura/validación de datos del propio proyecto.
from algoritmo_genetico.motor_genetico import optimizar
from sistema.lector_datos import RAIZ, cargar_datos, validar_config


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

# Los datos y la configuración por defecto se cargan una sola vez al iniciar.
DATOS = cargar_datos()
CONFIG = json.loads((RAIZ / "datos/configuracion.json").read_text(encoding="utf-8"))

# Carpetas de la interfaz: páginas HTML (templates) y archivos CSS/JS (static).
BASE = Path(__file__).resolve().parent
TEMPLATES = BASE / "templates"
STATIC = BASE / "static"

# Estado compartido de la ejecución: la página lo consulta para mostrar el avance.
ESTADO = {"estado": "listo", "progreso": None, "resultado": None, "error": None}

# El candado evita que dos hilos modifiquen ESTADO al mismo tiempo.
CANDADO = Lock()


# ============================================================
# EJECUCIÓN DEL ALGORITMO EN SEGUNDO PLANO
# ============================================================

# Corre el AG en un hilo aparte y va publicando su avance en ESTADO.
def trabajo(config):
    """Ejecuta el AG en un hilo y publica progreso sin bloquear la página."""

    # Cada generación, el AG entrega su fila de historial para dibujar la curva.
    def avance(fila):
        with CANDADO:
            ESTADO["progreso"] = fila

    try:
        resultado = optimizar(DATOS, config, avance)
        with CANDADO:
            ESTADO.update(estado="terminado", resultado=resultado)
    except Exception as exc:
        with CANDADO:
            ESTADO.update(estado="error", error=str(exc))


# ============================================================
# RUTAS DEL SISTEMA
# ============================================================

# Atiende las peticiones del navegador (GET para leer, POST para ejecutar el AG).
class Handler(BaseHTTPRequestHandler):

    # Envía una respuesta en formato JSON.
    def respuesta(self, value, status=200):
        data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # Peticiones GET: datos, estado, ejecución guardada y archivos de la interfaz.
    def do_GET(self):
        path = urlparse(self.path).path

        # Mercados, puntos, configuración por defecto y flota del PIGARS para la pestaña de datos.
        if path == "/api/datos":
            with (RAIZ / "datos/flota_publicada.csv").open(encoding="utf-8-sig", newline="") as f:
                flota = list(csv.DictReader(f))
            return self.respuesta(
                {
                    "mercados": DATOS["mercados"],
                    "puntos": DATOS["vial"]["puntos"],
                    "configuracion": CONFIG,
                    "flota_publicada": flota,
                }
            )

        # Avance o resultado de la ejecución en curso.
        if path == "/api/estado":
            with CANDADO:
                return self.respuesta(dict(ESTADO))

        # Ejecución guardada en resultados/ejecucion.json.
        if path == "/api/ejemplo":
            return self.respuesta(json.loads((RAIZ / "resultados/ejecucion.json").read_text(encoding="utf-8")))

        # Lista cerrada: nunca se sirve una ruta arbitraria del disco.
        archivos = {
            "/": TEMPLATES / "index.html",
            "/static/js/app.js": STATIC / "js/app.js",
            "/static/css/estilos.css": STATIC / "css/estilos.css",
        }
        if path not in archivos:
            return self.respuesta({"error": "Recurso no encontrado."}, 404)

        archivo = archivos[path]
        data = archivo.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", (mimetypes.guess_type(str(archivo))[0] or "text/plain") + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    # POST /api/optimizar: recibe la configuración del formulario y lanza el AG.
    def do_POST(self):
        if self.path != "/api/optimizar":
            return self.respuesta({"error": "Recurso no encontrado."}, 404)

        # Solo se aceptan peticiones de la propia página.
        origin = self.headers.get("Origin")
        if origin and origin != f'http://{self.headers.get("Host")}':
            return self.respuesta({"error": "Origen no permitido."}, 403)

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096:
                raise ValueError("Solicitud inválida.")

            entrada = json.loads(self.rfile.read(length))
            if not isinstance(entrada, dict) or set(entrada) - set(CONFIG):
                raise ValueError("Configuración desconocida.")

            # Los valores del formulario reemplazan a los de configuracion.json y se validan.
            config = validar_config(CONFIG | entrada, DATOS)
        except Exception as exc:
            return self.respuesta({"error": str(exc)}, 400)

        with CANDADO:
            if ESTADO["estado"] == "ejecutando":
                return self.respuesta({"error": "Ya hay una ejecución en curso."}, 409)
            ESTADO.update(estado="ejecutando", progreso=None, resultado=None, error=None)

        # El AG corre en otro hilo para que la página siga respondiendo.
        Thread(target=trabajo, args=(config,), daemon=True).start()
        self.respuesta({"estado": "ejecutando"}, 202)

    # Silencia el registro de cada petición en la terminal.
    def log_message(self, formato, *args):
        pass


# ============================================================
# EJECUCIÓN LOCAL
# ============================================================

# Inicia el servidor local en http://127.0.0.1:8765/ (el puerto se puede cambiar con --puerto).
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--puerto", type=int, default=8765)
    args = parser.parse_args()

    # Servidor solo local (127.0.0.1): no queda expuesto a otros equipos.
    servidor = ThreadingHTTPServer(("127.0.0.1", args.puerto), Handler)
    print(f"Rutas Chiclayo: http://127.0.0.1:{args.puerto}", flush=True)

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()

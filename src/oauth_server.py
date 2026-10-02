"""
Servidor HTTP ultraligero para completar la autorización OAuth 2.0
de la cuenta de Camila en la red local.
"""

import sys
import os
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import time

# Asegurar importación del módulo local
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from src.spotify_provider import SpotifyPlaybackProvider

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alexa Lyrics TV — Autorización Spotify</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #121212;
            color: #ffffff;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
        }
        .card {
            background: #1e1e1e;
            padding: 40px;
            border-radius: 16px;
            max-width: 480px;
            text-align: center;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5);
            border: 1px solid #333;
        }
        h1 { font-size: 24px; margin-bottom: 8px; color: #1DB954; }
        p { color: #b3b3b3; line-height: 1.5; font-size: 15px; }
        .btn {
            display: inline-block;
            background: #1DB954;
            color: #000;
            font-weight: 700;
            padding: 14px 28px;
            border-radius: 30px;
            text-decoration: none;
            margin-top: 24px;
            font-size: 16px;
            transition: transform 0.2s, background 0.2s;
        }
        .btn:hover { background: #1ed760; transform: scale(1.04); }
        .badge {
            background: #2a2a2a;
            border: 1px solid #444;
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 12px;
            display: inline-block;
            margin-bottom: 16px;
            color: #ccc;
        }
        .error { color: #ff5555; background: #3a1515; padding: 12px; border-radius: 8px; margin-top: 16px; font-size: 14px; }
        .success { color: #1DB954; font-size: 18px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="card">
        <div class="badge">🎙️ Alexa Lyrics TV — Configuración</div>
        <h1>Conexión con Spotify</h1>
        <p>Esta aplicación vinculará la cuenta <strong>Spotify Premium de Camila</strong> para leer en tiempo real la música que reproduce Alexa en casa.</p>
        {CONTENT}
    </div>
</body>
</html>"""


class OAuthHandler(BaseHTTPRequestHandler):
    provider: SpotifyPlaybackProvider = None

    def log_message(self, format, *args):
        # Log limpio en consola
        sys.stdout.write(f"[OAuthServer] {self.address_string()} - {format % args}\n")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/" or parsed.path == "":
            self._handle_home()
        elif parsed.path == "/callback":
            self._handle_callback(parsed.query)
        elif parsed.path == "/status":
            self._handle_status()
        else:
            self.send_error(404, "Ruta no encontrada")

    def _handle_home(self):
        if not self.provider.client_id or not self.provider.client_secret:
            content = """
            <div class="error">
                ⚠️ Faltan <code>SPOTIFY_CLIENT_ID</code> y/o <code>SPOTIFY_CLIENT_SECRET</code> en el archivo <code>.env</code>.
                <br><br>Por favor agrégalos antes de continuar.
            </div>
            """
        else:
            auth_url = self.provider.get_authorization_url()
            auth_state = "✅ Ya autenticado" if self.provider.is_authenticated() else "⏳ Pendiente de vincular"
            content = f"""
            <p>Estado actual: <strong>{auth_state}</strong></p>
            <a class="btn" href="{auth_url}">Vincular Cuenta de Camila</a>
            """

        html = HTML_TEMPLATE.replace("{CONTENT}", content)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _handle_callback(self, query_string):
        params = urllib.parse.parse_qs(query_string)

        if "error" in params:
            err = params["error"][0]
            content = f"""
            <div class="error">
                ❌ Error devuelto por Spotify: <strong>{err}</strong>.
            </div>
            <a class="btn" href="/">Intentar nuevamente</a>
            """
        elif "code" in params:
            code = params["code"][0]
            try:
                tokens = self.provider.exchange_code_for_tokens(code)
                content = """
                <div class="success">🎉 ¡Autorización Completada con Éxito!</div>
                <p style="margin-top: 16px;">La cuenta de Camila ha sido vinculada correctamente y los tokens se han almacenado de forma segura en el backend local.</p>
                <p>Ya puedes cerrar esta ventana y regresar a la terminal para ejecutar las pruebas con Alexa.</p>
                """
            except Exception as e:
                content = f"""
                <div class="error">
                    ❌ Fallo al intercambiar tokens: {str(e)}
                </div>
                <a class="btn" href="/">Reintentar</a>
                """
        else:
            content = "<div class='error'>Parámetros inválidos recibidos en el callback.</div>"

        html = HTML_TEMPLATE.replace("{CONTENT}", content)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _handle_status(self):
        is_auth = self.provider.is_authenticated()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps({"authenticated": is_auth, "timestamp": time.time()}).encode(
                "utf-8"
            )
        )


def start_oauth_server(port: int = 8888, host: str = "0.0.0.0"):
    provider = SpotifyPlaybackProvider()
    OAuthHandler.provider = provider

    server = HTTPServer((host, port), OAuthHandler)
    local_url = f"http://127.0.0.1:{port}"
    lan_url = f"http://192.168.1.88:{port}"

    print("\n" + "=" * 60)
    print(f"🚀 Servidor OAuth de Spotify iniciado en:")
    print(f"   Local:  {local_url}")
    print(f"   LAN:    {lan_url}")
    print("=" * 60)
    print("Abre esa URL en tu navegador para iniciar la vinculación.")
    print("Presiona Ctrl+C para detener el servidor cuando termines.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor OAuth detenido.")
        server.server_close()


if __name__ == "__main__":
    port = 8888
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    start_oauth_server(port=port)

import os
import sys
import importlib
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import core.router

class MigratorHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Inject zero-cache headers for all static files & responses
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_GET(self):
        importlib.reload(core.router)
        core.router.reload_all()
        if hasattr(core.router, 'dispatch_get') and core.router.dispatch_get(self):
            return
        return super().do_GET()

    def do_POST(self):
        importlib.reload(core.router)
        core.router.reload_all()
        core.router.dispatch_post(self)

    # Serve files from the frontend directory when requesting /
    def translate_path(self, path):
        root = os.path.dirname(os.path.abspath(__file__))
        if path == '/' or path == '':
            return os.path.join(root, 'frontend', 'index.html')
        return os.path.join(root, 'frontend', path.lstrip('/'))

def run(port=8081):
    server_address = ('', port)
    ThreadingHTTPServer.allow_reuse_address = True
    httpd = ThreadingHTTPServer(server_address, MigratorHandler)
    print(f"Starting web server on http://localhost:{port} (Dynamic Zero-Restart Reload Enabled)...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    print("Server stopped.")

if __name__ == '__main__':
    run()

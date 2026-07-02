#!/usr/bin/env python3
import subprocess
import time
import sys
import os

os.chdir(r"C:\Users\vicho\OneDrive\Escritorio\proyectos en desarrollo\proyecto turbohogar")

print("=" * 60)
print("TURBOHOGAR - INICIADOR DE SERVIDORES")
print("=" * 60)
print()

# Web Server
print("[1/2] Iniciando Web Server en puerto 8000...")
try:
    web_proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", "8000"]
    )
    print("[OK] Web Server iniciado (PID: %d)" % web_proc.pid)
except Exception as e:
    print("[ERROR] Web Server: %s" % e)
    sys.exit(1)

time.sleep(2)

# Flask
print("[2/2] Iniciando Flask Motor en puerto 5000...")
try:
    flask_proc = subprocess.Popen(
        [sys.executable, "server.py"]
    )
    print("[OK] Flask Motor iniciado (PID: %d)" % flask_proc.pid)
except Exception as e:
    print("[ERROR] Flask: %s" % e)
    sys.exit(1)

time.sleep(3)

print()
print("=" * 60)
print("[OK] SERVIDORES ACTIVOS")
print("=" * 60)
print()
print("Accede en: http://localhost:8000/turbohogar.html")
print()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nDeteniendo...")
    web_proc.terminate()
    flask_proc.terminate()
    time.sleep(2)

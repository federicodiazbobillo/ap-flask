import socket
import subprocess
import os
import signal
import sys
import time
import platform
from app import create_app  # Importa la factory

PORT = 80

LOG_PATH = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), "launch_debug.log"))


def log(msg):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {msg}\n")

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0

def find_processes_using_port_windows(port):
    try:
        output = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True, text=True)
        lines = output.strip().split('\n')
        pids = set()
        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 5:
                pids.add(int(parts[-1]))
        return list(pids)
    except subprocess.CalledProcessError:
        return []

def find_processes_using_port_unix(port):
    try:
        result = subprocess.check_output(f"lsof -i :{port} -t", shell=True)
        pids = [int(pid) for pid in result.decode().strip().split('\n')]
        return pids
    except subprocess.CalledProcessError:
        return []

def find_processes_using_port(port):
    if platform.system() == "Windows":
        return find_processes_using_port_windows(port)
    else:
        return find_processes_using_port_unix(port)

def kill_process(pid):
    try:
        if platform.system() == "Windows":
            subprocess.call(f"taskkill /PID {pid} /F", shell=True)
        else:
            os.kill(pid, signal.SIGKILL)
        log(f"🛑 Proceso {pid} detenido.")
    except Exception as e:
        log(f"⚠️ Error al intentar matar el proceso {pid}: {e}")

def launch_flask():
    try:
        log("🚀 Iniciando la aplicación Flask en http://127.0.0.1:80")
        app = create_app()
        app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
    except Exception as e:
        log("❌ Error al iniciar Flask:")
        import traceback
        log(traceback.format_exc())

if __name__ == "__main__":
    try:
        if is_port_in_use(PORT):
            pids = find_processes_using_port(PORT)
            log(f"🔍 El puerto {PORT} está ocupado por los procesos: {pids}. Cerrando...")
            for pid in pids:
                kill_process(pid)
            time.sleep(1)
        else:
            log(f"✅ El puerto {PORT} está libre.")

        launch_flask()
    except Exception as e:
        log("❌ Error general al iniciar el sistema:")
        import traceback
        log(traceback.format_exc())

import socket
import subprocess
import os
import signal
import time

PORT = 5000

def find_process_using_port(port):
    """Devuelve el PID del proceso que está usando el puerto, o None si está libre"""
    try:
        result = subprocess.check_output(f"lsof -i :{port} -t", shell=True)
        pid = int(result.decode().strip())
        return pid
    except subprocess.CalledProcessError:
        return None

def kill_process(pid):
    """Mata el proceso por PID"""
    try:
        os.kill(pid, signal.SIGKILL)
        print(f"🛑 Proceso {pid} detenido.")
        time.sleep(1)
    except Exception as e:
        print(f"⚠️ Error al intentar matar el proceso {pid}: {e}")

def launch_flask():
    """Lanza la app Flask"""
    print("🚀 Iniciando la aplicación Flask...")
    subprocess.call(["python3", "run.py"])

if __name__ == "__main__":
    pid = find_process_using_port(PORT)
    if pid:
        print(f"🔍 El puerto {PORT} está ocupado por el proceso {pid}. Cerrando...")
        kill_process(pid)
    else:
        print(f"✅ El puerto {PORT} está libre.")
    
    launch_flask()

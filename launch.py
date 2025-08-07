import socket
import subprocess
import os
import signal
import time

PORT = 5000

def find_processes_using_port(port):
    """Devuelve una lista de PIDs que están usando el puerto"""
    try:
        result = subprocess.check_output(f"lsof -i :{port} -t", shell=True)
        pids = [int(pid) for pid in result.decode().strip().split('\n')]
        return pids
    except subprocess.CalledProcessError:
        return []

def kill_process(pid):
    """Mata un solo proceso"""
    try:
        os.kill(pid, signal.SIGKILL)
        print(f"🛑 Proceso {pid} detenido.")
    except Exception as e:
        print(f"⚠️ Error al intentar matar el proceso {pid}: {e}")

def launch_flask():
    """Lanza la app Flask"""
    print("🚀 Iniciando la aplicación Flask...")
    subprocess.call(["python3", "run.py"])

if __name__ == "__main__":
    pids = find_processes_using_port(PORT)
    if pids:
        print(f"🔍 El puerto {PORT} está ocupado por los procesos: {pids}. Cerrando...")
        for pid in pids:
            kill_process(pid)
        time.sleep(1)
    else:
        print(f"✅ El puerto {PORT} está libre.")
    
    launch_flask()

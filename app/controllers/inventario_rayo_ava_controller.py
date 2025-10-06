# app/controllers/inventario_rayo_ava_controller.py
from flask import Blueprint, render_template, request, redirect, url_for
from app.db import get_conn  # tu helper existente para MySQL
import csv
import io

inventario_bp = Blueprint(
    "inventario_rayo_ava_bp",
    __name__,
    url_prefix="/inventario/rayo-ava",
    # Usamos el loader global de Flask: templates en app/templates/**
    # (no seteamos template_folder acá para evitar rutas relativas raras)
)

# -------------------------
# Utilidades
# -------------------------
def _to_int(value):
    if value is None:
        return 0
    s = str(value).strip().replace(",", "")
    if s == "" or s.lower() == "nan":
        return 0
    try:
        return int(float(s))
    except Exception:
        return 0

def _clip(s, n):
    s = (s or "").strip()
    return s[:n]

# -------------------------
# Rutas
# -------------------------
@inventario_bp.route("/", methods=["GET"])
def index():
    # El template debe estar en: app/templates/inventario/inventario_rayo_ava_cargar.html
    return render_template("inventario/inventario_rayo_ava_cargar.html")

@inventario_bp.route("/cargar", methods=["POST"])
def cargar():
    file = request.files.get("csv_file")
    if not file or file.filename == "":
        # Volvemos al formulario sin mensajes (no usamos flash)
        return redirect(url_for("inventario_rayo_ava_bp.index"))

    # Leer como texto (maneja BOM y fallback a latin-1)
    raw = file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    required = {"Imagen", "Nombre", "SKU", "UPC", "Disponibles", "En inventario", "Apartados"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        print(f"[WARN] CSV inválido. Cabeceras recibidas: {reader.fieldnames}")
        return redirect(url_for("inventario_rayo_ava_bp.index"))

    rows = []
    for i, row in enumerate(reader, start=1):
        sku_raw = (row.get("SKU") or "").strip().replace("-", "")
        if not sku_raw:
            # fila sin SKU -> ignorar
            continue
        try:
            sku = int(sku_raw)
        except ValueError:
            # Si querés soportar alfanuméricos, cambiá la PK en MySQL a VARCHAR y quitá este continue
            print(f"[INFO] SKU alfanumérico/ inválido en fila {i}: {sku_raw}. Se omite.")
            continue

        rows.append((
            sku,
            _clip(row.get("Nombre"), 255),     # defensivo por si el schema tiene VARCHAR(255)
            (row.get("Imagen") or "").strip(),
            _clip(row.get("UPC"), 128),        # defensivo
            _to_int(row.get("Disponibles")),
            _to_int(row.get("En inventario")),
            _to_int(row.get("Apartados")),
        ))

    if not rows:
        print("[INFO] No se encontraron filas válidas para importar.")
        return redirect(url_for("inventario_rayo_ava_bp.index"))

    sql = """
        INSERT INTO inventario_rayo_ava
        (sku, nombre, imagen, upc, disponibles, en_inventario, apartados)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE
            nombre = VALUES(nombre),
            imagen = VALUES(imagen),
            upc = VALUES(upc),
            disponibles = VALUES(disponibles),
            en_inventario = VALUES(en_inventario),
            apartados = VALUES(apartados)
    """

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.executemany(sql, rows)
        conn.commit()
        print(f"[OK] Importación completada. Filas afectadas (insert/update): {cur.rowcount}")
    except Exception as e:
        # Diagnóstico: ejecutar fila por fila para detectar la que rompe
        conn.rollback()
        print(f"[ERROR] executemany falló: {e}")
        for idx, params in enumerate(rows, start=1):
            try:
                cur.execute(sql, params)
            except Exception as e2:
                print(f"[✖] Falla en fila #{idx} con params={params} -> {e2}")
                break
        conn.rollback()
    finally:
        cur.close()

    # PRG: siempre redirigir al GET del formulario
    return redirect(url_for("inventario_rayo_ava_bp.index"))

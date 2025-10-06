from flask import Blueprint, render_template, request, jsonify
from app.db import get_conn
from app.integrations.mercadolibre.services.token_service import verificar_meli
import requests

questions_unanswered_bp = Blueprint(
    "questions_unanswered_bp", __name__,
    url_prefix="/communication/questions/unanswered"
)


# ──────────────────────────────────────────────
# Listar preguntas sin responder
# ──────────────────────────────────────────────
@questions_unanswered_bp.route("/", methods=["GET"])
def index():
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, text, item_id, isbn, status, date_created, answer,
               from_id, answered_questions, updated_at
        FROM questions_meli
        WHERE status = 'UNANSWERED'
        ORDER BY date_created DESC
        LIMIT 50
    """)
    cols = [c[0] for c in cursor.description]
    filas = cursor.fetchall()
    cursor.close()

    unanswered_questions = []
    access_token, user_id, error = verificar_meli()

    for fila in filas:
        q = {col: ('' if val is None else str(val)) for col, val in zip(cols, fila)}

        if q["item_id"] and access_token:
            url = f"https://api.mercadolibre.com/items/{q['item_id']}"
            resp = requests.get(url, headers={"Authorization": f"Bearer {access_token}"})
            if resp.status_code == 200:
                item = resp.json()
                q["item_title"] = item.get("title", "")
                q["item_thumbnail"] = item.get("thumbnail", "")
                q["item_permalink"] = item.get("permalink", "")
                q["item_status"] = item.get("status", "")
                q["manufacturing_time"] = None
                for st in item.get("sale_terms", []):
                    if st.get("id") == "MANUFACTURING_TIME":
                        q["manufacturing_time"] = st.get("value_name")
            else:
                q["item_title"] = ""
                q["item_thumbnail"] = ""
                q["item_permalink"] = ""
                q["item_status"] = ""
                q["manufacturing_time"] = None

        unanswered_questions.append(q)

    return render_template(
        "communication/questions/unanswered.html",
        unanswered_questions=unanswered_questions
    )


# ──────────────────────────────────────────────
# Eliminar pregunta en Meli y marcar en DB
# ──────────────────────────────────────────────
@questions_unanswered_bp.route("/delete/<question_id>", methods=["POST"])
def delete_question(question_id):
    access_token, user_id, error = verificar_meli()
    if not access_token:
        return jsonify({"error": "No access token"}), 401

    url = f"https://api.mercadolibre.com/questions/{question_id}"
    resp = requests.delete(url, headers={"Authorization": f"Bearer {access_token}"})

    if resp.status_code == 200:
        conn = get_conn()
        cur = conn.cursor()
        # Marcamos como eliminado desde el sistema (esperando callback CLOSED_UNANSWERED)
        cur.execute("""
            UPDATE questions_meli
            SET status = 'DELETED_FROM_SYSTEM'
            WHERE id = %s
        """, (question_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True})
    else:
        return jsonify({"error": resp.text}), resp.status_code


# ──────────────────────────────────────────────
# Responder pregunta en Meli y marcar en DB
# ──────────────────────────────────────────────
@questions_unanswered_bp.route("/answer/<question_id>", methods=["POST"])
def answer_question(question_id):
    data = request.get_json()
    answer_text = data.get("text", "").strip()
    if not answer_text:
        return jsonify({"error": "Respuesta vacía"}), 400

    access_token, user_id, error = verificar_meli()
    if not access_token:
        return jsonify({"error": "No access token"}), 401

    # Postear respuesta en Meli
    url = "https://api.mercadolibre.com/answers"
    payload = {"question_id": question_id, "text": answer_text}
    resp = requests.post(url, json=payload,
                         headers={"Authorization": f"Bearer {access_token}"})

    # Log detallado para debug
    print(f"📤 Enviando respuesta a Meli: {payload}")
    print(f"📥 Status {resp.status_code}: {resp.text}")

    if resp.status_code in (200, 201):
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE questions_meli
                SET status = 'ANSWERED_FROM_SYSTEM',
                    answer = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (answer_text, question_id))
            conn.commit()
        finally:
            cur.close()
            # ⚠️ No hacemos conn.close() para que flask_mysqldb maneje el cierre
        return jsonify({"success": True})
    else:
        return jsonify({"error": resp.text}), resp.status_code


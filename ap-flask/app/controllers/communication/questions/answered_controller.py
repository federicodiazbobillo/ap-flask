from flask import Blueprint, render_template
from app.db import get_conn

questions_answered_bp = Blueprint(
    "questions_answered_bp", __name__,
    url_prefix="/communication/questions/answered"
)

@questions_answered_bp.route("/", methods=["GET"])
def index():
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, text, item_id, isbn, status, date_created, answer,
               from_id, answered_questions, updated_at
        FROM questions_meli
        WHERE status = 'ANSWERED'
        ORDER BY updated_at DESC
        LIMIT 50
    """)
    cols = [c[0] for c in cursor.description]
    filas = cursor.fetchall()
    cursor.close()

    answered_questions = [
        {col: ('' if val is None else str(val)) for col, val in zip(cols, fila)}
        for fila in filas
    ]

    return render_template("communication/questions/answered.html", answered_questions=answered_questions)

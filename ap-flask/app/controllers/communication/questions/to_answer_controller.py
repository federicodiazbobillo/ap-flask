from flask import Blueprint, render_template

questions_to_answer_bp = Blueprint(
    "questions_to_answer_bp", __name__,
    url_prefix="/communication/questions/to_answer"
)

@questions_to_answer_bp.route("/", methods=["GET"])
def to_answer():
    return render_template("communication/questions/to_answer.html")

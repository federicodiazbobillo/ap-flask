from flask import Blueprint, render_template

questions_answered_bp = Blueprint(
    "questions_answered_bp", __name__,
    url_prefix="/communication/questions/answered"
)

@questions_answered_bp.route("/", methods=["GET"])
def answered():
    return render_template("communication/questions/answered.html")

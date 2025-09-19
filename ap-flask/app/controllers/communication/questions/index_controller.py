from flask import Blueprint, render_template

questions_index_bp = Blueprint(
    "questions_index_bp", __name__,
    url_prefix="/communication/questions"
)

@questions_index_bp.route("/", methods=["GET"])
def index():
    return render_template("communication/questions/index.html")

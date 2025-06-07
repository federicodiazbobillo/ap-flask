from flask import Blueprint, render_template, session, redirect, url_for

orders_bp = Blueprint('orders', __name__, url_prefix='/orders')

@orders_bp.route('/')
def index():
    if not session.get('user'):
        return redirect(url_for('auth.login'))
    return render_template('orders/index.html')

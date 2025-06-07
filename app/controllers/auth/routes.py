from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.models.users_model import validate_login

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if validate_login(username, password):
            session['user'] = username
            return redirect(url_for('orders.index'))
        else:
            flash("Credenciales inválidas")

    return render_template('login_page.html')

@auth_bp.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('auth.login'))

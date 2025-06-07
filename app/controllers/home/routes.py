from flask import render_template, redirect, session, url_for
from . import home_bp

@home_bp.route('/')
def index():
    if session.get('user'):
        return render_template('home/index.html')
    return redirect(url_for('auth.login'))

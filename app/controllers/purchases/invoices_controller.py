from flask import Blueprint, render_template

# Blueprint with English-named route and endpoint
invoices_bp = Blueprint('invoices_suppliers', __name__, url_prefix='/purchases/invoices_suppliers')

@invoices_bp.route('/')
def index():
    return render_template('purchases/invoices_suppliers.html', tipo='suppliers')

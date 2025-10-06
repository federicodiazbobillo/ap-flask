// static/js/purchases/invoices_suppliers_detail.js
(function () {
  console.debug('[invoices_suppliers_detail.js] cargado');
  console.log("✅ invoices_suppliers_detail.js cargado");
  // ---------- Helpers Bootstrap 4/5 ----------
  function showModal(modalId) {
    const el = document.getElementById(modalId);
    if (!el) return;
    try {
      if (window.bootstrap && window.bootstrap.Modal) {
        // Bootstrap 5
        new bootstrap.Modal(el).show();
      } else if (typeof $ !== 'undefined' && typeof $(el).modal === 'function') {
        // Bootstrap 4
        $(el).modal('show');
      } else {
        // Fallback muy simple
        el.classList.add('show');
        el.style.display = 'block';
        el.removeAttribute('aria-hidden');
      }
    } catch (e) {
      console.warn('No pude abrir el modal con la API de Bootstrap, uso fallback:', e);
      el.classList.add('show');
      el.style.display = 'block';
      el.removeAttribute('aria-hidden');
    }
  }

  // ---------- CSRF opcional ----------
  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta && meta.content ? meta.content : null;
  }

  // ---------- Render tabla de órdenes ----------
  function renderOrdenesTable(ordenes, itemId) {
    if (!Array.isArray(ordenes) || ordenes.length === 0) {
      return '<div class="alert alert-warning mb-0">No se encontraron órdenes para este ISBN.</div>';
    }

    const fmtTotal = (v) => {
      try {
        const n = typeof v === 'number' ? v : parseFloat(v);
        if (isNaN(n)) return v ?? '';
        return n.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      } catch {
        return v ?? '';
      }
    };

    const rows = ordenes.map(o => `
      <tr>
        <td>${o.fecha || '-'}</td>
        <td>#${o.order_id}</td>
        <td>${fmtTotal(o.total)}</td>
        <td>${o.estado || '-'}</td>
        <td>${o.quantity ?? '-'}</td>
        <td>${o.vinculadas ?? 0}</td>
        <td>
          <form method="post" action="/purchases/invoices_suppliers/detail/vincular_orden">
            <input type="hidden" name="item_id" value="${String(itemId || '')}">
            <input type="hidden" name="order_id" value="${String(o.order_id || '')}">
            <button type="submit" class="btn btn-sm btn-primary">Vincular</button>
          </form>
        </td>
      </tr>
    `).join('');

    return `
      <div class="table-responsive">
        <table class="table table-sm table-striped">
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Order ID</th>
              <th>Total</th>
              <th>Estado</th>
              <th>Cant.</th>
              <th>Vinculadas</th>
              <th>Acción</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  }

  // ---------- Delegación de click para .vincular-btn ----------
  document.addEventListener('click', function (e) {
    const btn = e.target.closest('.vincular-btn');
    if (!btn) return;

    e.preventDefault();

    const isbn = btn.dataset.isbn || '';
    const itemId = btn.dataset.itemId || '';
    const body = document.getElementById('modalContenido');
    if (body) body.innerHTML = '<p class="text-muted mb-0">Cargando…</p>';

    // Abrimos el modal de forma compatible (B4/B5)
    showModal('modalOrdenes');

    // Headers + CSRF si existe meta
    const headers = { 'Content-Type': 'application/json' };
    const csrf = getCsrfToken();
    if (csrf) headers['X-CSRFToken'] = csrf;

    fetch('/purchases/invoices_suppliers/detail/buscar_ordenes_por_isbn', {
      method: 'POST',
      headers,
      body: JSON.stringify({ isbn })
    })
      .then(async (r) => {
        const clone = r.clone();
        let data = null;
        try { data = await r.json(); } catch { /* ignore */ }
        if (!r.ok || !Array.isArray(data)) {
          const raw = await clone.text().catch(() => '(sin cuerpo)');
          throw new Error(`HTTP ${r.status}: ${raw}`);
        }
        return data;
      })
      .then((ordenes) => {
        if (body) body.innerHTML = renderOrdenesTable(ordenes, itemId);
      })
      .catch((err) => {
        console.error('Error cargando órdenes:', err);
        if (body) {
          body.innerHTML = `
            <div class="alert alert-danger">
              No se pudieron cargar las órdenes.<br>
              <small>${String(err.message || err)}</small>
            </div>`;
        }
      });
  });
})();

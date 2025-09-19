// static/js/purchases/modal_rayo.js
(function () {
  console.log("✅ modal_rayo.js cargado");

  // ---------- Helper para abrir modal ----------
  function showModal(modalId) {
    const el = document.getElementById(modalId);
    if (!el) {
      console.error("Modal no encontrado:", modalId);
      return;
    }
    if (window.bootstrap && window.bootstrap.Modal) {
      new bootstrap.Modal(el).show(); // Bootstrap 5
    } else if (typeof $ !== "undefined" && $(el).modal) {
      $(el).modal("show"); // Bootstrap 4
    } else {
      el.classList.add("show");
      el.style.display = "block";
      el.removeAttribute("aria-hidden");
    }
  }

  const nroFc = document.querySelector("h3")?.textContent?.replace("Detalle de Factura:", "").trim();
  const btn = document.getElementById("btn-abrir-crear-rayo");
  const body = document.getElementById("modalCrearRayoBody");

  if (!btn) {
    console.warn("⚠️ No se encontró el botón #btn-abrir-crear-rayo");
    return;
  }
  console.log("🔎 Botón Crear Rayo encontrado:", btn);

  // --- helper: límite de concurrencia para pedir títulos ---
  function fetchTitlesWithLimit(pairs, limit = 8) {
    let i = 0, active = 0;
    return new Promise(resolve => {
      function next() {
        if (i >= pairs.length && active === 0) return resolve();
        while (active < limit && i < pairs.length) {
          const [cell, code, tr] = pairs[i++];
          active++;
          fetch(`/purchases/invoices_suppliers/detail/titulo/${encodeURIComponent(code)}`)
            .then(r => r.ok ? r.json() : null)
            .then(d => {
              const title = d && typeof d.title === 'string' && d.title.trim()
                ? d.title.trim()
                : '—';
              cell.textContent = title;
              if (tr) tr.dataset.title = (title === '—' ? '' : title);
            })
            .catch(() => {
              cell.innerHTML = '<span class="text-muted">—</span>';
              if (tr) tr.dataset.title = '';
            })
            .finally(() => { active--; next(); });
        }
      }
      next();
    });
  }

  // --- portadas con fallback ---
  function initCovers(rootEl) {
    const NO_IMAGE_URL = 'https://sys.apricor.com.mx/images/np.jpg';
    const imgs = rootEl.querySelectorAll('img[data-ce-cover]');
    imgs.forEach(img => {
      const upper = img.getAttribute('data-upper') || '';
      const lower = img.getAttribute('data-lower') || '';
      img.dataset.state = 'init';
      function handleError() {
        const st = img.dataset.state;
        if (st === 'init' && lower) {
          img.dataset.state = 'tried-lower';
          img.src = lower;
          return;
        }
        img.dataset.state = 'placeholder';
        img.onerror = null;
        img.src = NO_IMAGE_URL;
      }
      img.onerror = handleError;
      if (upper) {
        img.src = upper;
      } else if (lower) {
        img.dataset.state = 'tried-lower';
        img.src = lower;
      } else {
        img.dataset.state = 'placeholder';
        img.onerror = null;
        img.src = NO_IMAGE_URL;
      }
    });
  }

  // === selección múltiple ===
  let selected = new Set();

  function getModalEl() {
    return document.getElementById('modalCrearRayo');
  }
  function getFooterEl() {
    return getModalEl().querySelector('.modal-footer');
  }
  function ensureCreateButton() {
    const footer = getFooterEl();
    if (!footer.querySelector('#btn-rayo-crear')) {
      const btnCrear = document.createElement('button');
      btnCrear.type = 'button';
      btnCrear.className = 'btn btn-success';
      btnCrear.id = 'btn-rayo-crear';
      btnCrear.disabled = true;
      btnCrear.textContent = 'Crear';
      btnCrear.addEventListener('click', handleCreateClick);
      footer.appendChild(btnCrear);
    }
  }

  function updateMasterAndCounter(container) {
    const counter = container.querySelector('#sel-counter');
    const master  = container.querySelector('#chk-select-all');
    const totalChecks = container.querySelectorAll('tbody input[type="checkbox"].itm').length;
    const count = selected.size;

    if (counter) counter.textContent = 'Seleccionados: ' + count;

    if (master) {
      if (count === 0) {
        master.indeterminate = false; master.checked = false;
      } else if (count === totalChecks) {
        master.indeterminate = false; master.checked = true;
      } else {
        master.indeterminate = true;
      }
    }

    const btnBottom = document.getElementById('btn-rayo-crear');
    const btnTop    = document.getElementById('btn-rayo-crear-top');
    if (btnBottom) btnBottom.disabled = (count === 0);
    if (btnTop)    btnTop.disabled    = (count === 0);
  }

  function buildCheckboxHeader() {
    return `
      <div class="d-flex justify-content-between align-items-center mb-2">
        <div class="custom-control custom-checkbox">
          <input type="checkbox" class="custom-control-input" id="chk-select-all" checked>
          <label class="custom-control-label" for="chk-select-all">Seleccionar todos</label>
        </div>
        <div class="d-flex align-items-center">
          <span id="sel-counter" class="text-muted mr-3">Seleccionados: 0</span>
          <button type="button" class="btn btn-success btn-sm" id="btn-rayo-crear-top">Crear</button>
        </div>
      </div>`;
  }

  function wireCreateButtons() {
    ['btn-rayo-crear', 'btn-rayo-crear-top'].forEach(id => {
      const b = document.getElementById(id);
      if (b) {
        b.onclick = handleCreateClick;
        b.disabled = (selected.size === 0);
      }
    });
  }

  // columna Estado: helpers
  function ensureStatusCell(tr) {
    let cell = tr.querySelector('.col-status');
    if (!cell) {
      cell = document.createElement('td');
      cell.className = 'col-status align-middle';
      tr.appendChild(cell);
    }
    return cell;
  }
  function setRowStatus(tr, kind, codeOrMsg='') {
    const cell = ensureStatusCell(tr);
    if (kind === 'ok') {
      cell.innerHTML = '<span class="text-success" title="Creado correctamente">✔</span>';
    } else if (kind === 'error') {
      const tip = codeOrMsg ? ` (${String(codeOrMsg)})` : '';
      cell.innerHTML = `<span class="text-danger" title="Error${tip}">✘${tip ? ' ' + String(codeOrMsg) : ''}</span>`;
    } else {
      cell.innerHTML = '<span class="text-muted">…</span>';
    }
  }

  function buildRowHtml(it, idx) {
    const raw = String(it.isbn ?? '').trim();
    const digits = raw.replace(/\D+/g, '');
    const prefer = (it.sku_norm && /^\d+$/.test(it.sku_norm)) ? it.sku_norm : digits;

    let coverCell = '<span class="text-muted">—</span>';
    if (/^\d{10,}$/.test(prefer)) {
      const sub = prefer.slice(0, 7);
      const name = prefer.slice(0, -1);
      const upper = `https://www.celesa.com/imagenes/${sub}/${name}.JPG`;
      const lower = `https://www.celesa.com/imagenes/${sub}/${name}.jpg`;
      coverCell = `<img data-ce-cover data-upper="${upper}" data-lower="${lower}" loading="lazy" alt="Portada" style="max-height:64px">`;
    }

    const rowId = `r-${idx}`;
    return `
      <tr id="${rowId}" data-isbn="${raw}" data-code="${prefer}" data-title="">
        <td style="width:40px;">
          <div class="custom-control custom-checkbox">
            <input type="checkbox" class="custom-control-input itm" id="chk-${rowId}" data-row-id="${rowId}" checked>
            <label class="custom-control-label" for="chk-${rowId}"></label>
          </div>
        </td>
        <td><code>${raw}</code></td>
        <td class="col-titulo"><span class="text-muted">Buscando…</span></td>
        <td class="col-cover">${coverCell}</td>
        <td class="col-status"></td>
      </tr>`;
  }

  function wireSelectionHandlers(container) {
    const master = container.querySelector('#chk-select-all');
    master.addEventListener('change', () => {
      selected.clear();
      const checks = container.querySelectorAll('tbody input[type="checkbox"].itm');
      checks.forEach(chk => {
        chk.checked = master.checked;
        if (master.checked) selected.add(chk.dataset.rowId);
      });
      updateMasterAndCounter(container);
    });

    container.querySelector('tbody').addEventListener('change', (e) => {
      if (e.target && e.target.matches('input[type="checkbox"].itm')) {
        const id = e.target.dataset.rowId;
        if (e.target.checked) selected.add(id); else selected.delete(id);
        updateMasterAndCounter(container);
      }
    });
  }

  async function handleCreateClick() {
    const rows = Array.from(body.querySelectorAll('tbody tr'));
    const chosen = rows.filter(r => selected.has(r.id));

    const items = chosen.map(r => {
      const sku = (r.dataset.code || '').trim();
      const titulo = (r.dataset.title || '').trim();
      const img = r.querySelector('img[data-ce-cover]');
      const foto = img ? (img.currentSrc || img.src || '').trim() : '';
      return { sku, titulo: titulo || '', foto };
    });

    if (!items.length) return;

    ['btn-rayo-crear','btn-rayo-crear-top'].forEach(id => {
      const b = document.getElementById(id);
      if (b) { b.disabled = true; b.textContent = 'Procesando...'; }
    });

    chosen.forEach(tr => setRowStatus(tr, 'pending'));

    try {
      const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
      const resp = await fetch(`/purchases/invoices_suppliers/detail/${encodeURIComponent(nroFc)}/rayo/create`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(csrf ? { 'X-CSRFToken': csrf } : {})
        },
        body: JSON.stringify({ nro_fc: nroFc, items })
      });

      const clone = resp.clone();
      let data = null, text = null;
      try { data = await resp.json(); } catch { text = await clone.text().catch(() => '(sin cuerpo)'); }

      if (!resp.ok || !data?.ok) {
        console.error("❌ Error creando en Rayo:", resp.status, text);
        chosen.forEach(tr => setRowStatus(tr, 'error', resp.status));
        return;
      }

      if (Array.isArray(data.results)) {
        data.results.forEach(r => {
          const tr = body.querySelector(`tr[data-code="${(r.sku || '').trim()}"]`);
          if (!tr) return;
          if (r.status === 'ok' || r.status === 'created' || r.status === true) {
            setRowStatus(tr, 'ok');
          } else {
            setRowStatus(tr, 'error', r.code || r.message || 'ERR');
          }
        });
      } else {
        chosen.forEach(tr => setRowStatus(tr, 'ok'));
      }

    } catch (err) {
      console.error('Excepción en fetch:', err);
      chosen.forEach(tr => setRowStatus(tr, 'error', 'NET'));
    } finally {
      ['btn-rayo-crear','btn-rayo-crear-top'].forEach(id => {
        const b = document.getElementById(id);
        if (b) { b.disabled = (selected.size === 0); b.textContent = 'Crear'; }
      });
    }
  }

  // --- abrir modal / cargar faltantes ---
  btn.addEventListener("click", function () {
    console.log("🟩 Click en botón Crear Rayo");
    selected.clear();
    ensureCreateButton();

    body.innerHTML = '<p class="text-muted mb-0">Cargando…</p>';

    // abrir modal explícitamente
    showModal("modalCrearRayo");

    fetch(`/purchases/invoices_suppliers/detail/faltantes/${encodeURIComponent(nroFc)}`)
      .then(async (r) => {
        const text = await r.clone().text();
        console.log("📦 Respuesta faltantes:", r.status, text);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return JSON.parse(text);
      })
      .then((payload) => {
        let items = [];
        if (Array.isArray(payload)) {
          items = payload;
        } else if (payload && typeof payload === 'object') {
          items = payload.items || payload.data || [];
        }
        if (!Array.isArray(items)) items = [];

        if (items.length === 0) {
          body.innerHTML = `<div class="alert alert-success mb-0">No hay productos faltantes en Rayo.</div>`;
          const btnCrear = document.getElementById('btn-rayo-crear');
          if (btnCrear) btnCrear.disabled = true;
          return;
        }

        const rows = items.map((it, idx) => buildRowHtml(it, idx)).join("");

        body.innerHTML = `
          ${buildCheckboxHeader()}
          <div class="table-responsive">
            <table class="table table-sm table-striped mb-0">
              <thead>
                <tr>
                  <th style="width:40px;"></th>
                  <th>ISBN/SKU</th>
                  <th>Título</th>
                  <th>Portada</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>
          </div>`;

        wireSelectionHandlers(body);

        body.querySelectorAll('tbody input[type="checkbox"].itm').forEach(chk => {
          chk.checked = true;
          selected.add(chk.dataset.rowId);
        });
        updateMasterAndCounter(body);

        wireCreateButtons();

        const tbody = body.querySelector('tbody');
        const pairs = Array.from(tbody.querySelectorAll('tr[data-code]')).map((tr) => {
          const cell = tr.querySelector('.col-titulo');
          const code = tr.getAttribute('data-code') || '';
          return [cell, code, tr];
        });
        fetchTitlesWithLimit(pairs, 8).finally(() => {
          updateMasterAndCounter(body);
        });

        initCovers(body);
      })
      .catch((err) => {
        console.error('Fallo al cargar faltantes:', err);
        body.innerHTML = `<div class="alert alert-danger mb-0">Error al cargar faltantes (${err.message}).</div>`;
        const btnCrear = document.getElementById('btn-rayo-crear');
        if (btnCrear) btnCrear.disabled = true;
      });
  });
})();

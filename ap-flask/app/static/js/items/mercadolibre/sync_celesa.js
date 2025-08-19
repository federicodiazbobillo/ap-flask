// static/js/items/mercadolibre/sync_celesa.js
(function () {
  // ---------- Utils ----------
  function qs(sel, ctx) { return (ctx || document).querySelector(sel); }
  function qsa(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

  // Mantener ?tab= en la URL al cambiar de pestaña
  function setURLParam(key, val) {
    const p = new URLSearchParams(window.location.search);
    if (val === null || val === undefined || val === '') p.delete(key);
    else p.set(key, val);
    history.replaceState(null, '', window.location.pathname + '?' + p.toString());
  }

  // ---------- Selección por página (encabezado) ----------
  function wireScope(scope) {
    const head = qs('#check_all_page_' + scope);
    const rows = () => qsa('.row-check-' + scope);

    function syncHeader() {
      const a = rows();
      if (!head) return;
      if (!a.length) {
        head.checked = false;
        head.indeterminate = false;
        return;
      }
      const all = a.every(c => c.checked);
      const some = a.some(c => c.checked);
      head.checked = all;
      head.indeterminate = !all && some;
    }

    if (head && !head.__wired) {
      head.__wired = true;
      head.addEventListener('change', () => {
        rows().forEach(c => { c.checked = head.checked; });
        syncHeader();
      });
    }

    // enlaza los checkboxes de fila (si no estaban enlazados)
    rows().forEach(c => {
      if (!c.__wired) {
        c.__wired = true;
        c.addEventListener('change', syncHeader);
      }
    });

    // estado inicial
    syncHeader();
  }

  // ---------- Selección global (todos los resultados filtrados) ----------
  function setGlobalMode(on) {
    // Deshabilita los controles de selección por página cuando está activo el global
    qsa('#check_all_page_general, #check_all_page_stock, .row-check').forEach(el => {
      el.disabled = on;
    });
    const btn = qs('#btn_mass_action');
    const hint = qs('#sel_hint');
    if (btn) btn.disabled = !on;
    if (hint) hint.style.display = on ? '' : 'none';
  }

  // ---------- Jobs (modal) ----------
  // Si necesitás la parte de jobs, mantenemos el código mínimo sin jQuery.
  const job = {
    modalEl: null, counts: null, lastIdml: null, lastCode: null, bar: null, alert: null, closeBtn: null,
    statusTemplate: null, intId: null
  };

  function openJobModal(title) {
    if (!job.modalEl) {
      job.modalEl = qs('#jobModal');
      job.counts = qs('#jobCounts');
      job.lastIdml = qs('#jobLastIdml');
      job.lastCode = qs('#jobLastCode');
      job.bar = qs('#jobProgressBar');
      job.alert = qs('#jobAlert');
      job.closeBtn = qs('#jobCloseBtn');
      job.statusTemplate = qs('#jobConfig')?.dataset?.statusTemplate || '';
    }
    qs('#jobModalLabel').textContent = title || 'Procesando…';
    job.alert.classList.add('d-none');
    job.bar.style.width = '0%';
    job.bar.textContent = '0%';
    job.counts.textContent = '0 / 0';
    job.lastIdml.textContent = '-';
    job.lastCode.textContent = '-';
    job.closeBtn.setAttribute('disabled', 'disabled');

    // Bootstrap 4 requiere jQuery para los modales. Como alternativa simple:
    job.modalEl.classList.add('show');
    job.modalEl.style.display = 'block';
    job.modalEl.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
    // backdrop básico
    if (!qs('.modal-backdrop')) {
      const bd = document.createElement('div');
      bd.className = 'modal-backdrop fade show';
      document.body.appendChild(bd);
    }
  }
  function closeJobModal() {
    if (!job.modalEl) return;
    job.modalEl.classList.remove('show');
    job.modalEl.style.display = 'none';
    job.modalEl.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open');
    qsa('.modal-backdrop').forEach(el => el.remove());
  }
  function setJobError(msg) {
    job.alert.textContent = msg || 'Error desconocido.';
    job.alert.classList.remove('d-none');
    job.closeBtn.removeAttribute('disabled');
  }
  function pollJob(jobId) {
    if (!job.statusTemplate) return;
    const url = job.statusTemplate.replace('__JOB__', jobId);
    job.intId = setInterval(async () => {
      try {
        const r = await fetch(url, { cache: 'no-store' });
        const js = await r.json();
        const total = js.total || 0;
        const processed = js.processed || 0;
        const ok = js.ok || 0;
        const code = js.code || 0;
        const pct = total > 0 ? Math.round(processed * 100 / total) : 0;

        job.counts.textContent = `${processed} / ${total} (ok: ${ok}, code: ${code})`;
        job.bar.style.width = `${pct}%`;
        job.bar.textContent = `${pct}%`;
        job.lastIdml.textContent = js.last_idml || '-';
        job.lastCode.textContent = js.last_code != null ? js.last_code : '-';

        if (js.unexpected) {
          clearInterval(job.intId);
          setJobError(`Código inesperado ${js.unexpected_code} en ${js.unexpected_idml}`);
        } else if (js.state === 'error') {
          clearInterval(job.intId);
          setJobError(js.message || 'Error durante el proceso');
        } else if (js.done || js.state === 'done') {
          clearInterval(job.intId);
          job.closeBtn.removeAttribute('disabled');
          job.closeBtn.addEventListener('click', closeJobModal, { once: true });
        }
      } catch (e) {
        clearInterval(job.intId);
        setJobError(e?.message || String(e));
      }
    }, 1000);
  }
  async function startJob(startUrl, payload, title) {
    try {
      openJobModal(title);
      const r = await fetch(startUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload || {})
      });
      const js = await r.json();
      if (!r.ok) {
        setJobError(js?.message || js?.error || `Error HTTP ${r.status}`);
        return;
      }
      if (!js.job_id) {
        setJobError('Respuesta inválida (sin job_id).');
        return;
      }
      pollJob(js.job_id);
    } catch (e) {
      setJobError(e?.message || String(e));
    }
  }

  // ---------- Filtros comunes (payload para jobs) ----------
  function getFiltersPayload(extra) {
    const statusesVal = (qs('#filter_statuses')?.value || '').trim();
    const statuses = statusesVal ? statusesVal.split(',').filter(Boolean) : [];
    const isbn_ok = (qs('#filter_isbn_ok')?.value || '').trim() || null;

    const payload = { selected_statuses: statuses, isbn_ok: isbn_ok };
    if (extra) Object.assign(payload, extra);
    return payload;
  }

  // ---------- Init ----------
  document.addEventListener('DOMContentLoaded', () => {
    // Wire selección por página en ambas pestañas
    wireScope('general');
    wireScope('stock');

    // Global “TODOS”
    const checkAllResults = qs('#check_all_results');
    if (checkAllResults) {
      checkAllResults.addEventListener('change', () => setGlobalMode(checkAllResults.checked));
      setGlobalMode(checkAllResults.checked);
    }

    // Mantener ?tab= en URL
    qsa('#syncTabs a[data-tab-target]').forEach(a => {
      a.addEventListener('click', () => {
        const tab = a.getAttribute('data-tab-target') || 'general';
        setURLParam('tab', tab);
        // re-evaluar encabezados al cambiar de pestaña
        setTimeout(() => {
          wireScope('general');
          wireScope('stock');
        }, 0);
      });
    });

    // Botones de jobs (si los usás)
    const btnNormalize = qs('#btnNormalizeApi');
    if (btnNormalize) {
      btnNormalize.addEventListener('click', () => {
        const payload = getFiltersPayload({
          batch_size: parseInt(qs('#batchSize').value || '100', 10),
          process_all: !!qs('#processAll').checked,
          max_items: parseInt(qs('#maxItems').value || '5000', 10)
        });
        startJob(btnNormalize.dataset.startUrl, payload, 'Verificando ISBN…');
      });
    }
    const btnVerify = qs('#btnVerifyApi');
    if (btnVerify) {
      btnVerify.addEventListener('click', () => {
        const payload = getFiltersPayload({
          batch_size: parseInt(qs('#batchSize').value || '100', 10),
          process_all: !!qs('#processAll').checked,
          max_items: parseInt(qs('#maxItems').value || '5000', 10)
        });
        startJob(btnVerify.dataset.startUrl, payload, 'Verificando status…');
      });
    }

    // (Stock) — si tenés botones de stock async, podés agregarlos aquí igual que arriba
  });
})();


// === PATCH: slider en fila mientras "PUTea" y luego muestra código ===
(function () {
  const qs  = (s, c) => (c || document).querySelector(s);
  const qsa = (s, c) => Array.from((c || document).querySelectorAll(s));

  // Helpers existentes a los que nos “enganchamos” si están, o fallback
  function currentScope() {
    const active = document.querySelector('#syncTabs .nav-link.active[data-tab-target]');
    const tab = active ? active.getAttribute('data-tab-target') : (qs('#activeTab')?.value || 'general');
    return (tab === 'stock') ? 'stock' : 'general';
  }
  function isGlobalSelected() {
    const g = qs('#check_all_results');
    return !!(g && g.checked);
  }
  function sleep(ms){ return new Promise(r => setTimeout(r, ms)); }

  // Obtiene los checkboxes “target” según selección global o por página
  function targetCheckboxes() {
    const scope = currentScope();
    const all = qsa('.row-check-' + scope);       // todos los de la página
    if (isGlobalSelected()) return all;           // modo “TODOS los resultados”: mostramos progreso en los visibles
    return all.filter(c => c.checked);            // solo los tildados
  }

  // Cambia la celda del checkbox por un slider “procesando…”
  function putRowInProgress(chk) {
    const td = chk.closest('td');
    if (!td) return;
    const id = (chk.value || chk.dataset.idml || '').replace(/[^A-Za-z0-9_-]/g, '_');
    td.dataset.prev = td.innerHTML; // por si luego querés restaurar
    td.innerHTML =
      `<div class="custom-control custom-switch" style="transform:scale(.9); white-space:nowrap;">
         <input type="checkbox" class="custom-control-input" id="sw_${id}" checked disabled>
         <label class="custom-control-label" for="sw_${id}">Actualizando…</label>
       </div>`;
  }

  // Reemplaza la celda por el código devuelto (badge)
  function putRowResult(chk, code) {
    const td = chk.closest('td');
    if (!td) return;
    let cls = 'secondary';
    if (code === 200) cls = 'success';
    else if (code === 404) cls = 'dark';
    else if (code === 429) cls = 'warning';
    else if (code >= 500) cls = 'danger';
    td.innerHTML = `<span class="badge badge-${cls}">${code}</span>`;
  }

  async function runFakePutOverSelection(btn) {
    const targets = targetCheckboxes();
    if (!targets.length) {
      alert('Seleccioná al menos una fila o tildá “TODOS los resultados”.');
      return;
    }

    // Deshabilito botón durante el proceso
    const oldHTML = btn.innerHTML;
    btn.innerHTML = 'Procesando…';
    btn.disabled = true;

    try {
      // Secuencial para que se note el efecto fila por fila
      for (const chk of targets) {
        putRowInProgress(chk);
        // Emulación del PUT real
        //await sleep(2000);                 // <<<< emula la actualización
        const code = 200;                  // TODO: reemplazar por el código real devuelto por tu endpoint
        putRowResult(chk, code);
      }

      // Si querés hacerlo real después:
      // const resp = await fetch(btn.dataset.putUrl, { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
      // const js = await resp.json();
      // y aplicás js.resultados[id] -> code por cada fila

    } catch (e) {
      alert('Error: ' + (e?.message || String(e)));
    } finally {
      btn.innerHTML = oldHTML;
      btn.disabled = false;
    }
  }

  // Wire de los botones PUT (si existen en el DOM)
  document.addEventListener('DOMContentLoaded', () => {
    const btnPutGeneral = qs('#btn_put_general');
    const btnPutStock   = qs('#btn_put_stock');

    function updateEnabled() {
      const scope = currentScope();
      const inPage = qsa('.row-check-' + scope);
      const anyChecked = inPage.some(c => c.checked);
      const on = isGlobalSelected() || anyChecked;
      if (btnPutGeneral) btnPutGeneral.disabled = !on;
      if (btnPutStock)   btnPutStock.disabled   = !on;
    }

    // Escuchamos cambios de selección para habilitar/deshabilitar
    ['general','stock'].forEach(scope => {
      qsa('.row-check-' + scope).forEach(c => c.addEventListener('change', updateEnabled));
      const head = qs('#check_all_page_' + scope);
      if (head) head.addEventListener('change', updateEnabled);
    });
    const global = qs('#check_all_results');
    if (global) global.addEventListener('change', updateEnabled);
    updateEnabled();

    if (btnPutGeneral) btnPutGeneral.addEventListener('click', () => runFakePutOverSelection(btnPutGeneral));
    if (btnPutStock)   btnPutStock.addEventListener('click',   () => runFakePutOverSelection(btnPutStock));
  });
})();

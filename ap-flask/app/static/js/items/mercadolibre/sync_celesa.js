// static/js/items/mercadolibre/sync_celesa.js
(function () {
  // ---------- Utils ----------
  const qs  = (s, c) => (c || document).querySelector(s);
  const qsa = (s, c) => Array.from((c || document).querySelectorAll(s));
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));

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
        updatePutButtonsEnabled();
      });
    }

    rows().forEach(c => {
      if (!c.__wired) {
        c.__wired = true;
        c.addEventListener('change', () => {
          syncHeader();
          updatePutButtonsEnabled();
        });
      }
    });

    syncHeader();
  }

  // ---------- Selección global (todos los resultados filtrados) ----------
  function setGlobalMode(on) {
    qsa('#check_all_page_general, #check_all_page_stock, .row-check').forEach(el => {
      el.disabled = on;
    });
    const btn = qs('#btn_mass_action');
    const hint = qs('#sel_hint');
    if (btn) btn.disabled = !on;
    if (hint) hint.style.display = on ? '' : 'none';
    updatePutButtonsEnabled();
  }

  // ---------- Jobs (modal) ----------
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

    job.modalEl.classList.add('show');
    job.modalEl.style.display = 'block';
    job.modalEl.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
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
    job.closeBtn.addEventListener('click', closeJobModal, { once: true });
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

  // ---------- PUT por selección ----------
  function currentScope() {
    const active = document.querySelector('#syncTabs .nav-link.active[data-tab-target]');
    const tab = active ? active.getAttribute('data-tab-target') : (qs('#activeTab')?.value || 'general');
    return (tab === 'stock') ? 'stock' : 'general';
  }
  function isGlobalSelected() {
    const g = qs('#check_all_results');
    return !!(g && g.checked);
  }
  function pageTargets() {
    const scope = currentScope();
    const all = qsa('.row-check-' + scope);
    if (isGlobalSelected()) return all;      // UI muestra progreso en visibles
    return all.filter(c => c.checked);
  }
  function putRowInProgress(chk) {
    const td = chk.closest('td');
    if (!td) return;
    const id = (chk.value || chk.dataset.idml || '').replace(/[^A-Za-z0-9_-]/g, '_');
    td.dataset.prev = td.innerHTML;
    td.innerHTML =
      `<div class="custom-control custom-switch" style="transform:scale(.9); white-space:nowrap;">
         <input type="checkbox" class="custom-control-input" id="sw_${id}" checked disabled>
         <label class="custom-control-label" for="sw_${id}">Actualizando…</label>
       </div>`;
  }
  function putRowResult(chk, code) {
    const td = chk.closest('td');
    if (!td) return;
    // Regla: 200 = OK (verde). Cualquier otro => error (rojo).
    const cls = (code === 200) ? 'success' : 'danger';
    td.innerHTML = `<span class="badge badge-${cls}">${String(code)}</span>`;
  }
  function updatePutButtonsEnabled() {
    const btnPutGeneral = qs('#btn_put_general');
    const btnPutStock   = qs('#btn_put_stock');
    const scope = currentScope();
    const inPage = qsa('.row-check-' + scope);
    const anyChecked = inPage.some(c => c.checked);
    const on = isGlobalSelected() || anyChecked;
    if (btnPutGeneral) btnPutGeneral.disabled = !on;
    if (btnPutStock)   btnPutStock.disabled   = !on;
  }

  async function runPutOverSelection(btn) {
    const targets = pageTargets();
    if (!targets.length) {
      alert('Seleccioná al menos una fila o tildá “TODOS los resultados”.');
      return;
    }

    // Deshabilitar botón durante el proceso
    const oldHTML = btn.innerHTML;
    btn.innerHTML = 'Procesando…';
    btn.disabled = true;

    try {
      // Prepara IDs (de las visibles / seleccionadas)
      const ids = [];
      for (const chk of targets) {
        if (chk.value) ids.push(String(chk.value));
      }

      // Poner todas las filas en "Actualizando…"
      targets.forEach(putRowInProgress);

      // Si hay endpoint, lo usamos; si no, emulamos local
      const putUrl = btn.dataset.putUrl;
      let results = null;

      if (putUrl) {
        // Enviamos también flags por si luego el backend quiere procesar TODO el filtro
        const payload = {
          ids,
          process_all: isGlobalSelected(),
          filters: getFiltersPayload()
        };
        // Emulación de tiempo de proceso
        await sleep(2000);
        const r = await fetch(putUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const js = await r.json().catch(() => ({}));
        if (!r.ok) {
          // Si el server devolvió error, marcamos todas las filas como error con el status HTTP
          results = Object.fromEntries(ids.map(i => [i, r.status || 500]));
        } else {
          results = (js && js.results) ? js.results : Object.fromEntries(ids.map(i => [i, 200]));
        }
      } else {
        // Modo emulación local (2s + 200)
        await sleep(2000);
        results = Object.fromEntries(ids.map(i => [i, 200]));
      }

      // Pintar resultados
      for (const chk of targets) {
        const id = String(chk.value || chk.dataset.idml || '');
        const code = (id && results && (id in results)) ? results[id] : 'ERR';
        putRowResult(chk, code);
      }

    } catch (e) {
      alert('Error: ' + (e?.message || String(e)));
      // En caso de error global, marcamos visibles como error
      pageTargets().forEach(chk => putRowResult(chk, 'ERR'));
    } finally {
      btn.innerHTML = oldHTML;
      btn.disabled = false;
    }
  }

  // ---------- Init ----------
  document.addEventListener('DOMContentLoaded', () => {
    // Wire selección por página
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
        setTimeout(() => {
          wireScope('general');
          wireScope('stock');
          updatePutButtonsEnabled();
        }, 0);
      });
    });

    // Botones de jobs (si están)
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

    // Botones PUT
    const btnPutGeneral = qs('#btn_put_general');
    const btnPutStock   = qs('#btn_put_stock');
    if (btnPutGeneral) btnPutGeneral.addEventListener('click', () => runPutOverSelection(btnPutGeneral));
    if (btnPutStock)   btnPutStock.addEventListener('click',   () => runPutOverSelection(btnPutStock));

    updatePutButtonsEnabled();
  });
})();

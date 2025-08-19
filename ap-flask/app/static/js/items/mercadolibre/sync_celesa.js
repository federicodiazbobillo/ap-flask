// static/js/items/mercadolibre/sync_celesa.js

(function () {
  function qs(sel, ctx) { return (ctx || document).querySelector(sel); }
  function qsa(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

  // --- Helpers URL ---
  function getURLParams() {
    const p = new URLSearchParams(window.location.search);
    return p;
  }
  function setURLParam(key, val) {
    const p = getURLParams();
    if (val === null || val === undefined || val === '') p.delete(key);
    else p.set(key, val);
    history.replaceState(null, '', window.location.pathname + '?' + p.toString());
  }

  // --- Lee filtros actuales dejados por el server ---
  function getFiltersPayload(extra) {
    const statusesVal = (qs('#filter_statuses')?.value || '').trim();
    const statuses = statusesVal ? statusesVal.split(',').filter(Boolean) : [];
    const isbn_ok = (qs('#filter_isbn_ok')?.value || '').trim() || null;

    const payload = {
      selected_statuses: statuses,
      isbn_ok: isbn_ok,
    };
    if (extra) Object.assign(payload, extra);
    return payload;
  }

  // --- Modal & polling de jobs (reusado) ---
  const job = {
    modal: null,
    counts: null,
    lastIdml: null,
    lastCode: null,
    bar: null,
    alert: null,
    closeBtn: null,
    statusTemplate: null,
    intId: null
  };

  function openJobModal(title) {
    if (!job.modal) {
      job.modal = $('#jobModal');
      job.counts = qs('#jobCounts');
      job.lastIdml = qs('#jobLastIdml');
      job.lastCode = qs('#jobLastCode');
      job.bar = qs('#jobProgressBar');
      job.alert = qs('#jobAlert');
      job.closeBtn = $('#jobCloseBtn');
      job.statusTemplate = qs('#jobConfig')?.dataset?.statusTemplate || '';
    }
    $('#jobModalLabel').text(title || 'Procesando…');
    job.alert.classList.add('d-none');
    job.bar.style.width = '0%';
    job.bar.textContent = '0%';
    job.counts.textContent = '0 / 0';
    job.lastIdml.textContent = '-';
    job.lastCode.textContent = '-';
    job.closeBtn.prop('disabled', true);
    job.modal.modal('show');
  }

  function setJobError(msg) {
    job.alert.textContent = msg || 'Error desconocido.';
    job.alert.classList.remove('d-none');
    job.closeBtn.prop('disabled', false);
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
          job.closeBtn.prop('disabled', false);
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
        headers: {'Content-Type': 'application/json'},
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

  // --- Botones (Generales) ---
  const btnNormalize = qs('#btnNormalizeApi');
  if (btnNormalize) {
    btnNormalize.addEventListener('click', () => {
      const batchSize = parseInt(qs('#batchSize').value || '100', 10);
      const processAll = !!qs('#processAll').checked;
      const payload = getFiltersPayload({
        batch_size: batchSize,
        process_all: processAll,
        max_items: parseInt(qs('#maxItems').value || '5000', 10)
      });
      startJob(btnNormalize.dataset.startUrl, payload, 'Verificando ISBN…');
    });
  }

  const btnVerify = qs('#btnVerifyApi');
  if (btnVerify) {
    btnVerify.addEventListener('click', () => {
      const batchSize = parseInt(qs('#batchSize').value || '100', 10);
      const processAll = !!qs('#processAll').checked;
      const payload = getFiltersPayload({
        batch_size: batchSize,
        process_all: processAll,
        max_items: parseInt(qs('#maxItems').value || '5000', 10)
      });
      startJob(btnVerify.dataset.startUrl, payload, 'Verificando status…');
    });
  }

  // --- Botones (Stock) ---
  const btnStockPush = qs('#btnStockPush');
  if (btnStockPush) {
    btnStockPush.addEventListener('click', () => {
      const payload = getFiltersPayload({
        batch_size: parseInt(qs('#stockBatchSize').value || '100', 10),
        process_all: !!qs('#stockProcessAll').checked,
        max_items: parseInt(qs('#stockMaxItems').value || '5000', 10)
      });
      startJob(btnStockPush.dataset.startUrl, payload, 'Subiendo stock a ML…');
    });
  }

  const btnStockPull = qs('#btnStockPull');
  if (btnStockPull) {
    btnStockPull.addEventListener('click', () => {
      const payload = getFiltersPayload({
        batch_size: parseInt(qs('#stockBatchSize').value || '100', 10),
        process_all: !!qs('#stockProcessAll').checked,
        max_items: parseInt(qs('#stockMaxItems').value || '5000', 10)
      });
      startJob(btnStockPull.dataset.startUrl, payload, 'Trayendo stock desde ML…');
    });
  }

  const btnStockSync = qs('#btnStockSync');
  if (btnStockSync) {
    btnStockSync.addEventListener('click', () => {
      const payload = getFiltersPayload({
        batch_size: parseInt(qs('#stockBatchSize').value || '100', 10),
        process_all: !!qs('#stockProcessAll').checked,
        max_items: parseInt(qs('#stockMaxItems').value || '5000', 10)
      });
      startJob(btnStockSync.dataset.startUrl, payload, 'Reconciliando diferencias…');
    });
  }

  // --- Check ALL (hint) ---
  const checkAll = qs('#check_all_results');
  const btnMass = qs('#btn_mass_action');
  const selHint = qs('#sel_hint');
  if (checkAll && btnMass && selHint) {
    checkAll.addEventListener('change', () => {
      const on = checkAll.checked;
      btnMass.disabled = !on;
      selHint.style.display = on ? '' : 'none';
    });
  }

  // --- Pestaña activa en URL (para recarga/deeplink) ---
  qsa('[data-tab-target]').forEach(a => {
    a.addEventListener('click', () => {
      const tab = a.getAttribute('data-tab-target') || 'general';
      setURLParam('tab', tab);
    });
  });

  // Inicial: si hay #activeTab forzamos el estado visual (por si el HTML no lo dejó activo)
  const initialTab = (qs('#activeTab')?.value || 'general');
  if (initialTab === 'stock') {
    $('#tablink-stock').tab('show');
  } else {
    $('#tablink-general').tab('show');
  }

})();

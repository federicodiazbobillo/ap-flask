// static/js/items/mercadolibre/sync_celesa.js
(function () {
  function boot() {
    // ===== Helpers DOM =====
    function qs(sel, ctx) { return (ctx || document).querySelector(sel); }
    function qsa(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

    // ===== Helpers URL =====
    function getURLParams() { return new URLSearchParams(window.location.search); }
    function setURLParam(key, val) {
      const p = getURLParams();
      if (val === null || val === undefined || val === '') p.delete(key);
      else p.set(key, val);
      history.replaceState(null, '', window.location.pathname + '?' + p.toString());
    }

    // ===== Filtros actuales (server → JS) =====
    function getFiltersPayload(extra) {
      const statusesVal = (qs('#filter_statuses')?.value || '').trim();
      const statuses = statusesVal ? statusesVal.split(',').filter(Boolean) : [];
      const isbn_ok = (qs('#filter_isbn_ok')?.value || '').trim() || null;
      const payload = { selected_statuses: statuses, isbn_ok: isbn_ok };
      if (extra) Object.assign(payload, extra);
      return payload;
    }

    // ================== JOB MODAL + POLLING (igual que tenías) ==================
    const job = {
      modal: null, counts: null, lastIdml: null, lastCode: null,
      bar: null, alert: null, closeBtn: null, statusTemplate: null, intId: null
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

    // ================== Botones “Generales” (igual que tenías) ==================
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

    // ================== NUEVO: Selección por fila / página / TODOS ==================
    const $checkAllResults = $('#check_all_results');  // checkbox global (todos los resultados filtrados)
    const $checkPage = $('#check_page');               // checkbox de cabecera (esta página)
    const $rowChecks = $('.row-check');                // checkbox por fila (esta página)
    const $btnMass = $('#btn_mass_action');
    const selHint = qs('#sel_hint');
    const totalResults = parseInt((qs('#sel_total')?.value || `${qs('#total_count')?.value || 0}`), 10) || (parseInt(qs('.total-count')?.textContent || '0', 10) || 0) || 0;
    // ^^^ si no tenés #sel_total/#total_count, no pasa nada: el hint igual funciona.

    // helpers selección
    function pageAllChecked() {
      if ($rowChecks.length === 0) return false;
      for (const el of $rowChecks.toArray()) if (!el.checked) return false;
      return true;
    }
    function pageAnyChecked() {
      for (const el of $rowChecks.toArray()) if (el.checked) return true;
      return false;
    }
    function selectedIdsOnPage() {
      return $rowChecks.toArray()
        .filter(el => el.checked)
        .map(el => el.getAttribute('data-idml'))
        .filter(Boolean);
    }
    function updateMassUI() {
      // Si está activo “todos los resultados”, ignoramos los de la página
      if ($checkAllResults.prop('checked')) {
        $btnMass.prop('disabled', false);
        if (selHint) selHint.style.display = '';
        // opcional: desactivar visualmente los de la página
        $checkPage.prop('checked', false);
        return;
      }
      // Modo selección por página
      if (selHint) selHint.style.display = 'none';
      // El header se marca solo si todas las filas están marcadas
      $checkPage.prop('checked', pageAllChecked());
      // Habilitar botón si hay al menos 1 seleccionado en la página
      $btnMass.prop('disabled', !pageAnyChecked());
    }

    // Eventos
    if ($checkAllResults.length) {
      $checkAllResults.on('change', function () {
        if (this.checked) {
          // Desmarca selección por página para no confundir
          $checkPage.prop('checked', false);
          $rowChecks.prop('checked', false);
        }
        updateMassUI();
      });
    }

    if ($checkPage.length) {
      $checkPage.on('change', function () {
        // Cambia todos los de la página y desactiva “todos los resultados”
        $checkAllResults.prop('checked', false);
        $rowChecks.prop('checked', this.checked);
        updateMassUI();
      });
    }

    if ($rowChecks.length) {
      $rowChecks.on('change', function () {
        // Cualquier cambio en la página desactiva “todos los resultados”
        $checkAllResults.prop('checked', false);
        updateMassUI();
      });
    }

    // Botón acción masiva (placeholder: muestra qué se seleccionó)
    if ($btnMass.length) {
      $btnMass.on('click', function () {
        if ($checkAllResults.prop('checked')) {
          // Modo “todos los resultados del filtro”
          const msg = totalResults
            ? `Se aplicará la acción a TODOS los ${totalResults} resultados del filtro actual.`
            : 'Se aplicará la acción a TODOS los resultados del filtro actual.';
          alert(msg);
        } else {
          // Modo “esta página”
          const ids = selectedIdsOnPage();
          if (ids.length === 0) {
            alert('No hay filas seleccionadas en esta página.');
            return;
          }
          alert(`Se aplicará la acción a ${ids.length} ítems de esta página:\n\n${ids.join(', ')}`);
        }
        // acá después disparás tu POST real…
      });
    }

    // Estado inicial UI
    updateMassUI();

    // ================== Tabs: mantener ?tab= en URL ==================
    const tabs = document.querySelectorAll('#syncTabs a[data-tab-target]');
    const sharedForm = document.getElementById('sharedFiltersForm');
    const sharedTabInput = document.getElementById('sharedTab');

    function currentTab() {
      const active = document.querySelector('#syncTabs .nav-link.active[data-tab-target]');
      return active ? active.getAttribute('data-tab-target') : (document.getElementById('activeTab')?.value || 'general');
    }
    function syncSharedTab() { if (sharedTabInput) sharedTabInput.value = currentTab(); }

    // Al cargar, reflejar pestaña
    syncSharedTab();

    // Cambiar ?tab= al cambiar de pestaña (BS4)
    $(tabs).on('shown.bs.tab', function (e) {
      const tab = e.target.getAttribute('data-tab-target') || 'general';
      const url = new URL(window.location.href);
      url.searchParams.set('tab', tab);
      window.history.replaceState({}, '', url.toString());
      syncSharedTab();
    });

    if (sharedForm) {
      sharedForm.addEventListener('submit', function () { syncSharedTab(); });
    }

    // Forzar visual inicial según hidden #activeTab (BS4)
    const initialTab = (qs('#activeTab')?.value || 'general');
    if (initialTab === 'stock') {
      $('#tablink-stock').tab('show');
    } else {
      $('#tablink-general').tab('show');
    }
  }

  // Esperar jQuery (evita "$ is not defined")
  if (window.jQuery) {
    boot();
  } else {
    const iv = setInterval(() => {
      if (window.jQuery) { clearInterval(iv); boot(); }
    }, 50);
  }
})();

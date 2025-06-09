document.addEventListener("DOMContentLoaded", function () {
    const statusBox = document.getElementById('sync-status');

    function showStatus(message, color) {
        statusBox.style.display = 'block';
        statusBox.textContent = message;
        statusBox.className = 'alert alert-' + color;
    }

    document.getElementById('btn-sync-all')?.addEventListener('click', () => {
        showStatus("Sincronizando todo...", "primary");
        fetch('/meli/sync/all')
            .then(res => res.json())
            .then(data => showStatus("✅ Sincronización completa", "success"))
            .catch(err => showStatus("❌ Error en la sincronización", "danger"));
    });

    document.getElementById('btn-sync-month')?.addEventListener('click', () => {
        showStatus("Sincronizando último mes...", "success");
        fetch('/meli/sync/month')
            .then(res => res.json())
            .then(data => showStatus("✅ Sincronización mensual completa", "success"))
            .catch(err => showStatus("❌ Error en la sincronización", "danger"));
    });

    document.getElementById('btn-sync-48h')?.addEventListener('click', () => {
        showStatus("Sincronizando últimas 48 horas...", "warning");
        fetch('/meli/sync/last48h')
            .then(res => res.json())
            .then(data => showStatus("✅ Sincronización 48h completa", "success"))
            .catch(err => showStatus("❌ Error en la sincronización", "danger"));
    });
});

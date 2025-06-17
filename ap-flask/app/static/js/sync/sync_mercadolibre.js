document.addEventListener("DOMContentLoaded", function () {
    const statusBox = document.getElementById('sync-status');

    function showStatus(message, color) {
        statusBox.style.display = 'block';
        statusBox.textContent = message;
        statusBox.className = 'alert alert-' + color;
    }

    // Sincronizar todo
    document.getElementById('btn-sync-all')?.addEventListener('click', () => {
        showStatus("Sincronizando todo...", "primary");
        fetch('/sync/mercadolibre/sync')
            .then(res => res.json())
            .then(data => showStatus("✅ Sincronización completa", "success"))
            .catch(err => showStatus("❌ Error en la sincronización", "danger"));
    });

    // Sincronizar último mes
    document.getElementById('btn-sync-month')?.addEventListener('click', () => {
        showStatus("Sincronizando último mes...", "success");
        fetch('/sync/mercadolibre/sync?period=month')
            .then(res => res.json())
            .then(data => showStatus("✅ Sincronización mensual completa", "success"))
            .catch(err => showStatus("❌ Error en la sincronización", "danger"));
    });

    // Sincronizar últimas 48h
    document.getElementById('btn-sync-48h')?.addEventListener('click', () => {
        showStatus("Sincronizando últimas 48 horas...", "warning");
        fetch('/sync/mercadolibre/sync?period=48h')
            .then(res => res.json())
            .then(data => showStatus("✅ Sincronización 48h completa", "success"))
            .catch(err => showStatus("❌ Error en la sincronización", "danger"));
    });
});

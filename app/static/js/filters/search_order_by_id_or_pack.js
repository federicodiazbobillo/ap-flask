document.addEventListener("DOMContentLoaded", function () {
    const btn = document.getElementById('btn-sincronizar-id');
    if (!btn) return;

    btn.addEventListener('click', function () {
        const id = document.getElementById('input-order-id').value.trim();
        if (!id) {
            alert("Por favor ingrese un ID");
            return;
        }

        fetch(`/orders/logistica/buscar?id=${id}`)
            .then(res => res.json())
            .then(data => {
                if (data.order) {
                    console.log("Orden encontrada:", data);
                    alert(`✅ Orden encontrada en campo "${data.coincidencia_en}"`);
                } else {
                    alert("❌ No se encontró la orden.");
                }
            })
            .catch(error => {
                console.error("Error en la búsqueda:", error);
                alert("⚠️ Error al buscar la orden.");
            });
    });
});

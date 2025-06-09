document.addEventListener("DOMContentLoaded", function () {
    const btnBuscar = document.getElementById('btn-buscar-id');
    const inputId = document.getElementById('input-order-id-busqueda');
    const tabla = document.getElementById('tabla-ordenes');

    if (!btnBuscar || !inputId || !tabla) return;

    btnBuscar.addEventListener('click', function () {
        const valorId = inputId.value.trim();
        if (!valorId) {
            alert("Por favor ingrese un ID de orden o pack.");
            return;
        }

        const url = `/orders/logistica/buscar?id=${valorId}`;

        fetch(url)
            .then(res => res.json())
            .then(data => {
                const tbody = tabla.querySelector('tbody');
                tbody.innerHTML = '';

                if (data.order) {
                    const orden = data.order;
                    const items = orden.items || [];

                    const fila = document.createElement('tr');
                    fila.innerHTML = `
                        <td>${orden.order_id}</td>
                        <td>${orden.created_at ? new Date(orden.created_at).toLocaleString() : '-'}</td>
                        <td>$${parseFloat(orden.total_amount || 0).toFixed(2)}</td>
                        <td>${orden.status || '-'}</td>
                        <td>${orden.shipping && orden.shipping.list_cost ? '$' + parseFloat(orden.shipping.list_cost).toFixed(2) : '-'}</td>
                        <td>
                            ${items.length > 0 ? `
                            <table class="table table-sm table-bordered mb-0">
                                <thead class="bg-light">
                                    <tr>
                                        <th>ID</th>
                                        <th>SKU</th>
                                        <th>Cant.</th>
                                        <th>Días Fab.</th>
                                        <th>Comisión</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${items.map(item => `
                                        <tr>
                                            <td>${item.item_id}</td>
                                            <td>${item.seller_sku || '-'}</td>
                                            <td>${item.quantity}</td>
                                            <td>${item.manufacturing_days || 0}</td>
                                            <td>$${parseFloat(item.sale_fee || 0).toFixed(2)}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>` : '-'}
                        </td>
                    `;
                    tbody.appendChild(fila);
                } else {
                    alert("❌ No se encontró la orden.");
                }
            })
            .catch(error => {
                console.error("Error al buscar:", error);
                alert("Ocurrió un error al buscar la orden.");
            });
    });
});

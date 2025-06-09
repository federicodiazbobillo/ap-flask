document.addEventListener("DOMContentLoaded", function () {
    const btnSearch = document.getElementById('btn-buscar-id');
    const btnClear = document.getElementById('btn-limpiar-filtros');
    const inputId = document.getElementById('input-order-id-busqueda');
    const table = document.getElementById('tabla-ordenes');

    if (!btnSearch || !inputId || !table) return;

    // Buscar por ID
    btnSearch.addEventListener('click', function () {
        const id = inputId.value.trim();
        if (!id) {
            alert("Por favor ingrese un ID de orden o pack.");
            return;
        }

        fetch(`/orders/logistica/search?id=${id}`)
            .then(res => res.json())
            .then(data => renderOrders(data.orders))
            .catch(error => {
                console.error("Error al buscar:", error);
                alert("Ocurrió un error al buscar la orden.");
            });
    });

    // Limpiar filtros
    if (btnClear) {
        btnClear.addEventListener('click', function () {
            inputId.value = "";

            fetch('/orders/logistica/search')
                .then(res => res.json())
                .then(data => renderOrders(data.orders))
                .catch(error => {
                    console.error("Error al restaurar órdenes:", error);
                    alert("Ocurrió un error al restaurar la tabla.");
                });
        });
    }

    function renderOrders(orders) {
        const tbody = table.querySelector('tbody');
        tbody.innerHTML = '';

        if (!orders || orders.length === 0) {
            alert("No se encontraron órdenes.");
            return;
        }

        orders.forEach(order => {
            const items = order.items || [];

            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${order.order_id}</td>
                <td>${order.created_at ? new Date(order.created_at).toLocaleString() : '-'}</td>
                <td>$${parseFloat(order.total_amount || 0).toFixed(2)}</td>
                <td>${order.status || '-'}</td>
                <td>${order.shipping && order.shipping.list_cost ? '$' + parseFloat(order.shipping.list_cost).toFixed(2) : '-'}</td>
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
            tbody.appendChild(row);
        });
    }
});

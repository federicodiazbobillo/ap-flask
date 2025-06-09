// static/js/filtros_aplicados/costos_filtros.js

document.addEventListener("DOMContentLoaded", () => {
  const btnSearch = document.getElementById('btn-buscar-id');
  const btnClear  = document.getElementById('btn-limpiar-filtros');
  const input     = document.getElementById('input-order-id-busqueda');
  const table     = document.getElementById('tabla-ordenes');

  if (!btnSearch || !btnClear || !input || !table) return;

  function renderOrders(orders) {
    const tbody = table.querySelector('tbody');
    tbody.innerHTML = '';
    if (!orders.length) {
      alert("No se encontraron órdenes.");
      return;
    }
    orders.forEach(order => {
      const items = order.items || [];
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${order.order_id}</td>
        <td>${order.created_at ? new Date(order.created_at).toLocaleString() : '-'}</td>
        <td>$${parseFloat(order.total_amount||0).toFixed(2)}</td>
        <td>${order.status||'-'}</td>
        <td>${order.shipping?.list_cost ? '$'+parseFloat(order.shipping.list_cost).toFixed(2) : '-'}</td>
        <td>${
          items.length
            ? `<table class="table table-sm table-bordered mb-0">
                 <thead><tr>
                   <th>ID</th><th>SKU</th><th>Cant.</th><th>Días Fab.</th><th>Comisión</th>
                 </tr></thead>
                 <tbody>${
                   items.map(i=>`
                     <tr>
                       <td>${i.item_id}</td>
                       <td>${i.seller_sku||'-'}</td>
                       <td>${i.quantity}</td>
                       <td>${i.manufacturing_days||0}</td>
                       <td>$${parseFloat(i.sale_fee||0).toFixed(2)}</td>
                     </tr>
                   `).join('')
                 }</tbody>
               </table>`
            : `-`
        }</td>
      `;
      tbody.appendChild(row);
    });
  }

  // buscar
  btnSearch.addEventListener('click', () => {
    const id = input.value.trim();
    if (!id) return alert("Por favor ingrese un ID.");
    fetch(`/orders/costos/search?id=${id}`)
      .then(r => r.json())
      .then(data => renderOrders(data.orders))
      .catch(e => alert("Error al buscar."));
  });

  // limpiar
  btnClear.addEventListener('click', () => {
    input.value = '';
    fetch('/orders/costos/search')
      .then(r => r.json())
      .then(data => renderOrders(data.orders))
      .catch(e => alert("Error al restaurar."));
  });
});

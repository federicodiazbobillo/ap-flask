document.addEventListener('DOMContentLoaded', () => {
    const mostrarModal = () => $('#modalCargando').modal('show');
    const ocultarModal = () => $('#modalCargando').modal('hide');

    const mostrarMensajeExito = (mensaje) => {
        const div = document.getElementById('mensaje-exito');
        if (div) {
            div.innerHTML = `<div class="card-body">${mensaje}</div>`;
            div.style.display = 'block';
            setTimeout(() => {
                div.style.display = 'none';
            }, 4000);
        }
    };

    const manejarRespuesta = (res) => {
        ocultarModal();
        if (res.error) {
            alert(res.message || '❌ Error al sincronizar.');
        } else {
            console.log(res);
            mostrarMensajeExito(res.message || '✅ Sincronización exitosa.');
        }
    };

    // 🔁 Todo
    const btnTodo = document.getElementById('btn-sincronizar-todo');
    if (btnTodo) {
        btnTodo.addEventListener('click', (e) => {
            e.preventDefault();
            mostrarModal();
            fetch('/ordenes/sincronizar')
                .then(res => res.json())
                .then(manejarRespuesta)
                .catch(err => {
                    ocultarModal();
                    alert('❌ Error al sincronizar todas las órdenes.');
                    console.error(err);
                });
        });
    }

    // 📅 Último mes
    const btnMes = document.getElementById('btn-sincronizar-mes');
    if (btnMes) {
        btnMes.addEventListener('click', (e) => {
            e.preventDefault();
            mostrarModal();
            fetch('/ordenes/sincronizar?periodo=mes')
                .then(res => res.json())
                .then(manejarRespuesta)
                .catch(err => {
                    ocultarModal();
                    alert('❌ Error al sincronizar últimas órdenes del mes.');
                    console.error(err);
                });
        });
    }

    // ⏱️ Últimas 48h
    const btn48h = document.getElementById('btn-sincronizar-48h');
    if (btn48h) {
        btn48h.addEventListener('click', (e) => {
            e.preventDefault();
            mostrarModal();
            fetch('/ordenes/sincronizar?periodo=48h')
                .then(res => res.json())
                .then(manejarRespuesta)
                .catch(err => {
                    ocultarModal();
                    alert('❌ Error al sincronizar últimas 48h.');
                    console.error(err);
                });
        });
    }

    // 🔍 Por ID
    const btnId = document.getElementById('btn-sincronizar-id');
    if (btnId) {
        btnId.addEventListener('click', () => {
            const orderId = document.getElementById('input-order-id').value.trim();
            if (!orderId) {
                alert('⚠️ Debes ingresar un ID de orden válido');
                return;
            }

            mostrarModal();
            fetch(`/ordenes/sincronizar?id=${orderId}`)
                .then(res => res.json())
                .then(manejarRespuesta)
                .catch(err => {
                    ocultarModal();
                    alert('❌ Error inesperado al sincronizar orden.');
                    console.error(err);
                });
        });
    }
});
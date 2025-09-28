$(function() {
  // Función para cargar contenido en cada pestaña
  function loadTabContent(tabId, url) {
    const container = $(tabId);
    container.html('<div class="spinner-border text-primary" role="status"></div>');
    $.get(url, function(data) {
      container.html(data);
    }).fail(function(xhr) {
      container.html(
        '<p class="text-danger">❌ Error al cargar contenido: ' + xhr.status + '</p>'
      );
    });
  }

  // Precargar "Pendientes" al inicio
  loadTabContent("#pending", "/communication/questions/unanswered/");

  // Precargar "Respondidas" al inicio (si no querés, comentá esta línea)
  loadTabContent("#answered", "/communication/questions/answered/");

  // Cuando el usuario cambia de pestaña, refresca el contenido
  $('a[data-toggle="tab"]').on("shown.bs.tab", function(e) {
    const target = $(e.target).attr("href"); // #stats, #pending, #answered
    if (target === "#pending") {
      loadTabContent("#pending", "/communication/questions/unanswered/");
    } else if (target === "#answered") {
      loadTabContent("#answered", "/communication/questions/answered/");
    }
  });
});

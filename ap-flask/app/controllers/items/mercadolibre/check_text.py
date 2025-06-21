import re

def contiene_datos_contacto(texto: str) -> bool:
    if not texto:
        return False

    patrones = [
        r'@',                    # mails o redes
        r'\.com',
        r'\.org',
        r'\.net',                                  # dominios
        r'https?:\/\/',          # URLs con protocolo
        r'www\.',                # URLs sin protocolo
        r'tel[:\s]*\+?\d+',      # teléfono explícito
        r'\.ar\b',               # dominio local
        r'facebook\.com|instagram\.com|tiktok\.com'  # redes comunes
    ]

    for patron in patrones:
        if re.search(patron, texto, re.IGNORECASE):
            return True
    return False


def validar_campos_textuales_meli(data_item: dict) -> bool:
    textos = []

    # Campo title
    title = data_item.get("title", "")
    textos.append(title)

    # Campo attributes (value_name)
    atributos = data_item.get("attributes", [])
    for attr in atributos:
        value = attr.get("value_name")
        if value:
            textos.append(value)

    # Validar todos los campos
    return any(contiene_datos_contacto(t) for t in textos)

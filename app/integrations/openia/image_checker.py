import os
import openai
import requests
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

def analizar_imagen_con_ia(url_imagen):
    try:
        result = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Analizá esta imagen con atención al detalle. Buscá si contiene datos de contacto, como números de teléfono, correos electrónicos, ubicaciones físicas, URLs, redes sociales o códigos QR, aunque estén parcial o visualmente integrados. "
                        "Incluí cualquier texto que comience con '@', íconos o símbolos como una 'a' dentro de un círculo (como ⓐ o Ⓐ), o cualquier otra forma visual que sugiera un correo electrónico. "
                        "Detectá también códigos QR aunque estén integrados en ilustraciones o decoraciones. "
                        "Si la imagen contiene alguno de estos elementos, respondé con 'Sí'. Si la respuesta es 'Sí', listá los datos encontrados o mencioná claramente que hay un QR. Caso contrario, respondé 'No'."
                    )
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": url_imagen}}
                    ]
                }
            ],
            max_tokens=500,
        )
        return result.choices[0].message.content.strip()
    except Exception as e:
        return f"Error al analizar imagen: {e}"

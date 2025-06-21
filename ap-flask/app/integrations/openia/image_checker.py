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
                        "Detectá si en esta imagen aparecen datos de contacto, como números de teléfono, correos electrónicos, "
                        "ubicaciones físicas, URLs o redes sociales. Incluí texto que comience con '@' y símbolos como 'a' dentro de un círculo. "
                        "Respondé con 'Sí' o 'No'. Si es 'Sí', listá los datos encontrados."
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

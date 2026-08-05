from __future__ import annotations

import os

from google import genai

from autotube.core.config import load_settings


MODELO_PREDETERMINADO = "gemini-3.6-flash"


class GeminiClient:
    """Cliente central para comunicarse con Gemini."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        settings = load_settings()

        self.api_key = (
            api_key
            or settings.gemini_api_key
            or ""
        ).strip()

        self.model = (
            model
            or os.getenv("GEMINI_MODEL")
            or MODELO_PREDETERMINADO
        ).strip()

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY no está configurada en el archivo .env."
            )

        self.client = genai.Client(api_key=self.api_key)

    def generar_texto(self, prompt: str) -> str:
        """Envía un prompt a Gemini y devuelve el texto generado."""
        prompt_limpio = prompt.strip()

        if not prompt_limpio:
            raise ValueError("El prompt no puede estar vacío.")

        respuesta = self.client.models.generate_content(
            model=self.model,
            contents=prompt_limpio,
        )

        texto = (respuesta.text or "").strip()

        if not texto:
            raise RuntimeError(
                "Gemini respondió, pero no devolvió contenido de texto."
            )

        return texto

    def probar_conexion(self) -> str:
        """Realiza una prueba sencilla de conexión con Gemini."""
        return self.generar_texto(
            "Responde exactamente con estas palabras: "
            "CONEXION GEMINI CORRECTA"
        )
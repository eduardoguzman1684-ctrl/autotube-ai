from __future__ import annotations

import json
import logging
import os
import random
import time
from typing import Any

import httpx
from google import genai
from google.genai import errors, types

from autotube.core.config import load_settings


MODELO_PREDETERMINADO = "gemini-3.6-flash"
MODELO_RESPALDO = "gemini-3.5-flash-lite"

logger = logging.getLogger("autotube.gemini")


class GeminiClient:
    """Cliente central para comunicarse con Gemini."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        fallback_model: str | None = None,
        max_attempts: int = 3,
        base_delay: float = 2.0,
        request_timeout_seconds: float | None = None,
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

        self.fallback_model = (
            fallback_model
            or os.getenv("GEMINI_FALLBACK_MODEL")
            or MODELO_RESPALDO
        ).strip()

        self.max_attempts = max(1, max_attempts)
        self.base_delay = max(0.5, base_delay)

        if request_timeout_seconds is None:
            try:
                request_timeout_seconds = float(
                    os.getenv(
                        "GEMINI_TIMEOUT_SECONDS",
                        "90",
                    )
                )
            except (TypeError, ValueError):
                request_timeout_seconds = 90.0

        self.request_timeout_seconds = max(
            15.0,
            min(
                float(request_timeout_seconds),
                300.0,
            ),
        )
        self.last_model_used: str | None = None

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY no está configurada en el archivo .env."
            )

        self.client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(
                timeout=int(
                    self.request_timeout_seconds
                    * 1000
                ),
            ),
        )

    def _modelos_disponibles(self) -> list[str]:
        """Devuelve los modelos en orden de prioridad sin duplicados."""
        modelos: list[str] = []

        for modelo in (self.model, self.fallback_model):
            if modelo and modelo not in modelos:
                modelos.append(modelo)

        return modelos

    def _generar_con_modelo(
        self,
        modelo: str,
        prompt: str,
        config: types.GenerateContentConfig | None = None,
    ) -> str:
        """Genera contenido con reintentos ante fallos temporales."""
        ultimo_error: Exception | None = None

        for intento in range(1, self.max_attempts + 1):
            try:
                respuesta = self.client.models.generate_content(
                    model=modelo,
                    contents=prompt,
                    config=config,
                )

                texto = (respuesta.text or "").strip()

                if not texto:
                    raise RuntimeError(
                        "Gemini respondió, pero no devolvió contenido."
                    )

                self.last_model_used = modelo
                return texto

            except (
                errors.ServerError,
                httpx.TransportError,
            ) as error:
                ultimo_error = error

                if intento >= self.max_attempts:
                    break

                espera = (
                    self.base_delay * (2 ** (intento - 1))
                    + random.uniform(0.2, 0.8)
                )

                logger.warning(
                    "Gemini no disponible | modelo=%s | "
                    "intento=%s/%s | reintento en %.1f segundos",
                    modelo,
                    intento,
                    self.max_attempts,
                    espera,
                )

                time.sleep(espera)

            except errors.ClientError as error:
                ultimo_error = error
                mensaje = str(error)

                if (
                    "429" in mensaje
                    or "RESOURCE_EXHAUSTED" in mensaje
                    or "quota" in mensaje.lower()
                ):
                    logger.warning(
                        "Cuota agotada para %s. "
                        "Probando el modelo de respaldo.",
                        modelo,
                    )
                    break

                raise

        raise RuntimeError(
            f"El modelo {modelo} continúa temporalmente no disponible."
        ) from ultimo_error

    def _generar_con_respaldo(
        self,
        prompt: str,
        config: types.GenerateContentConfig | None = None,
    ) -> str:
        """Prueba el modelo principal y luego el modelo de respaldo."""
        ultimo_error: Exception | None = None

        for modelo in self._modelos_disponibles():
            try:
                return self._generar_con_modelo(
                    modelo=modelo,
                    prompt=prompt,
                    config=config,
                )

            except RuntimeError as error:
                ultimo_error = error

                logger.warning(
                    "Se agotaron los intentos para %s. "
                    "Probando el siguiente modelo.",
                    modelo,
                )

        raise RuntimeError(
            "Gemini no está disponible después de probar "
            "el modelo principal y el modelo de respaldo."
        ) from ultimo_error

    def generar_texto(self, prompt: str) -> str:
        """Genera una respuesta de texto normal."""
        prompt_limpio = prompt.strip()

        if not prompt_limpio:
            raise ValueError("El prompt no puede estar vacío.")

        return self._generar_con_respaldo(prompt_limpio)

    def generar_json(
        self,
        prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Genera y valida una respuesta JSON estructurada."""
        prompt_limpio = prompt.strip()

        if not prompt_limpio:
            raise ValueError("El prompt no puede estar vacío.")

        if not schema:
            raise ValueError("El esquema JSON no puede estar vacío.")

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=schema,
        )

        texto = self._generar_con_respaldo(
            prompt=prompt_limpio,
            config=config,
        )

        try:
            resultado = json.loads(texto)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                "Gemini devolvió una respuesta JSON inválida."
            ) from error

        if not isinstance(resultado, dict):
            raise RuntimeError(
                "La respuesta JSON debe contener un objeto principal."
            )

        return resultado

    def probar_conexion(self) -> str:
        """Realiza una prueba sencilla de conexión con Gemini."""
        return self.generar_texto(
            "Responde exactamente con estas palabras: "
            "CONEXION GEMINI CORRECTA"
        )
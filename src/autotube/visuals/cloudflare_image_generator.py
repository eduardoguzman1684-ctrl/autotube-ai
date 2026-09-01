from __future__ import annotations

import base64
import hashlib
import io
import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from dotenv import dotenv_values
from PIL import Image, ImageOps


DEFAULT_MODEL = "@cf/black-forest-labs/flux-1-schnell"
PROMPT_VERSION = "autotube-documental-v9"
WIDTH = 1920
HEIGHT = 1080


class CuotaImagenIAAgotada(RuntimeError):
    """Indica que se consumio la asignacion gratuita diaria."""


class ConfiguracionImagenIAInvalida(RuntimeError):
    """Indica que faltan credenciales validas para Workers AI."""


class GeneradorImagenCloudflare:
    """Genera imagenes documentales con Workers AI y cache recuperable."""

    def __init__(
        self,
        data_dir: Path,
        session: requests.Session | None = None,
        max_attempts: int = 5,
    ) -> None:
        self.data_dir = data_dir.resolve()
        self.project_root = self.data_dir.parent
        self.cache_dir = (
            self.data_dir
            / "cache"
            / "cloudflare_images"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = session or requests.Session()
        self.max_attempts = max(1, int(max_attempts))

        file_config = dotenv_values(
            self.project_root / ".env"
        )

        self.account_id = str(
            file_config.get("CLOUDFLARE_ACCOUNT_ID")
            or os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
        ).strip()
        self.api_token = str(
            file_config.get("CLOUDFLARE_API_TOKEN")
            or os.getenv("CLOUDFLARE_API_TOKEN", "")
        ).strip()
        self.model = str(
            file_config.get("CLOUDFLARE_IMAGE_MODEL")
            or os.getenv("CLOUDFLARE_IMAGE_MODEL", "")
            or DEFAULT_MODEL
        ).strip()

        self._validate_configuration()

    def _validate_configuration(self) -> None:
        if not re.fullmatch(
            r"[0-9a-fA-F]{32}",
            self.account_id,
        ):
            raise ConfiguracionImagenIAInvalida(
                "CLOUDFLARE_ACCOUNT_ID debe contener exactamente "
                "32 caracteres hexadecimales."
            )

        if (
            not self.api_token
            or self.api_token == self.account_id
            or self.api_token.startswith("cfk_")
        ):
            raise ConfiguracionImagenIAInvalida(
                "CLOUDFLARE_API_TOKEN no contiene un token de API "
                "independiente y valido."
            )

        if not self.model.startswith("@cf/"):
            raise ConfiguracionImagenIAInvalida(
                "CLOUDFLARE_IMAGE_MODEL no contiene un modelo "
                "oficial de Workers AI."
            )

    @staticmethod
    def _list_values(value: Any, maximum: int = 4) -> list[str]:
        if not isinstance(value, list):
            return []

        return [
            " ".join(str(item).split())
            for item in value
            if str(item).strip()
        ][:maximum]

    def build_prompt(
        self,
        clip: dict[str, Any],
        variant: int,
    ) -> str:
        """Crea un prompt visual unido a la narracion exacta."""
        narration = " ".join(
            str(clip.get("texto_narrado", "")).split()
        )
        concept = " ".join(
            str(
                clip.get("concepto_central", "")
                or clip.get("descripcion", "")
            ).split()
        )
        description = " ".join(
            str(clip.get("descripcion", "")).split()
        )
        required = self._list_values(
            clip.get("criterios_obligatorios", [])
        )
        forbidden = self._list_values(
            clip.get("elementos_prohibidos", [])
        )

        combined = " ".join(
            [narration, concept, description]
        ).lower()

        exclusions = [
            "written words",
            "captions",
            "logos",
            "watermark",
            "decorative data",
        ]

        if not any(
            word in combined
            for word in (
                "grafico",
                "gráfico",
                "diagrama",
                "estadistica",
                "estadística",
                "chart",
                "graph",
            )
        ):
            exclusions.extend(
                ["chart", "graph", "diagram", "infographic"]
            )

        if not any(
            word in combined
            for word in ("interfaz", "pantalla", "interface", "screen")
        ):
            exclusions.append("invented interface")

        if not any(
            word in combined
            for word in ("robot", "humanoide", "humanoid")
        ):
            exclusions.append("generic humanoid robot")

        fixed = (
            "Create one photorealistic cinematic documentary still. "
            "The image must directly illustrate the narration, not a "
            "generic technology metaphor. Center the principal subject "
            "and compose it for a 16:9 crop. Natural documentary lighting, "
            "credible location, realistic people and objects, high detail. "
            "Do not include: "
            + ", ".join(exclusions)
            + ". If people are needed, use fictional "
            "non-identifiable people and do not imitate a real public figure. "
            "This is an illustrative reconstruction, not evidence of a real "
            "event. "
        )

        parts = [
            fixed,
            f"NARRATION: {narration}",
            f"CENTRAL CONCEPT: {concept}",
            f"TARGET DESCRIPTION: {description}",
            (
                "REQUIRED VISUAL ELEMENTS: "
                + "; ".join(required)
            ),
            (
                "FORBIDDEN ELEMENTS: "
                + "; ".join(forbidden)
            ),
            (
                "VARIATION: "
                + str(variant)
                + ". Use a distinct camera angle while preserving "
                "the exact concept."
            ),
        ]

        prompt = "\n".join(
            part
            for part in parts
            if not part.endswith(": ")
        )

        return prompt[:2048]

    def _fingerprint(self, prompt: str) -> str:
        payload = (
            PROMPT_VERSION
            + "\n"
            + self.model
            + "\n"
            + prompt
        )
        return hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _response_json(response: requests.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            return {}

        return data if isinstance(data, dict) else {}

    @staticmethod
    def _error_details(data: dict[str, Any]) -> tuple[int, str]:
        errors = data.get("errors", [])

        if not isinstance(errors, list) or not errors:
            return 0, "Respuesta sin detalle de error."

        first = errors[0]
        if not isinstance(first, dict):
            return 0, str(first)

        try:
            code = int(first.get("code", 0) or 0)
        except (TypeError, ValueError):
            code = 0

        message = str(first.get("message", first))
        return code, message

    @staticmethod
    def _decode_image(data: dict[str, Any]) -> bytes:
        result = data.get("result", {})
        image = (
            result.get("image", "")
            if isinstance(result, dict)
            else ""
        )

        if not isinstance(image, str) or not image.strip():
            raise RuntimeError(
                "Workers AI no devolvio una imagen."
            )

        if "," in image:
            image = image.split(",", 1)[1]

        try:
            return base64.b64decode(
                image,
                validate=True,
            )
        except (ValueError, TypeError) as error:
            raise RuntimeError(
                "Workers AI devolvio una imagen Base64 invalida."
            ) from error

    @staticmethod
    def _save_widescreen(image_bytes: bytes, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)

        try:
            with Image.open(io.BytesIO(image_bytes)) as source:
                source.load()
                image = ImageOps.fit(
                    source.convert("RGB"),
                    (WIDTH, HEIGHT),
                    method=Image.Resampling.LANCZOS,
                    centering=(0.5, 0.5),
                )
        except (OSError, ValueError) as error:
            raise RuntimeError(
                "Workers AI devolvio un archivo de imagen danado."
            ) from error

        temporary = destination.with_suffix(
            destination.suffix + ".tmp"
        )
        image.save(
            temporary,
            format="JPEG",
            quality=92,
            optimize=True,
            progressive=True,
        )
        temporary.replace(destination)

    def _request_image(self, prompt: str) -> bytes:
        url = (
            "https://api.cloudflare.com/client/v4/accounts/"
            + self.account_id
            + "/ai/run/"
            + self.model
        )

        last_error: Exception | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.session.post(
                    url,
                    headers={
                        "Authorization": "Bearer " + self.api_token,
                        "Content-Type": "application/json",
                    },
                    json={"prompt": prompt},
                    timeout=180,
                )

            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ) as error:
                last_error = error

                if attempt >= self.max_attempts:
                    break

                delay = min(30, 2**attempt)
                print(
                    "  Conexion interrumpida con Workers AI. "
                    f"Reintento {attempt}/{self.max_attempts - 1} "
                    f"en {delay} segundos..."
                )
                time.sleep(delay)
                continue

            data = self._response_json(response)

            if response.ok:
                return self._decode_image(data)

            code, message = self._error_details(data)

            if code == 3036 or "daily free allocation" in message.lower():
                raise CuotaImagenIAAgotada(
                    "Workers AI agoto la asignacion gratuita diaria "
                    "de 10,000 neuronas. Reanuda la produccion cuando "
                    "Cloudflare restablezca la cuota."
                )

            retryable = (
                response.status_code in {408, 500, 502, 503, 504}
                or code in {3007, 3008, 3040}
            )

            if retryable and attempt < self.max_attempts:
                delay = min(30, 2**attempt)
                print(
                    "  Workers AI temporalmente no disponible. "
                    f"Reintento {attempt}/{self.max_attempts - 1} "
                    f"en {delay} segundos..."
                )
                time.sleep(delay)
                continue

            raise RuntimeError(
                "Workers AI rechazo la generacion "
                f"(HTTP {response.status_code}, codigo {code}): "
                f"{message}"
            )

        raise RuntimeError(
            "Workers AI no pudo generar la imagen despues de "
            f"{self.max_attempts} intentos de conexion."
        ) from last_error

    def generate(
        self,
        clip: dict[str, Any],
        destination: Path,
        variant: int,
    ) -> dict[str, Any]:
        """Genera o restaura una candidata y devuelve su trazabilidad."""
        prompt = self.build_prompt(
            clip=clip,
            variant=variant,
        )
        fingerprint = self._fingerprint(prompt)
        cached = self.cache_dir / f"{fingerprint}.jpg"

        reused = cached.is_file() and cached.stat().st_size > 0

        if reused:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cached, destination)
        else:
            image_bytes = self._request_image(prompt)
            self._save_widescreen(
                image_bytes=image_bytes,
                destination=destination,
            )

        narration = " ".join(
            str(clip.get("texto_narrado", "")).split()
        )

        return {
            "proveedor": "cloudflare_workers_ai",
            "modelo": self.model,
            "version_prompt": PROMPT_VERSION,
            "prompt": prompt,
            "prompt_sha256": fingerprint,
            "narracion_sha256": hashlib.sha256(
                narration.encode("utf-8")
            ).hexdigest(),
            "variante": variant,
            "ancho": WIDTH,
            "alto": HEIGHT,
            "formato": "jpeg",
            "reutilizada_cache": reused,
            "generada_en": (
                datetime.now()
                .astimezone()
                .isoformat(timespec="seconds")
            ),
            "declaracion": (
                "Imagen ilustrativa generada por inteligencia artificial."
            ),
        }

    def confirm_cache(
        self,
        source: Path,
        fingerprint: str,
    ) -> Path:
        """Conserva solamente candidatas aprobadas por el verificador."""
        destination = self.cache_dir / f"{fingerprint}.jpg"

        if not destination.is_file():
            temporary = destination.with_suffix(".jpg.tmp")
            shutil.copy2(source, temporary)
            temporary.replace(destination)

        return destination

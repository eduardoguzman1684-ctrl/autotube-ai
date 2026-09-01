from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx
from google.genai import errors, types
from PIL import Image, ImageDraw, ImageOps

from autotube.ai.gemini_client import GeminiClient


class VerificadorVisualGemini:
    """Selecciona la imagen mÃ¡s coherente mediante Gemini."""

    def __init__(
        self,
        cliente: GeminiClient | None = None,
        umbral: int = 88,
    ) -> None:
        self.cliente = cliente or GeminiClient()
        self.umbral = max(0, min(100, umbral))

    def _generar_multimodal(
        self,
        prompt: str,
        parte_imagen: types.Part,
        config: types.GenerateContentConfig,
    ) -> Any:
        """Genera con reintentos y modelo de respaldo ante errores 503."""
        modelos: list[str] = []

        for modelo in (
            self.cliente.model,
            self.cliente.fallback_model,
        ):
            if modelo and modelo not in modelos:
                modelos.append(modelo)

        ultimo_error: Exception | None = None

        for modelo in modelos:
            for intento in range(1, 3):
                try:
                    respuesta = (
                        self.cliente.client.models.generate_content(
                            model=modelo,
                            contents=[
                                prompt,
                                parte_imagen,
                            ],
                            config=config,
                        )
                    )

                    self.cliente.last_model_used = modelo
                    return respuesta

                except (
                    errors.ServerError,
                    httpx.TransportError,
                ) as error:
                    ultimo_error = error

                    if intento < 2:
                        espera = 5 * intento

                        if isinstance(
                            error,
                            httpx.TimeoutException,
                        ):
                            motivo = (
                                "no respondi? dentro del l?mite"
                            )
                        elif isinstance(
                            error,
                            httpx.TransportError,
                        ):
                            motivo = (
                                "presento un error temporal de transporte"
                            )
                        else:
                            motivo = "esta saturado"

                        print(
                            f"  Gemini {motivo}. "
                            f"Reintento {intento}/2 "
                            f"en {espera} segundos..."
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
                        print(
                            "  Cuota agotada para "
                            f"{modelo}. Probando el modelo de respaldo."
                        )
                        break

                    raise

            print(
                "  Modelo temporalmente no disponible: "
                f"{modelo}. Probando respaldo."
            )

        raise RuntimeError(
            "Gemini contin?a temporalmente no disponible "
            "despu?s de probar ambos modelos."
        ) from ultimo_error

    def _crear_lamina(
        self,
        imagenes: list[Path],
        destino: Path,
    ) -> None:
        ancho_celda = 480
        alto_celda = 300
        columnas = 2
        filas = 3

        lamina = Image.new(
            "RGB",
            (
                ancho_celda * columnas,
                alto_celda * filas,
            ),
            color=(15, 18, 25),
        )

        dibujo = ImageDraw.Draw(lamina)

        for indice, ruta in enumerate(imagenes[:6]):
            fila = indice // columnas
            columna = indice % columnas

            x = columna * ancho_celda
            y = fila * alto_celda

            with Image.open(ruta) as original:
                imagen = ImageOps.fit(
                    original.convert("RGB"),
                    (
                        ancho_celda,
                        alto_celda,
                    ),
                    method=Image.Resampling.LANCZOS,
                )

            lamina.paste(imagen, (x, y))

            dibujo.rectangle(
                (
                    x + 10,
                    y + 10,
                    x + 75,
                    y + 60,
                ),
                fill=(0, 0, 0),
                outline=(0, 220, 255),
                width=3,
            )

            dibujo.text(
                (x + 29, y + 22),
                str(indice + 1),
                fill=(255, 255, 255),
            )

        destino.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        lamina.save(
            destino,
            format="JPEG",
            quality=88,
        )

    def _crear_lamina_lote(
        self,
        grupos: list[dict[str, Any]],
        destino: Path,
    ) -> None:
        """Crea una l?mina con cinco clips y cuatro opciones por clip."""
        ancho_celda = 400
        alto_celda = 260
        columnas = 4
        filas = len(grupos)

        lamina = Image.new(
            "RGB",
            (
                ancho_celda * columnas,
                alto_celda * filas,
            ),
            color=(15, 18, 25),
        )

        dibujo = ImageDraw.Draw(lamina)
        letras = "ABCDE"

        for fila, grupo in enumerate(grupos):
            imagenes = list(
                grupo.get("imagenes", [])
            )[:columnas]

            for columna, ruta_imagen in enumerate(imagenes):
                x = columna * ancho_celda
                y = fila * alto_celda

                try:
                    with Image.open(
                        Path(ruta_imagen)
                    ) as original:
                        original.load()

                        imagen = ImageOps.fit(
                            original.convert("RGB"),
                            (
                                ancho_celda,
                                alto_celda,
                            ),
                            method=Image.Resampling.LANCZOS,
                        )

                except (OSError, ValueError) as error:
                    ruta_danada = Path(
                        ruta_imagen
                    )

                    print(
                        "  AVISO imagen candidata danada: "
                        f"{ruta_danada.name}. "
                        "Se omitira y se continuara."
                    )

                    try:
                        ruta_danada.unlink(
                            missing_ok=True
                        )
                    except OSError:
                        pass

                    imagen = Image.new(
                        "RGB",
                        (
                            ancho_celda,
                            alto_celda,
                        ),
                        color=(55, 18, 28),
                    )

                    dibujo_error = ImageDraw.Draw(
                        imagen
                    )

                    dibujo_error.text(
                        (
                            70,
                            alto_celda // 2,
                        ),
                        "IMAGEN NO DISPONIBLE",
                        fill=(255, 210, 215),
                    )

                lamina.paste(imagen, (x, y))

                etiqueta = (
                    f"{letras[fila]}{columna + 1}"
                )

                dibujo.rectangle(
                    (
                        x + 8,
                        y + 8,
                        x + 78,
                        y + 52,
                    ),
                    fill=(0, 0, 0),
                    outline=(0, 220, 255),
                    width=3,
                )

                dibujo.text(
                    (x + 20, y + 20),
                    etiqueta,
                    fill=(255, 255, 255),
                )

        destino.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        lamina.save(
            destino,
            format="JPEG",
            quality=88,
        )

    def seleccionar_lote(
        self,
        grupos: list[dict[str, Any]],
        lamina_temporal: Path,
    ) -> dict[str, dict[str, Any]]:
        """Selecciona im?genes para un m?ximo de cinco clips."""
        grupos_validos = [
            grupo
            for grupo in grupos[:5]
            if grupo.get("imagenes")
        ]

        if not grupos_validos:
            raise ValueError(
                "No se proporcionaron grupos visuales."
            )

        self._crear_lamina_lote(
            grupos=grupos_validos,
            destino=lamina_temporal,
        )

        letras = "ABCDE"
        requisitos: list[str] = []

        for indice, grupo in enumerate(grupos_validos):
            requisitos.append(
                f"{letras[indice]} | "
                f"ID={grupo['id']} | "
                f"OPCIONES={len(grupo['imagenes'][:4])}\n"
                f"{grupo['requisito_visual']}"
            )

        schema = {
            "type": "object",
            "properties": {
                "resultados": {
                    "type": "array",
                    "minItems": len(grupos_validos),
                    "maxItems": len(grupos_validos),
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                            },
                            "seleccion": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 4,
                            },
                            "puntaje": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 100,
                            },
                            "aprobada": {
                                "type": "boolean",
                            },
                            "cumple_concepto": {
                                "type": "boolean",
                            },
                            "cumple_obligatorios": {
                                "type": "boolean",
                            },
                            "viola_prohibidos": {
                                "type": "boolean",
                            },
                            "descripcion": {
                                "type": "string",
                            },
                            "motivo": {
                                "type": "string",
                            },
                        },
                        "required": [
                            "id",
                            "seleccion",
                            "puntaje",
                            "aprobada",
                            "cumple_concepto",
                            "cumple_obligatorios",
                            "viola_prohibidos",
                            "descripcion",
                            "motivo",
                        ],
                    },
                },
            },
            "required": [
                "resultados",
            ],
        }

        prompt = f"""
Act?a como director visual de un documental profesional.

La l?mina contiene varias filas:

- Fila A corresponde al primer requisito.
- Fila B corresponde al segundo requisito.
- Fila C corresponde al tercero.
- Fila D corresponde al cuarto.
- Fila E corresponde al quinto.
- Cada fila tiene hasta cuatro opciones numeradas del 1 al 4.

REQUISITOS:

{chr(10).join(requisitos)}

Eval?a cada fila de manera independiente.

Reglas obligatorias:

- Devuelve exactamente un resultado por cada ID.
- seleccion indica la columna elegida dentro de su propia fila.
- Evalua primero el CONCEPTO CENTRAL.
- Comprueba uno por uno todos los CRITERIOS OBLIGATORIOS.
- Comprueba que no aparezca ningun ELEMENTO PROHIBIDO.
- cumple_concepto solo puede ser true cuando la imagen comunica
  directamente el concepto central, sin depender de una metafora.
- cumple_obligatorios solo puede ser true cuando todos los elementos
  obligatorios visualmente comprobables aparecen.
- viola_prohibidos debe ser true cuando aparezca cualquier sustituto
  o elemento expresamente prohibido.
- aprobada solo puede ser true cuando cumple_concepto=true,
  cumple_obligatorios=true, viola_prohibidos=false y el puntaje
  alcanza {self.umbral}/100.
- Si falla una sola condicion usa seleccion=0 y aprobada=false.
- No aceptes reuniones empresariales como comites cientificos.
- No aceptes operadores financieros como investigadores de IA.
- No aceptes computadoras domesticas como servidores, GPU
  especializada, superordenadores o centros de datos.
- No aceptes una imagen solo porque comparte palabras generales.
- No cruces imagenes entre filas.
"""

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=schema,
        )

        parte_imagen = types.Part.from_bytes(
            data=lamina_temporal.read_bytes(),
            mime_type="image/jpeg",
        )

        respuesta = self._generar_multimodal(
            prompt=prompt,
            parte_imagen=parte_imagen,
            config=config,
        )

        contenido = json.loads(
            respuesta.text or "{}"
        )

        recibidos = contenido.get(
            "resultados",
            [],
        )

        por_id = {
            str(resultado.get("id", "")): resultado
            for resultado in recibidos
            if isinstance(resultado, dict)
        }

        finales: dict[str, dict[str, Any]] = {}

        for grupo in grupos_validos:
            identificador = str(grupo["id"])
            resultado = dict(
                por_id.get(
                    identificador,
                    {},
                )
            )

            seleccion = int(
                resultado.get(
                    "seleccion",
                    0,
                )
            )

            puntaje = int(
                resultado.get(
                    "puntaje",
                    0,
                )
            )

            cantidad = len(
                grupo["imagenes"][:4]
            )

            aprobada = bool(
                resultado.get(
                    "aprobada",
                    False,
                )
            )

            cumple_concepto = bool(
                resultado.get(
                    "cumple_concepto",
                    False,
                )
            )

            cumple_obligatorios = bool(
                resultado.get(
                    "cumple_obligatorios",
                    False,
                )
            )

            viola_prohibidos = bool(
                resultado.get(
                    "viola_prohibidos",
                    True,
                )
            )

            if (
                seleccion < 1
                or seleccion > cantidad
                or puntaje < self.umbral
                or not aprobada
                or not cumple_concepto
                or not cumple_obligatorios
                or viola_prohibidos
            ):
                resultado["seleccion"] = 0
                resultado["aprobada"] = False
                resultado["ruta_seleccionada"] = ""

            else:
                resultado["ruta_seleccionada"] = str(
                    grupo["imagenes"][
                        seleccion - 1
                    ]
                )

            resultado["id"] = identificador
            finales[identificador] = resultado

        return finales

    def seleccionar(
        self,
        imagenes: list[Path],
        requisito_visual: str,
        lamina_temporal: Path,
    ) -> dict[str, Any]:
        candidatas = imagenes[:6]

        if not candidatas:
            raise ValueError(
                "No se proporcionaron imÃ¡genes candidatas."
            )

        self._crear_lamina(
            imagenes=candidatas,
            destino=lamina_temporal,
        )

        schema = {
            "type": "object",
            "properties": {
                "seleccion": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": len(candidatas),
                },
                "puntaje": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                },
                "aprobada": {
                    "type": "boolean",
                },
                "cumple_concepto": {
                    "type": "boolean",
                },
                "cumple_obligatorios": {
                    "type": "boolean",
                },
                "viola_prohibidos": {
                    "type": "boolean",
                },
                "descripcion": {
                    "type": "string",
                },
                "motivo": {
                    "type": "string",
                },
            },
            "required": [
                "seleccion",
                "puntaje",
                "aprobada",
                "cumple_concepto",
                "cumple_obligatorios",
                "viola_prohibidos",
                "descripcion",
                "motivo",
            ],
        }

        prompt = f"""
ActÃºa como director visual de un documental profesional.

REQUISITO VISUAL:
{requisito_visual}

La lÃ¡mina contiene {len(candidatas)} imÃ¡genes numeradas.

Selecciona la imagen que represente con mayor precisiÃ³n el
requisito visual.

Reglas:

- Evalua directamente el CONCEPTO CENTRAL.
- Comprueba todos los CRITERIOS OBLIGATORIOS.
- Rechaza cualquier ELEMENTO PROHIBIDO.
- No elijas una imagen solamente porque sea atractiva.
- Rechaza imagenes genericas o conceptualmente aproximadas.
- cumple_concepto requiere coincidencia visual directa.
- cumple_obligatorios requiere todos los elementos observables.
- viola_prohibidos debe ser true si aparece un elemento prohibido.
- aprobada solo puede ser true cuando cumple_concepto=true,
  cumple_obligatorios=true, viola_prohibidos=false y el puntaje
  alcanza {self.umbral}/100.
- Si falla una condicion usa seleccion=0 y aprobada=false.
- No confundas computadoras domesticas con hardware especializado.
- La seleccion debe coincidir directamente con la narracion.
"""

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=schema,
        )

        parte_imagen = types.Part.from_bytes(
            data=lamina_temporal.read_bytes(),
            mime_type="image/jpeg",
        )

        respuesta = self._generar_multimodal(
            prompt=prompt,
            parte_imagen=parte_imagen,
            config=config,
        )

        resultado = json.loads(respuesta.text)

        seleccion = int(
            resultado.get("seleccion", 0)
        )

        puntaje = int(
            resultado.get("puntaje", 0)
        )

        aprobada = bool(
            resultado.get("aprobada", False)
        )

        cumple_concepto = bool(
            resultado.get(
                "cumple_concepto",
                False,
            )
        )

        cumple_obligatorios = bool(
            resultado.get(
                "cumple_obligatorios",
                False,
            )
        )

        viola_prohibidos = bool(
            resultado.get(
                "viola_prohibidos",
                True,
            )
        )

        if (
            seleccion < 1
            or seleccion > len(candidatas)
            or puntaje < self.umbral
            or not aprobada
            or not cumple_concepto
            or not cumple_obligatorios
            or viola_prohibidos
        ):
            resultado["seleccion"] = 0
            resultado["aprobada"] = False
            resultado["ruta_seleccionada"] = ""
            return resultado

        resultado["ruta_seleccionada"] = str(
            candidatas[seleccion - 1]
        )

        return resultado

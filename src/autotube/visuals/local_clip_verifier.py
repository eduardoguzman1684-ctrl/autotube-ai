from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

from PIL import Image


class VerificadorVisualCLIP:
    """Respaldo visual local basado en similitud imagen-texto.

    CLIP nunca aprueba por nombre de archivo, URL o metadata. El modelo
    inspecciona los pixeles de cada candidata y los compara con el contrato
    visual del clip. Los casos ambiguos permanecen rechazados.
    """

    def __init__(
        self,
        umbral: int = 88,
        modelo: str | None = None,
    ) -> None:
        self.umbral = max(0, min(100, umbral))
        self.modelo_nombre = (
            modelo
            or os.getenv(
                "AUTOTUBE_CLIP_MODEL",
                "openai/clip-vit-base-patch32",
            )
        )
        self.similitud_minima = self._leer_decimal(
            "AUTOTUBE_CLIP_MIN_SIMILARITY",
            0.21,
        )
        self.margen_minimo = self._leer_decimal(
            "AUTOTUBE_CLIP_MIN_MARGIN",
            0.008,
        )
        self.similitud_criterio = self._leer_decimal(
            "AUTOTUBE_CLIP_CRITERIA_SIMILARITY",
            0.16,
        )
        self._modelo: Any | None = None
        self._procesador: Any | None = None
        self._torch: Any | None = None
        self._dispositivo = "cpu"

    @staticmethod
    def _leer_decimal(nombre: str, predeterminado: float) -> float:
        try:
            return float(os.getenv(nombre, str(predeterminado)))
        except (TypeError, ValueError):
            return predeterminado

    def _cargar_modelo(self) -> None:
        if self._modelo is not None:
            return

        try:
            import torch
            from transformers import CLIPModel, CLIPProcessor
        except ImportError as error:
            raise RuntimeError(
                "Faltan torch y transformers. Ejecuta nuevamente el "
                "instalador CLIP v12 desde el entorno virtual."
            ) from error

        try:
            procesador = CLIPProcessor.from_pretrained(
                self.modelo_nombre,
            )
            modelo = CLIPModel.from_pretrained(
                self.modelo_nombre,
            )
        except Exception as error:
            raise RuntimeError(
                "No se pudo descargar o abrir el modelo CLIP local. "
                "Comprueba Internet durante la primera instalacion."
            ) from error

        dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
        modelo.to(dispositivo)
        modelo.eval()

        self._torch = torch
        self._procesador = procesador
        self._modelo = modelo
        self._dispositivo = dispositivo

    @staticmethod
    def _secciones(requisito: str) -> dict[str, list[str]]:
        resultado: dict[str, list[str]] = {
            "concepto": [],
            "descripcion": [],
            "criterios": [],
            "prohibidos": [],
            "alternativas": [],
        }
        seccion = ""

        for linea_original in requisito.splitlines():
            linea = linea_original.strip()

            if not linea:
                continue

            mayusculas = linea.upper()

            if mayusculas.startswith("CONCEPTO CENTRAL:"):
                valor = linea.split(":", 1)[1].strip()
                if valor:
                    resultado["concepto"].append(valor)
                seccion = ""
                continue

            if mayusculas.startswith("DESCRIPCION OBJETIVO:"):
                valor = linea.split(":", 1)[1].strip()
                if valor:
                    resultado["descripcion"].append(valor)
                seccion = ""
                continue

            if mayusculas == "CRITERIOS OBLIGATORIOS:":
                seccion = "criterios"
                continue

            if mayusculas == "ELEMENTOS PROHIBIDOS:":
                seccion = "prohibidos"
                continue

            if mayusculas.startswith("CONTEXTO NARRADO:"):
                seccion = ""
                continue

            if mayusculas == "BUSQUEDAS ALTERNATIVAS:":
                seccion = "alternativas"
                continue

            if seccion and linea.startswith("-"):
                valor = linea[1:].strip()
                if valor:
                    resultado[seccion].append(valor)

        return resultado

    @staticmethod
    def _unicos(textos: list[str], limite: int) -> list[str]:
        vistos: set[str] = set()
        salida: list[str] = []

        for texto in textos:
            limpio = " ".join(str(texto).split())[:350]
            clave = limpio.casefold()

            if not limpio or clave in vistos:
                continue

            vistos.add(clave)
            salida.append(limpio)

            if len(salida) >= limite:
                break

        return salida

    def _calcular_similitudes(
        self,
        imagenes: list[Path],
        textos: list[str],
    ) -> list[list[float]]:
        self._cargar_modelo()
        abiertas: list[Image.Image] = []

        try:
            for ruta in imagenes:
                with Image.open(ruta) as original:
                    abiertas.append(original.convert("RGB"))

            entradas = self._procesador(
                text=textos,
                images=abiertas,
                return_tensors="pt",
                padding=True,
                truncation=True,
            )
            entradas = {
                clave: valor.to(self._dispositivo)
                for clave, valor in entradas.items()
            }

            with self._torch.inference_mode():
                salida = self._modelo(**entradas)
                imagen = salida.image_embeds
                texto = salida.text_embeds
                imagen = imagen / imagen.norm(
                    dim=-1,
                    keepdim=True,
                )
                texto = texto / texto.norm(
                    dim=-1,
                    keepdim=True,
                )
                matriz = imagen @ texto.T

            return [
                [float(valor) for valor in fila]
                for fila in matriz.detach().cpu().tolist()
            ]
        finally:
            for imagen in abiertas:
                imagen.close()

    def _puntaje_publico(
        self,
        similitud: float,
        aprobada: bool,
    ) -> int:
        if aprobada:
            extra = max(
                0,
                round(
                    (similitud - self.similitud_minima)
                    * 250
                ),
            )
            return min(100, self.umbral + extra)

        proporcion = max(
            0.0,
            min(
                1.0,
                similitud / max(self.similitud_minima, 0.001),
            ),
        )
        return min(self.umbral - 1, round(proporcion * 87))

    def seleccionar(
        self,
        imagenes: list[Path],
        requisito_visual: str,
        lamina_temporal: Path | None = None,
    ) -> dict[str, Any]:
        candidatas = [Path(ruta) for ruta in imagenes[:6]]

        if not candidatas:
            raise ValueError("No se proporcionaron imagenes candidatas.")

        for ruta in candidatas:
            if not ruta.is_file():
                raise FileNotFoundError(
                    f"No existe la imagen candidata: {ruta}"
                )

        secciones = self._secciones(requisito_visual)
        centrales = self._unicos(
            secciones["concepto"] + secciones["descripcion"],
            2,
        )
        criterios = self._unicos(secciones["criterios"], 4)
        alternativas = self._unicos(secciones["alternativas"], 3)
        prohibidos = self._unicos(secciones["prohibidos"], 4)

        if not centrales:
            raise ValueError(
                "El contrato visual no contiene un concepto central."
            )

        positivos = centrales + criterios + alternativas
        textos = positivos + prohibidos
        matriz = self._calcular_similitudes(candidatas, textos)

        cantidad_centrales = len(centrales)
        inicio_criterios = cantidad_centrales
        fin_criterios = inicio_criterios + len(criterios)
        inicio_alternativas = fin_criterios
        fin_positivos = len(positivos)

        evaluaciones: list[dict[str, Any]] = []

        for indice, fila in enumerate(matriz):
            valores_centrales = fila[:cantidad_centrales]
            valores_criterios = fila[inicio_criterios:fin_criterios]
            valores_alternativas = fila[
                inicio_alternativas:fin_positivos
            ]
            valores_prohibidos = fila[fin_positivos:]

            central = max(valores_centrales)
            apoyo = (
                max(valores_alternativas)
                if valores_alternativas
                else central
            )
            criterio_promedio = (
                sum(valores_criterios) / len(valores_criterios)
                if valores_criterios
                else central
            )
            combinado = (
                central * 0.70
                + criterio_promedio * 0.20
                + apoyo * 0.10
            )
            criterio_minimo = (
                min(valores_criterios)
                if valores_criterios
                else central
            )
            prohibido_maximo = (
                max(valores_prohibidos)
                if valores_prohibidos
                else -1.0
            )

            evaluaciones.append(
                {
                    "indice": indice,
                    "central": central,
                    "criterio_minimo": criterio_minimo,
                    "combinado": combinado,
                    "prohibido_maximo": prohibido_maximo,
                }
            )

        evaluaciones.sort(
            key=lambda elemento: elemento["combinado"],
            reverse=True,
        )
        mejor = evaluaciones[0]
        segundo = (
            evaluaciones[1]["combinado"]
            if len(evaluaciones) > 1
            else -1.0
        )
        margen = mejor["combinado"] - segundo
        similitud_requerida = self.similitud_minima + (
            0.02 if len(candidatas) == 1 else 0.0
        )
        cumple_concepto = mejor["combinado"] >= similitud_requerida
        cumple_obligatorios = (
            mejor["criterio_minimo"] >= self.similitud_criterio
        )
        seleccion_clara = (
            len(candidatas) == 1
            or margen >= self.margen_minimo
        )
        viola_prohibidos = (
            bool(prohibidos)
            and mejor["prohibido_maximo"]
            >= mejor["combinado"] - 0.005
            and mejor["prohibido_maximo"]
            >= self.similitud_minima - 0.02
        )
        aprobada = (
            cumple_concepto
            and cumple_obligatorios
            and seleccion_clara
            and not viola_prohibidos
        )
        puntaje = self._puntaje_publico(
            mejor["combinado"],
            aprobada,
        )
        seleccion = mejor["indice"] + 1 if aprobada else 0

        if aprobada:
            motivo = (
                "Coincidencia semantica visual aprobada localmente; "
                "la mejor candidata supera los limites conservadores."
            )
        elif not cumple_concepto:
            motivo = "La imagen no alcanza la similitud visual minima."
        elif not cumple_obligatorios:
            motivo = "No se sostienen todos los criterios observables."
        elif not seleccion_clara:
            motivo = "Las mejores candidatas son demasiado ambiguas."
        else:
            motivo = "La imagen se parece a un elemento prohibido."

        return {
            "seleccion": seleccion,
            "puntaje": puntaje,
            "aprobada": aprobada,
            "cumple_concepto": cumple_concepto,
            "cumple_obligatorios": cumple_obligatorios,
            "viola_prohibidos": viola_prohibidos,
            "descripcion": (
                "Verificacion local de los pixeles mediante CLIP."
            ),
            "motivo": motivo,
            "ruta_seleccionada": (
                str(candidatas[seleccion - 1])
                if seleccion > 0
                else ""
            ),
            "verificador": "CLIP local",
            "modelo_verificador": self.modelo_nombre,
            "similitud_clip": round(mejor["combinado"], 6),
            "margen_clip": (
                round(margen, 6)
                if math.isfinite(margen)
                else 0.0
            ),
            "verificacion_degradada": False,
            "aprobacion_por_metadata": False,
        }

    def seleccionar_lote(
        self,
        grupos: list[dict[str, Any]],
        lamina_temporal: Path | None = None,
    ) -> dict[str, dict[str, Any]]:
        resultados: dict[str, dict[str, Any]] = {}

        for grupo in grupos[:5]:
            identificador = str(grupo.get("id", ""))
            imagenes = [Path(ruta) for ruta in grupo.get("imagenes", [])]

            if not identificador or not imagenes:
                continue

            resultado = self.seleccionar(
                imagenes=imagenes[:4],
                requisito_visual=str(
                    grupo.get("requisito_visual", "")
                ),
                lamina_temporal=lamina_temporal,
            )
            resultado["id"] = identificador
            resultados[identificador] = resultado

        return resultados

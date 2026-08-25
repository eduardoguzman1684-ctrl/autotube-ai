from __future__ import annotations

import html
import json
import shutil
import time
import webbrowser
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


class CentroControlAutoTube:
    """Consolida el estado operativo local del proyecto."""

    TOTAL_PASOS_PREDETERMINADO = 11

    def __init__(
        self,
        project_root: Path,
    ) -> None:
        self.project_root = Path(
            project_root
        ).resolve()

    @staticmethod
    def _leer_json(
        ruta: Path,
    ) -> dict[str, Any]:
        if not ruta.is_file():
            return {}

        try:
            datos = json.loads(
                ruta.read_text(
                    encoding="utf-8-sig"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ):
            return {}

        return (
            datos
            if isinstance(datos, dict)
            else {}
        )

    def _ultimo(
        self,
        *patrones: str,
    ) -> Path | None:
        archivos: list[Path] = []

        for patron in patrones:
            archivos.extend(
                ruta
                for ruta in self.project_root.glob(
                    patron
                )
                if ruta.is_file()
            )

        if not archivos:
            return None

        return max(
            archivos,
            key=lambda ruta: ruta.stat().st_mtime,
        )

    @staticmethod
    def _fecha_archivo(
        ruta: Path | None,
    ) -> str:
        if ruta is None or not ruta.exists():
            return ""

        return (
            datetime.fromtimestamp(
                ruta.stat().st_mtime
            )
            .astimezone()
            .isoformat(timespec="seconds")
        )

    @staticmethod
    def _tamano_legible(
        bytes_totales: int | float,
    ) -> str:
        valor = float(
            max(
                0,
                bytes_totales,
            )
        )

        unidades = [
            "B",
            "KB",
            "MB",
            "GB",
            "TB",
        ]

        for unidad in unidades:
            if valor < 1024 or unidad == "TB":
                if unidad == "B":
                    return f"{int(valor)} {unidad}"

                return f"{valor:.1f} {unidad}"

            valor /= 1024

        return f"{valor:.1f} TB"

    @staticmethod
    def _duracion_legible(
        segundos: Any,
    ) -> str:
        try:
            total = max(
                0,
                int(
                    round(
                        float(segundos)
                    )
                ),
            )
        except (
            TypeError,
            ValueError,
        ):
            total = 0

        horas, resto = divmod(
            total,
            3600,
        )
        minutos, segundos_finales = divmod(
            resto,
            60,
        )

        if horas:
            return (
                f"{horas}:"
                f"{minutos:02d}:"
                f"{segundos_finales:02d}"
            )

        return (
            f"{minutos}:"
            f"{segundos_finales:02d}"
        )

    def _estado_pipeline(
        self,
    ) -> dict[str, Any]:
        ruta = (
            self.project_root
            / "data"
            / "pipeline_state.json"
        )

        datos = self._leer_json(
            ruta
        )

        completados_raw = datos.get(
            "pasos_completados",
            [],
        )

        completados = (
            [
                str(elemento)
                for elemento in completados_raw
            ]
            if isinstance(
                completados_raw,
                list,
            )
            else []
        )

        total = int(
            datos.get(
                "total_pasos",
                self.TOTAL_PASOS_PREDETERMINADO,
            )
            or self.TOTAL_PASOS_PREDETERMINADO
        )

        total = max(
            total,
            len(completados),
            1,
        )

        duraciones_raw = datos.get(
            "duraciones_pasos",
            {},
        )

        duraciones = (
            duraciones_raw
            if isinstance(
                duraciones_raw,
                dict,
            )
            else {}
        )

        return {
            "archivo": str(ruta),
            "existe": ruta.is_file(),
            "actualizado_en": self._fecha_archivo(
                ruta
            ),
            "completado": bool(
                datos.get(
                    "completado",
                    False,
                )
            ),
            "pasos_completados": completados,
            "cantidad_completados": len(
                completados
            ),
            "total_pasos": total,
            "progreso_porcentaje": round(
                min(
                    100.0,
                    len(completados)
                    / total
                    * 100,
                ),
                1,
            ),
            "ultimo_error": str(
                datos.get(
                    "ultimo_error",
                    "",
                )
                or ""
            ),
            "parametros": (
                datos.get(
                    "parametros",
                    {},
                )
                if isinstance(
                    datos.get(
                        "parametros",
                        {},
                    ),
                    dict,
                )
                else {}
            ),
            "duraciones_pasos": duraciones,
            "duracion_total_segundos": round(
                sum(
                    float(valor)
                    for valor in duraciones.values()
                    if isinstance(
                        valor,
                        (
                            int,
                            float,
                        ),
                    )
                ),
                2,
            ),
        }

    def _calidad(
        self,
    ) -> dict[str, Any]:
        ruta = self._ultimo(
            "data/quality/media_quality_*.json"
        )

        datos = (
            self._leer_json(ruta)
            if ruta
            else {}
        )

        errores = datos.get(
            "errores",
            [],
        )

        advertencias = datos.get(
            "advertencias",
            [],
        )

        return {
            "archivo": (
                str(ruta)
                if ruta
                else ""
            ),
            "actualizado_en": self._fecha_archivo(
                ruta
            ),
            "estado": str(
                datos.get(
                    "estado",
                    "sin_informe",
                )
            ),
            "errores": (
                errores
                if isinstance(
                    errores,
                    list,
                )
                else []
            ),
            "advertencias": (
                advertencias
                if isinstance(
                    advertencias,
                    list,
                )
                else []
            ),
            "video": (
                datos.get(
                    "video",
                    {},
                )
                if isinstance(
                    datos.get(
                        "video",
                        {},
                    ),
                    dict,
                )
                else {}
            ),
            "subtitulos": (
                datos.get(
                    "subtitulos",
                    {},
                )
                if isinstance(
                    datos.get(
                        "subtitulos",
                        {},
                    ),
                    dict,
                )
                else {}
            ),
            "miniatura": (
                datos.get(
                    "miniatura",
                    {},
                )
                if isinstance(
                    datos.get(
                        "miniatura",
                        {},
                    ),
                    dict,
                )
                else {}
            ),
            "metadata": (
                datos.get(
                    "metadata",
                    {},
                )
                if isinstance(
                    datos.get(
                        "metadata",
                        {},
                    ),
                    dict,
                )
                else {}
            ),
            "shorts": (
                datos.get(
                    "shorts",
                    [],
                )
                if isinstance(
                    datos.get(
                        "shorts",
                        [],
                    ),
                    list,
                )
                else []
            ),
        }

    def _produccion(
        self,
        calidad: dict[str, Any],
        publicacion: dict[str, Any] | None = None,
        pipeline: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata_ruta = (
            self.project_root
            / "data"
            / "publish"
            / "metadata.json"
        )

        metadata = self._leer_json(
            metadata_ruta
        )

        publicacion = publicacion or {}
        pipeline = pipeline or {}

        titulo = str(
            metadata.get(
                "title",
                calidad.get(
                    "metadata",
                    {},
                ).get(
                    "titulo",
                    "Sin titulo",
                ),
            )
        )

        video_calidad = calidad.get(
            "video",
            {},
        )

        ruta_video_texto = str(
            video_calidad.get(
                "archivo",
                "",
            )
        )

        ruta_video = (
            Path(ruta_video_texto)
            if ruta_video_texto
            else self._ultimo(
                "output/videos/render_*/"
                "video_final_subtitulado_musica.mp4",
                "output/videos/render_*/"
                "video_final.mp4",
            )
        )

        existe_video = bool(
            ruta_video
            and ruta_video.is_file()
        )

        ruta_normalizada = (
            str(ruta_video.resolve()).casefold()
            if ruta_video
            else ""
        )

        publicado: dict[str, Any] | None = None
        elementos = publicacion.get(
            "elementos",
            [],
        )

        if isinstance(elementos, list):
            for elemento in elementos:
                if (
                    not isinstance(elemento, dict)
                    or elemento.get("estado") != "publicado"
                    or not elemento.get("video_id")
                    or not elemento.get("sha256")
                ):
                    continue

                archivo = str(
                    elemento.get(
                        "archivo",
                        "",
                    )
                )

                coincide_ruta = bool(
                    archivo
                    and ruta_normalizada
                    and str(
                        Path(archivo).resolve()
                    ).casefold()
                    == ruta_normalizada
                )

                coincide_titulo = (
                    str(
                        elemento.get(
                            "titulo",
                            "",
                        )
                    ).strip().casefold()
                    == titulo.strip().casefold()
                )

                if coincide_ruta or coincide_titulo:
                    publicado = elemento
                    break

        pipeline_en_curso = bool(
            not pipeline.get("completado")
            and int(
                pipeline.get(
                    "cantidad_completados",
                    0,
                )
                or 0
            )
            > 0
        )

        if pipeline_en_curso:
            estado_produccion = "en_produccion"
        elif existe_video:
            estado_produccion = "disponible_local"
        elif publicado:
            estado_produccion = "publicado_sin_copia_local"
        else:
            estado_produccion = "sin_video"

        tamano = (
            ruta_video.stat().st_size
            if existe_video
            else int(
                video_calidad.get(
                    "tamano_bytes",
                    0,
                )
                or 0
            )
        )

        return {
            "titulo": titulo,
            "video": (
                str(ruta_video)
                if ruta_video
                else ""
            ),
            "video_existe": existe_video,
            "estado": estado_produccion,
            "publicado": bool(publicado),
            "url": (
                str(
                    publicado.get(
                        "url",
                        "",
                    )
                )
                if publicado
                else ""
            ),
            "actualizado_en": self._fecha_archivo(
                ruta_video
                if isinstance(
                    ruta_video,
                    Path,
                )
                else None
            ),
            "tamano_bytes": tamano,
            "tamano": self._tamano_legible(
                tamano
            ),
            "duracion_segundos": float(
                video_calidad.get(
                    "duracion_segundos",
                    0,
                )
                or 0
            ),
            "duracion": self._duracion_legible(
                video_calidad.get(
                    "duracion_segundos",
                    0,
                )
            ),
            "resolucion": (
                f"{video_calidad.get('ancho', 0)}x"
                f"{video_calidad.get('alto', 0)}"
                if video_calidad
                else ""
            ),
            "fps": video_calidad.get(
                "fps",
                0,
            ),
            "codec": video_calidad.get(
                "codec_video",
                "",
            ),
            "metadata": str(
                metadata_ruta
            ),
        }

    def _publicacion(
        self,
    ) -> dict[str, Any]:
        ruta = (
            self.project_root
            / "data"
            / "publish"
            / "upload_queue.json"
        )

        datos = self._leer_json(
            ruta
        )

        elementos_raw = datos.get(
            "elementos",
            [],
        )

        elementos = (
            [
                elemento
                for elemento in elementos_raw
                if isinstance(
                    elemento,
                    dict,
                )
            ]
            if isinstance(
                elementos_raw,
                list,
            )
            else []
        )

        estados = Counter(
            str(
                elemento.get(
                    "estado",
                    "desconocido",
                )
            )
            for elemento in elementos
        )

        publicados = [
            elemento
            for elemento in elementos
            if elemento.get(
                "estado"
            )
            == "publicado"
        ]

        pendientes = [
            elemento
            for elemento in elementos
            if elemento.get(
                "estado"
            )
            not in {
                "publicado",
                "cancelado",
            }
        ]

        return {
            "archivo": str(ruta),
            "actualizado_en": self._fecha_archivo(
                ruta
            ),
            "total": len(
                elementos
            ),
            "estados": dict(
                estados
            ),
            "publicados": len(
                publicados
            ),
            "pendientes": len(
                pendientes
            ),
            "elementos": elementos,
            "ultimo_url": next(
                (
                    str(
                        elemento.get(
                            "url",
                            "",
                        )
                    )
                    for elemento in reversed(
                        elementos
                    )
                    if elemento.get(
                        "url"
                    )
                ),
                "",
            ),
        }

    def _analytics(
        self,
    ) -> dict[str, Any]:
        ruta = (
            self.project_root
            / "data"
            / "analytics"
            / "strategy_profile.json"
        )

        datos = self._leer_json(
            ruta
        )

        confianza = datos.get(
            "confianza",
            {},
        )

        metricas = datos.get(
            "metricas",
            {},
        )

        periodo = datos.get(
            "periodo",
            {},
        )

        recomendaciones = datos.get(
            "recomendaciones",
            [],
        )

        return {
            "archivo": str(ruta),
            "actualizado_en": self._fecha_archivo(
                ruta
            ),
            "disponible": bool(
                datos
            ),
            "confianza": (
                confianza
                if isinstance(
                    confianza,
                    dict,
                )
                else {}
            ),
            "metricas": (
                metricas
                if isinstance(
                    metricas,
                    dict,
                )
                else {}
            ),
            "periodo": (
                periodo
                if isinstance(
                    periodo,
                    dict,
                )
                else {}
            ),
            "recomendaciones": (
                recomendaciones
                if isinstance(
                    recomendaciones,
                    list,
                )
                else []
            ),
            "videos_analizados": (
                datos.get(
                    "videos_analizados",
                    [],
                )
                if isinstance(
                    datos.get(
                        "videos_analizados",
                        [],
                    ),
                    list,
                )
                else []
            ),
        }

    def _experimento(
        self,
    ) -> dict[str, Any]:
        ruta = (
            self.project_root
            / "data"
            / "experiments"
            / "experimento_actual.json"
        )

        datos = self._leer_json(
            ruta
        )

        evaluacion = datos.get(
            "evaluacion",
            {},
        )

        return {
            "archivo": str(ruta),
            "actualizado_en": self._fecha_archivo(
                ruta
            ),
            "disponible": bool(
                datos
            ),
            "experimento_id": str(
                datos.get(
                    "experimento_id",
                    "",
                )
            ),
            "variable": str(
                datos.get(
                    "variable",
                    "",
                )
            ),
            "estado": str(
                datos.get(
                    "estado",
                    "sin_experimento",
                )
            ),
            "cantidad_variantes": int(
                datos.get(
                    "cantidad_variantes",
                    0,
                )
                or 0
            ),
            "metrica": (
                datos.get(
                    "metrica",
                    {},
                )
                if isinstance(
                    datos.get(
                        "metrica",
                        {},
                    ),
                    dict,
                )
                else {}
            ),
            "evaluacion": (
                evaluacion
                if isinstance(
                    evaluacion,
                    dict,
                )
                else {}
            ),
            "variantes": (
                datos.get(
                    "variantes",
                    [],
                )
                if isinstance(
                    datos.get(
                        "variantes",
                        [],
                    ),
                    list,
                )
                else []
            ),
        }

    def _almacenamiento(
        self,
    ) -> dict[str, Any]:
        uso = shutil.disk_usage(
            self.project_root
        )

        output_dir = (
            self.project_root
            / "output"
        )

        tamano_output = 0
        cantidad_archivos = 0

        if output_dir.is_dir():
            for ruta in output_dir.rglob(
                "*"
            ):
                if not ruta.is_file():
                    continue

                try:
                    tamano_output += (
                        ruta.stat().st_size
                    )
                    cantidad_archivos += 1
                except OSError:
                    continue

        libre_porcentaje = round(
            uso.free
            / uso.total
            * 100
            if uso.total
            else 0.0,
            1,
        )

        return {
            "total_bytes": uso.total,
            "usado_bytes": uso.used,
            "libre_bytes": uso.free,
            "total": self._tamano_legible(
                uso.total
            ),
            "usado": self._tamano_legible(
                uso.used
            ),
            "libre": self._tamano_legible(
                uso.free
            ),
            "libre_porcentaje": libre_porcentaje,
            "output_bytes": tamano_output,
            "output": self._tamano_legible(
                tamano_output
            ),
            "archivos_output": cantidad_archivos,
        }

    def _logs(
        self,
        pipeline: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        pipeline = pipeline or {}

        ruta = (
            self.project_root
            / "logs"
            / "autotube.log"
        )

        if not ruta.is_file():
            return {
                "archivo": str(ruta),
                "errores_recientes": 0,
                "errores_historicos": 0,
                "errores_activos": 0,
                "advertencias_recientes": 0,
                "ultimo_error": "",
            }

        try:
            lineas = ruta.read_text(
                encoding="utf-8",
                errors="replace",
            ).splitlines()[-500:]
        except OSError:
            lineas = []

        errores = [
            linea
            for linea in lineas
            if "| ERROR |" in linea
        ]

        advertencias = [
            linea
            for linea in lineas
            if "| WARNING |" in linea
        ]

        return {
            "archivo": str(ruta),
            "actualizado_en": self._fecha_archivo(
                ruta
            ),
            "lineas_analizadas": len(
                lineas
            ),
            "errores_recientes": len(
                errores
            ),
            "errores_historicos": len(
                errores
            ),
            "errores_activos": int(
                bool(
                    pipeline.get(
                        "ultimo_error"
                    )
                )
            ),
            "advertencias_recientes": len(
                advertencias
            ),
            "ultimo_error": (
                errores[-1]
                if errores
                else ""
            ),
        }

    @staticmethod
    def _alertas(
        pipeline: dict[str, Any],
        calidad: dict[str, Any],
        publicacion: dict[str, Any],
        almacenamiento: dict[str, Any],
        produccion: dict[str, Any],
    ) -> list[dict[str, str]]:
        alertas: list[dict[str, str]] = []

        if pipeline.get(
            "ultimo_error"
        ):
            alertas.append(
                {
                    "nivel": "critica",
                    "mensaje": (
                        "Pipeline con error: "
                        + str(
                            pipeline[
                                "ultimo_error"
                            ]
                        )
                    ),
                }
            )

        estado_calidad = str(
            calidad.get(
                "estado",
                "sin_informe",
            )
        ).lower()

        if estado_calidad not in {
            "aprobado",
            "sin_informe",
        }:
            alertas.append(
                {
                    "nivel": "critica",
                    "mensaje": (
                        "El control multimedia no esta aprobado."
                    ),
                }
            )

        estado_produccion = str(
            produccion.get(
                "estado",
                "sin_video",
            )
        )

        if estado_produccion == "en_produccion":
            alertas.append(
                {
                    "nivel": "informativa",
                    "mensaje": (
                        "La produccion esta actualmente en curso."
                    ),
                }
            )
        elif (
            not produccion.get(
                "video_existe"
            )
            and estado_produccion
            == "publicado_sin_copia_local"
        ):
            alertas.append(
                {
                    "nivel": "informativa",
                    "mensaje": (
                        "Video publicado y verificado; "
                        "la copia local fue limpiada."
                    ),
                }
            )
        elif not produccion.get(
            "video_existe"
        ):
            alertas.append(
                {
                    "nivel": "critica",
                    "mensaje": (
                        "No se encontro el video final."
                    ),
                }
            )

        estados = publicacion.get(
            "estados",
            {},
        )

        if estados.get(
            "error",
            0,
        ):
            alertas.append(
                {
                    "nivel": "critica",
                    "mensaje": (
                        "La cola de YouTube contiene errores."
                    ),
                }
            )

        aplazados_limite = int(
            estados.get(
                "aplazado_limite",
                0,
            )
            or 0
        )

        if aplazados_limite:
            alertas.append(
                {
                    "nivel": "advertencia",
                    "mensaje": (
                        f"{aplazados_limite} publicaciones "
                        "esperan el reinicio del limite de YouTube."
                    ),
                }
            )

        aplazados_conexion = int(
            estados.get(
                "aplazado_conexion",
                0,
            )
            or 0
        )

        if aplazados_conexion:
            alertas.append(
                {
                    "nivel": "advertencia",
                    "mensaje": (
                        f"{aplazados_conexion} publicaciones "
                        "esperan recuperacion de conexion."
                    ),
                }
            )

        if (
            pipeline.get(
                "progreso_porcentaje",
                0,
            )
            >= 100
            and not pipeline.get(
                "completado"
            )
        ):
            alertas.append(
                {
                    "nivel": "advertencia",
                    "mensaje": (
                        "Las etapas base terminaron, pero "
                        "la etapa final no marco el pipeline "
                        "como completado."
                    ),
                }
            )

        libre_porcentaje = float(
            almacenamiento.get(
                "libre_porcentaje",
                0,
            )
            or 0
        )

        libre_bytes = int(
            almacenamiento.get(
                "libre_bytes",
                0,
            )
            or 0
        )

        if (
            libre_porcentaje < 5
            or libre_bytes
            < 5 * 1024**3
        ):
            alertas.append(
                {
                    "nivel": "critica",
                    "mensaje": (
                        "Espacio en disco criticamente bajo."
                    ),
                }
            )
        elif libre_porcentaje < 15:
            alertas.append(
                {
                    "nivel": "advertencia",
                    "mensaje": (
                        "Queda menos de 15% de espacio en disco."
                    ),
                }
            )

        if not alertas:
            alertas.append(
                {
                    "nivel": "informativa",
                    "mensaje": (
                        "No se detectaron problemas operativos."
                    ),
                }
            )

        return alertas

    def recopilar(
        self,
    ) -> dict[str, Any]:
        pipeline = self._estado_pipeline()
        calidad = self._calidad()
        publicacion = self._publicacion()
        produccion = self._produccion(
            calidad,
            publicacion=publicacion,
            pipeline=pipeline,
        )
        analytics = self._analytics()
        experimento = self._experimento()
        almacenamiento = self._almacenamiento()
        logs = self._logs(
            pipeline=pipeline
        )

        alertas = self._alertas(
            pipeline=pipeline,
            calidad=calidad,
            publicacion=publicacion,
            almacenamiento=almacenamiento,
            produccion=produccion,
        )

        niveles = {
            alerta["nivel"]
            for alerta in alertas
        }

        if "critica" in niveles:
            estado_general = "critico"
        elif "advertencia" in niveles:
            estado_general = "atencion"
        else:
            estado_general = "operativo"

        return {
            "version": 1,
            "generado_en": (
                datetime.now()
                .astimezone()
                .isoformat(timespec="seconds")
            ),
            "estado_general": estado_general,
            "pipeline": pipeline,
            "produccion": produccion,
            "calidad": calidad,
            "publicacion": publicacion,
            "analytics": analytics,
            "experimento": experimento,
            "almacenamiento": almacenamiento,
            "logs": logs,
            "alertas": alertas,
        }

    def guardar(
        self,
        datos: dict[str, Any],
        crear_historico: bool = True,
    ) -> dict[str, Path]:
        marca = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        data_dir = (
            self.project_root
            / "data"
            / "operations"
        )

        output_dir = (
            self.project_root
            / "output"
            / "dashboard"
        )

        data_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        historico = (
            data_dir
            / f"dashboard_{marca}.json"
        )

        actual = (
            data_dir
            / "dashboard_latest.json"
        )

        contenido = json.dumps(
            datos,
            ensure_ascii=False,
            indent=2,
        )

        if crear_historico:
            historico.write_text(
                contenido,
                encoding="utf-8",
            )
        else:
            historico = actual

        actual.write_text(
            contenido,
            encoding="utf-8",
        )

        html_path = (
            output_dir
            / "centro_control.html"
        )

        html_path.write_text(
            self._crear_html(
                datos
            ),
            encoding="utf-8",
        )

        return {
            "historico": historico,
            "actual": actual,
            "html": html_path,
        }

    @staticmethod
    def _crear_html(
        datos: dict[str, Any],
    ) -> str:
        pipeline = datos["pipeline"]
        produccion = datos["produccion"]
        calidad = datos["calidad"]
        publicacion = datos["publicacion"]
        analytics = datos["analytics"]
        experimento = datos["experimento"]
        almacenamiento = datos["almacenamiento"]
        logs = datos["logs"]

        def seguro(
            valor: Any,
        ) -> str:
            return html.escape(
                str(valor)
            )

        alertas_html = "".join(
            (
                '<li class="'
                + seguro(
                    alerta["nivel"]
                )
                + '">'
                + seguro(
                    alerta["mensaje"]
                )
                + "</li>"
            )
            for alerta in datos["alertas"]
        )

        estados_cola = "".join(
            (
                "<tr><td>"
                + seguro(estado)
                + "</td><td>"
                + seguro(cantidad)
                + "</td></tr>"
            )
            for estado, cantidad in sorted(
                publicacion["estados"].items()
            )
        )

        duraciones = pipeline.get(
            "duraciones_pasos",
            {},
        )

        filas_duraciones = "".join(
            (
                "<tr><td>"
                + seguro(nombre)
                + "</td><td>"
                + seguro(
                    f"{float(segundos):.1f} s"
                )
                + "</td></tr>"
            )
            for nombre, segundos in duraciones.items()
            if isinstance(
                segundos,
                (
                    int,
                    float,
                ),
            )
        )

        if not filas_duraciones:
            filas_duraciones = (
                "<tr><td colspan='2'>"
                "Los tiempos se registraran en la "
                "proxima produccion.</td></tr>"
            )

        confianza = analytics.get(
            "confianza",
            {},
        )

        metricas = analytics.get(
            "metricas",
            {},
        )

        metrica_experimento = experimento.get(
            "metrica",
            {},
        )

        intervalo_actualizacion = int(
            datos.get(
                "actualizacion_automatica_segundos",
                0,
            )
            or 0
        )

        meta_actualizacion = (
            (
                '<meta http-equiv="refresh" '
                f'content="{intervalo_actualizacion}">'
            )
            if intervalo_actualizacion >= 5
            else ""
        )

        estilos = """
:root {
  color-scheme: dark;
  --bg: #07101f;
  --panel: #111d31;
  --line: #273a57;
  --text: #eef6ff;
  --muted: #9fb2ca;
  --cyan: #00d9f5;
  --green: #32d583;
  --yellow: #fdb022;
  --red: #f97066;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: linear-gradient(145deg, #050a14, var(--bg));
  color: var(--text);
  font-family: Segoe UI, Arial, sans-serif;
}
main {
  max-width: 1380px;
  margin: auto;
  padding: 28px;
}
header {
  display: flex;
  justify-content: space-between;
  align-items: end;
  gap: 20px;
  margin-bottom: 22px;
}
h1 { margin: 0; font-size: 30px; }
h2 { margin-top: 0; font-size: 18px; }
small, .muted { color: var(--muted); }
.badge {
  display: inline-block;
  padding: 8px 14px;
  border-radius: 999px;
  font-weight: 700;
  text-transform: uppercase;
}
.operativo { background: #123c2b; color: var(--green); }
.atencion { background: #4a3611; color: var(--yellow); }
.critico { background: #4a1f24; color: var(--red); }
.grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 16px;
}
.card {
  grid-column: span 4;
  background: rgba(17, 29, 49, .96);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 12px 35px rgba(0,0,0,.22);
}
.card.wide { grid-column: span 6; }
.card.full { grid-column: 1 / -1; }
.metric {
  font-size: 28px;
  font-weight: 750;
  color: var(--cyan);
  margin: 4px 0;
}
.progress {
  height: 12px;
  background: #26354b;
  border-radius: 999px;
  overflow: hidden;
  margin: 12px 0;
}
.progress > div {
  height: 100%;
  background: linear-gradient(90deg, #00a9ce, var(--cyan));
}
table {
  width: 100%;
  border-collapse: collapse;
}
td, th {
  padding: 9px;
  border-bottom: 1px solid var(--line);
  text-align: left;
}
ul { padding-left: 20px; }
li { margin: 9px 0; }
li.critica { color: var(--red); }
li.advertencia { color: var(--yellow); }
li.informativa { color: var(--green); }
.path {
  word-break: break-all;
  color: var(--muted);
  font-size: 12px;
}
@media (max-width: 900px) {
  .card, .card.wide { grid-column: 1 / -1; }
  header { align-items: start; flex-direction: column; }
}
"""

        return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
{meta_actualizacion}
<title>Centro de Control AutoTube AI</title>
<style>{estilos}</style>
</head>
<body>
<main>
<header>
  <div>
    <small>NEXON IA</small>
    <h1>Centro de Control AutoTube AI</h1>
    <div class="muted">Actualizado: {seguro(datos["generado_en"])}</div>
  </div>
  <span class="badge {seguro(datos["estado_general"])}">
    {seguro(datos["estado_general"])}
  </span>
</header>

<section class="grid">
  <article class="card">
    <h2>Pipeline</h2>
    <div class="metric">{seguro(pipeline["progreso_porcentaje"])}%</div>
    <div>{seguro(pipeline["cantidad_completados"])} de {seguro(pipeline["total_pasos"])} pasos</div>
    <div class="progress"><div style="width:{seguro(pipeline["progreso_porcentaje"])}%"></div></div>
    <div>Completado: {seguro(pipeline["completado"])}</div>
  </article>

  <article class="card">
    <h2>Produccion</h2>
    <div class="metric">{seguro(produccion["duracion"])}</div>
    <div>{seguro(produccion["resolucion"])} · {seguro(produccion["fps"])} FPS</div>
    <div>{seguro(produccion["tamano"])}</div>
    <p>{seguro(produccion["titulo"])}</p>
    <div>Estado: {seguro(produccion.get("estado", "sin_video"))}</div>
  </article>

  <article class="card">
    <h2>Control multimedia</h2>
    <div class="metric">{seguro(calidad["estado"].upper())}</div>
    <div>Errores: {seguro(len(calidad["errores"]))}</div>
    <div>Advertencias: {seguro(len(calidad["advertencias"]))}</div>
    <div>Shorts: {seguro(len(calidad["shorts"]))}</div>
  </article>

  <article class="card">
    <h2>Publicacion</h2>
    <div class="metric">{seguro(publicacion["publicados"])} / {seguro(publicacion["total"])}</div>
    <div>Publicados / registrados</div>
    <div>Pendientes: {seguro(publicacion["pendientes"])}</div>
    <table>{estados_cola}</table>
  </article>

  <article class="card">
    <h2>Analytics</h2>
    <div class="metric">{seguro(metricas.get("views", 0))} vistas</div>
    <div>Retencion: {seguro(round(float(metricas.get("retencion_porcentaje", 0) or 0), 1))}%</div>
    <div>Interaccion: {seguro(round(float(metricas.get("interaccion_porcentaje", 0) or 0), 1))}%</div>
    <div>Confianza: {seguro(str(confianza.get("nivel", "sin datos")).upper())}</div>
  </article>

  <article class="card">
    <h2>Experimento A/B</h2>
    <div class="metric">{seguro(experimento.get("variable", "") or "Sin experimento")}</div>
    <div>Estado: {seguro(experimento["estado"])}</div>
    <div>Variantes: {seguro(experimento["cantidad_variantes"])}</div>
    <div>Metrica: {seguro(metrica_experimento.get("primaria", ""))}</div>
  </article>

  <article class="card wide">
    <h2>Almacenamiento</h2>
    <div class="metric">{seguro(almacenamiento["libre"])} libres</div>
    <div>{seguro(almacenamiento["libre_porcentaje"])}% disponible</div>
    <div>Carpeta output: {seguro(almacenamiento["output"])}</div>
    <div>Archivos en output: {seguro(almacenamiento["archivos_output"])}</div>
  </article>

  <article class="card wide">
    <h2>Registros recientes</h2>
    <div class="metric">{seguro(logs.get("errores_activos", 0))} errores activos</div>
    <div>Errores historicos: {seguro(logs.get("errores_historicos", 0))}</div>
    <div>Advertencias: {seguro(logs["advertencias_recientes"])}</div>
    <p class="path">{seguro(pipeline.get("ultimo_error", "") or "Sin errores activos.")}</p>
  </article>

  <article class="card wide">
    <h2>Tiempos por etapa</h2>
    <table>
      <thead><tr><th>Etapa</th><th>Duracion</th></tr></thead>
      <tbody>{filas_duraciones}</tbody>
    </table>
  </article>

  <article class="card wide">
    <h2>Alertas operativas</h2>
    <ul>{alertas_html}</ul>
  </article>

  <article class="card full">
    <h2>Archivos principales</h2>
    <p class="path">Video: {seguro(produccion["video"])}</p>
    <p class="path">Calidad: {seguro(calidad["archivo"])}</p>
    <p class="path">Cola: {seguro(publicacion["archivo"])}</p>
    <p class="path">Experimento: {seguro(experimento["archivo"])}</p>
  </article>
</section>
</main>
</body>
</html>
"""

    def imprimir(
        self,
        datos: dict[str, Any],
        rutas: dict[str, Path],
    ) -> None:
        pipeline = datos["pipeline"]
        produccion = datos["produccion"]
        calidad = datos["calidad"]
        publicacion = datos["publicacion"]
        analytics = datos["analytics"]
        experimento = datos["experimento"]
        almacenamiento = datos["almacenamiento"]
        logs = datos["logs"]

        confianza = analytics.get(
            "confianza",
            {},
        )

        metricas = analytics.get(
            "metricas",
            {},
        )

        print()
        print("CENTRO DE CONTROL AUTOTUBE AI")
        print("=" * 72)
        print(
            "ESTADO GENERAL:",
            datos["estado_general"].upper(),
        )
        print(
            "Pipeline:",
            f"{pipeline['cantidad_completados']}/"
            f"{pipeline['total_pasos']} pasos",
            f"({pipeline['progreso_porcentaje']}%)",
            "| Completado:",
            pipeline["completado"],
        )
        print(
            "Produccion:",
            produccion["titulo"],
        )
        print(
            "Video:",
            produccion["duracion"],
            "|",
            produccion["resolucion"],
            "|",
            produccion["tamano"],
        )
        print(
            "Calidad:",
            calidad["estado"].upper(),
            "| Errores:",
            len(
                calidad["errores"]
            ),
            "| Advertencias:",
            len(
                calidad["advertencias"]
            ),
        )
        print(
            "YouTube:",
            publicacion["publicados"],
            "publicados |",
            publicacion["pendientes"],
            "pendientes |",
            publicacion["estados"],
        )
        print(
            "Analytics:",
            metricas.get(
                "views",
                0,
            ),
            "vistas | Retencion:",
            round(
                float(
                    metricas.get(
                        "retencion_porcentaje",
                        0,
                    )
                    or 0
                ),
                1,
            ),
            "% | Confianza:",
            str(
                confianza.get(
                    "nivel",
                    "sin datos",
                )
            ).upper(),
        )
        print(
            "Experimento:",
            (
                experimento["variable"]
                if experimento["disponible"]
                else "ninguno"
            ),
            "| Estado:",
            experimento["estado"],
            "| Variantes:",
            experimento["cantidad_variantes"],
        )
        print(
            "Disco:",
            almacenamiento["libre"],
            "libres",
            f"({almacenamiento['libre_porcentaje']}%)",
            "| output:",
            almacenamiento["output"],
        )
        print(
            "Logs recientes:",
            logs.get(
                "errores_activos",
                0,
            ),
            "errores activos |",
            logs.get(
                "errores_historicos",
                0,
            ),
            "historicos |",
            logs["advertencias_recientes"],
            "advertencias",
        )

        print("-" * 72)
        print("ALERTAS")

        for alerta in datos["alertas"]:
            print(
                f"[{alerta['nivel'].upper()}] "
                f"{alerta['mensaje']}"
            )

        print("=" * 72)
        print(
            "Panel HTML:",
            rutas["html"],
        )
        print(
            "Informe JSON:",
            rutas["historico"],
        )
        print("=" * 72)

    def generar(
        self,
        abrir: bool = False,
        actualizacion_automatica_segundos: int = 0,
        crear_historico: bool = True,
        imprimir: bool = True,
    ) -> dict[str, Any]:
        datos = self.recopilar()
        datos[
            "actualizacion_automatica_segundos"
        ] = max(
            0,
            int(
                actualizacion_automatica_segundos
            ),
        )

        rutas = self.guardar(
            datos,
            crear_historico=crear_historico,
        )

        if imprimir:
            self.imprimir(
                datos,
                rutas,
            )

        if abrir:
            webbrowser.open(
                rutas["html"].resolve().as_uri()
            )

        return {
            "datos": datos,
            "rutas": rutas,
        }

    def seguir(
        self,
        intervalo: int = 30,
        abrir: bool = True,
    ) -> dict[str, Any]:
        intervalo = max(
            5,
            int(
                intervalo
            ),
        )

        resultado = self.generar(
            abrir=abrir,
            actualizacion_automatica_segundos=intervalo,
        )

        print(
            "Actualizacion automatica:",
            f"cada {intervalo} segundos.",
        )
        print(
            "Presiona Ctrl+C para detener "
            "solo la actualizacion del panel."
        )

        try:
            while True:
                time.sleep(
                    intervalo
                )

                resultado = self.generar(
                    abrir=False,
                    actualizacion_automatica_segundos=intervalo,
                    crear_historico=False,
                    imprimir=False,
                )

        except KeyboardInterrupt:
            print()
            print(
                "Actualizacion automatica detenida."
            )

        return resultado

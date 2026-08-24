from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class LimpiadorAlmacenamiento:
    """Audita y elimina solo archivos regenerables y no protegidos."""

    CARPETAS_PRUEBA = (
        "hardware_tests",
        "pexels_tests",
        "wikimedia_tests",
        "voice_tests",
        "previews",
    )

    FINALES_YOUTUBE = (
        "video_final_subtitulado_musica.mp4",
        "video_final_listo_youtube.mp4",
        "video_final_subtitulado.mp4",
    )

    def __init__(
        self,
        project_root: Path,
    ) -> None:
        self.project_root = Path(
            project_root
        ).resolve()

        self.output_dir = (
            self.project_root
            / "output"
        ).resolve()

        self.operations_dir = (
            self.project_root
            / "data"
            / "operations"
        )

    @staticmethod
    def _ahora() -> str:
        return (
            datetime.now()
            .astimezone()
            .isoformat(timespec="seconds")
        )

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

    @staticmethod
    def _guardar_json_atomico(
        ruta: Path,
        datos: dict[str, Any],
    ) -> None:
        ruta.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporal = ruta.with_suffix(
            ruta.suffix + ".tmp"
        )

        temporal.write_text(
            json.dumps(
                datos,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        temporal.replace(
            ruta
        )

    @staticmethod
    def _tamano(
        ruta: Path,
    ) -> int:
        try:
            if ruta.is_file() or ruta.is_symlink():
                return ruta.stat().st_size

            total = 0

            for archivo in ruta.rglob("*"):
                try:
                    if archivo.is_file():
                        total += archivo.stat().st_size
                except OSError:
                    continue

            return total

        except OSError:
            return 0

    @staticmethod
    def _tamano_legible(
        bytes_total: int,
    ) -> str:
        valor = float(
            max(
                0,
                bytes_total,
            )
        )

        for unidad in (
            "B",
            "KB",
            "MB",
            "GB",
            "TB",
        ):
            if (
                valor < 1024
                or unidad == "TB"
            ):
                return (
                    f"{valor:.1f} {unidad}"
                )

            valor /= 1024

        return "0 B"

    def _ruta_segura(
        self,
        ruta: Path,
    ) -> bool:
        try:
            resuelta = ruta.resolve()
            resuelta.relative_to(
                self.output_dir
            )
        except (
            OSError,
            ValueError,
        ):
            return False

        return (
            resuelta != self.output_dir
            and resuelta.exists()
        )

    def _extraer_rutas(
        self,
        valor: Any,
        salida: set[Path],
    ) -> None:
        if isinstance(
            valor,
            dict,
        ):
            for elemento in valor.values():
                self._extraer_rutas(
                    elemento,
                    salida,
                )
            return

        if isinstance(
            valor,
            list,
        ):
            for elemento in valor:
                self._extraer_rutas(
                    elemento,
                    salida,
                )
            return

        if not isinstance(
            valor,
            str,
        ):
            return

        texto = valor.strip()

        if (
            not texto
            or "://" in texto
        ):
            return

        candidata = Path(
            texto
        ).expanduser()

        if not candidata.is_absolute():
            candidata = (
                self.project_root
                / candidata
            )

        try:
            candidata = candidata.resolve()
        except OSError:
            return

        if not candidata.exists():
            return

        try:
            candidata.relative_to(
                self.output_dir
            )
        except ValueError:
            return

        salida.add(
            candidata
        )

    def _fuentes_referencia(
        self,
    ) -> list[Path]:
        fuentes: list[Path] = []

        cola = (
            self.project_root
            / "data"
            / "publish"
            / "upload_queue.json"
        )

        if cola.is_file():
            fuentes.append(
                cola
            )

        calidad = sorted(
            (
                self.project_root
                / "data"
                / "quality"
            ).glob(
                "media_quality_*.json"
            ),
            key=lambda ruta: (
                ruta.stat().st_mtime
            ),
            reverse=True,
        )

        if calidad:
            fuentes.append(
                calidad[0]
            )

        fuentes.extend(
            ruta
            for ruta in self.project_root.glob(
                "output/shorts/shorts_*/"
                "shorts_manifest.json"
            )
            if ruta.is_file()
        )

        fuentes.extend(
            ruta
            for ruta in self.project_root.glob(
                "output/youtube/publish_*.json"
            )
            if ruta.is_file()
        )

        experimento = (
            self.project_root
            / "data"
            / "experiments"
            / "experimento_actual.json"
        )

        if experimento.is_file():
            fuentes.append(
                experimento
            )

        return fuentes

    def rutas_protegidas(
        self,
    ) -> set[Path]:
        protegidas: set[Path] = set()

        for fuente in self._fuentes_referencia():
            datos = self._leer_json(
                fuente
            )

            self._extraer_rutas(
                datos,
                protegidas,
            )

        renders = [
            ruta
            for ruta in self.project_root.glob(
                "output/videos/render_*"
            )
            if ruta.is_dir()
        ]

        if renders:
            reciente = max(
                renders,
                key=lambda ruta: (
                    ruta.stat().st_mtime
                ),
            ).resolve()

            protegidas.add(
                reciente
            )

        return protegidas

    @staticmethod
    def _contiene_protegido(
        ruta: Path,
        protegidas: set[Path],
    ) -> bool:
        objetivo = ruta.resolve()

        for protegida in protegidas:
            try:
                protegida_resuelta = (
                    protegida.resolve()
                )
            except OSError:
                continue

            if protegida_resuelta == objetivo:
                return True

            if ruta.is_dir():
                try:
                    protegida_resuelta.relative_to(
                        objetivo
                    )
                    return True
                except ValueError:
                    pass

        return False

    def _candidato(
        self,
        ruta: Path,
        tipo: str,
        motivo: str,
    ) -> dict[str, Any]:
        tamano = self._tamano(
            ruta
        )

        return {
            "ruta": str(
                ruta.resolve()
            ),
            "tipo": tipo,
            "motivo": motivo,
            "tamano_bytes": tamano,
            "tamano": self._tamano_legible(
                tamano
            ),
            "es_directorio": ruta.is_dir(),
            "eliminado": False,
            "error": "",
        }

    def _antiguo(
        self,
        ruta: Path,
        horas: int = 24,
    ) -> bool:
        limite = (
            datetime.now()
            - timedelta(
                hours=horas
            )
        ).timestamp()

        try:
            return (
                ruta.stat().st_mtime
                < limite
            )
        except OSError:
            return False


    def _candidatos_publicados(
        self,
    ) -> list[dict[str, Any]]:
        cola_path = (
            self.project_root
            / "data"
            / "publish"
            / "upload_queue.json"
        )

        cola = self._leer_json(
            cola_path
        )

        candidatos: list[
            dict[str, Any]
        ] = []

        for elemento in cola.get(
            "elementos",
            [],
        ):
            if not isinstance(
                elemento,
                dict,
            ):
                continue

            if elemento.get(
                "estado"
            ) != "publicado":
                continue

            video_id = str(
                elemento.get(
                    "video_id",
                    "",
                )
            ).strip()

            registrado = str(
                elemento.get(
                    "sha256",
                    "",
                )
            ).strip().lower()

            archivo = Path(
                str(
                    elemento.get(
                        "archivo",
                        "",
                    )
                )
            )

            if (
                not video_id
                or not registrado
                or not archivo.is_file()
            ):
                continue

            if not self._ruta_segura(
                archivo
            ):
                continue

            digest = hashlib.sha256()

            try:
                with archivo.open(
                    "rb"
                ) as entrada:
                    for bloque in iter(
                        lambda: entrada.read(
                            1024 * 1024
                        ),
                        b"",
                    ):
                        digest.update(
                            bloque
                        )
            except OSError:
                continue

            calculado = (
                digest.hexdigest()
            )

            if calculado != registrado:
                continue

            candidato = self._candidato(
                archivo,
                "publicado_verificado",
                (
                    "Archivo publicado en YouTube "
                    "con video_id y SHA256 verificados."
                ),
            )

            candidato.update(
                {
                    "video_id": video_id,
                    "elemento_id": str(
                        elemento.get(
                            "id",
                            "",
                        )
                    ),
                    "sha256": calculado,
                    "sha256_verificado": True,
                }
            )

            candidatos.append(
                candidato
            )

        return candidatos

    def auditar(
        self,
        incluir_publicados: bool = False,
    ) -> dict[str, Any]:
        protegidas = (
            self.rutas_protegidas()
        )

        candidatos: list[
            dict[str, Any]
        ] = []

        if incluir_publicados:
            candidatos.extend(
                self._candidatos_publicados()
            )

        for nombre in self.CARPETAS_PRUEBA:
            ruta = (
                self.output_dir
                / nombre
            )

            if (
                ruta.exists()
                and not self._contiene_protegido(
                    ruta,
                    protegidas,
                )
            ):
                candidatos.append(
                    self._candidato(
                        ruta,
                        "pruebas",
                        (
                            "Salida de prueba regenerable "
                            "y no referenciada."
                        ),
                    )
                )

        renders = sorted(
            (
                ruta
                for ruta in (
                    self.output_dir
                    / "videos"
                ).glob(
                    "render_*"
                )
                if ruta.is_dir()
            ),
            key=lambda ruta: (
                ruta.stat().st_mtime
            ),
            reverse=True,
        )

        render_reciente = (
            renders[0].resolve()
            if renders
            else None
        )

        for render in renders:
            render_resuelto = (
                render.resolve()
            )

            if (
                render_reciente is not None
                and render_resuelto
                == render_reciente
            ):
                continue

            if self._contiene_protegido(
                render,
                protegidas,
            ):
                continue

            archivos_mp4 = [
                ruta
                for ruta in render.glob(
                    "*.mp4"
                )
                if ruta.is_file()
                and ruta.stat().st_size > 0
            ]

            finales = [
                render / nombre
                for nombre in self.FINALES_YOUTUBE
                if (
                    (render / nombre).is_file()
                    and (
                        render
                        / nombre
                    ).stat().st_size > 0
                )
            ]

            if (
                not archivos_mp4
                and self._antiguo(
                    render,
                    horas=24,
                )
            ):
                candidatos.append(
                    self._candidato(
                        render,
                        "render_incompleto",
                        (
                            "Render antiguo sin ningun "
                            "video MP4 terminado."
                        ),
                    )
                )
                continue

            if (
                archivos_mp4
                and all(
                    ruta.name == "preview.mp4"
                    for ruta in archivos_mp4
                )
                and self._antiguo(
                    render,
                    horas=24,
                )
            ):
                candidatos.append(
                    self._candidato(
                        render,
                        "preview",
                        (
                            "Render antiguo que contiene "
                            "solo una vista previa."
                        ),
                    )
                )
                continue

            work = (
                render
                / "work"
            )

            if (
                work.is_dir()
                and not self._contiene_protegido(
                    work,
                    protegidas,
                )
            ):
                candidatos.append(
                    self._candidato(
                        work,
                        "temporales_render",
                        (
                            "Clips temporales regenerables "
                            "de un render."
                        ),
                    )
                )

            intermedio = (
                render
                / "video_final.mp4"
            )

            if (
                finales
                and intermedio.is_file()
                and not self._contiene_protegido(
                    intermedio,
                    protegidas,
                )
            ):
                candidatos.append(
                    self._candidato(
                        intermedio,
                        "video_intermedio",
                        (
                            "Existe una version finalizada "
                            "para YouTube en el mismo render."
                        ),
                    )
                )

        temporales = []

        for patron in (
            "**/*.tmp",
            "**/*_tmp.*",
            "**/*.part",
        ):
            temporales.extend(
                self.output_dir.glob(
                    patron
                )
            )

        for temporal in temporales:
            if (
                temporal.exists()
                and self._antiguo(
                    temporal,
                    horas=24,
                )
                and not self._contiene_protegido(
                    temporal,
                    protegidas,
                )
            ):
                candidatos.append(
                    self._candidato(
                        temporal,
                        "temporal",
                        "Archivo temporal antiguo.",
                    )
                )

        candidatos_ordenados = sorted(
            candidatos,
            key=lambda item: (
                int(
                    item["tamano_bytes"]
                )
            ),
            reverse=True,
        )

        candidatos_finales: list[
            dict[str, Any]
        ] = []

        rutas_directorio: list[Path] = []

        for candidato in candidatos_ordenados:
            ruta = Path(
                candidato["ruta"]
            )

            contenido = False

            for directorio in rutas_directorio:
                try:
                    ruta.relative_to(
                        directorio
                    )
                    contenido = True
                    break
                except ValueError:
                    continue

            if contenido:
                continue

            candidatos_finales.append(
                candidato
            )

            if candidato[
                "es_directorio"
            ]:
                rutas_directorio.append(
                    ruta
                )

        total = sum(
            int(
                candidato[
                    "tamano_bytes"
                ]
            )
            for candidato in candidatos_finales
        )

        uso = shutil.disk_usage(
            self.project_root
        )

        return {
            "version": 1,
            "generado_en": self._ahora(),

            "modo": (
                "seguro_y_publicados"
                if incluir_publicados
                else "seguro"
            ),
            "incluir_publicados": incluir_publicados,
            "confirmado": False,
            "estado": "auditado",
            "project_root": str(
                self.project_root
            ),
            "output": str(
                self.output_dir
            ),
            "protegidos": [
                str(ruta)
                for ruta in sorted(
                    protegidas,
                    key=lambda item: str(
                        item
                    ).casefold(),
                )
            ],
            "cantidad_protegidos": len(
                protegidas
            ),
            "candidatos": candidatos_finales,
            "cantidad_candidatos": len(
                candidatos_finales
            ),
            "recuperable_bytes": total,
            "recuperable": self._tamano_legible(
                total
            ),
            "disco_antes": {
                "libre_bytes": uso.free,
                "libre": self._tamano_legible(
                    uso.free
                ),
                "libre_gb": round(
                    uso.free
                    / (1024 ** 3),
                    2,
                ),
            },
            "disco_estimado_despues": {
                "libre_bytes": (
                    uso.free
                    + total
                ),
                "libre": self._tamano_legible(
                    uso.free
                    + total
                ),
                "libre_gb": round(
                    (
                        uso.free
                        + total
                    )
                    / (1024 ** 3),
                    2,
                ),
            },
            "errores": [],
        }

    def guardar_informe(
        self,
        informe: dict[str, Any],
    ) -> dict[str, Path]:
        marca = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        historico = (
            self.operations_dir
            / f"storage_cleanup_{marca}.json"
        )

        actual = (
            self.operations_dir
            / "storage_cleanup_latest.json"
        )

        self._guardar_json_atomico(
            historico,
            informe,
        )

        self._guardar_json_atomico(
            actual,
            informe,
        )

        return {
            "historico": historico,
            "actual": actual,
        }

    def ejecutar(
        self,
        confirmar: bool = False,
        incluir_publicados: bool = False,
    ) -> dict[str, Any]:
        informe = self.auditar(
            incluir_publicados=incluir_publicados,
        )
        informe["confirmado"] = confirmar

        if not confirmar:
            rutas = self.guardar_informe(
                informe
            )

            return {
                "informe": informe,
                "rutas": rutas,
            }

        informe["estado"] = (
            "eliminando"
        )

        rutas = self.guardar_informe(
            informe
        )

        eliminados = 0
        liberados = 0
        publicados_eliminados: set[str] = set()

        for candidato in informe[
            "candidatos"
        ]:
            ruta = Path(
                candidato["ruta"]
            )

            if not self._ruta_segura(
                ruta
            ):
                candidato["error"] = (
                    "Ruta inexistente o fuera de output."
                )
                informe["errores"].append(
                    (
                        f"Ruta rechazada por seguridad: "
                        f"{ruta}"
                    )
                )
                continue

            try:
                if (
                    ruta.is_symlink()
                    or ruta.is_file()
                ):
                    ruta.unlink()
                elif ruta.is_dir():
                    shutil.rmtree(
                        ruta
                    )
                else:
                    candidato["error"] = (
                        "Tipo de archivo no compatible."
                    )
                    continue

            except OSError as error:
                candidato["error"] = str(
                    error
                )
                informe["errores"].append(
                    f"{ruta}: {error}"
                )
                continue

            candidato["eliminado"] = True
            eliminados += 1
            liberados += int(
                candidato[
                    "tamano_bytes"
                ]
            )

            if (
                candidato.get("tipo")
                == "publicado_verificado"
                and candidato.get("video_id")
            ):
                publicados_eliminados.add(
                    str(
                        candidato["video_id"]
                    )
                )

        if publicados_eliminados:
            cola_path = (
                self.project_root
                / "data"
                / "publish"
                / "upload_queue.json"
            )

            cola = self._leer_json(
                cola_path
            )

            actualizado_en = self._ahora()

            for elemento in cola.get(
                "elementos",
                [],
            ):
                if (
                    isinstance(
                        elemento,
                        dict,
                    )
                    and str(
                        elemento.get(
                            "video_id",
                            "",
                        )
                    )
                    in publicados_eliminados
                ):
                    elemento[
                        "archivo_local_disponible"
                    ] = False
                    elemento[
                        "archivo_local_eliminado_en"
                    ] = actualizado_en
                    elemento[
                        "sha256_verificado_antes_de_eliminar"
                    ] = True

            cola["actualizado_en"] = (
                actualizado_en
            )

            self._guardar_json_atomico(
                cola_path,
                cola,
            )

        uso_despues = shutil.disk_usage(
            self.project_root
        )

        informe["eliminados"] = eliminados
        informe["liberados_bytes"] = (
            liberados
        )
        informe["liberados"] = (
            self._tamano_legible(
                liberados
            )
        )
        informe["disco_despues"] = {
            "libre_bytes": (
                uso_despues.free
            ),
            "libre": self._tamano_legible(
                uso_despues.free
            ),
            "libre_gb": round(
                uso_despues.free
                / (1024 ** 3),
                2,
            ),
        }
        informe["estado"] = (
            "completado"
            if not informe["errores"]
            else "completado_con_errores"
        )
        informe["finalizado_en"] = (
            self._ahora()
        )

        rutas = self.guardar_informe(
            informe
        )

        return {
            "informe": informe,
            "rutas": rutas,
        }

    @staticmethod
    def imprimir(
        resultado: dict[str, Any],
    ) -> None:
        informe = resultado["informe"]

        print()
        print(
            "LIMPIEZA SEGURA DE ALMACENAMIENTO"
        )
        print("=" * 72)
        print(
            "Modo:",
            (
                "ELIMINACION CONFIRMADA"
                if informe["confirmado"]
                else "SIMULACION"
            ),
        )
        print(
            "Rutas protegidas:",
            informe["cantidad_protegidos"],
        )
        print(
            "Candidatos seguros:",
            informe["cantidad_candidatos"],
        )
        print(
            "Espacio recuperable:",
            informe["recuperable"],
        )
        print(
            "Disco libre:",
            informe["disco_antes"]["libre"],
            "->",
            informe[
                "disco_estimado_despues"
            ]["libre"],
        )
        print("-" * 72)

        for indice, candidato in enumerate(
            informe["candidatos"],
            start=1,
        ):
            print(
                f"{indice}. "
                f"[{candidato['tipo'].upper()}] "
                f"{candidato['tamano']}"
            )
            print(
                "  ",
                candidato["ruta"],
            )
            print(
                "   Motivo:",
                candidato["motivo"],
            )

        if not informe["candidatos"]:
            print(
                "No se encontraron archivos "
                "seguros para limpiar."
            )

        if informe["confirmado"]:
            print("-" * 72)
            print(
                "Elementos eliminados:",
                informe.get(
                    "eliminados",
                    0,
                ),
            )
            print(
                "Espacio liberado:",
                informe.get(
                    "liberados",
                    "0 B",
                ),
            )

        for error in informe["errores"]:
            print(
                "[ERROR]",
                error,
            )

        print("=" * 72)
        print(
            "Informe:",
            resultado["rutas"][
                "historico"
            ],
        )
        print("=" * 72)

from __future__ import annotations

import csv
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


class EjecucionEnCursoError(RuntimeError):
    """Indica que otro guardian mantiene el bloqueo activo."""


class GuardianPipeline:
    """Ejecuta AutoTube de forma segura y registra cada intento."""

    MINIMO_LIBRE_GB = 15.0

    def __init__(
        self,
        project_root: Path,
    ) -> None:
        self.project_root = Path(
            project_root
        ).resolve()

        self.data_dir = (
            self.project_root
            / "data"
            / "automation"
        )

        self.lock_path = (
            self.data_dir
            / "pipeline.lock"
        )

        self.latest_path = (
            self.data_dir
            / "guardian_latest.json"
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

        temporal.replace(ruta)

    @staticmethod
    def _pid_activo_windows(
        pid: int,
    ) -> bool:
        try:
            resultado = subprocess.run(
                [
                    "tasklist",
                    "/FI",
                    f"PID eq {pid}",
                    "/FO",
                    "CSV",
                    "/NH",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
        except (
            OSError,
            subprocess.SubprocessError,
        ):
            return False

        if resultado.returncode != 0:
            return False

        try:
            filas = list(
                csv.reader(
                    resultado.stdout.splitlines()
                )
            )
        except csv.Error:
            return False

        for fila in filas:
            if (
                len(fila) >= 2
                and fila[1].strip() == str(pid)
            ):
                return True

        return False

    @classmethod
    def _pid_activo(
        cls,
        pid: int,
    ) -> bool:
        if pid <= 0:
            return False

        if pid == os.getpid():
            return True

        if os.name == "nt":
            return cls._pid_activo_windows(
                pid
            )

        try:
            os.kill(
                pid,
                0,
            )
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False

        return True

    def estado_bloqueo(
        self,
    ) -> dict[str, Any]:
        datos = self._leer_json(
            self.lock_path
        )

        try:
            pid = int(
                datos.get(
                    "pid",
                    0,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            pid = 0

        activo = (
            self.lock_path.is_file()
            and self._pid_activo(pid)
        )

        return {
            "archivo": str(
                self.lock_path
            ),
            "existe": self.lock_path.is_file(),
            "activo": activo,
            "obsoleto": (
                self.lock_path.is_file()
                and not activo
            ),
            "pid": pid,
            "iniciado_en": str(
                datos.get(
                    "iniciado_en",
                    "",
                )
            ),
            "token": str(
                datos.get(
                    "token",
                    "",
                )
            ),
        }

    def adquirir_bloqueo(
        self,
    ) -> str:
        self.data_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        bloqueo = self.estado_bloqueo()

        if bloqueo["activo"]:
            raise EjecucionEnCursoError(
                "Ya existe una ejecucion automatica "
                f"activa con PID {bloqueo['pid']}."
            )

        if bloqueo["obsoleto"]:
            self.lock_path.unlink(
                missing_ok=True
            )

        token = uuid.uuid4().hex

        contenido = json.dumps(
            {
                "pid": os.getpid(),
                "token": token,
                "iniciado_en": self._ahora(),
                "project_root": str(
                    self.project_root
                ),
            },
            ensure_ascii=False,
            indent=2,
        )

        try:
            descriptor = os.open(
                self.lock_path,
                (
                    os.O_CREAT
                    | os.O_EXCL
                    | os.O_WRONLY
                ),
            )
        except FileExistsError as error:
            raise EjecucionEnCursoError(
                "Otro proceso adquirio el bloqueo "
                "mientras se iniciaba el guardian."
            ) from error

        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
        ) as archivo:
            archivo.write(
                contenido
            )

        return token

    def liberar_bloqueo(
        self,
        token: str,
    ) -> bool:
        datos = self._leer_json(
            self.lock_path
        )

        if (
            not token
            or datos.get("token") != token
        ):
            return False

        self.lock_path.unlink(
            missing_ok=True
        )

        return True

    def _espacio_libre(
        self,
    ) -> dict[str, Any]:
        uso = shutil.disk_usage(
            self.project_root
        )

        libre_gb = (
            uso.free
            / (1024 ** 3)
        )

        return {
            "total_bytes": uso.total,
            "libre_bytes": uso.free,
            "libre_gb": round(
                libre_gb,
                2,
            ),
            "libre_porcentaje": round(
                (
                    uso.free
                    / uso.total
                    * 100
                )
                if uso.total
                else 0.0,
                2,
            ),
        }

    def _minimo_libre_gb(
        self,
    ) -> float:
        valor = os.getenv(
            "AUTOTUBE_MIN_FREE_GB",
            str(
                self.MINIMO_LIBRE_GB
            ),
        )

        try:
            return max(
                1.0,
                float(valor),
            )
        except (
            TypeError,
            ValueError,
        ):
            return self.MINIMO_LIBRE_GB

    @staticmethod
    def _dns_google() -> tuple[
        bool,
        str,
    ]:
        try:
            socket.getaddrinfo(
                "oauth2.googleapis.com",
                443,
                type=socket.SOCK_STREAM,
            )
        except OSError as error:
            return (
                False,
                str(error),
            )

        return (
            True,
            "Resolucion DNS disponible.",
        )

    def preflight(
        self,
        comprobar_bloqueo: bool = True,
    ) -> dict[str, Any]:
        errores: list[str] = []
        advertencias: list[str] = []

        herramientas = {
            "ffmpeg": shutil.which(
                "ffmpeg"
            )
            or "",
            "ffprobe": shutil.which(
                "ffprobe"
            )
            or "",
            "autotube": str(
                self._ejecutable_autotube()
                or ""
            ),
        }

        for nombre in (
            "ffmpeg",
            "ffprobe",
            "autotube",
        ):
            if not herramientas[nombre]:
                errores.append(
                    f"No se encontro {nombre}."
                )

        disco = self._espacio_libre()
        minimo_gb = self._minimo_libre_gb()

        if disco["libre_gb"] < minimo_gb:
            errores.append(
                "Espacio insuficiente: "
                f"{disco['libre_gb']} GB libres; "
                f"se requieren {minimo_gb:.1f} GB."
            )
        elif disco["libre_porcentaje"] < 15:
            advertencias.append(
                "Queda menos de 15% de espacio "
                "en la unidad del proyecto."
            )

        conexion, motivo_conexion = (
            self._dns_google()
        )

        if not conexion:
            advertencias.append(
                "Google no esta disponible por DNS: "
                f"{motivo_conexion}"
            )

        bloqueo = self.estado_bloqueo()

        if (
            comprobar_bloqueo
            and bloqueo["activo"]
        ):
            errores.append(
                "Ya existe una ejecucion automatica "
                f"activa con PID {bloqueo['pid']}."
            )

        estado_pipeline = self._leer_json(
            self.project_root
            / "data"
            / "pipeline_state.json"
        )

        return {
            "generado_en": self._ahora(),
            "aprobado": not errores,
            "errores": errores,
            "advertencias": advertencias,
            "herramientas": herramientas,
            "disco": disco,
            "minimo_libre_gb": minimo_gb,
            "conexion_google": {
                "disponible": conexion,
                "motivo": motivo_conexion,
            },
            "bloqueo": bloqueo,
            "pipeline": {
                "disponible": bool(
                    estado_pipeline
                ),
                "completado": bool(
                    estado_pipeline.get(
                        "completado",
                        False,
                    )
                ),
                "ultimo_error": str(
                    estado_pipeline.get(
                        "ultimo_error",
                        "",
                    )
                ),
                "pasos_completados": len(
                    estado_pipeline.get(
                        "pasos_completados",
                        [],
                    )
                    if isinstance(
                        estado_pipeline.get(
                            "pasos_completados",
                            [],
                        ),
                        list,
                    )
                    else []
                ),
            },
        }

    def _ejecutable_autotube(
        self,
    ) -> Path | None:
        candidatos = []

        if os.name == "nt":
            candidatos.append(
                self.project_root
                / ".venv"
                / "Scripts"
                / "autotube.exe"
            )
        else:
            candidatos.append(
                self.project_root
                / ".venv"
                / "bin"
                / "autotube"
            )

        for candidato in candidatos:
            if candidato.is_file():
                return candidato

        encontrado = shutil.which(
            "autotube"
        )

        return (
            Path(encontrado)
            if encontrado
            else None
        )

    def _comando_base(
        self,
    ) -> list[str]:
        ejecutable = (
            self._ejecutable_autotube()
        )

        if ejecutable is not None:
            return [
                str(ejecutable)
            ]

        return [
            sys.executable,
            "-c",
            (
                "from autotube.main "
                "import main; main()"
            ),
        ]

    def debe_reanudar(
        self,
    ) -> bool:
        estado = self._leer_json(
            self.project_root
            / "data"
            / "pipeline_state.json"
        )

        if not estado:
            return False

        if bool(
            estado.get(
                "completado",
                False,
            )
        ):
            return False

        completados = estado.get(
            "pasos_completados",
            [],
        )

        return bool(
            estado.get(
                "ultimo_error",
                "",
            )
            or (
                isinstance(
                    completados,
                    list,
                )
                and completados
            )
        )

    def construir_comandos(
        self,
        publicar: bool = True,
        control_profundo: bool = True,
        limpiar_publicados: bool = True,
    ) -> list[dict[str, Any]]:
        base = self._comando_base()
        comandos: list[dict[str, Any]] = []

        if publicar:
            comandos.append(
                {
                    "nombre": (
                        "Reanudacion de publicaciones"
                    ),
                    "comando": (
                        base
                        + [
                            "publish-resume",
                        ]
                    ),
                }
            )

        pipeline = (
            base
            + [
                "run",
            ]
        )

        if self.debe_reanudar():
            pipeline.append(
                "--reanudar"
            )

        if control_profundo:
            pipeline.append(
                "--control-profundo"
            )

        if not publicar:
            pipeline.append(
                "--sin-publicar"
            )

        comandos.append(
            {
                "nombre": "Pipeline de produccion",
                "comando": pipeline,
            }
        )

        if (
            publicar
            and limpiar_publicados
        ):
            comandos.append(
                {
                    "nombre": (
                        "Limpieza de publicaciones "
                        "verificadas"
                    ),
                    "comando": (
                        base
                        + [
                            "storage-clean",
                            "--publicados",
                            "--confirmar",
                        ]
                    ),
                }
            )

        return comandos

    def _guardar_informe(
        self,
        informe: dict[str, Any],
    ) -> dict[str, Path]:
        marca = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        historico = (
            self.data_dir
            / f"guardian_{marca}.json"
        )

        self._guardar_json_atomico(
            historico,
            informe,
        )

        self._guardar_json_atomico(
            self.latest_path,
            informe,
        )

        return {
            "historico": historico,
            "actual": self.latest_path,
        }

    def ejecutar(
        self,
        dry_run: bool = False,
        publicar: bool = True,
        control_profundo: bool = True,
        limpiar_publicados: bool = True,
    ) -> dict[str, Any]:
        preflight = self.preflight(
            comprobar_bloqueo=True,
        )

        comandos = self.construir_comandos(
            publicar=publicar,
            control_profundo=control_profundo,
            limpiar_publicados=limpiar_publicados,
        )

        informe: dict[str, Any] = {
            "version": 1,
            "iniciado_en": self._ahora(),
            "finalizado_en": "",
            "estado": "simulacion",
            "dry_run": dry_run,
            "publicar": publicar,

            "control_profundo": control_profundo,
            "limpiar_publicados": limpiar_publicados,
            "preflight": preflight,
            "comandos": [
                {
                    "nombre": item["nombre"],
                    "comando": [
                        str(parte)
                        for parte in item[
                            "comando"
                        ]
                    ],
                    "estado": "pendiente",
                    "codigo_salida": None,
                    "duracion_segundos": 0.0,
                }
                for item in comandos
            ],
            "error": "",
        }

        if dry_run:
            informe["finalizado_en"] = (
                self._ahora()
            )

            rutas = self._guardar_informe(
                informe
            )

            return {
                "informe": informe,
                "rutas": rutas,
            }

        if not preflight["aprobado"]:
            informe["estado"] = (
                "bloqueado_preflight"
            )
            informe["error"] = " | ".join(
                preflight["errores"]
            )
            informe["finalizado_en"] = (
                self._ahora()
            )

            rutas = self._guardar_informe(
                informe
            )

            return {
                "informe": informe,
                "rutas": rutas,
            }

        token = ""

        try:
            token = self.adquirir_bloqueo()
            informe["estado"] = "en_progreso"

            for indice, item in enumerate(
                comandos
            ):
                registro = informe[
                    "comandos"
                ][indice]

                registro["estado"] = (
                    "en_progreso"
                )
                inicio = time.monotonic()

                resultado = subprocess.run(
                    item["comando"],
                    cwd=self.project_root,
                    check=False,
                )

                registro[
                    "duracion_segundos"
                ] = round(
                    time.monotonic()
                    - inicio,
                    2,
                )

                registro[
                    "codigo_salida"
                ] = resultado.returncode

                if resultado.returncode != 0:
                    registro["estado"] = (
                        "error"
                    )
                    informe["estado"] = "error"
                    informe["error"] = (
                        f"{item['nombre']} termino "
                        "con codigo "
                        f"{resultado.returncode}."
                    )
                    break

                registro["estado"] = (
                    "completado"
                )

            else:
                informe["estado"] = (
                    "completado"
                )

        except (
            EjecucionEnCursoError,
            OSError,
            subprocess.SubprocessError,
        ) as error:
            informe["estado"] = "error"
            informe["error"] = str(error)

        finally:
            if token:
                self.liberar_bloqueo(
                    token
                )

            informe["finalizado_en"] = (
                self._ahora()
            )

        rutas = self._guardar_informe(
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
        preflight = informe["preflight"]

        print()
        print(
            "GUARDIAN AUTONOMO AUTOTUBE AI"
        )
        print("=" * 72)
        print(
            "Estado:",
            str(
                informe["estado"]
            ).upper(),
        )
        print(
            "Modo:",
            (
                "SIMULACION"
                if informe["dry_run"]
                else "EJECUCION REAL"
            ),
        )
        print(
            "Preflight:",
            (
                "APROBADO"
                if preflight["aprobado"]
                else "BLOQUEADO"
            ),
        )
        print(
            "Disco libre:",
            f"{preflight['disco']['libre_gb']} GB",
            "| Minimo:",
            f"{preflight['minimo_libre_gb']} GB",
        )

        for advertencia in preflight[
            "advertencias"
        ]:
            print(
                "[ADVERTENCIA]",
                advertencia,
            )

        for error in preflight["errores"]:
            print(
                "[ERROR]",
                error,
            )

        print("-" * 72)

        for registro in informe["comandos"]:
            comando = " ".join(
                str(parte)
                for parte in registro[
                    "comando"
                ]
            )

            print(
                f"{registro['nombre']}: "
                f"{registro['estado']}"
            )
            print(
                "  ",
                comando,
            )

        if informe["error"]:
            print("-" * 72)
            print(
                "Ultimo error:",
                informe["error"],
            )

        print("=" * 72)
        print(
            "Informe:",
            resultado["rutas"][
                "historico"
            ],
        )
        print("=" * 72)

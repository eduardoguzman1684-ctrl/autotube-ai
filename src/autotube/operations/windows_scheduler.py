from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

from autotube.content.channel_profiles import (
    DEFAULT_CHANNEL,
    channel_profile,
    normalize_channel_slug,
)


class ProgramadorWindows:
    """Instala y administra la tarea automatica de AutoTube."""

    PREFIJO_TAREA = "AutoTube AI - Guardian"

    DIAS = {
        "lunes": "MON",
        "martes": "TUE",
        "miercoles": "WED",
        "miércoles": "WED",
        "jueves": "THU",
        "viernes": "FRI",
        "sabado": "SAT",
        "sábado": "SAT",
        "domingo": "SUN",
        "mon": "MON",
        "tue": "TUE",
        "wed": "WED",
        "thu": "THU",
        "fri": "FRI",
        "sat": "SAT",
        "sun": "SUN",
    }

    def __init__(
        self,
        project_root: Path,
        channel_slug: str = DEFAULT_CHANNEL,
    ) -> None:
        self.project_root = Path(
            project_root
        ).resolve()

        self.channel_slug = normalize_channel_slug(
            channel_slug
        )
        self.channel_name = str(
            channel_profile(
                self.channel_slug
            )["display_name"]
        )
        self.task_name = (
            f"{self.PREFIJO_TAREA} - "
            f"{self.channel_name}"
        )

        self.automation_dir = (
            self.project_root
            / "data"
            / "automation"
            / "channels"
            / self.channel_slug
        )

        self.launcher_path = (
            self.automation_dir
            / f"autotube_guardian_{self.channel_slug}.cmd"
        )

        self.log_path = (
            self.project_root
            / "logs"
            / f"guardian_{self.channel_slug}.log"
        )

    @staticmethod
    def validar_hora(
        hora: str,
    ) -> str:
        texto = str(
            hora
        ).strip()

        if not re.fullmatch(
            r"(?:[01]\d|2[0-3]):[0-5]\d",
            texto,
        ):
            raise ValueError(
                "La hora debe usar el formato HH:MM "
                "de 24 horas."
            )

        return texto

    @classmethod
    def normalizar_dias(
        cls,
        dias: str,
    ) -> list[str]:
        partes = [
            parte.strip().lower()
            for parte in re.split(
                r"[,;]",
                str(dias),
            )
            if parte.strip()
        ]

        if not partes:
            raise ValueError(
                "Debes indicar al menos un dia."
            )

        salida: list[str] = []

        for parte in partes:
            codigo = cls.DIAS.get(
                parte
            )

            if not codigo:
                raise ValueError(
                    f"Dia no reconocido: {parte}"
                )

            if codigo not in salida:
                salida.append(
                    codigo
                )

        return salida

    def _autotube_exe(
        self,
    ) -> Path:
        if os.name == "nt":
            ruta = (
                self.project_root
                / ".venv"
                / "Scripts"
                / "autotube.exe"
            )
        else:
            ruta = (
                self.project_root
                / ".venv"
                / "bin"
                / "autotube"
            )

        if not ruta.is_file():
            raise FileNotFoundError(
                "No se encontro el ejecutable "
                f"del entorno virtual: {ruta}"
            )

        return ruta

    def contenido_lanzador(
        self,
    ) -> str:
        autotube = self._autotube_exe()

        return "\r\n".join(
            [
                "@echo off",
                "setlocal",
                (
                    'cd /d "'
                    + str(
                        self.project_root
                    )
                    + '"'
                ),
                (
                    'if not exist "'
                    + str(autotube)
                    + '" exit /b 2'
                ),
                (
                    '"'
                    + str(autotube)
                    + '" guardian-run --canal '
                    + self.channel_slug
                    + ' '
                    + '>> "'
                    + str(
                        self.log_path
                    )
                    + '" 2>&1'
                ),
                "exit /b %ERRORLEVEL%",
                "",
            ]
        )

    def crear_lanzador(
        self,
    ) -> Path:
        self.automation_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.log_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.launcher_path.write_text(
            self.contenido_lanzador(),
            encoding="utf-8",
        )

        return self.launcher_path

    def comando_instalacion(
        self,
        hora: str,
        dias: str,
    ) -> list[str]:
        hora_valida = self.validar_hora(
            hora
        )

        dias_validos = (
            self.normalizar_dias(
                dias
            )
        )

        return [
            "schtasks",
            "/Create",
            "/TN",
            self.task_name,
            "/TR",
            str(
                self.launcher_path
            ),
            "/SC",
            "WEEKLY",
            "/D",
            ",".join(
                dias_validos
            ),
            "/ST",
            hora_valida,
            "/RL",
            "LIMITED",
            "/F",
        ]

    def instalar(
        self,
        hora: str = "08:00",
        dias: str = "lunes,miercoles,viernes",
        confirmar: bool = False,
    ) -> dict[str, Any]:
        comando = self.comando_instalacion(
            hora=hora,
            dias=dias,
        )

        resultado: dict[str, Any] = {
            "accion": "instalar",
            "canal": self.channel_slug,
            "nombre_canal": self.channel_name,
            "confirmado": confirmar,
            "instalado": False,
            "hora": self.validar_hora(
                hora
            ),
            "dias": self.normalizar_dias(
                dias
            ),
            "tarea": self.task_name,
            "lanzador": str(
                self.launcher_path
            ),
            "comando": comando,
            "codigo_salida": None,
            "salida": "",
            "error": "",
        }

        if not confirmar:
            return resultado

        if os.name != "nt":
            resultado["error"] = (
                "La instalacion automatica solo "
                "esta disponible en Windows."
            )
            return resultado

        self.crear_lanzador()

        try:
            proceso = subprocess.run(
                comando,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
        except (
            OSError,
            subprocess.SubprocessError,
        ) as error:
            resultado["error"] = str(
                error
            )
            return resultado

        resultado["codigo_salida"] = (
            proceso.returncode
        )

        resultado["salida"] = (
            proceso.stdout
            or ""
        ).strip()

        resultado["error"] = (
            proceso.stderr
            or ""
        ).strip()

        resultado["instalado"] = (
            proceso.returncode == 0
        )

        return resultado

    def consultar(
        self,
    ) -> dict[str, Any]:
        resultado: dict[str, Any] = {
            "canal": self.channel_slug,
            "nombre_canal": self.channel_name,
            "tarea": self.task_name,
            "instalada": False,
            "codigo_salida": None,
            "salida": "",
            "error": "",
        }

        if os.name != "nt":
            resultado["error"] = (
                "La consulta de tareas solo "
                "esta disponible en Windows."
            )
            return resultado

        try:
            proceso = subprocess.run(
                [
                    "schtasks",
                    "/Query",
                    "/TN",
                    self.task_name,
                    "/FO",
                    "LIST",
                    "/V",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
        except (
            OSError,
            subprocess.SubprocessError,
        ) as error:
            resultado["error"] = str(
                error
            )
            return resultado

        resultado["codigo_salida"] = (
            proceso.returncode
        )

        resultado["salida"] = (
            proceso.stdout
            or ""
        ).strip()

        resultado["error"] = (
            proceso.stderr
            or ""
        ).strip()

        resultado["instalada"] = (
            proceso.returncode == 0
        )

        return resultado

    def eliminar(
        self,
        confirmar: bool = False,
    ) -> dict[str, Any]:
        comando = [
            "schtasks",
            "/Delete",
            "/TN",
            self.task_name,
            "/F",
        ]

        resultado: dict[str, Any] = {
            "accion": "eliminar",
            "canal": self.channel_slug,
            "nombre_canal": self.channel_name,
            "confirmado": confirmar,
            "eliminada": False,
            "tarea": self.task_name,
            "comando": comando,
            "codigo_salida": None,
            "salida": "",
            "error": "",
        }

        if not confirmar:
            return resultado

        if os.name != "nt":
            resultado["error"] = (
                "La eliminacion automatica solo "
                "esta disponible en Windows."
            )
            return resultado

        try:
            proceso = subprocess.run(
                comando,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
        except (
            OSError,
            subprocess.SubprocessError,
        ) as error:
            resultado["error"] = str(
                error
            )
            return resultado

        resultado["codigo_salida"] = (
            proceso.returncode
        )

        resultado["salida"] = (
            proceso.stdout
            or ""
        ).strip()

        resultado["error"] = (
            proceso.stderr
            or ""
        ).strip()

        resultado["eliminada"] = (
            proceso.returncode == 0
        )

        return resultado

    @staticmethod
    def imprimir_instalacion(
        resultado: dict[str, Any],
    ) -> None:
        print()
        print(
            "PROGRAMADOR AUTOMATICO AUTOTUBE AI"
        )
        print("=" * 72)
        print(
            "Tarea:",
            resultado["tarea"],
        )
        print(
            "Canal:",
            f"{resultado['nombre_canal']} "
            f"({resultado['canal']})",
        )
        print(
            "Horario:",
            resultado["hora"],
            "| Dias:",
            ",".join(
                resultado["dias"]
            ),
        )
        print(
            "Modo:",
            (
                "INSTALACION REAL"
                if resultado["confirmado"]
                else "SIMULACION"
            ),
        )
        print(
            "Comando:",
            " ".join(
                resultado["comando"]
            ),
        )

        if resultado["confirmado"]:
            print(
                "Resultado:",
                (
                    "INSTALADA"
                    if resultado["instalado"]
                    else "ERROR"
                ),
            )

        if resultado["salida"]:
            print(
                resultado["salida"]
            )

        if resultado["error"]:
            print(
                resultado["error"]
            )

        print("=" * 72)

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from autotube.ai.gemini_client import GeminiClient
from autotube.content.channel_profiles import (
    DEFAULT_CHANNEL,
    channel_profile,
    editorial_prompt,
    experiments_directory,
    normalize_channel_slug,
    strategy_profile_path,
)
from autotube.content.thumbnail_generator import (
    GeneradorMiniaturaYouTube,
)


VARIABLES_VALIDAS = {
    "titulo",
    "miniatura",
    "gancho",
    "duracion",
}


class GestorExperimentosYouTube:
    """Genera experimentos editoriales sin modificar publicaciones."""

    def __init__(
        self,
        project_root: Path,
        cliente: GeminiClient | None = None,
        channel_slug: str = DEFAULT_CHANNEL,
    ) -> None:
        self.project_root = Path(project_root)
        self.cliente = cliente
        self.channel_slug = normalize_channel_slug(channel_slug)
        self.profile = channel_profile(self.channel_slug)
        self.output_dir = experiments_directory(
            self.project_root,
            self.channel_slug,
        )

    def _latest(self, *patrones: str) -> Path:
        archivos: list[Path] = []

        for patron in patrones:
            archivos.extend(
                ruta
                for ruta in self.project_root.glob(patron)
                if ruta.is_file()
            )

        if not archivos:
            raise FileNotFoundError(
                "No se encontro ningun archivo para: "
                + ", ".join(patrones)
            )

        return max(
            archivos,
            key=lambda ruta: ruta.stat().st_mtime,
        )

    @staticmethod
    def _leer_json(ruta: Path) -> dict[str, Any]:
        datos = json.loads(
            ruta.read_text(encoding="utf-8-sig")
        )

        if not isinstance(datos, dict):
            raise ValueError(
                f"El archivo no contiene un objeto JSON: {ruta}"
            )

        return datos

    def _metadata(
        self,
    ) -> tuple[dict[str, Any], Path]:
        ruta = (
            self.project_root
            / "data"
            / "publish"
            / "metadata.json"
        )

        if not ruta.is_file():
            raise FileNotFoundError(
                "No existe data/publish/metadata.json."
            )

        return self._leer_json(ruta), ruta

    def _guion(
        self,
    ) -> tuple[dict[str, Any], Path]:
        ruta = self._latest(
            "data/scripts/guion_corregido_*.json",
            "data/scripts/guion_*.json",
        )

        return self._leer_json(ruta), ruta

    def _perfil_estrategico(
        self,
    ) -> tuple[dict[str, Any], Path | None]:
        ruta = strategy_profile_path(
            self.project_root / "data",
            self.channel_slug,
        )

        if not ruta.is_file():
            return {}, None

        try:
            return self._leer_json(ruta), ruta
        except (
            OSError,
            ValueError,
            json.JSONDecodeError,
        ):
            return {}, None

    @staticmethod
    def _texto(
        valor: Any,
        respaldo: str,
        limite: int,
    ) -> str:
        texto = " ".join(
            str(valor or respaldo).split()
        ).strip()

        if len(texto) <= limite:
            return texto

        recortado = texto[:limite].rsplit(
            " ",
            1,
        )[0].rstrip(
            " ,;:-"
        )

        return (
            recortado
            or texto[:limite].strip()
        )

    @staticmethod
    def _duracion(
        valor: Any,
        respaldo: float,
    ) -> float:
        try:
            duracion = float(valor)
        except (TypeError, ValueError):
            duracion = respaldo

        return round(
            min(20.0, max(6.0, duracion)),
            1,
        )

    @staticmethod
    def _metrica(variable: str) -> dict[str, Any]:
        if variable in {
            "titulo",
            "miniatura",
        }:
            return {
                "primaria": "ctr_impresiones",
                "secundarias": [
                    "views",
                    "averageViewPercentage",
                ],
                "requiere_dato_manual": True,
                "nota": (
                    "Registrar el CTR desde YouTube Studio "
                    "si no esta disponible mediante la API."
                ),
            }

        if variable == "gancho":
            return {
                "primaria": "averageViewPercentage",
                "secundarias": [
                    "averageViewDuration",
                    "estimatedMinutesWatched",
                ],
                "requiere_dato_manual": False,
            }

        return {
            "primaria": "averageViewPercentage",
            "secundarias": [
                "estimatedMinutesWatched",
                "averageViewDuration",
            ],
            "requiere_dato_manual": False,
        }

    def _resolver_experimento(
        self,
        archivo: str | Path | None = None,
    ) -> tuple[dict[str, Any], Path]:
        if archivo is None:
            ruta = self.output_dir / "experimento_actual.json"
        else:
            ruta = Path(archivo).expanduser()

            if not ruta.is_absolute():
                ruta = self.project_root / ruta

        ruta = ruta.resolve()

        if not ruta.is_file():
            raise FileNotFoundError(
                f"No existe el experimento: {ruta}"
            )

        experimento = self._leer_json(ruta)

        if archivo is None:
            identificador = str(
                experimento.get(
                    "experimento_id",
                    "",
                )
            )

            historico = (
                ruta.parent
                / f"experimento_{identificador}.json"
            )

            if historico.is_file():
                ruta = historico

        return experimento, ruta

    @staticmethod
    def _numero_opcional(
        valor: Any,
        nombre: str,
    ) -> float | None:
        if valor is None:
            return None

        try:
            numero = float(valor)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"{nombre} debe ser numerico."
            ) from error

        if numero < 0:
            raise ValueError(
                f"{nombre} no puede ser negativo."
            )

        return round(numero, 3)

    @staticmethod
    def _evaluar(
        experimento: dict[str, Any],
    ) -> dict[str, Any]:
        variantes = experimento.get(
            "variantes",
            [],
        )

        minimo = int(
            experimento.get(
                "reglas",
                {},
            ).get(
                "vistas_minimas_por_variante",
                100,
            )
        )

        metrica = str(
            experimento.get(
                "metrica",
                {},
            ).get(
                "primaria",
                "",
            )
        )

        faltantes: list[dict[str, Any]] = []
        valores: list[tuple[str, float]] = []

        for variante in variantes:
            if not isinstance(variante, dict):
                continue

            codigo = str(
                variante.get(
                    "codigo",
                    "",
                )
            )

            resultado = variante.get(
                "resultado",
                {},
            )

            if not isinstance(resultado, dict):
                resultado = {}

            vistas = int(
                resultado.get(
                    "views",
                    0,
                )
                or 0
            )

            valor = resultado.get(
                metrica
            )

            razones: list[str] = []

            if vistas < minimo:
                razones.append(
                    f"faltan {minimo - vistas} vistas"
                )

            if valor is None:
                razones.append(
                    f"falta {metrica}"
                )

            if razones:
                faltantes.append(
                    {
                        "codigo": codigo,
                        "razones": razones,
                    }
                )
                continue

            valores.append(
                (
                    codigo,
                    float(valor),
                )
            )

        if faltantes or len(valores) < 2:
            return {
                "estado": "recopilando_datos",
                "ganador_provisional": "",
                "metrica": metrica,
                "faltantes": faltantes,
                "nota": (
                    "No se declara ganador hasta que todas "
                    "las variantes alcancen el minimo."
                ),
            }

        valores.sort(
            key=lambda elemento: elemento[1],
            reverse=True,
        )

        mejor_codigo, mejor_valor = valores[0]
        segundo_codigo, segundo_valor = valores[1]
        diferencia = round(
            mejor_valor - segundo_valor,
            3,
        )

        umbral = (
            0.5
            if metrica == "ctr_impresiones"
            else 3.0
        )

        if diferencia < umbral:
            return {
                "estado": "sin_diferencia_clara",
                "ganador_provisional": "",
                "metrica": metrica,
                "mejor_variante": mejor_codigo,
                "mejor_valor": mejor_valor,
                "segunda_variante": segundo_codigo,
                "segundo_valor": segundo_valor,
                "diferencia": diferencia,
                "umbral": umbral,
                "nota": (
                    "La diferencia observada no supera "
                    "el umbral minimo definido."
                ),
            }

        return {
            "estado": "ganador_provisional",
            "ganador_provisional": mejor_codigo,
            "metrica": metrica,
            "mejor_valor": mejor_valor,
            "segunda_variante": segundo_codigo,
            "segundo_valor": segundo_valor,
            "diferencia": diferencia,
            "umbral": umbral,
            "nota": (
                "Resultado provisional; no se aplica "
                "automaticamente a YouTube."
            ),
        }

    def registrar_resultado(
        self,
        codigo: str,
        vistas: int,
        ctr: float | None = None,
        retencion: float | None = None,
        duracion_media: float | None = None,
        minutos_vistos: float | None = None,
        archivo: str | Path | None = None,
    ) -> dict[str, Any]:
        experimento, ruta = (
            self._resolver_experimento(
                archivo
            )
        )

        codigo = codigo.strip().upper()

        if vistas < 0:
            raise ValueError(
                "Las vistas no pueden ser negativas."
            )

        variantes = experimento.get(
            "variantes",
            [],
        )

        variante_objetivo = next(
            (
                variante
                for variante in variantes
                if (
                    isinstance(variante, dict)
                    and str(
                        variante.get(
                            "codigo",
                            "",
                        )
                    ).upper()
                    == codigo
                )
            ),
            None,
        )

        if variante_objetivo is None:
            raise ValueError(
                f"No existe la variante {codigo}."
            )

        metrica_primaria = str(
            experimento.get(
                "metrica",
                {},
            ).get(
                "primaria",
                "",
            )
        )

        resultado = {
            "registrado_en": (
                datetime.now()
                .astimezone()
                .isoformat(timespec="seconds")
            ),
            "views": int(vistas),
            "ctr_impresiones": self._numero_opcional(
                ctr,
                "CTR",
            ),
            "averageViewPercentage": self._numero_opcional(
                retencion,
                "Retencion",
            ),
            "averageViewDuration": self._numero_opcional(
                duracion_media,
                "Duracion media",
            ),
            "estimatedMinutesWatched": self._numero_opcional(
                minutos_vistos,
                "Minutos vistos",
            ),
        }

        if resultado.get(
            metrica_primaria
        ) is None:
            raise ValueError(
                "Falta la metrica primaria del experimento: "
                f"{metrica_primaria}"
            )

        variante_objetivo["resultado"] = resultado

        evaluacion = self._evaluar(
            experimento
        )

        experimento["evaluacion"] = evaluacion
        experimento["estado"] = evaluacion["estado"]
        experimento["actualizado_en"] = (
            datetime.now()
            .astimezone()
            .isoformat(timespec="seconds")
        )

        contenido = json.dumps(
            experimento,
            ensure_ascii=False,
            indent=2,
        )

        ruta.write_text(
            contenido,
            encoding="utf-8",
        )

        ruta_actual = self.output_dir / "experimento_actual.json"

        ruta_actual.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        ruta_actual.write_text(
            contenido,
            encoding="utf-8",
        )

        return {
            "experimento": experimento,
            "archivo": ruta,
            "evaluacion": evaluacion,
        }

    def generar(
        self,
        variable: str = "titulo",
        cantidad: int = 3,
        renderizar_miniaturas: bool = True,
    ) -> dict[str, Any]:
        variable = variable.strip().lower()

        if variable not in VARIABLES_VALIDAS:
            raise ValueError(
                "Variable invalida. Usa: "
                "titulo, miniatura, gancho o duracion."
            )

        if cantidad < 3 or cantidad > 5:
            raise ValueError(
                "La cantidad debe estar entre 3 y 5."
            )

        metadata, ruta_metadata = self._metadata()
        contenido_guion, ruta_guion = self._guion()
        perfil, ruta_perfil = self._perfil_estrategico()
        contexto_editorial = editorial_prompt(
            self.channel_slug
        )

        for nombre, contenido in (
            ("metadata", metadata),
            ("guion", contenido_guion),
        ):
            source_channel = normalize_channel_slug(
                str(
                    contenido.get(
                        "channel_slug",
                        DEFAULT_CHANNEL,
                    )
                )
            )

            if source_channel != self.channel_slug:
                raise RuntimeError(
                    f"BLOQUEO EDITORIAL: {nombre} pertenece a "
                    f"{source_channel}, no a {self.channel_slug}."
                )

        guion = contenido_guion.get(
            "guion",
            {},
        )

        if not isinstance(guion, dict):
            guion = {}

        idea = contenido_guion.get(
            "idea_original",
            {},
        )

        if not isinstance(idea, dict):
            idea = {}

        titulo_base = self._texto(
            metadata.get(
                "title",
                guion.get(
                    "titulo",
                    self.profile["default_niche"],
                ),
            ),
            self.profile["default_niche"],
            100,
        )

        gancho_base = self._texto(
            guion.get(
                "gancho_inicial",
                idea.get(
                    "gancho",
                    self.profile["mission"],
                ),
            ),
            (
                self.profile["mission"]
            ),
            500,
        )

        duracion_base = self._duracion(
            guion.get(
                "duracion_estimada_minutos",
                idea.get(
                    "duracion_minutos",
                    15,
                ),
            ),
            15.0,
        )

        texto_miniatura_base = (
            GeneradorMiniaturaYouTube._texto_corto(
                titulo_base
            )
        )

        contexto_guion = json.dumps(
            {
                "titulo": guion.get("titulo", titulo_base),
                "objetivo": guion.get("objetivo", ""),
                "gancho_inicial": gancho_base,
                "introduccion": guion.get("introduccion", ""),
                "escenas": guion.get("escenas", [])[:5],
            },
            ensure_ascii=False,
        )[:18000]

        contexto_perfil = json.dumps(
            perfil,
            ensure_ascii=False,
        )[:7000]

        cantidad_alternativas = cantidad - 1

        reglas_variable = {
            "titulo": (
                "Cambia solamente el titulo. Conserva exactamente "
                "el texto de miniatura, el gancho y la duracion base. "
                "Cada titulo debe tener entre 45 y 70 caracteres, "
                "un solo conflicto central y cero clickbait enganoso."
            ),
            "miniatura": (
                "Cambia solamente texto_miniatura. Conserva exactamente "
                "el titulo, el gancho y la duracion base. Usa entre 2 y "
                "5 palabras, alta legibilidad y maximo 32 caracteres."
            ),
            "gancho": (
                "Cambia solamente gancho_inicial. Conserva exactamente "
                "el titulo, el texto de miniatura y la duracion base. "
                "La promesa o consecuencia debe aparecer en los primeros "
                "8 segundos, sin saludo ni introduccion lenta."
            ),
            "duracion": (
                "Cambia solamente duracion_objetivo_minutos. Conserva "
                "exactamente titulo, texto de miniatura y gancho. "
                "Propone duraciones entre 8 y 12 minutos para comparar "
                "contra el documental actual."
            ),
        }

        prompt = f"""
Actua como estratega de experimentacion editorial para YouTube.

PERFIL DEL CANAL:
{contexto_editorial}

NIVEL ACTUAL DE EVIDENCIA:
Exploratorio. No declares ganadores anticipadamente.

VARIABLE UNICA DEL EXPERIMENTO:
{variable}

REGLA PRINCIPAL:
{reglas_variable[variable]}

CONTROL A:
- titulo: {titulo_base}
- texto_miniatura: {texto_miniatura_base}
- gancho_inicial: {gancho_base}
- duracion_objetivo_minutos: {duracion_base}

PERFIL ESTRATEGICO:
{contexto_perfil}

CONTENIDO REAL DEL DOCUMENTAL:
{contexto_guion}

Genera exactamente {cantidad_alternativas} alternativas.
No cambies ninguna variable distinta de la indicada.
Cada alternativa debe probar un angulo diferente y explicar
una hipotesis medible. No inventes hechos ausentes del guion.
""".strip()

        schema = {
            "type": "object",
            "properties": {
                "variantes": {
                    "type": "array",
                    "minItems": cantidad_alternativas,
                    "maxItems": cantidad_alternativas,
                    "items": {
                        "type": "object",
                        "properties": {
                            "titulo": {
                                "type": "string",
                            },
                            "texto_miniatura": {
                                "type": "string",
                            },
                            "gancho_inicial": {
                                "type": "string",
                            },
                            "duracion_objetivo_minutos": {
                                "type": "number",
                            },
                            "angulo": {
                                "type": "string",
                            },
                            "hipotesis": {
                                "type": "string",
                            },
                        },
                        "required": [
                            "titulo",
                            "texto_miniatura",
                            "gancho_inicial",
                            "duracion_objetivo_minutos",
                            "angulo",
                            "hipotesis",
                        ],
                    },
                },
            },
            "required": [
                "variantes",
            ],
        }

        cliente = (
            self.cliente
            or GeminiClient()
        )

        respuesta = cliente.generar_json(
            prompt=prompt,
            schema=schema,
        )

        alternativas_raw = respuesta.get(
            "variantes",
            [],
        )

        if not isinstance(
            alternativas_raw,
            list,
        ):
            raise RuntimeError(
                "Gemini no devolvio variantes validas."
            )

        alternativas = [
            elemento
            for elemento in alternativas_raw
            if isinstance(elemento, dict)
        ][:cantidad_alternativas]

        if len(alternativas) != cantidad_alternativas:
            raise RuntimeError(
                "Gemini no genero la cantidad esperada "
                "de variantes."
            )

        variantes: list[dict[str, Any]] = [
            {
                "codigo": "A",
                "control": True,
                "titulo": titulo_base,
                "texto_miniatura": texto_miniatura_base,
                "gancho_inicial": gancho_base,
                "duracion_objetivo_minutos": duracion_base,
                "angulo": "Control actual",
                "hipotesis": (
                    "Referencia para comparar las alternativas."
                ),
                "miniatura": "",
                "resultado": {},
            }
        ]

        for indice, alternativa in enumerate(
            alternativas,
            start=1,
        ):
            codigo = chr(
                ord("A") + indice
            )

            titulo = (
                self._texto(
                    alternativa.get("titulo"),
                    titulo_base,
                    100,
                )
                if variable == "titulo"
                else titulo_base
            )

            texto_miniatura = (
                self._texto(
                    alternativa.get(
                        "texto_miniatura"
                    ),
                    texto_miniatura_base,
                    32,
                ).upper()
                if variable == "miniatura"
                else texto_miniatura_base
            )

            gancho = (
                self._texto(
                    alternativa.get(
                        "gancho_inicial"
                    ),
                    gancho_base,
                    500,
                )
                if variable == "gancho"
                else gancho_base
            )

            duracion = (
                self._duracion(
                    alternativa.get(
                        "duracion_objetivo_minutos"
                    ),
                    duracion_base,
                )
                if variable == "duracion"
                else duracion_base
            )

            variantes.append(
                {
                    "codigo": codigo,
                    "control": False,
                    "titulo": titulo,
                    "texto_miniatura": texto_miniatura,
                    "gancho_inicial": gancho,
                    "duracion_objetivo_minutos": duracion,
                    "angulo": self._texto(
                        alternativa.get("angulo"),
                        f"Alternativa {codigo}",
                        180,
                    ),
                    "hipotesis": self._texto(
                        alternativa.get("hipotesis"),
                        (
                            "La variante puede mejorar "
                            "la metrica principal."
                        ),
                        300,
                    ),
                    "miniatura": "",
                    "resultado": {},
                }
            )

        marca = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        experimento_id = (
            f"{marca}_{variable}"
        )

        if (
            variable == "miniatura"
            and renderizar_miniaturas
        ):
            generador_miniatura = (
                GeneradorMiniaturaYouTube(
                    project_root=self.project_root,
                    channel_slug=self.channel_slug,
                )
            )

            for variante in variantes:
                nombre = (
                    f"experimento_{experimento_id}_"
                    f"{variante['codigo']}.jpg"
                )

                ruta_miniatura, _ = (
                    generador_miniatura.generar(
                        forzar=True,
                        titulo_override=titulo_base,
                        gancho_override=variante[
                            "texto_miniatura"
                        ],
                        nombre_salida=nombre,
                    )
                )

                variante["miniatura"] = str(
                    ruta_miniatura.resolve()
                )

        metrica = self._metrica(
            variable
        )

        experimento = {
            "version": 1,
            "experimento_id": experimento_id,
            "creado_en": (
                datetime.now()
                .astimezone()
                .isoformat(timespec="seconds")
            ),
            "estado": "planificado",
            "channel_slug": self.channel_slug,
            "canal": self.profile["display_name"],
            "variable": variable,
            "cantidad_variantes": len(variantes),
            "metrica": metrica,
            "reglas": {
                "cambiar_una_sola_variable": True,
                "vistas_minimas_por_variante": 100,
                "no_declarar_ganador_antes_del_minimo": True,
                "publicacion_automatica": False,
            },
            "variantes": variantes,
            "evaluacion": {
                "estado": "recopilando_datos",
                "ganador_provisional": "",
                "metrica": metrica["primaria"],
                "faltantes": [
                    {
                        "codigo": variante["codigo"],
                        "razones": [
                            "faltan resultados",
                        ],
                    }
                    for variante in variantes
                ],
                "nota": (
                    "No se declara ganador hasta alcanzar "
                    "el minimo por variante."
                ),
            },
            "fuentes": {
                "metadata": str(
                    ruta_metadata.resolve()
                ),
                "guion": str(
                    ruta_guion.resolve()
                ),
                "perfil_estrategico": (
                    str(ruta_perfil.resolve())
                    if ruta_perfil
                    else ""
                ),
            },
        }

        output_dir = self.output_dir

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        ruta_experimento = (
            output_dir
            / f"experimento_{experimento_id}.json"
        )

        ruta_actual = (
            output_dir
            / "experimento_actual.json"
        )

        contenido = json.dumps(
            experimento,
            ensure_ascii=False,
            indent=2,
        )

        ruta_experimento.write_text(
            contenido,
            encoding="utf-8",
        )

        ruta_actual.write_text(
            contenido,
            encoding="utf-8",
        )

        return {
            "experimento": experimento,
            "archivo": ruta_experimento,
            "actual": ruta_actual,
        }

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class Subtitulo:
    """Una entrada sincronizada de un archivo SRT."""

    inicio: float
    final: float
    texto: str


@dataclass(frozen=True)
class FragmentoShort:
    """Fragmento candidato para convertirse en Short."""

    inicio: float
    final: float
    texto: str
    puntuacion: float

    @property
    def duracion(self) -> float:
        return max(0.0, self.final - self.inicio)


class GeneradorShorts:
    """Genera Shorts verticales a partir del documental mas reciente."""

    ANCHO = 1080
    ALTO = 1920

    PALABRAS_GANCHO = {
        "alerta",
        "amenaza",
        "cambio",
        "crisis",
        "debate",
        "descubrir",
        "futuro",
        "impacto",
        "imposible",
        "inteligencia",
        "nunca",
        "peligro",
        "problema",
        "revolucion",
        "riesgo",
        "secreto",
        "sorprendente",
        "transformar",
        "verdad",
    }

    FRASES_DEBILES = (
        "bienvenidos a",
        "en este documental",
        "a continuacion",
        "para concluir",
        "en conclusion",
        "suscribete",
        "deja tu comentario",
        "gracias por ver",
    )

    INICIOS_CONTINUACION = (
        "a la ",
        "al ",
        "como ",
        "con ",
        "de ",
        "del ",
        "durante ",
        "el cual ",
        "en ",
        "incluso ",
        "la cual ",
        "lo que ",
        "para ",
        "por ",
        "que ",
        "sino ",
        "su ",
        "sus ",
        "tambien ",
        "un ",
        "una ",
        "y ",
    )

    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root).resolve()

    def _latest(self, pattern: str) -> Path:
        archivos = [
            ruta
            for ruta in self.project_root.glob(pattern)
            if ruta.is_file() and ruta.stat().st_size > 0
        ]

        if not archivos:
            raise FileNotFoundError(
                f"No se encontro ningun archivo para: {pattern}"
            )

        return max(archivos, key=lambda ruta: ruta.stat().st_mtime)

    def _buscar_video(self) -> Path:
        """Prefiere el video limpio para evitar subtitulos duplicados."""
        patrones = (
            "output/videos/render_*/video_final.mp4",
            "output/videos/render_*/video_final_musica.mp4",
            "output/videos/render_*/video_final_subtitulado_musica.mp4",
        )

        for patron in patrones:
            candidatos = [
                ruta
                for ruta in self.project_root.glob(patron)
                if ruta.is_file()
                and ruta.stat().st_size > 0
            ]

            if candidatos:
                return max(
                    candidatos,
                    key=lambda ruta: ruta.stat().st_mtime,
                )

        raise FileNotFoundError(
            "No se encontro un video final para generar Shorts."
        )

    def _buscar_srt(self) -> Path:
        return self._latest(
            "output/subtitles/subtitulos_*/subtitulos.srt"
        )

    def _metadata(self) -> dict[str, Any]:
        ruta = self.project_root / "data" / "publish" / "metadata.json"

        if not ruta.is_file():
            return {}

        contenido = json.loads(ruta.read_text(encoding="utf-8-sig"))
        return contenido if isinstance(contenido, dict) else {}

    @staticmethod
    def _tiempo_a_segundos(valor: str) -> float:
        horas, minutos, resto = valor.strip().replace(".", ",").split(":")
        segundos, milisegundos = resto.split(",")
        return (
            int(horas) * 3600
            + int(minutos) * 60
            + int(segundos)
            + int(milisegundos.ljust(3, "0")[:3]) / 1000
        )

    @staticmethod
    def _segundos_a_srt(valor: float) -> str:
        total_ms = max(0, round(valor * 1000))
        horas, resto = divmod(total_ms, 3_600_000)
        minutos, resto = divmod(resto, 60_000)
        segundos, milisegundos = divmod(resto, 1000)
        return (
            f"{horas:02d}:{minutos:02d}:{segundos:02d},"
            f"{milisegundos:03d}"
        )

    def _leer_srt(self, ruta: Path) -> list[Subtitulo]:
        contenido = ruta.read_text(encoding="utf-8-sig")
        bloques = re.split(r"\r?\n\s*\r?\n", contenido.strip())
        subtitulos: list[Subtitulo] = []

        for bloque in bloques:
            lineas = [linea.strip() for linea in bloque.splitlines()]
            linea_tiempo = next(
                (linea for linea in lineas if "-->" in linea),
                "",
            )

            if not linea_tiempo:
                continue

            try:
                inicio_texto, final_texto = [
                    parte.strip()
                    for parte in linea_tiempo.split("-->", maxsplit=1)
                ]
                posicion = lineas.index(linea_tiempo)
                texto = " ".join(lineas[posicion + 1 :]).strip()

                if texto:
                    subtitulos.append(
                        Subtitulo(
                            inicio=self._tiempo_a_segundos(inicio_texto),
                            final=self._tiempo_a_segundos(final_texto),
                            texto=texto,
                        )
                    )
            except (TypeError, ValueError):
                continue

        if not subtitulos:
            raise RuntimeError("El archivo SRT no contiene entradas validas.")

        return subtitulos

    @staticmethod
    def _normalizar(texto: str) -> str:
        base = unicodedata.normalize("NFKD", texto.lower())
        return "".join(
            caracter
            for caracter in base
            if not unicodedata.combining(caracter)
        )

    def _puntuar(
        self,
        texto: str,
        duracion: float,
        inicio_natural: bool = True,
        final_natural: bool = True,
    ) -> float:
        normalizado = self._normalizar(texto)
        palabras = re.findall(r"[a-z0-9]+", normalizado)
        puntuacion = 0.0

        puntuacion += sum(
            2.2
            for palabra in set(palabras)
            if palabra in self.PALABRAS_GANCHO
        )
        puntuacion += texto.count("?") * 3.0
        puntuacion += texto.count("!") * 2.0
        puntuacion += min(4.0, len(re.findall(r"\d+", texto)) * 1.5)

        if 36 <= duracion <= 48:
            puntuacion += 6.0
        else:
            puntuacion -= abs(duracion - 42) * 0.18

        if 85 <= len(palabras) <= 145:
            puntuacion += 4.0

        for frase in self.FRASES_DEBILES:
            if frase in normalizado:
                puntuacion -= 12.0

        if normalizado.startswith(("pero ", "sin embargo", "imagina")):
            puntuacion += 3.0

        puntuacion += 7.0 if inicio_natural else -14.0
        puntuacion += 4.0 if final_natural else -7.0

        return round(puntuacion, 3)

    def _inicio_natural(
        self,
        subtitulos: list[Subtitulo],
        indice: int,
    ) -> bool:
        actual = subtitulos[indice]
        limpio = actual.texto.strip()
        normalizado = self._normalizar(limpio)

        if any(
            normalizado.startswith(prefijo)
            for prefijo in self.INICIOS_CONTINUACION
        ):
            return False

        if indice == 0:
            return True

        anterior = subtitulos[indice - 1]
        pausa = actual.inicio - anterior.final
        anterior_cierra = anterior.texto.rstrip().endswith((".", "?", "!"))
        empieza_mayuscula = bool(limpio) and limpio[0].isupper()

        return anterior_cierra or pausa >= 0.55 or empieza_mayuscula

    @staticmethod
    def _final_natural(
        subtitulos: list[Subtitulo],
        indice: int,
    ) -> bool:
        actual = subtitulos[indice]

        if actual.texto.rstrip().endswith((".", "?", "!")):
            return True

        if indice + 1 >= len(subtitulos):
            return True

        return subtitulos[indice + 1].inicio - actual.final >= 0.55

    def _candidatos(
        self,
        subtitulos: list[Subtitulo],
        duracion_objetivo: float,
    ) -> list[FragmentoShort]:
        candidatos: list[FragmentoShort] = []
        duracion_total = subtitulos[-1].final
        inicio_permitido = min(45.0, duracion_total * 0.08)
        final_permitido = max(inicio_permitido + 60, duracion_total - 35)

        for indice, primero in enumerate(subtitulos):
            if primero.inicio < inicio_permitido:
                continue

            if primero.inicio >= final_permitido:
                break

            seleccionados: list[Subtitulo] = []
            inicio_natural = self._inicio_natural(subtitulos, indice)

            for indice_actual, actual in enumerate(
                subtitulos[indice:],
                start=indice,
            ):
                if actual.inicio >= final_permitido:
                    break

                seleccionados.append(actual)
                duracion = actual.final - primero.inicio

                if duracion < max(28.0, duracion_objetivo - 8):
                    continue

                if duracion > min(58.0, duracion_objetivo + 10):
                    break

                texto = " ".join(item.texto for item in seleccionados)
                candidatos.append(
                    FragmentoShort(
                        inicio=primero.inicio,
                        final=actual.final,
                        texto=texto,
                        puntuacion=self._puntuar(
                            texto,
                            duracion,
                            inicio_natural=inicio_natural,
                            final_natural=self._final_natural(
                                subtitulos,
                                indice_actual,
                            ),
                        ),
                    )
                )

        if not candidatos:
            raise RuntimeError(
                "No fue posible construir fragmentos desde los subtitulos."
            )

        return candidatos

    @staticmethod
    def _se_superponen(
        primero: FragmentoShort,
        segundo: FragmentoShort,
        margen: float = 18.0,
    ) -> bool:
        return not (
            primero.final + margen <= segundo.inicio
            or segundo.final + margen <= primero.inicio
        )

    def seleccionar_fragmentos(
        self,
        subtitulos: list[Subtitulo],
        cantidad: int = 4,
        duracion_objetivo: float = 42.0,
    ) -> list[FragmentoShort]:
        cantidad = max(1, min(6, cantidad))
        candidatos = self._candidatos(subtitulos, duracion_objetivo)
        duracion_total = subtitulos[-1].final
        seleccionados: list[FragmentoShort] = []

        ancho_zona = max(1.0, duracion_total / cantidad)

        for zona in range(cantidad):
            izquierda = zona * ancho_zona
            derecha = (zona + 1) * ancho_zona
            opciones = [
                candidato
                for candidato in candidatos
                if izquierda
                <= (candidato.inicio + candidato.final) / 2
                < derecha
                and not any(
                    self._se_superponen(candidato, previo)
                    for previo in seleccionados
                )
            ]

            if opciones:
                seleccionados.append(
                    max(opciones, key=lambda item: item.puntuacion)
                )

        if len(seleccionados) < cantidad:
            for candidato in sorted(
                candidatos,
                key=lambda item: item.puntuacion,
                reverse=True,
            ):
                if any(
                    self._se_superponen(candidato, previo)
                    for previo in seleccionados
                ):
                    continue

                seleccionados.append(candidato)

                if len(seleccionados) >= cantidad:
                    break

        return sorted(
            seleccionados[:cantidad],
            key=lambda item: item.puntuacion,
            reverse=True,
        )

    def _gancho(self, texto: str) -> str:
        limpio = " ".join(texto.replace("\n", " ").split())
        normalizado = self._normalizar(limpio)

        reglas = (
            (
                ("plagio", "derechos de autor", "imagenes protegidas"),
                "¿LA IA APRENDE O ESTÁ COPIANDO?",
            ),
            (
                (
                    "plegamiento de proteinas",
                    "certamen del ano",
                    "estructuras reales",
                    "alphafold",
                ),
                "LA IA RESOLVIÓ UN MISTERIO DE 50 AÑOS",
            ),
            (
                (
                    "industria farmaceutica",
                    "descubrimiento de nuevos medicamentos",
                    "farmaco seguro",
                    "moleculas terapeuticas",
                ),
                "LA IA ESTÁ ACELERANDO NUEVOS MEDICAMENTOS",
            ),
            (
                ("hollywood", "huelgas", "sindicatos de guionistas"),
                "HOLLYWOOD LE DECLARÓ LA GUERRA A LA IA",
            ),
            (
                (
                    "artistas visuales",
                    "creadores",
                    "creativos",
                    "actores de voz",
                ),
                "LOS CREADORES SE REBELAN CONTRA LA IA",
            ),
            (
                (
                    "derechos laborales",
                    "precarizacion",
                    "defensa de los derechos",
                ),
                "¿QUIÉN PROTEGE TU TRABAJO FRENTE A LA IA?",
            ),
            (
                ("empleo", "trabajo", "laboral", "trabajadores"),
                "¿LA IA VA A QUITARTE EL TRABAJO?",
            ),
            (
                ("datos", "privacidad", "informacion personal"),
                "TUS DATOS ESTÁN ALIMENTANDO A LA IA",
            ),
            (
                ("ludismo", "ludita", "resistencia humana"),
                "LA NUEVA REBELIÓN CONTRA LA IA",
            ),
            (
                ("web", "internet", "buscadores", "navegador"),
                "ADIÓS A LA WEB QUE CONOCEMOS",
            ),
            (
                ("riesgo", "peligro", "sin control"),
                "¿QUIÉN CONTROLA REALMENTE A LA IA?",
            ),
            (
                ("derechos", "defensa legitima"),
                "¿QUIÉN PROTEGE TUS DERECHOS ANTE LA IA?",
            ),
            (
                ("innovacion", "avance tecnologico"),
                "EL COSTO OCULTO DE LA INNOVACIÓN",
            ),
        )

        for indicadores, gancho in reglas:
            if any(indicador in normalizado for indicador in indicadores):
                return gancho

        oraciones = [
            oracion.strip()
            for oracion in re.split(r"(?<=[.!?])\s+", limpio)
            if len(oracion.split()) >= 4
        ]

        if not oraciones:
            oraciones = [limpio]

        primera = max(
            oraciones,
            key=lambda oracion: self._puntuar(
                oracion,
                duracion=42.0,
            ),
        )
        palabras = primera.split()

        if len(palabras) < 5:
            palabras = limpio.split()

        salida: list[str] = []
        total = 0

        for palabra in palabras:
            extra = len(palabra) + (1 if salida else 0)

            if total + extra > 68:
                break

            salida.append(palabra)
            total += extra

        gancho = " ".join(salida).strip(" .,:;-")

        if len(" ".join(palabras)) > 68:
            gancho = "ESTO CAMBIÓ PARA SIEMPRE EL FUTURO DE LA IA"

        return (gancho or "LA IA ESTA CAMBIANDO TODO").upper()

    @staticmethod
    def _fuente(tamano: int, negrita: bool = True) -> ImageFont.ImageFont:
        candidatos = (
            Path(r"C:\Windows\Fonts\arialbd.ttf"),
            Path(r"C:\Windows\Fonts\segoeuib.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ) if negrita else (
            Path(r"C:\Windows\Fonts\arial.ttf"),
            Path(r"C:\Windows\Fonts\segoeui.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        )

        for ruta in candidatos:
            if ruta.is_file():
                try:
                    return ImageFont.truetype(str(ruta), tamano)
                except OSError:
                    continue

        return ImageFont.load_default()

    @staticmethod
    def _ajustar_lineas(
        dibujo: ImageDraw.ImageDraw,
        texto: str,
        fuente: ImageFont.ImageFont,
        ancho_maximo: int,
        max_lineas: int,
    ) -> list[str]:
        palabras = texto.split()
        lineas: list[str] = []
        actual: list[str] = []

        for palabra in palabras:
            prueba = " ".join(actual + [palabra])
            caja = dibujo.textbbox((0, 0), prueba, font=fuente)

            if caja[2] - caja[0] <= ancho_maximo:
                actual.append(palabra)
                continue

            if actual:
                lineas.append(" ".join(actual))
            actual = [palabra]

        if actual:
            lineas.append(" ".join(actual))

        return lineas[:max_lineas]

    def _crear_overlay(self, gancho: str, destino: Path) -> None:
        imagen = Image.new(
            "RGBA",
            (self.ANCHO, self.ALTO),
            (0, 0, 0, 0),
        )
        dibujo = ImageDraw.Draw(imagen)

        dibujo.rounded_rectangle(
            (34, 34, 1046, 330),
            radius=34,
            fill=(4, 8, 22, 224),
            outline=(0, 214, 235, 235),
            width=4,
        )
        dibujo.rounded_rectangle(
            (54, 54, 300, 116),
            radius=15,
            fill=(6, 12, 28, 245),
            outline=(0, 224, 245, 255),
            width=3,
        )

        fuente_marca = self._fuente(34)
        fuente_gancho = self._fuente(54)
        fuente_cta = self._fuente(34)

        dibujo.text(
            (82, 68),
            "NEXON IA",
            font=fuente_marca,
            fill=(255, 255, 255, 255),
        )

        lineas = self._ajustar_lineas(
            dibujo,
            gancho,
            fuente_gancho,
            920,
            3,
        )
        alto_linea = 68
        y = 138

        for indice, linea in enumerate(lineas):
            caja = dibujo.textbbox((0, 0), linea, font=fuente_gancho)
            x = (self.ANCHO - (caja[2] - caja[0])) // 2
            color = (245, 48, 68, 255) if indice == len(lineas) - 1 else (
                255,
                255,
                255,
                255,
            )
            dibujo.text(
                (x, y),
                linea,
                font=fuente_gancho,
                fill=color,
                stroke_width=3,
                stroke_fill=(0, 0, 0, 255),
            )
            y += alto_linea

        dibujo.rounded_rectangle(
            (74, 1548, 930, 1656),
            radius=28,
            fill=(4, 8, 22, 232),
            outline=(122, 58, 237, 245),
            width=4,
        )

        cta = "DOCUMENTAL COMPLETO EN NEXON IA"
        caja_cta = dibujo.textbbox((0, 0), cta, font=fuente_cta)
        x_cta = (self.ANCHO - (caja_cta[2] - caja_cta[0])) // 2
        dibujo.text(
            (x_cta, 1582),
            cta,
            font=fuente_cta,
            fill=(255, 255, 255, 255),
        )

        imagen.save(destino, "PNG")

    def _crear_srt_fragmento(
        self,
        subtitulos: list[Subtitulo],
        fragmento: FragmentoShort,
        destino: Path,
    ) -> None:
        bloques: list[str] = []
        numero = 1

        for subtitulo in subtitulos:
            if subtitulo.final <= fragmento.inicio:
                continue
            if subtitulo.inicio >= fragmento.final:
                break

            inicio = max(0.0, subtitulo.inicio - fragmento.inicio)
            final = min(
                fragmento.duracion,
                subtitulo.final - fragmento.inicio,
            )

            if final <= inicio:
                continue

            bloques.append(
                "\n".join(
                    (
                        str(numero),
                        f"{self._segundos_a_srt(inicio)} --> "
                        f"{self._segundos_a_srt(final)}",
                        subtitulo.texto,
                    )
                )
            )
            numero += 1

        destino.write_text(
            "\n\n".join(bloques) + "\n",
            encoding="utf-8-sig",
        )

    @staticmethod
    def _ruta_filtro(ruta: Path) -> str:
        texto = str(ruta.resolve()).replace("\\", "/")
        texto = texto.replace(":", r"\:")
        texto = texto.replace("'", r"\'")
        return texto

    def _renderizar(
        self,
        video: Path,
        fragmento: FragmentoShort,
        srt: Path,
        overlay: Path,
        salida: Path,
    ) -> None:
        ffmpeg = shutil.which("ffmpeg")

        if not ffmpeg:
            raise FileNotFoundError("FFmpeg no esta disponible en PATH.")

        srt_filtro = self._ruta_filtro(srt)
        filtro = (
            "[0:v]setpts=PTS-STARTPTS,split=2[fondo][frente];"
            "[fondo]"
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            "gblur=sigma=30,"
            "eq=brightness=-0.30:saturation=0.85[fondo_vertical];"
            "[frente]"
            "scale=1280:-2,"
            "crop=1080:720[frente_limpio];"            "[fondo_vertical][frente_limpio]"
            "overlay=0:(H-h)/2[base];"
            "[base][1:v]overlay=0:0:shortest=1[marca];"
            f"[marca]subtitles='{srt_filtro}':"
            "force_style='FontName=Arial,FontSize=11,"
            "PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,"
            "BackColour=&H88000000,"
            "BorderStyle=3,Outline=1,Shadow=0,"
            "Alignment=2,MarginL=15,MarginR=15,MarginV=72'[v]"
        )

        comando = [
            ffmpeg,
            "-y",
            "-ss",
            f"{fragmento.inicio:.3f}",
            "-t",
            f"{fragmento.duracion:.3f}",
            "-i",
            str(video),
            "-loop",
            "1",
            "-i",
            str(overlay),
            "-filter_complex",
            filtro,
            "-map",
            "[v]",
            "-map",
            "0:a:0?",
            "-af",
            "loudnorm=I=-14:TP=-1.5:LRA=7",
            "-ar",
            "48000",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            "-shortest",
            str(salida),
        ]

        subprocess.run(
            comando,
            cwd=self.project_root,
            check=True,
        )

        if not salida.is_file() or salida.stat().st_size == 0:
            raise RuntimeError(f"No se genero correctamente: {salida}")

    def generar(
        self,
        cantidad: int = 4,
        duracion_objetivo: float = 42.0,
        solo_plan: bool = False,
    ) -> dict[str, Any]:
        video = self._buscar_video()
        srt = self._buscar_srt()
        metadata = self._metadata()
        subtitulos = self._leer_srt(srt)
        fragmentos = self.seleccionar_fragmentos(
            subtitulos,
            cantidad=cantidad,
            duracion_objetivo=duracion_objetivo,
        )

        marca_tiempo = datetime.now().strftime("%Y%m%d_%H%M%S")
        carpeta = (
            self.project_root
            / "output"
            / "shorts"
            / f"shorts_{marca_tiempo}"
        )
        carpeta.mkdir(parents=True, exist_ok=True)

        elementos: list[dict[str, Any]] = []

        for indice, fragmento in enumerate(fragmentos, start=1):
            gancho = self._gancho(fragmento.texto)
            archivo = carpeta / f"short_{indice:02d}.mp4"
            srt_corto = carpeta / f"short_{indice:02d}.srt"
            overlay = carpeta / f"short_{indice:02d}_overlay.png"

            elemento = {
                "orden": indice,
                "inicio_segundos": round(fragmento.inicio, 3),
                "final_segundos": round(fragmento.final, 3),
                "duracion_segundos": round(fragmento.duracion, 3),
                "puntuacion": fragmento.puntuacion,
                "gancho": gancho,
                "texto": fragmento.texto,
                "titulo": f"{gancho[:85]} #Shorts",
                "descripcion": (
                    f"{gancho}\n\n"
                    "Mira el documental completo en NEXON IA.\n\n"
                    "#InteligenciaArtificial #Tecnologia #Shorts"
                ),
                "archivo": str(archivo) if not solo_plan else "",
            }

            if not solo_plan:
                self._crear_srt_fragmento(
                    subtitulos,
                    fragmento,
                    srt_corto,
                )
                self._crear_overlay(gancho, overlay)
                self._renderizar(
                    video,
                    fragmento,
                    srt_corto,
                    overlay,
                    archivo,
                )

            elementos.append(elemento)

        manifiesto = {
            "generado_en": datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
            "titulo_documental": metadata.get("title", ""),
            "video_origen": str(video),
            "subtitulos_origen": str(srt),
            "resolucion": "1080x1920",
            "cantidad": len(elementos),
            "solo_plan": solo_plan,
            "shorts": elementos,
        }

        manifiesto_ruta = carpeta / "shorts_manifest.json"
        manifiesto_ruta.write_text(
            json.dumps(manifiesto, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        manifiesto["manifiesto"] = str(manifiesto_ruta)
        return manifiesto


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genera Shorts verticales desde el documental mas reciente."
    )
    parser.add_argument("--cantidad", type=int, default=4)
    parser.add_argument("--duracion", type=float, default=42.0)
    parser.add_argument("--solo-plan", action="store_true")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[3]
    generador = GeneradorShorts(project_root)
    resultado = generador.generar(
        cantidad=args.cantidad,
        duracion_objetivo=args.duracion,
        solo_plan=args.solo_plan,
    )

    print()
    print("GENERADOR DE SHORTS")
    print("=" * 72)
    print("Video:", resultado["video_origen"])
    print("Resolucion:", resultado["resolucion"])
    print("Cantidad:", resultado["cantidad"])

    for short in resultado["shorts"]:
        print()
        print(
            f"{short['orden']}. {short['gancho']} | "
            f"{short['inicio_segundos']:.1f}-"
            f"{short['final_segundos']:.1f}s | "
            f"{short['duracion_segundos']:.1f}s | "
            f"score={short['puntuacion']:.1f}"
        )
        if short["archivo"]:
            print("   Archivo:", short["archivo"])

    print()
    print("Manifiesto:", resultado["manifiesto"])
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

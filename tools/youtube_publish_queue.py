from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from youtube_channels import (
    CHANNEL_CHOICES,
    DEFAULT_CHANNEL,
    channel_profile,
    normalize_channel_slug,
)


ROOT = Path(__file__).resolve().parents[1]
QUEUE_FILE = (
    ROOT
    / "data"
    / "publish"
    / "upload_queue.json"
)


def channel_of_element(element: dict[str, Any]) -> str:
    return normalize_channel_slug(
        str(
            element.get(
                "channel_slug",
                DEFAULT_CHANNEL,
            )
        )
    )


def publication_id(
    kind: str,
    sha256: str,
    channel_slug: str,
) -> str:
    if channel_slug == DEFAULT_CHANNEL:
        return f"{kind}:{sha256[:24]}"

    return f"{kind}:{channel_slug}:{sha256[:24]}"


def shorts_state_file(
    manifest: Path,
    channel_slug: str,
) -> Path:
    if channel_slug == DEFAULT_CHANNEL:
        return manifest.parent / "youtube_publish.json"

    return manifest.parent / f"youtube_publish_{channel_slug}.json"


def ahora() -> str:
    return (
        datetime.now()
        .astimezone()
        .isoformat(timespec="seconds")
    )


def cargar_json(
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

        return (
            datos
            if isinstance(datos, dict)
            else {}
        )

    except (
        OSError,
        json.JSONDecodeError,
    ):
        return {}


def cargar_cola() -> dict[str, Any]:
    datos = cargar_json(
        QUEUE_FILE
    )

    if not datos:
        datos = {
            "version": 1,
            "creado_en": ahora(),
            "actualizado_en": ahora(),
            "elementos": [],
        }

    if not isinstance(
        datos.get("elementos"),
        list,
    ):
        datos["elementos"] = []

    return datos


def guardar_cola(
    cola: dict[str, Any],
) -> None:
    QUEUE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    cola["actualizado_en"] = ahora()

    QUEUE_FILE.write_text(
        json.dumps(
            cola,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def ultimo(
    patron: str,
) -> Path | None:
    archivos = [
        ruta
        for ruta in ROOT.glob(
            patron
        )
        if ruta.is_file()
    ]

    if not archivos:
        return None

    return max(
        archivos,
        key=lambda ruta: ruta.stat().st_mtime,
    )


def ruta_segura(
    valor: Any,
) -> Path | None:
    if not valor:
        return None

    try:
        ruta = Path(
            str(valor)
        ).expanduser()

        if not ruta.is_absolute():
            ruta = ROOT / ruta

        return ruta.resolve()

    except OSError:
        return None


def huella_archivo(
    ruta: Path,
    cola: dict[str, Any],
) -> str:
    tamano = ruta.stat().st_size
    modificado = ruta.stat().st_mtime_ns
    ruta_texto = str(
        ruta.resolve()
    )

    for elemento in cola.get(
        "elementos",
        [],
    ):
        if not isinstance(
            elemento,
            dict,
        ):
            continue

        if (
            elemento.get("archivo")
            == ruta_texto
            and elemento.get(
                "tamano_bytes"
            ) == tamano
            and elemento.get(
                "modificado_ns"
            ) == modificado
            and elemento.get(
                "sha256"
            )
        ):
            return str(
                elemento["sha256"]
            )

    resumen = hashlib.sha256()

    with ruta.open("rb") as entrada:
        while True:
            bloque = entrada.read(
                4 * 1024 * 1024
            )

            if not bloque:
                break

            resumen.update(
                bloque
            )

    return resumen.hexdigest()


def buscar_publicacion_documental(
    video: Path,
    sha256: str,
    channel_slug: str,
) -> tuple[
    Path | None,
    dict[str, Any],
]:
    manifiestos = sorted(
        [
            ruta
            for ruta in ROOT.glob(
                "output/youtube/"
                "publish_*.json"
            )
            if ruta.is_file()
        ],
        key=lambda ruta: ruta.stat().st_mtime,
        reverse=True,
    )

    video_resuelto = video.resolve()

    for manifiesto in manifiestos:
        datos = cargar_json(
            manifiesto
        )

        manifest_channel = normalize_channel_slug(
            str(
                datos.get(
                    "channel_slug",
                    DEFAULT_CHANNEL,
                )
            )
        )

        if manifest_channel != channel_slug:
            continue

        ruta_publicada = ruta_segura(
            datos.get("video")
        )

        misma_ruta = (
            ruta_publicada is not None
            and ruta_publicada
            == video_resuelto
        )

        misma_huella = (
            bool(
                datos.get("sha256")
            )
            and datos.get("sha256")
            == sha256
        )

        if misma_ruta or misma_huella:
            return (
                manifiesto,
                datos,
            )

    return (
        None,
        {},
    )


def indice_elementos(
    cola: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        str(
            elemento.get(
                "id",
                "",
            )
        ): elemento
        for elemento in cola.get(
            "elementos",
            [],
        )
        if (
            isinstance(
                elemento,
                dict,
            )
            and elemento.get("id")
        )
    }


def agregar_o_actualizar(
    cola: dict[str, Any],
    nuevo: dict[str, Any],
) -> None:
    indice = indice_elementos(
        cola
    )

    identificador = str(
        nuevo["id"]
    )

    existente = indice.get(
        identificador
    )

    if existente is None:
        nuevo.setdefault(
            "creado_en",
            ahora(),
        )
        nuevo.setdefault(
            "intentos",
            0,
        )
        nuevo.setdefault(
            "ultimo_error",
            "",
        )
        nuevo["actualizado_en"] = (
            ahora()
        )

        cola["elementos"].append(
            nuevo
        )
        return

    estado_anterior = str(
        existente.get(
            "estado",
            "",
        )
    )

    video_id_anterior = str(
        existente.get(
            "video_id",
            "",
        )
    )

    existente.update(
        nuevo
    )

    if (
        estado_anterior
        == "publicado"
        and nuevo.get(
            "estado"
        )
        != "publicado"
    ):
        existente["estado"] = (
            "publicado"
        )
        existente["video_id"] = (
            video_id_anterior
        )

        if video_id_anterior:
            existente["url"] = (
                "https://youtu.be/"
                f"{video_id_anterior}"
            )

    if existente.get("estado") != "error":
        existente["ultimo_error"] = ""

    existente["actualizado_en"] = (
        ahora()
    )


def depurar_aliases_cruzados(
    cola: dict[str, Any],
) -> int:
    """Elimina pendientes duplicados atribuidos al canal incorrecto."""
    elementos = [
        elemento
        for elemento in cola.get("elementos", [])
        if isinstance(elemento, dict)
    ]
    eliminar: set[str] = set()

    for elemento in elementos:
        if elemento.get("estado") != "pendiente":
            continue

        sha256 = str(elemento.get("sha256", ""))
        archivo = str(elemento.get("archivo", ""))
        canal = channel_of_element(elemento)

        if not sha256 or not archivo:
            continue

        pertenece_otro_canal = any(
            otro is not elemento
            and str(otro.get("sha256", "")) == sha256
            and str(otro.get("archivo", "")) == archivo
            and channel_of_element(otro) != canal
            and (
                otro.get("estado") == "publicado"
                or str(otro.get("creado_en", ""))
                < str(elemento.get("creado_en", ""))
            )
            for otro in elementos
        )

        if pertenece_otro_canal:
            eliminar.add(str(elemento.get("id", "")))

    if eliminar:
        cola["elementos"] = [
            elemento
            for elemento in elementos
            if str(elemento.get("id", "")) not in eliminar
        ]

    return len(eliminar)


def inicio_pipeline_canal(
    channel_slug: str,
) -> datetime | None:
    """Obtiene el inicio de la producción activa del canal."""
    estado = cargar_json(
        ROOT
        / "data"
        / "pipeline_states"
        / f"{channel_slug}.json"
    )
    valor = str(estado.get("iniciado_en", "")).strip()

    if not valor:
        return None

    try:
        return datetime.fromisoformat(valor)
    except ValueError:
        return None


def sincronizar(
    cola: dict[str, Any] | None = None,
    channel_slug: str = DEFAULT_CHANNEL,
) -> dict[str, Any]:
    channel_slug = normalize_channel_slug(channel_slug)
    profile = channel_profile(channel_slug)

    if cola is None:
        cola = cargar_cola()

    aliases_eliminados = depurar_aliases_cruzados(cola)
    if aliases_eliminados:
        print(
            "AVISO: se retiraron "
            f"{aliases_eliminados} pendientes duplicados "
            "atribuidos al canal incorrecto."
        )

    video = ultimo(
        "output/videos/render_*/"
        "video_final_subtitulado_musica.mp4"
    )

    if video is None:
        video = ultimo(
            "output/videos/render_*/"
            "video_final.mp4"
        )

    if video is not None:
        metadata_candidate = cargar_json(
            ROOT
            / "data"
            / "publish"
            / "metadata.json"
        )
        metadata_channel = normalize_channel_slug(
            str(
                metadata_candidate.get(
                    "channel_slug",
                    DEFAULT_CHANNEL,
                )
            )
        )

        if metadata_channel != channel_slug:
            video = None

    if video is not None:
        inicio_pipeline = inicio_pipeline_canal(
            channel_slug
        )

        if (
            inicio_pipeline is not None
            and video.stat().st_mtime
            < inicio_pipeline.timestamp() - 60
        ):
            print(
                "AVISO: el video local mas reciente es anterior "
                "a la produccion del canal y no se agregara a "
                "su cola."
            )
            video = None

    if video is not None:
        sha256 = huella_archivo(
            video,
            cola,
        )

        canal_de_otra_huella = next(
            (
                channel_of_element(elemento)
                for elemento in cola.get("elementos", [])
                if isinstance(elemento, dict)
                and str(elemento.get("sha256", "")) == sha256
                and channel_of_element(elemento) != channel_slug
            ),
            "",
        )

        if canal_de_otra_huella:
            print(
                "AVISO: el archivo pertenece a otro canal "
                f"({canal_de_otra_huella}) y no se agregara "
                f"a {channel_slug}."
            )
            video = None

    if video is not None:
        sha256 = huella_archivo(
            video,
            cola,
        )

        manifiesto, publicacion = (
            buscar_publicacion_documental(
                video,
                sha256,
                channel_slug,
            )
        )

        metadata = cargar_json(
            ROOT
            / "data"
            / "publish"
            / "metadata.json"
        )

        video_id = str(
            publicacion.get(
                "video_id",
                "",
            )
        )

        elemento = {
            "id": publication_id(
                "documental",
                sha256,
                channel_slug,
            ),
            "tipo": "documental",
            "channel_slug": channel_slug,
            "channel_name": profile["display_name"],
            "orden": 0,
            "titulo": str(
                publicacion.get(
                    "title",
                    metadata.get(
                        "title",
                        video.stem,
                    ),
                )
            ),
            "archivo": str(
                video.resolve()
            ),
            "tamano_bytes": (
                video.stat().st_size
            ),
            "modificado_ns": (
                video.stat().st_mtime_ns
            ),
            "sha256": sha256,
            "estado": (
                "publicado"
                if video_id
                else "pendiente"
            ),
            "video_id": video_id,
            "url": (
                "https://youtu.be/"
                f"{video_id}"
                if video_id
                else ""
            ),
            "manifiesto": (
                str(
                    manifiesto.resolve()
                )
                if manifiesto
                else ""
            ),
        }

        agregar_o_actualizar(
            cola,
            elemento,
        )

    manifiesto_shorts = ultimo(
        "output/shorts/shorts_*/"
        "shorts_manifest.json"
    )

    if manifiesto_shorts is not None:
        candidate_short_manifest = cargar_json(
            manifiesto_shorts
        )
        manifest_channel = normalize_channel_slug(
            str(
                candidate_short_manifest.get(
                    "channel_slug",
                    DEFAULT_CHANNEL,
                )
            )
        )

        if manifest_channel != channel_slug:
            manifiesto_shorts = None

    if manifiesto_shorts:
        datos_shorts = cargar_json(
            manifiesto_shorts
        )

        estado_ruta = shorts_state_file(
            manifiesto_shorts,
            channel_slug,
        )

        estado_publicacion = (
            cargar_json(
                estado_ruta
            )
        )

        registros = {
            int(
                registro.get(
                    "orden",
                    0,
                )
            ): registro
            for registro in (
                estado_publicacion.get(
                    "publicaciones",
                    [],
                )
            )
            if isinstance(
                registro,
                dict,
            )
        }

        estado_lote = str(
            estado_publicacion.get(
                "estado",
                "",
            )
        )

        shorts = datos_shorts.get(
            "shorts",
            [],
        )

        if isinstance(
            shorts,
            list,
        ):
            for posicion, short in enumerate(
                shorts,
                start=1,
            ):
                if not isinstance(
                    short,
                    dict,
                ):
                    continue

                orden = int(
                    short.get(
                        "orden",
                        posicion,
                    )
                )

                archivo = ruta_segura(
                    short.get("archivo")
                )

                if (
                    archivo is None
                    or not archivo.is_file()
                ):
                    continue

                sha256 = huella_archivo(
                    archivo,
                    cola,
                )

                registro = registros.get(
                    orden,
                    {},
                )

                video_id = str(
                    registro.get(
                        "video_id",
                        "",
                    )
                )

                if video_id:
                    estado = "publicado"
                elif (
                    estado_lote
                    == "pendiente_limite_youtube"
                ):
                    estado = (
                        "aplazado_limite"
                    )
                elif (
                    estado_lote
                    == "pendiente_conexion_youtube"
                ):
                    estado = (
                        "aplazado_conexion"
                    )
                else:
                    estado = "pendiente"

                elemento = {
                    "id": publication_id(
                        "short",
                        sha256,
                        channel_slug,
                    ),
                    "tipo": "short",
                    "channel_slug": channel_slug,
                    "channel_name": profile["display_name"],
                    "orden": orden,
                    "titulo": str(
                        short.get(
                            "titulo",
                            archivo.stem,
                        )
                    ),
                    "archivo": str(
                        archivo.resolve()
                    ),
                    "tamano_bytes": (
                        archivo.stat().st_size
                    ),
                    "modificado_ns": (
                        archivo.stat().st_mtime_ns
                    ),
                    "sha256": sha256,
                    "estado": estado,
                    "video_id": video_id,
                    "url": (
                        "https://youtu.be/"
                        f"{video_id}"
                        if video_id
                        else ""
                    ),
                    "manifiesto": str(
                        manifiesto_shorts.resolve()
                    ),
                    "estado_publicacion": (
                        str(
                            estado_ruta.resolve()
                        )
                    ),
                }

                agregar_o_actualizar(
                    cola,
                    elemento,
                )

    guardar_cola(
        cola
    )

    return cola


def resumen_estados(
    cola: dict[str, Any],
    channel_slug: str = DEFAULT_CHANNEL,
) -> dict[str, int]:
    channel_slug = normalize_channel_slug(channel_slug)
    resumen: dict[str, int] = {}

    for elemento in cola.get(
        "elementos",
        [],
    ):
        if not isinstance(
            elemento,
            dict,
        ):
            continue

        if channel_of_element(elemento) != channel_slug:
            continue

        estado = str(
            elemento.get(
                "estado",
                "desconocido",
            )
        )

        resumen[estado] = (
            resumen.get(
                estado,
                0,
            )
            + 1
        )

    return resumen


def mostrar_estado(
    cola: dict[str, Any],
    channel_slug: str = DEFAULT_CHANNEL,
) -> None:
    channel_slug = normalize_channel_slug(channel_slug)
    profile = channel_profile(channel_slug)
    elementos = [
        elemento
        for elemento in cola.get(
            "elementos",
            [],
        )
        if isinstance(
            elemento,
            dict,
        )
        and channel_of_element(elemento) == channel_slug
    ]

    print()
    print(
        f"{profile['display_name'].upper()} "
        "- COLA DE PUBLICACION"
    )
    print("=" * 72)
    print(
        f"Elementos registrados: "
        f"{len(elementos)}"
    )

    for estado, cantidad in sorted(
        resumen_estados(
            cola,
            channel_slug,
        ).items()
    ):
        print(
            f"{estado}: {cantidad}"
        )

    print("=" * 72)

    for posicion, elemento in enumerate(
        elementos,
        start=1,
    ):
        tipo = str(
            elemento.get(
                "tipo",
                "",
            )
        ).upper()

        estado = str(
            elemento.get(
                "estado",
                "",
            )
        ).upper()

        titulo = str(
            elemento.get(
                "titulo",
                "Sin titulo",
            )
        )

        print()
        print(
            f"{posicion}. "
            f"[{tipo}] [{estado}] "
            f"{titulo}"
        )

        if elemento.get("url"):
            print(
                f"   {elemento['url']}"
            )

        print(
            "   SHA256: "
            f"{str(elemento.get('sha256', ''))[:16]}..."
        )

        if elemento.get(
            "ultimo_error"
        ):
            print(
                "   Ultimo error: "
                f"{elemento['ultimo_error']}"
            )

    print()
    print(
        f"Archivo de cola: {QUEUE_FILE}"
    )
    print("=" * 72)


def marcar_error(
    cola: dict[str, Any],
    identificadores: set[str],
    error: Exception,
) -> None:
    for elemento in cola.get(
        "elementos",
        [],
    ):
        if not isinstance(
            elemento,
            dict,
        ):
            continue

        if str(
            elemento.get(
                "id",
                "",
            )
        ) not in identificadores:
            continue

        elemento["estado"] = "error"
        elemento["ultimo_error"] = (
            str(error)[-1000:]
        )
        elemento["intentos"] = (
            int(
                elemento.get(
                    "intentos",
                    0,
                )
            )
            + 1
        )
        elemento["actualizado_en"] = (
            ahora()
        )

    guardar_cola(
        cola
    )


def reanudar(
    dry_run: bool,
    channel_slug: str = DEFAULT_CHANNEL,
) -> int:
    channel_slug = normalize_channel_slug(channel_slug)
    cola = sincronizar(
        channel_slug=channel_slug,
    )

    pendientes = [
        elemento
        for elemento in cola.get(
            "elementos",
            [],
        )
        if (
            isinstance(
                elemento,
                dict,
            )
            and elemento.get(
                "estado"
            )
            in {
                "pendiente",
                "aplazado_limite",
                "aplazado_conexion",
                "error",
            }
            and channel_of_element(elemento) == channel_slug
        )
    ]

    if not pendientes:
        print(
            "No hay publicaciones pendientes."
        )
        return 0

    documentales = [
        elemento
        for elemento in pendientes
        if elemento.get(
            "tipo"
        )
        == "documental"
    ]

    if documentales:
        documental = documentales[-1]

        comando_documental = [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "youtube_publish_all.py"
            ),
            "--canal",
            channel_slug,
        ]

        print()
        print(
            "DOCUMENTAL PENDIENTE:"
        )
        print(
            documental.get(
                "titulo",
                "",
            )
        )

        if dry_run:
            print(
                "SIMULACION:",
                " ".join(
                    comando_documental
                ),
            )
        else:
            try:
                subprocess.run(
                    comando_documental,
                    cwd=ROOT,
                    check=True,
                )

            except subprocess.CalledProcessError as error:
                marcar_error(
                    cola,
                    {
                        str(
                            documental["id"]
                        )
                    },
                    error,
                )
                raise

    cola = sincronizar(
        cargar_cola(),
        channel_slug=channel_slug,
    )

    pendientes_shorts = [
        elemento
        for elemento in cola.get(
            "elementos",
            [],
        )
        if (
            isinstance(
                elemento,
                dict,
            )
            and elemento.get(
                "tipo"
            )
            == "short"
            and elemento.get(
                "estado"
            )
            in {
                "pendiente",
                "aplazado_limite",
                "aplazado_conexion",
                "error",
            }
            and channel_of_element(elemento) == channel_slug
        )
    ]

    grupos: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for elemento in pendientes_shorts:
        manifiesto = str(
            elemento.get(
                "manifiesto",
                "",
            )
        )

        if manifiesto:
            grupos.setdefault(
                manifiesto,
                [],
            ).append(
                elemento
            )

    for manifiesto, elementos in grupos.items():
        comando_shorts = [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "youtube_publish_shorts.py"
            ),
            "--manifiesto",
            manifiesto,
            "--canal",
            channel_slug,
        ]

        print()
        print(
            "LOTE DE SHORTS PENDIENTE:"
        )
        print(
            manifiesto
        )
        print(
            f"Cantidad pendiente: "
            f"{len(elementos)}"
        )

        if dry_run:
            print(
                "SIMULACION:",
                " ".join(
                    comando_shorts
                ),
            )
            continue

        try:
            subprocess.run(
                comando_shorts,
                cwd=ROOT,
                check=True,
            )

        except subprocess.CalledProcessError as error:
            marcar_error(
                cola,
                {
                    str(
                        elemento["id"]
                    )
                    for elemento in elementos
                },
                error,
            )
            raise

        cola = sincronizar(
            cargar_cola(),
            channel_slug=channel_slug,
        )

    print()
    print(
        "REANUDACION FINALIZADA"
    )

    mostrar_estado(
        sincronizar(
            cargar_cola(),
            channel_slug=channel_slug,
        ),
        channel_slug,
    )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Administra la cola segura "
            "de publicaciones de AutoTube AI."
        )
    )

    subcomandos = parser.add_subparsers(
        dest="accion",
        required=True,
    )

    sync_parser = subcomandos.add_parser(
        "sync",
        help=(
            "Detecta videos y Shorts "
            "y actualiza la cola."
        ),
    )

    status_parser = subcomandos.add_parser(
        "status",
        help=(
            "Muestra el estado de "
            "la cola de publicacion."
        ),
    )

    resume_parser = (
        subcomandos.add_parser(
            "resume",
            help=(
                "Reanuda publicaciones "
                "sin duplicar las completadas."
            ),
        )
    )

    resume_parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Muestra las acciones "
            "sin subir contenido."
        ),
    )

    for command_parser in (
        sync_parser,
        status_parser,
        resume_parser,
    ):
        command_parser.add_argument(
            "--canal",
            choices=CHANNEL_CHOICES,
            default=DEFAULT_CHANNEL,
            help="Canal cuya cola se administrara.",
        )

    args = parser.parse_args()

    if args.accion == "sync":
        cola = sincronizar(
            channel_slug=args.canal,
        )
        mostrar_estado(
            cola,
            args.canal,
        )
        return 0

    if args.accion == "status":
        cola = sincronizar(
            channel_slug=args.canal,
        )
        mostrar_estado(
            cola,
            args.canal,
        )
        return 0

    if args.accion == "resume":
        return reanudar(
            dry_run=args.dry_run,
            channel_slug=args.canal,
        )

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import youtube_publish_all as publicador
from youtube_channels import (
    CHANNEL_CHOICES,
    DEFAULT_CHANNEL,
    channel_profile,
    normalize_channel_slug,
)


ROOT = Path(__file__).resolve().parents[1]


def ultimo_manifiesto() -> Path:
    archivos = [
        ruta
        for ruta in ROOT.glob(
            "output/shorts/shorts_*/shorts_manifest.json"
        )
        if ruta.is_file()
    ]

    if not archivos:
        raise FileNotFoundError(
            "No se encontro ningun manifiesto de Shorts."
        )

    return max(
        archivos,
        key=lambda ruta: ruta.stat().st_mtime,
    )


def guardar_estado(ruta: Path, estado: dict[str, Any]) -> None:
    estado["actualizado_en"] = (
        datetime.now()
        .astimezone()
        .isoformat(timespec="seconds")
    )

    ruta.write_text(
        json.dumps(
            estado,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def es_limite_subida(error: Exception) -> bool:
    partes = [str(error)]

    contenido = getattr(
        error,
        "content",
        "",
    )

    if isinstance(contenido, bytes):
        contenido = contenido.decode(
            "utf-8",
            errors="replace",
        )

    partes.append(str(contenido))
    mensaje = " ".join(partes).lower()

    indicadores = (
        "uploadlimitexceeded",
        "exceeded the number of videos",
        "daily upload limit",
        "upload limit reached",
    )

    return any(
        indicador in mensaje
        for indicador in indicadores
    )


def es_error_conexion(
    error: Exception,
) -> bool:
    """Detecta fallos temporales de DNS, SSL o transporte."""
    mensajes: list[str] = []
    actual: BaseException | None = error
    visitados: set[int] = set()

    while (
        actual is not None
        and id(actual) not in visitados
    ):
        visitados.add(
            id(actual)
        )
        mensajes.append(
            str(actual)
        )
        actual = (
            actual.__cause__
            or actual.__context__
        )

    mensaje = " ".join(
        mensajes
    ).lower()

    indicadores = (
        "getaddrinfo failed",
        "failed to resolve",
        "name resolution",
        "nameresolutionerror",
        "temporary failure in name resolution",
        "max retries exceeded",
        "connectionerror",
        "transporterror",
        "connection reset",
        "connection aborted",
        "remote disconnected",
        "server disconnected",
        "eof occurred in violation of protocol",
        "timed out",
        "timeout",
    )

    return any(
        indicador in mensaje
        for indicador in indicadores
    )


def ordenes_pendientes(
    shorts: list[dict[str, Any]],
    publicaciones: dict[int, dict[str, Any]],
) -> list[int]:
    pendientes: list[int] = []

    for elemento in shorts:
        orden = int(
            elemento.get(
                "orden",
                0,
            )
        )

        registro = publicaciones.get(
            orden,
            {},
        )

        if not registro.get("video_id"):
            pendientes.append(orden)

    return pendientes


def resolver_manifiesto(
    argumento: str | None,
) -> Path:
    if not argumento:
        return ultimo_manifiesto()

    ruta = Path(argumento).expanduser()

    if not ruta.is_absolute():
        ruta = ROOT / ruta

    ruta = ruta.resolve()

    if not ruta.is_file():
        raise FileNotFoundError(
            f"No existe el manifiesto indicado: {ruta}"
        )

    return ruta


def ruta_estado_publicacion(
    manifiesto: Path,
    channel_slug: str,
) -> Path:
    if channel_slug == DEFAULT_CHANNEL:
        return manifiesto.parent / "youtube_publish.json"

    return (
        manifiesto.parent
        / f"youtube_publish_{channel_slug}.json"
    )


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula la publicacion sin subir videos.",
    )

    parser.add_argument(
        "--manifiesto",
        default=None,
        help=(
            "Ruta del shorts_manifest.json que se "
            "publicara o reanudara."
        ),
    )

    parser.add_argument(
        "--canal",
        choices=CHANNEL_CHOICES,
        default=DEFAULT_CHANNEL,
        help="Canal de YouTube que recibira los Shorts.",
    )

    args = parser.parse_args()
    profile = channel_profile(args.canal)

    manifiesto_ruta = resolver_manifiesto(
        args.manifiesto
    )

    datos = json.loads(
        manifiesto_ruta.read_text(
            encoding="utf-8-sig"
        )
    )

    manifest_channel = normalize_channel_slug(
        str(
            datos.get(
                "channel_slug",
                DEFAULT_CHANNEL,
            )
        )
    )

    if manifest_channel != args.canal:
        raise RuntimeError(
            "BLOQUEO DE SEGURIDAD: este lote de Shorts pertenece "
            f"a {manifest_channel}, no a {args.canal}."
        )

    shorts_raw = datos.get(
        "shorts",
        [],
    )

    if not isinstance(shorts_raw, list) or not shorts_raw:
        raise RuntimeError(
            "El manifiesto no contiene Shorts validos."
        )

    shorts: list[dict[str, Any]] = [
        elemento
        for elemento in shorts_raw
        if isinstance(elemento, dict)
    ]

    if not shorts:
        raise RuntimeError(
            "El manifiesto no contiene Shorts validos."
        )

    estado_ruta = ruta_estado_publicacion(
        manifiesto_ruta,
        args.canal,
    )

    if estado_ruta.is_file():
        estado = json.loads(
            estado_ruta.read_text(
                encoding="utf-8-sig"
            )
        )

        state_channel = str(
            estado.get(
                "channel_slug",
                DEFAULT_CHANNEL,
            )
        )

        if state_channel != args.canal:
            raise RuntimeError(
                "El estado de este lote pertenece al canal "
                f"{state_channel}, no a {args.canal}."
            )
    else:
        estado = {
            "creado_en": (
                datetime.now()
                .astimezone()
                .isoformat(timespec="seconds")
            ),
            "manifiesto": str(
                manifiesto_ruta
            ),
            "channel_slug": args.canal,
            "channel_name": profile["display_name"],
            "visibilidad": "private",
            "estado": "pendiente",
            "publicaciones": [],
            "pendientes": [
                int(
                    elemento.get(
                        "orden",
                        0,
                    )
                )
                for elemento in shorts
            ],
        }

    publicaciones = {
        int(
            elemento.get(
                "orden",
                0,
            )
        ): elemento
        for elemento in estado.get(
            "publicaciones",
            [],
        )
        if isinstance(elemento, dict)
    }

    print()
    print(
        f"{profile['display_name'].upper()} "
        "- PUBLICACION DE SHORTS"
    )
    print("=" * 56)
    print(f"Manifiesto: {manifiesto_ruta}")
    print(f"Cantidad: {len(shorts)}")
    print("Visibilidad: private")
    print("=" * 56)

    control_multimedia = (
        ROOT
        / "tools"
        / "media_quality_check.py"
    )

    if not control_multimedia.is_file():
        raise FileNotFoundError(
            "No existe el control multimedia: "
            f"{control_multimedia}"
        )

    print()
    print(
        "CONTROL TECNICO PREVIO A LOS SHORTS"
    )

    subprocess.run(
        [
            sys.executable,
            str(control_multimedia),
            "--validar-shorts",
            "--manifiesto-shorts",
            str(manifiesto_ruta),
        ],
        cwd=ROOT,
        check=True,
    )

    if not args.dry_run:
        estado["estado"] = "en_progreso"
        estado["pendientes"] = ordenes_pendientes(
            shorts,
            publicaciones,
        )
        guardar_estado(
            estado_ruta,
            estado,
        )

    youtube = None

    for elemento in shorts:
        orden = int(
            elemento.get(
                "orden",
                0,
            )
        )

        archivo = Path(
            str(
                elemento.get(
                    "archivo",
                    "",
                )
            )
        )

        if not archivo.is_file():
            raise FileNotFoundError(
                f"No existe el Short {orden}: {archivo}"
            )

        titulo = str(
            elemento.get(
                "titulo",
                f"{profile['display_name']} Short {orden}",
            )
        ).strip()

        if "#shorts" not in titulo.lower():
            titulo = f"{titulo} #Shorts"

        titulo = titulo[:100]

        descripcion = str(
            elemento.get(
                "descripcion",
                profile["short_description"],
            )
        )[:5000]

        print()
        print(
            f"{orden}/{len(shorts)} "
            f"{titulo}"
        )
        print(f"Archivo: {archivo}")

        anterior = publicaciones.get(
            orden
        )

        if anterior and anterior.get(
            "video_id"
        ):
            print(
                "OMITIDO: ya fue subido en "
                "una ejecucion anterior."
            )
            print(
                f"https://youtu.be/"
                f"{anterior['video_id']}"
            )
            continue

        if args.dry_run:
            print(
                "SIMULACION: no se subira."
            )
            continue

        metadata = {
            "title": titulo,
            "description": descripcion,
            "tags": profile["short_tags"],
            "category_id": "28",
            "language": "es",
        }

        print(
            "Subiendo en modo privado..."
        )

        try:
            if youtube is None:
                youtube = (
                    publicador.youtube_client(
                        args.canal
                    )
                )

            video_id = (
                publicador.upload_video(
                    youtube,
                    archivo,
                    metadata,
                )
            )

        except Exception as error:
            if es_error_conexion(
                error
            ):
                pendientes = ordenes_pendientes(
                    shorts,
                    publicaciones,
                )

                estado["estado"] = (
                    "pendiente_conexion_youtube"
                )
                estado["motivo"] = (
                    "conexion_temporal_no_disponible"
                )
                estado["detalle_error"] = str(
                    error
                )[-1200:]
                estado["conexion_detectada_en"] = (
                    datetime.now()
                    .astimezone()
                    .isoformat(timespec="seconds")
                )
                estado["siguiente_orden"] = orden
                estado["pendientes"] = pendientes
                estado["publicaciones"] = [
                    publicaciones[clave]
                    for clave in sorted(
                        publicaciones
                    )
                ]

                guardar_estado(
                    estado_ruta,
                    estado,
                )

                print()
                print("=" * 56)
                print(
                    "CONEXION CON YOUTUBE NO DISPONIBLE"
                )
                print(
                    "Los Shorts pendientes quedaron "
                    "guardados de forma segura."
                )
                print(
                    "Cuando regrese la conexion ejecuta:"
                )
                print(
                    "autotube publish-resume "
                    f"--canal {args.canal}"
                )
                print(
                    f"Estado: {estado_ruta}"
                )
                print("=" * 56)

                return 0

            if not es_limite_subida(
                error
            ):
                raise

            pendientes = ordenes_pendientes(
                shorts,
                publicaciones,
            )

            estado["estado"] = (
                "pendiente_limite_youtube"
            )
            estado["motivo"] = (
                "uploadLimitExceeded"
            )
            estado["limite_detectado_en"] = (
                datetime.now()
                .astimezone()
                .isoformat(timespec="seconds")
            )
            estado["siguiente_orden"] = orden
            estado["pendientes"] = pendientes
            estado["publicaciones"] = [
                publicaciones[clave]
                for clave in sorted(
                    publicaciones
                )
            ]

            guardar_estado(
                estado_ruta,
                estado,
            )

            print()
            print("=" * 56)
            print(
                "LIMITE DIARIO DE YOUTUBE ALCANZADO"
            )
            print(
                "Los Shorts pendientes quedaron "
                "guardados de forma segura."
            )
            print(
                "Espera hasta 24 horas y ejecuta:"
            )
            print(
                "python tools/youtube_publish_shorts.py "
                f'--manifiesto "{manifiesto_ruta}" '
                f"--canal {args.canal}"
            )
            print(
                f"Estado: {estado_ruta}"
            )
            print("=" * 56)

            return 0

        registro = {
            "orden": orden,
            "channel_slug": args.canal,
            "channel_name": profile["display_name"],
            "video_id": video_id,
            "url": (
                f"https://youtu.be/{video_id}"
            ),
            "titulo": titulo,
            "archivo": str(archivo),
            "publicado_en": (
                datetime.now()
                .astimezone()
                .isoformat(timespec="seconds")
            ),
            "visibilidad": "private",
        }

        publicaciones[orden] = registro
        estado["publicaciones"] = [
            publicaciones[clave]
            for clave in sorted(
                publicaciones
            )
        ]
        estado["pendientes"] = (
            ordenes_pendientes(
                shorts,
                publicaciones,
            )
        )

        guardar_estado(
            estado_ruta,
            estado,
        )

        print(
            f"SUBIDO: {registro['url']}"
        )

    print()
    print("=" * 56)

    if args.dry_run:
        print("SIMULACION CORRECTA")
        print(
            "No se ha subido nada a YouTube."
        )

    else:
        estado["estado"] = "completado"
        estado["pendientes"] = []
        estado["completado_en"] = (
            datetime.now()
            .astimezone()
            .isoformat(timespec="seconds")
        )

        guardar_estado(
            estado_ruta,
            estado,
        )

        print(
            "PUBLICACION DE SHORTS COMPLETADA"
        )
        print(
            f"Estado: {estado_ruta}"
        )

    print("=" * 56)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

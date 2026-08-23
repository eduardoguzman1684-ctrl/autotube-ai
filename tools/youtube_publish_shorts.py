from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import youtube_publish_all as publicador


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
            "No se encontró ningún manifiesto de Shorts."
        )

    return max(archivos, key=lambda ruta: ruta.stat().st_mtime)


def guardar_estado(ruta: Path, estado: dict) -> None:
    ruta.write_text(
        json.dumps(estado, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula la publicación sin subir videos.",
    )
    args = parser.parse_args()

    manifiesto_ruta = ultimo_manifiesto()
    datos = json.loads(
        manifiesto_ruta.read_text(encoding="utf-8-sig")
    )
    shorts = datos.get("shorts", [])

    if not isinstance(shorts, list) or not shorts:
        raise RuntimeError(
            "El manifiesto no contiene Shorts válidos."
        )

    estado_ruta = manifiesto_ruta.parent / "youtube_publish.json"

    if estado_ruta.is_file():
        estado = json.loads(
            estado_ruta.read_text(encoding="utf-8-sig")
        )
    else:
        estado = {
            "creado_en": datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
            "manifiesto": str(manifiesto_ruta),
            "visibilidad": "private",
            "publicaciones": [],
        }

    publicaciones = {
        int(elemento.get("orden", 0)): elemento
        for elemento in estado.get("publicaciones", [])
        if isinstance(elemento, dict)
    }

    print()
    print("NEXON IA - PUBLICACIÓN DE SHORTS")
    print("=" * 56)
    print(f"Manifiesto: {manifiesto_ruta}")
    print(f"Cantidad: {len(shorts)}")
    print("Visibilidad: private")
    print("=" * 56)

    youtube = None

    for elemento in shorts:
        orden = int(elemento.get("orden", 0))
        archivo = Path(str(elemento.get("archivo", "")))

        if not archivo.is_file():
            raise FileNotFoundError(
                f"No existe el Short {orden}: {archivo}"
            )

        titulo = str(
            elemento.get("titulo", f"NEXON IA Short {orden}")
        ).strip()

        if "#shorts" not in titulo.lower():
            titulo = f"{titulo} #Shorts"

        titulo = titulo[:100]
        descripcion = str(
            elemento.get(
                "descripcion",
                "Contenido de NEXON IA.",
            )
        )[:5000]

        print()
        print(f"{orden}/{len(shorts)} {titulo}")
        print(f"Archivo: {archivo}")

        anterior = publicaciones.get(orden)

        if anterior and anterior.get("video_id"):
            print(
                "OMITIDO: ya fue subido en una ejecución anterior."
            )
            print(f"https://youtu.be/{anterior['video_id']}")
            continue

        if args.dry_run:
            print("SIMULACIÓN: no se subirá.")
            continue

        if youtube is None:
            youtube = publicador.youtube_client()

        metadata = {
            "title": titulo,
            "description": descripcion,
            "tags": [
                "Inteligencia Artificial",
                "Tecnología",
                "Ciencia",
                "NEXON IA",
                "Shorts",
            ],
            "category_id": "28",
            "language": "es",
        }

        print("Subiendo en modo privado...")
        video_id = publicador.upload_video(
            youtube,
            archivo,
            metadata,
        )

        registro = {
            "orden": orden,
            "video_id": video_id,
            "url": f"https://youtu.be/{video_id}",
            "titulo": titulo,
            "archivo": str(archivo),
            "publicado_en": datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
            "visibilidad": "private",
        }

        publicaciones[orden] = registro
        estado["publicaciones"] = [
            publicaciones[clave]
            for clave in sorted(publicaciones)
        ]
        guardar_estado(estado_ruta, estado)
        print(f"SUBIDO: {registro['url']}")

    print()
    print("=" * 56)

    if args.dry_run:
        print("SIMULACIÓN CORRECTA")
        print("No se ha subido nada a YouTube.")
    else:
        print("PUBLICACIÓN DE SHORTS COMPLETADA")
        print(f"Estado: {estado_ruta}")

    print("=" * 56)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

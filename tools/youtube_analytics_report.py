from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


ROOT = Path(__file__).resolve().parents[1]
TOKEN_FILE = ROOT / "config" / "youtube" / "analytics_token.json"
OUTPUT_DIR = ROOT / "data" / "analytics"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def credenciales() -> Credentials:
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(
            "No existe analytics_token.json. "
            "Ejecuta tools/youtube_analytics_auth.py."
        )

    creds = Credentials.from_authorized_user_file(
        str(TOKEN_FILE),
        SCOPES,
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(
            creds.to_json(),
            encoding="utf-8",
        )

    if not creds.valid:
        raise RuntimeError(
            "Las credenciales de YouTube Analytics no son validas."
        )

    return creds


def convertir_filas(respuesta: dict[str, Any]) -> list[dict[str, Any]]:
    columnas = [
        columna["name"]
        for columna in respuesta.get("columnHeaders", [])
    ]

    return [
        dict(zip(columnas, fila))
        for fila in respuesta.get("rows", [])
    ]


def consultar(
    api,
    inicio: date,
    fin: date,
    metricas: str,
    dimensiones: str | None = None,
    ordenar: str | None = None,
    max_resultados: int | None = None,
) -> dict[str, Any]:
    parametros: dict[str, Any] = {
        "ids": "channel==MINE",
        "startDate": inicio.isoformat(),
        "endDate": fin.isoformat(),
        "metrics": metricas,
    }

    if dimensiones:
        parametros["dimensions"] = dimensiones

    if ordenar:
        parametros["sort"] = ordenar

    if max_resultados:
        parametros["maxResults"] = max_resultados

    return api.reports().query(**parametros).execute()


def informacion_canal(youtube) -> dict[str, str]:
    respuesta = youtube.channels().list(
        part="snippet",
        mine=True,
    ).execute()

    elementos = respuesta.get("items", [])

    if not elementos:
        return {
            "id": "",
            "titulo": "Canal de YouTube",
        }

    canal = elementos[0]

    return {
        "id": str(canal.get("id", "")),
        "titulo": str(
            canal.get("snippet", {}).get(
                "title",
                "Canal de YouTube",
            )
        ),
    }


def titulos_videos(youtube, ids: list[str]) -> dict[str, str]:
    titulos: dict[str, str] = {}

    for posicion in range(0, len(ids), 50):
        lote = ids[posicion:posicion + 50]

        if not lote:
            continue

        respuesta = youtube.videos().list(
            part="snippet",
            id=",".join(lote),
        ).execute()

        for elemento in respuesta.get("items", []):
            video_id = str(elemento.get("id", ""))
            titulo = str(
                elemento.get("snippet", {}).get(
                    "title",
                    "Video sin titulo",
                )
            )
            titulos[video_id] = titulo

    return titulos


def formato_duracion(segundos: Any) -> str:
    try:
        total = max(0, int(round(float(segundos))))
    except (TypeError, ValueError):
        total = 0

    minutos, segundos_restantes = divmod(total, 60)
    return f"{minutos}:{segundos_restantes:02d}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genera un informe de YouTube Analytics."
    )
    parser.add_argument(
        "--dias",
        type=int,
        default=28,
        help="Cantidad de dias que se analizaran.",
    )
    parser.add_argument(
        "--max-videos",
        type=int,
        default=50,
        help="Cantidad maxima de videos en el informe.",
    )
    args = parser.parse_args()

    dias = max(1, min(args.dias, 3650))
    max_videos = max(1, min(args.max_videos, 200))

    fin = date.today() - timedelta(days=1)
    inicio = fin - timedelta(days=dias - 1)

    creds = credenciales()

    analytics = build(
        "youtubeAnalytics",
        "v2",
        credentials=creds,
        cache_discovery=False,
    )

    youtube = build(
        "youtube",
        "v3",
        credentials=creds,
        cache_discovery=False,
    )

    canal = informacion_canal(youtube)

    metricas_base = (
        "views,"
        "estimatedMinutesWatched,"
        "averageViewDuration,"
        "subscribersGained,"
        "subscribersLost"
    )

    filas_resumen = convertir_filas(
        consultar(
            analytics,
            inicio,
            fin,
            metricas_base,
        )
    )

    resumen = (
        filas_resumen[0]
        if filas_resumen
        else {
            "views": 0,
            "estimatedMinutesWatched": 0,
            "averageViewDuration": 0,
            "subscribersGained": 0,
            "subscribersLost": 0,
        }
    )

    try:
        filas_interaccion = convertir_filas(
            consultar(
                analytics,
                inicio,
                fin,
                "likes,comments,shares",
            )
        )

        if filas_interaccion:
            resumen.update(filas_interaccion[0])

    except HttpError as error:
        print(
            "AVISO: no se pudieron consultar algunas "
            f"metricas de interaccion: {error.resp.status}"
        )

    diario = convertir_filas(
        consultar(
            analytics,
            inicio,
            fin,
            metricas_base,
            dimensiones="day",
            ordenar="day",
        )
    )

    metricas_video = (
        "views,"
        "estimatedMinutesWatched,"
        "averageViewDuration,"
        "likes,"
        "comments,"
        "shares,"
        "subscribersGained,"
        "subscribersLost"
    )

    try:
        videos = convertir_filas(
            consultar(
                analytics,
                inicio,
                fin,
                metricas_video,
                dimensiones="video",
                ordenar="-views",
                max_resultados=max_videos,
            )
        )

    except HttpError:
        videos = convertir_filas(
            consultar(
                analytics,
                inicio,
                fin,
                metricas_base,
                dimensiones="video",
                ordenar="-views",
                max_resultados=max_videos,
            )
        )

    ids_videos = [
        str(video.get("video", ""))
        for video in videos
        if video.get("video")
    ]

    mapa_titulos = titulos_videos(
        youtube,
        ids_videos,
    )

    for video in videos:
        video_id = str(video.get("video", ""))
        video["titulo"] = mapa_titulos.get(
            video_id,
            "Video sin titulo disponible",
        )
        video["url"] = (
            f"https://youtu.be/{video_id}"
            if video_id
            else ""
        )

    informe = {
        "generado_en": datetime.now()
        .astimezone()
        .isoformat(timespec="seconds"),
        "fuente": "YouTube Analytics API v2",
        "periodo": {
            "inicio": inicio.isoformat(),
            "fin": fin.isoformat(),
            "dias": dias,
        },
        "canal": canal,
        "resumen": resumen,
        "rendimiento_diario": diario,
        "videos": videos,
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    salida = (
        OUTPUT_DIR
        / (
            "youtube_analytics_"
            + datetime.now().strftime("%Y%m%d_%H%M%S")
            + ".json"
        )
    )

    salida.write_text(
        json.dumps(
            informe,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("YOUTUBE ANALYTICS - NEXON IA")
    print("=" * 64)
    print(f"Canal: {canal['titulo']}")
    print(f"Periodo: {inicio} a {fin}")
    print(f"Visualizaciones: {resumen.get('views', 0)}")
    print(
        "Minutos vistos: "
        f"{resumen.get('estimatedMinutesWatched', 0)}"
    )
    print(
        "Duracion media: "
        f"{formato_duracion(resumen.get('averageViewDuration', 0))}"
    )
    print(
        "Suscriptores ganados: "
        f"{resumen.get('subscribersGained', 0)}"
    )
    print(
        "Suscriptores perdidos: "
        f"{resumen.get('subscribersLost', 0)}"
    )
    print(
        "Interacciones: "
        f"{resumen.get('likes', 0)} likes, "
        f"{resumen.get('comments', 0)} comentarios, "
        f"{resumen.get('shares', 0)} compartidos"
    )

    print()
    print("VIDEOS CON MAYOR RENDIMIENTO")
    print("-" * 64)

    if not videos:
        print(
            "Todavia no hay datos individuales disponibles "
            "para este periodo."
        )

    for posicion, video in enumerate(videos[:10], start=1):
        print(
            f"{posicion}. {video.get('titulo', 'Sin titulo')}"
        )
        print(
            f"   Vistas: {video.get('views', 0)} | "
            "Duracion media: "
            f"{formato_duracion(video.get('averageViewDuration', 0))}"
        )
        print(f"   {video.get('url', '')}")

    print()
    print(f"Informe guardado: {salida}")
    print("=" * 64)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HttpError as error:
        print(
            f"Error de YouTube Analytics API: {error}",
        )
        raise SystemExit(1)

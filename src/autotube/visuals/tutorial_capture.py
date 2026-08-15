from __future__ import annotations

import json
import os
import shutil
import subprocess
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from .tutorial_drivers import obtener_driver
from .tutorial_annotations import aplicar_anotaciones_tutorial
from typing import Any
from urllib.parse import urlparse


PLATAFORMAS: dict[str, dict[str, Any]] = {
    "make": {
        "url": "https://www.make.com/en",
        "hosts": [
            "make.com",
            "www.make.com",
        ],
        "pantallas": {
            "registro": "https://www.make.com/en/register",
            "registrarse": "https://www.make.com/en/register",
            "crear cuenta": "https://www.make.com/en/register",
            "login": "https://www.make.com/en/login",
            "inicio de sesion": "https://www.make.com/en/login",
        },
    },
    "chatgpt": {
        "url": "https://chatgpt.com/",
        "hosts": [
            "chatgpt.com",
            "www.chatgpt.com",
        ],
        "pantallas": {},
    },
    "openai": {
        "url": "https://platform.openai.com/",
        "hosts": [
            "openai.com",
            "platform.openai.com",
        ],
        "pantallas": {
            "api": "https://platform.openai.com/docs/",
            "documentacion": "https://platform.openai.com/docs/",
            "api key": "https://platform.openai.com/api-keys",
            "clave api": "https://platform.openai.com/api-keys",
        },
    },
    "gmail": {
        "url": "https://mail.google.com/",
        "hosts": [
            "google.com",
            "mail.google.com",
            "accounts.google.com",
        ],
        "pantallas": {},
    },
    "n8n": {
        "url": "https://n8n.io/",
        "hosts": [
            "n8n.io",
            "www.n8n.io",
        ],
        "pantallas": {},
    },
    "supabase": {
        "url": "https://supabase.com/",
        "hosts": [
            "supabase.com",
            "www.supabase.com",
            "app.supabase.com",
        ],
        "pantallas": {},
    },
    "notion": {
        "url": "https://www.notion.so/",
        "hosts": [
            "notion.so",
            "www.notion.so",
        ],
        "pantallas": {},
    },
    "claude": {
        "url": "https://claude.ai/",
        "hosts": [
            "claude.ai",
        ],
        "pantallas": {},
    },
    "cursor": {
        "url": "https://www.cursor.com/",
        "hosts": [
            "cursor.com",
            "www.cursor.com",
        ],
        "pantallas": {},
    },
    "v0": {
        "url": "https://v0.dev/",
        "hosts": [
            "v0.dev",
            "www.v0.dev",
        ],
        "pantallas": {},
    },
    "heygen": {
        "url": "https://www.heygen.com/",
        "hosts": [
            "heygen.com",
            "www.heygen.com",
        ],
        "pantallas": {},
    },
    "elevenlabs": {
        "url": "https://elevenlabs.io/",
        "hosts": [
            "elevenlabs.io",
            "www.elevenlabs.io",
        ],
        "pantallas": {},
    },
}


def normalizar(texto: str) -> str:
    valor = unicodedata.normalize(
        "NFKD",
        str(texto).lower(),
    )

    valor = "".join(
        caracter
        for caracter in valor
        if not unicodedata.combining(caracter)
    )

    valor = re.sub(
        r"[^a-z0-9\s]+",
        " ",
        valor,
    )

    return re.sub(
        r"\s+",
        " ",
        valor,
    ).strip()


def detectar_plataforma(
    elemento: dict[str, Any],
) -> str:
    """Detecta la plataforma del clip."""
    declarada = normalizar(
        str(
            elemento.get(
                "plataforma",
                "",
            )
        )
    )

    if declarada in PLATAFORMAS:
        return declarada

    texto = " ".join(
        str(
            elemento.get(
                campo,
                "",
            )
        )
        for campo in (
            "texto_narrado",
            "descripcion",
            "pantalla_objetivo",
            "accion_visual",
        )
    )

    texto = normalizar(
        texto
    )

    alias = {
        "make com": "make",
        "make": "make",
        "chatgpt": "chatgpt",
        "chat gpt": "chatgpt",
        "openai": "openai",
        "open ai": "openai",
        "gmail": "gmail",
        "n8n": "n8n",
        "supabase": "supabase",
        "notion": "notion",
        "claude": "claude",
        "cursor": "cursor",
        "v0": "v0",
        "heygen": "heygen",
        "elevenlabs": "elevenlabs",
        "eleven labs": "elevenlabs",
    }

    for clave, plataforma in alias.items():
        if clave in texto:
            return plataforma

    return ""


def resolver_url(
    plataforma: str,
    elemento: dict[str, Any],
) -> str:
    """Resuelve una URL oficial segura."""
    config = PLATAFORMAS.get(
        plataforma
    )

    if not config:
        raise RuntimeError(
            f"Plataforma no soportada: {plataforma}"
        )

    url_declarada = str(
        elemento.get(
            "url_oficial",
            "",
        )
    ).strip()

    if url_declarada:
        parsed = urlparse(
            url_declarada
        )

        host = (
            parsed.hostname
            or ""
        ).lower()

        permitido = any(
            host == dominio
            or host.endswith(
                "." + dominio
            )
            for dominio in config["hosts"]
        )

        if permitido:
            return url_declarada

    pantalla = normalizar(
        str(
            elemento.get(
                "pantalla_objetivo",
                "",
            )
        )
    )

    for clave, url in config.get(
        "pantallas",
        {},
    ).items():
        if normalizar(clave) in pantalla:
            return str(url)

    return str(
        config["url"]
    )


def localizar_manifiesto_tutorial(
    output_dir: Path,
    archivo: Path | None = None,
) -> Path:
    """Localiza assets_manifest.json."""
    if archivo is not None:
        ruta = archivo.expanduser()

        if not ruta.is_absolute():
            ruta = (
                Path.cwd()
                / ruta
            )

        ruta = ruta.resolve()

        if not ruta.is_file():
            raise FileNotFoundError(
                f"No existe el manifiesto: {ruta}"
            )

        return ruta

    archivos = sorted(
        (
            output_dir
            / "assets"
        ).glob(
            "coleccion_*/assets_manifest.json"
        ),
        key=lambda ruta: ruta.stat().st_mtime,
        reverse=True,
    )

    if not archivos:
        raise FileNotFoundError(
            "No se encontr? ning?n assets_manifest.json."
        )

    return archivos[0]


def cargar_manifiesto_tutorial(
    output_dir: Path,
    archivo: Path | None = None,
) -> tuple[dict[str, Any], Path]:
    ruta = localizar_manifiesto_tutorial(
        output_dir=output_dir,
        archivo=archivo,
    )

    contenido = json.loads(
        ruta.read_text(
            encoding="utf-8"
        )
    )

    return contenido, ruta


class CapturadorTutorial:
    """Captura interfaces reales de plataformas web."""

    def __init__(
        self,
        project_root: Path,
    ) -> None:
        self.project_root = (
            Path(project_root)
            .resolve()
        )

        self.profile_dir = (
            self.project_root
            / "config"
            / "edge_tutorial_profile"
        )

        self.profile_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _playwright(self):
        try:
            from playwright.sync_api import (
                sync_playwright,
            )
        except ImportError as error:
            raise RuntimeError(
                "Playwright no est? instalado. "
                "Ejecuta: pip install -e ."
            ) from error

        return sync_playwright

    def abrir_sesion(
        self,
        plataforma: str,
    ) -> None:
        """
        Abre Microsoft Edge normal usando el perfil local
        de NEXON IA. Playwright no interviene en el login.
        """
        plataforma = normalizar(
            plataforma
        )

        if plataforma not in PLATAFORMAS:
            raise ValueError(
                "Plataforma no soportada: "
                + plataforma
            )

        url = str(
            PLATAFORMAS[
                plataforma
            ]["url"]
        )

        candidatos: list[Path] = []

        edge_path = shutil.which(
            "msedge"
        )

        if edge_path:
            candidatos.append(
                Path(edge_path)
            )

        for variable in (
            "ProgramFiles(x86)",
            "ProgramFiles",
            "LOCALAPPDATA",
        ):
            base = os.environ.get(
                variable
            )

            if base:
                candidatos.append(
                    Path(base)
                    / "Microsoft"
                    / "Edge"
                    / "Application"
                    / "msedge.exe"
                )

        edge = next(
            (
                ruta
                for ruta in candidatos
                if ruta.is_file()
            ),
            None,
        )

        if edge is None:
            raise FileNotFoundError(
                "No se encontro Microsoft Edge."
            )

        self.profile_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { $_.CommandLine -like '*edge_tutorial_profile*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

        comando = [
            str(edge),
            f"--user-data-dir={self.profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--remote-debugging-port=9222",
            "--remote-debugging-address=127.0.0.1",
            url,
        ]

        subprocess.Popen(
            comando,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        print()
        print("=" * 70)
        print("EDGE NORMAL ABIERTO")
        print("=" * 70)
        print(f"Plataforma: {plataforma}")
        print(f"URL: {url}")
        print(f"Perfil: {self.profile_dir}")
        print()
        print(
            "Comprueba que puedes navegar normalmente "
            "y que tu sesion esta iniciada."
        )
        print()
        print(
            "Deja esta ventana de Edge abierta durante las capturas."
        )
        print("CDP: 127.0.0.1:9222")
        return

    def _limpiar_datos_sensibles(
        self,
        pagina: Any,
    ) -> None:
        """Vac?a campos que podr?an contener credenciales."""
        try:
            pagina.evaluate(
                """
                () => {
                    const campos = document.querySelectorAll(
                        'input[type="password"],' +
                        'input[type="email"],' +
                        'input[autocomplete*="password"],' +
                        'input[autocomplete*="email"]'
                    );

                    for (const campo of campos) {
                        campo.value = '';
                        campo.setAttribute(
                            'value',
                            ''
                        );
                    }
                }
                """
            )
        except Exception:
            pass

    def _cerrar_cookies(
        self,
        pagina: Any,
    ) -> None:
        patrones = [
            "Accept all",
            "Accept",
            "Aceptar todo",
            "Aceptar",
            "Allow all",
        ]

        for texto in patrones:
            try:
                boton = pagina.get_by_role(
                    "button",
                    name=re.compile(
                        f"^{re.escape(texto)}$",
                        re.IGNORECASE,
                    ),
                )

                if boton.count():
                    boton.first.click(
                        timeout=1200
                    )
                    return

            except Exception:
                continue

    def capturar(
        self,
        manifiesto: dict[str, Any],
        ruta_manifiesto: Path,
        forzar: bool = False,
        limite: int = 0,
        mostrar_navegador: bool = False,
    ) -> dict[str, Any]:
        """Captura todos los clips captura_web_real."""
        elementos = manifiesto.get(
            "elementos",
            [],
        )

        if not isinstance(
            elementos,
            list,
        ):
            raise RuntimeError(
                "El manifiesto no contiene elementos."
            )

        pendientes = [
            elemento
            for elemento in elementos
            if isinstance(
                elemento,
                dict,
            )
            and str(
                elemento.get(
                    "tipo_recurso",
                    "",
                )
            ) == "captura_web_real"
            and (
                str(
                    elemento.get(
                        "estado",
                        "",
                    )
                )
                in {
                    "pendiente_generacion",
                    "error",
                }
                or forzar
            )
        ]

        if limite > 0:
            pendientes = pendientes[
                :limite
            ]

        if not pendientes:
            return {
                "capturadas": 0,
                "errores": 0,
                "pendientes": 0,
            }

        sync_playwright = (
            self._playwright()
        )

        capturadas = 0
        errores = 0

        with sync_playwright() as p:
            endpoint = "http" + "://" + "127.0.0.1:9222"
            navegador = p.chromium.connect_over_cdp(endpoint)

            if not navegador.contexts:
                raise RuntimeError(
                    "No se encontro un contexto abierto en Edge."
                )

            contexto = navegador.contexts[0]

            pagina = (
                contexto.pages[0]
                if contexto.pages
                else contexto.new_page()
            )


            for numero, elemento in enumerate(
                pendientes,
                start=1,
            ):
                plataforma = (
                    detectar_plataforma(
                        elemento
                    )
                )

                if not plataforma:
                    elemento["estado"] = (
                        "error"
                    )

                    elemento["error"] = (
                        "No se pudo detectar "
                        "la plataforma."
                    )

                    errores += 1
                    continue

                try:
                    url = resolver_url(
                        plataforma,
                        elemento,
                    )

                    segmento_indice = int(
                        elemento.get(
                            "segmento_indice",
                            0,
                        )
                        or 0
                    )

                    clip_orden = int(
                        elemento.get(
                            "clip_orden",
                            numero,
                        )
                        or numero
                    )

                    titulo_segmento = str(
                        elemento.get(
                            "segmento_titulo",
                            f"Segmento {segmento_indice}",
                        )
                    )

                    carpeta = (
                        ruta_manifiesto.parent
                        / (
                            f"{segmento_indice:02d}_"
                            + re.sub(
                                r"[^a-zA-Z0-9_-]+",
                                "_",
                                normalizar(
                                    titulo_segmento
                                ),
                            ).strip("_")
                        )
                    )

                    carpeta.mkdir(
                        parents=True,
                        exist_ok=True,
                    )

                    destino = (
                        carpeta
                        / (
                            f"clip_{clip_orden:02d}_"
                            f"web_{plataforma}.png"
                        )
                    )

                    print(
                        f"Capturando {numero}/"
                        f"{len(pendientes)}: "
                        f"{plataforma} | "
                        f"{elemento.get('pantalla_objetivo', '')}"
                    )

                    driver = obtener_driver(
                        plataforma
                    )

                    resultado_driver = driver.preparar(
                        contexto,
                        elemento,
                        url,
                    )

                    pagina = resultado_driver.pagina

                    pagina.wait_for_timeout(
                        1200
                    )

                    self._cerrar_cookies(
                        pagina
                    )

                    pagina.wait_for_timeout(
                        500
                    )

                    self._limpiar_datos_sensibles(
                        pagina
                    )

                    actual = (
                        pagina.url.lower()
                    )

                    requiere_login = bool(
                        elemento.get(
                            "requiere_login",
                            False,
                        )
                    )

                    objetivo = normalizar(
                        str(
                            elemento.get(
                                "pantalla_objetivo",
                                "",
                            )
                        )
                    )

                    parece_login = any(
                        token in actual
                        for token in (
                            "login",
                            "signin",
                            "sign-in",
                            "auth",
                        )
                    )

                    if (
                        requiere_login
                        and parece_login
                        and "login"
                        not in objetivo
                        and "sesion"
                        not in objetivo
                    ):
                        raise RuntimeError(
                            "La pantalla requiere sesi?n. "
                            "Ejecuta primero: "
                            "autotube tutorial-capture "
                            f"--login {plataforma}"
                        )

                    ejecutar_accion = getattr(
                        driver,
                        "ejecutar_accion",
                        None,
                    )

                    if callable(ejecutar_accion):
                        resultado_accion = ejecutar_accion(
                            pagina,
                            elemento,
                        )
                    else:
                        resultado_accion = "sin_accion_especifica"

                    pagina.wait_for_timeout(
                        800
                    )

                    # Gmail puede contener informacion privada.
                    # Solo permitimos la captura cuando el driver
                    # ha creado y verificado la capa sanitizada.
                    if (
                        plataforma == "gmail"
                        and requiere_login
                    ):
                        overlay_gmail = pagina.locator(
                            "#autotube-gmail-safe-overlay"
                        )

                        gmail_sanitizado = (
                            resultado_accion
                            == "gmail_inbox_sanitizado"
                            and overlay_gmail.count() > 0
                            and overlay_gmail.first.is_visible()
                            and pagina.get_attribute(
                                "body",
                                "data-autotube-gmail-sanitized",
                            )
                            == "true"
                        )

                        if not gmail_sanitizado:
                            raise RuntimeError(
                                "Gmail autenticado no paso "
                                "la verificacion de privacidad. "
                                "La captura fue bloqueada antes "
                                "de guardar cualquier screenshot."
                            )

                    # Guard obligatorio para Make + Gmail Watch emails.
                    # Ningun screenshot puede ejecutarse si la
                    # sanitizacion completa no esta confirmada.
                    objetivo_make_gmail = " ".join(
                        str(
                            elemento.get(
                                campo,
                                "",
                            )
                            or ""
                        )
                        for campo in (
                            "pantalla_objetivo",
                            "accion_visual",
                            "texto_narrado",
                            "descripcion_visual",
                        )
                    ).lower()

                    requiere_guard_make_gmail = (
                        plataforma == "make"
                        and requiere_login
                        and "gmail" in objetivo_make_gmail
                        and (
                            "watch emails"
                            in objetivo_make_gmail
                            or "watch email"
                            in objetivo_make_gmail
                        )
                    )

                    if requiere_guard_make_gmail:
                        demo_cuenta = pagina.locator(
                            "#autotube-demo-gmail-account"
                        )

                        demo_etiqueta = pagina.locator(
                            "#autotube-demo-gmail-label"
                        )

                        subject = pagina.locator(
                            'input[name="subject"]'
                        )

                        include_words = pagina.locator(
                            'input[name="includeWords"]'
                        )

                        cuenta_real = pagina.locator(
                            'imt-picker['
                            'placeholder="Choose an account"'
                            ']'
                        )

                        cuenta_real_oculta = False

                        for i in range(
                            cuenta_real.count()
                        ):
                            try:
                                if not cuenta_real.nth(
                                    i
                                ).is_visible():
                                    continue

                                opacidad = (
                                    cuenta_real.nth(
                                        i
                                    ).evaluate(
                                        "(e) => "
                                        "getComputedStyle(e).opacity"
                                    )
                                )

                                if float(opacidad) == 0.0:
                                    cuenta_real_oculta = True
                                    break
                            except Exception:
                                pass

                        asunto_demo_ok = False
                        palabras_demo_ok = False

                        try:
                            asunto_demo_ok = (
                                subject.count() > 0
                                and subject.first.is_visible()
                                and subject.first.input_value()
                                == "Solicitud de presupuesto"
                            )
                        except Exception:
                            pass

                        try:
                            palabras_demo_ok = (
                                include_words.count() > 0
                                and include_words.first.is_visible()
                                and include_words.first.input_value()
                                == "automatizacion IA"
                            )
                        except Exception:
                            pass

                        make_gmail_sanitizado = (
                            resultado_accion
                            == "gmail_watch_config_sanitizado"
                            and pagina.get_attribute(
                                "body",
                                "data-autotube-make-gmail-sanitized",
                            )
                            == "true"
                            and demo_cuenta.count() > 0
                            and demo_cuenta.first.is_visible()
                            and demo_etiqueta.count() > 0
                            and demo_etiqueta.first.is_visible()
                            and cuenta_real_oculta
                            and asunto_demo_ok
                            and palabras_demo_ok
                        )

                        if not make_gmail_sanitizado:
                            raise RuntimeError(
                                "Make/Gmail Watch emails no paso "
                                "la verificacion de privacidad. "
                                "La captura fue bloqueada antes "
                                "de Page.captureScreenshot."
                            )

                    import base64

                    sesion_cdp = contexto.new_cdp_session(pagina)
                    try:
                        captura = sesion_cdp.send(
                            "Page.captureScreenshot",
                            {
                                "format": "png",
                                "fromSurface": True,
                                "captureBeyondViewport": False,
                            },
                        )
                        destino.write_bytes(
                            base64.b64decode(captura["data"])
                        )
                    finally:
                        sesion_cdp.detach()

                    anotaciones_aplicadas = aplicar_anotaciones_tutorial(
                        destino,
                        {
                            **elemento,
                            "plataforma": plataforma,
                        },
                    )


                    elemento["estado"] = (
                        "generado_local"
                    )

                    elemento["fuente"] = (
                        "playwright_web_real"
                    )

                    elemento["archivo"] = str(
                        destino.resolve()
                    )

                    elemento["captura_web"] = {
                        "plataforma": plataforma,
                        "driver": resultado_driver.driver,
                        "navegacion_realizada": resultado_driver.navegacion_realizada,
                        "accion_driver": resultado_accion,
                        "anotaciones": anotaciones_aplicadas,
                        "url": pagina.url,
                        "url_solicitada": url,
                        "pantalla_objetivo": (
                            elemento.get(
                                "pantalla_objetivo",
                                "",
                            )
                        ),
                        "accion_visual": (
                            elemento.get(
                                "accion_visual",
                                "",
                            )
                        ),
                        "interfaz_real": True,
                    }

                    elemento.pop(
                        "error",
                        None,
                    )

                    capturadas += 1

                except Exception as error:
                    elemento["estado"] = (
                        "error"
                    )

                    elemento["error"] = str(
                        error
                    )

                    errores += 1

                    print(
                        "  ERROR:",
                        error,
                    )


        total_pendientes = sum(
            1
            for elemento in elementos
            if isinstance(
                elemento,
                dict,
            )
            and str(
                elemento.get(
                    "estado",
                    "",
                )
            ) == "pendiente_generacion"
        )

        resumen = manifiesto.setdefault(
            "resumen",
            {},
        )

        resumen["capturas_web_reales"] = (
            sum(
                1
                for elemento in elementos
                if isinstance(
                    elemento,
                    dict,
                )
                and elemento.get(
                    "fuente"
                )
                == "playwright_web_real"
            )
        )

        resumen[
            "pendientes_generacion"
        ] = total_pendientes

        resumen["errores"] = sum(
            1
            for elemento in elementos
            if isinstance(
                elemento,
                dict,
            )
            and str(
                elemento.get(
                    "estado",
                    "",
                )
            ) == "error"
        )

        manifiesto[
            "actualizado_en"
        ] = (
            datetime.now()
            .astimezone()
            .isoformat(
                timespec="seconds"
            )
        )

        ruta_manifiesto.write_text(
            json.dumps(
                manifiesto,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return {
            "capturadas": capturadas,
            "errores": errores,
            "pendientes": total_pendientes,
        }



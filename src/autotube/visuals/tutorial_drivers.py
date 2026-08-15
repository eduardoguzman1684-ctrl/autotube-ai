from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class DriverResult:
    pagina: Any
    url_solicitada: str
    navegacion_realizada: bool
    driver: str


class TutorialDriverBase:
    nombre = "generico"
    dominios: tuple[str, ...] = ()

    def _host_valido(self, url: str) -> bool:
        try:
            host = (urlparse(url).hostname or "").lower()
        except Exception:
            return False

        return any(
            host == dominio
            or host.endswith("." + dominio)
            for dominio in self.dominios
        )

    def _pagina_existente(
        self,
        contexto: Any,
    ) -> Any | None:
        for pagina in reversed(
            contexto.pages
        ):
            if self._host_valido(
                pagina.url
            ):
                return pagina

        return None

    def seleccionar_pagina(
        self,
        contexto: Any,
    ) -> Any:
        pagina = self._pagina_existente(
            contexto
        )

        if pagina is not None:
            return pagina

        if contexto.pages:
            return contexto.pages[0]

        return contexto.new_page()

    def debe_conservar_estado(
        self,
        pagina: Any,
        elemento: dict[str, Any],
    ) -> bool:
        return False

    def preparar(
        self,
        contexto: Any,
        elemento: dict[str, Any],
        url_solicitada: str,
    ) -> DriverResult:
        pagina = self.seleccionar_pagina(
            contexto
        )

        if self.debe_conservar_estado(
            pagina,
            elemento,
        ):
            return DriverResult(
                pagina=pagina,
                url_solicitada=url_solicitada,
                navegacion_realizada=False,
                driver=self.nombre,
            )

        if (
            not pagina.url
            or pagina.url
            != url_solicitada
        ):
            pagina.goto(
                url_solicitada,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            pagina.wait_for_timeout(
                1800
            )

            navegacion = True

        else:
            navegacion = False

        return DriverResult(
            pagina=pagina,
            url_solicitada=url_solicitada,
            navegacion_realizada=navegacion,
            driver=self.nombre,
        )


class MakeTutorialDriver(
    TutorialDriverBase
):
    nombre = "make"
    dominios = (
        "make.com",
    )

    _objetivos_estado = (
        "scenario",
        "escenario",
        "editor",
        "module",
        "modulo",
        "history",
        "historial",
        "run once",
        "dashboard",
        "organization",
        "organizacion",
        "gmail",
        "openai",
        "mapping",
        "mapeo",
        "error handler",
    )

    def _pagina_es_404(
        self,
        pagina: Any,
    ) -> bool:
        try:
            texto = pagina.locator(
                "body"
            ).inner_text(
                timeout=3000
            ).lower()

            return (
                "404" in texto
                and "page not found" in texto
            )
        except Exception:
            return False

    def _es_editor_real(
        self,
        pagina: Any,
    ) -> bool:
        try:
            selectores = (
                "canvas.surface",
                "canvas.cursor-grab",
                ".i-designer canvas",
            )

            for selector in selectores:
                locator = pagina.locator(
                    selector
                )

                if (
                    locator.count() > 0
                    and locator.first.is_visible()
                ):
                    return True

            return False
        except Exception:
            return False

    def debe_conservar_estado(
        self,
        pagina: Any,
        elemento: dict[str, Any],
    ) -> bool:
        url_actual = (
            pagina.url or ""
        ).lower()

        if not self._host_valido(
            url_actual
        ):
            return False

        if self._pagina_es_404(
            pagina
        ):
            return False

        if "make.com/en/login" in url_actual:
            return False

        objetivo = " ".join(
            str(elemento.get(clave, ""))
            for clave in (
                "pantalla_objetivo",
                "accion_visual",
                "descripcion_visual",
                "texto_narrado",
            )
        ).lower()

        requiere_login = bool(
            elemento.get(
                "requiere_login",
                False,
            )
        )

        if (
            requiere_login
            and ".make.com"
            in url_actual
        ):
            return True

        return (
            any(
                token in objetivo
                for token in self._objetivos_estado
            )
            and ".make.com"
            in url_actual
        )

    def preparar(
        self,
        contexto: Any,
        elemento: dict[str, Any],
        url: str,
    ) -> DriverResult:
        paginas_app = []

        for candidata in contexto.pages:
            try:
                url_candidata = (
                    candidata.url or ""
                ).lower()

                host_candidato = (
                    urlparse(
                        url_candidata
                    ).hostname
                    or ""
                ).lower()

                if (
                    host_candidato.endswith(
                        ".make.com"
                    )
                    and host_candidato
                    not in (
                        "www.make.com",
                        "make.com",
                    )
                    and "login"
                    not in url_candidata
                ):
                    puntaje = 100

                    if "/organization/" in url_candidata:
                        puntaje += 30

                    if "/dashboard" in url_candidata:
                        puntaje += 20

                    if "/scenarios" in url_candidata:
                        puntaje += 40

                    paginas_app.append(
                        (
                            puntaje,
                            candidata,
                        )
                    )
            except Exception:
                continue

        if paginas_app:
            pagina = max(
                paginas_app,
                key=lambda item: item[0],
            )[1]
        else:
            pagina = self.seleccionar_pagina(
                contexto
            )

        url_actual = (
            pagina.url or ""
        ).lower()

        objetivo = " ".join(
            str(elemento.get(clave, ""))
            for clave in (
                "pantalla_objetivo",
                "accion_visual",
                "descripcion_visual",
                "texto_narrado",
            )
        ).lower()

        requiere_editor = any(
            token in objetivo
            for token in (
                "editor",
                "buscador de m",
                "watch emails",
                "modulo",
                "m?dulo",
                "scenario",
                "escenario",
            )
        )

        if (
            requiere_editor
            and self._host_valido(
                url_actual
            )
            and not self._pagina_es_404(
                pagina
            )
            and self._es_editor_real(
                pagina
            )
        ):
            return DriverResult(
                pagina=pagina,
                url_solicitada=url,
                navegacion_realizada=False,
                driver=self.nombre,
            )

        if (
            requiere_editor
            and (
                self._pagina_es_404(
                    pagina
                )
                or "/scenarios/edit"
                in (url or "").lower()
                or not self._es_editor_real(
                    pagina
                )
            )
        ):
            host = ""

            for candidato in (
                pagina.url or "",
                url or "",
            ):
                try:
                    parsed = urlparse(
                        candidato
                    )

                    if (
                        parsed.hostname
                        and parsed.hostname.endswith(
                            "make.com"
                        )
                    ):
                        host = parsed.netloc
                        break
                except Exception:
                    pass

            if not host:
                host = "us1.make.com"

            url_actual_app = (
                pagina.url or ""
            ).lower()

            host_actual_app = (
                urlparse(
                    url_actual_app
                ).hostname
                or ""
            ).lower()

            ya_en_app = (
                host_actual_app.endswith(
                    ".make.com"
                )
                and host_actual_app
                not in (
                    "www.make.com",
                    "make.com",
                )
                and "login"
                not in url_actual_app
                and not self._pagina_es_404(
                    pagina
                )
            )

            if ya_en_app:
                destino = pagina.url

                pagina.wait_for_timeout(
                    1500
                )
            else:
                destino = f"https://{host}/"

                pagina.goto(
                    destino,
                    wait_until="domcontentloaded",
                    timeout=90000,
                )

                pagina.wait_for_timeout(
                    3500
                )

            if self._pagina_es_404(
                pagina
            ):
                raise RuntimeError(
                    "Make devolvio 404 al "
                    f"abrir {destino}"
                )

            if "login" in (
                pagina.url or ""
            ).lower():
                raise RuntimeError(
                    "La sesion de Make no esta "
                    "iniciada en el navegador tutorial"
                )

            if not self._es_editor_real(
                pagina
            ):
                def click_texto(
                    textos: tuple[str, ...],
                ) -> bool:
                    for texto in textos:
                        try:
                            candidatos = pagina.locator(
                                "button, a, [role='button']"
                            ).filter(
                                has_text=texto
                            )

                            cantidad = min(
                                candidatos.count(),
                                8,
                            )

                            for indice in range(
                                cantidad
                            ):
                                candidato = (
                                    candidatos.nth(
                                        indice
                                    )
                                )

                                if not candidato.is_visible():
                                    continue

                                try:
                                    candidato.click(
                                        timeout=5000
                                    )
                                except Exception:
                                    candidato.evaluate(
                                        "(e) => e.click()"
                                    )

                                return True
                        except Exception:
                            continue

                    return False

                creado = click_texto(
                    (
                        "Create a new scenario",
                        "Create scenario",
                        "New scenario",
                    )
                )

                if not creado:
                    escenarios = click_texto(
                        (
                            "Scenarios",
                            "My scenarios",
                        )
                    )

                    if escenarios:
                        pagina.wait_for_timeout(
                            2200
                        )

                        creado = click_texto(
                            (
                                "Create a new scenario",
                                "Create scenario",
                                "New scenario",
                            )
                        )

                if not creado:
                    raise RuntimeError(
                        "No encontre el boton para "
                        "crear un escenario en Make. "
                        f"URL actual: {pagina.url}"
                    )

                pagina.wait_for_timeout(
                    5000
                )

            if self._pagina_es_404(
                pagina
            ):
                raise RuntimeError(
                    "Make termino en una pagina 404 "
                    "despues de crear el escenario"
                )

            if not self._es_editor_real(
                pagina
            ):
                pagina.wait_for_timeout(
                    4000
                )

            if not self._es_editor_real(
                pagina
            ):
                raise RuntimeError(
                    "Make no mostro un editor real "
                    "despues de crear el escenario. "
                    f"URL actual: {pagina.url}"
                )

            return DriverResult(
                pagina=pagina,
                url_solicitada=url,
                navegacion_realizada=True,
                driver=self.nombre,
            )

        return super().preparar(
            contexto,
            elemento,
            url,
        )

    def _visible(
        self,
        locator: Any,
    ) -> bool:
        try:
            return (
                locator.count() > 0
                and locator.first.is_visible()
            )
        except Exception:
            return False

    def _click_dom(
        self,
        locator: Any,
    ) -> bool:
        try:
            visibles = [
                locator.nth(i)
                for i in range(locator.count())
                if locator.nth(i).is_visible()
            ]

            if not visibles:
                return False

            visibles[0].evaluate(
                "(e)=>e.click()"
            )
            return True
        except Exception:
            return False

    def _abrir_selector_modulos(
        self,
        pagina: Any,
    ) -> bool:
        buscador = pagina.get_by_placeholder(
            "Search all apps or modules"
        )

        detalle = pagina.locator(
            ".app-search-detail-container.show"
        )

        # Si ya esta abierto, conservar el estado.
        if (
            self._visible(buscador)
            or self._visible(detalle)
        ):
            return True

        # Salir de cualquier modo de colocacion,
        # panel temporal o herramienta activa.
        try:
            pagina.keyboard.press("Escape")
            pagina.wait_for_timeout(200)
            pagina.keyboard.press("Escape")
            pagina.wait_for_timeout(300)
        except Exception:
            pass

        canvas = pagina.locator(
            "canvas"
        ).first

        if (
            canvas.count() == 0
            or not canvas.is_visible()
        ):
            return False

        box = canvas.bounding_box()

        if not box:
            return False

        # Zonas libres probadas del lienzo.
        # La primera (82%, 25%) funciona en el
        # editor actual de Make.
        puntos = (
            (0.82, 0.25),
            (0.72, 0.38),
            (0.22, 0.25),
            (0.18, 0.58),
            (0.82, 0.58),
        )

        for rx, ry in puntos:
            x = (
                box["x"]
                + box["width"] * rx
            )

            y = (
                box["y"]
                + box["height"] * ry
            )

            try:
                pagina.mouse.dblclick(
                    x,
                    y,
                    delay=100,
                )

                pagina.wait_for_timeout(
                    750
                )
            except Exception:
                continue

            buscador = (
                pagina.get_by_placeholder(
                    "Search all apps or modules"
                )
            )

            detalle = pagina.locator(
                ".app-search-detail-container.show"
            )

            if (
                self._visible(buscador)
                or self._visible(detalle)
            ):
                return True

            try:
                pagina.keyboard.press(
                    "Escape"
                )
                pagina.wait_for_timeout(
                    200
                )
            except Exception:
                pass

        # Respaldo para variantes de Make que
        # utilicen el boton + inferior.
        pluses = pagina.locator(
            "button:has(i.fa-plus)"
        )

        for i in range(
            pluses.count()
        ):
            boton = pluses.nth(i)

            try:
                if not boton.is_visible():
                    continue

                boton.click(
                    force=True,
                    timeout=3000,
                )

                pagina.wait_for_timeout(
                    700
                )

                buscador = (
                    pagina.get_by_placeholder(
                        "Search all apps or modules"
                    )
                )

                detalle = pagina.locator(
                    ".app-search-detail-container.show"
                )

                if (
                    self._visible(buscador)
                    or self._visible(detalle)
                ):
                    return True

            except Exception:
                pass

        return False

    def _mostrar_gmail_watch(
        self,
        pagina: Any,
    ) -> bool:
        """
        Abre Gmail como primer modulo del escenario.

        Watch emails es un trigger y Make solo lo muestra
        cuando se esta seleccionando el primer modulo.
        """

        def primero_visible(locator):
            for i in range(locator.count()):
                try:
                    if locator.nth(i).is_visible():
                        return locator.nth(i)
                except Exception:
                    pass
            return None

        # Si ya estamos dentro del detalle correcto,
        # no hay que volver a abrir el selector.
        detalle = pagina.locator(
            ".app-search-detail-container.show"
        )

        if self._visible(detalle):
            try:
                contenido = (
                    detalle.first
                    .inner_text(timeout=1200)
                    .lower()
                )

                if (
                    "gmail" in contenido
                    and "watch emails" in contenido
                ):
                    return True
            except Exception:
                pass

        # Cerrar overlays o selectores anteriores.
        try:
            pagina.keyboard.press("Escape")
            pagina.wait_for_timeout(250)
            pagina.keyboard.press("Escape")
            pagina.wait_for_timeout(400)
        except Exception:
            pass

        # Buscar exclusivamente el canvas grande
        # del Scenario Builder.
        box_editor = None

        canvases = pagina.locator("canvas")

        for i in range(canvases.count()):
            try:
                canvas = canvases.nth(i)

                if not canvas.is_visible():
                    continue

                box = canvas.bounding_box()

                if (
                    box
                    and box["width"] > 500
                    and box["height"] > 400
                ):
                    box_editor = box
                    break
            except Exception:
                pass

        if box_editor is None:
            return False

        # Clic SIMPLE en el centro del canvas.
        # Este abre el selector del PRIMER modulo,
        # que incluye triggers como Watch emails.
        x = (
            box_editor["x"]
            + box_editor["width"] * 0.50
        )

        y = (
            box_editor["y"]
            + box_editor["height"] * 0.50
        )

        try:
            pagina.mouse.click(x, y)
            pagina.wait_for_timeout(1800)
        except Exception:
            return False

        buscador = primero_visible(
            pagina.get_by_placeholder(
                "Search all apps or modules"
            )
        )

        if buscador is None:
            return False

        try:
            buscador.click(force=True)
            buscador.fill("")
            buscador.type(
                "Gmail",
                delay=80,
            )
            pagina.wait_for_timeout(2200)
        except Exception:
            return False

        gmail = primero_visible(
            pagina.get_by_text(
                "Gmail",
                exact=True,
            )
        )

        if gmail is None:
            return False

        try:
            gmail.click(
                force=True,
                timeout=5000,
            )
            pagina.wait_for_timeout(1200)
        except Exception:
            return False

        # Verificacion principal.
        watch_texto = primero_visible(
            pagina.get_by_text(
                "Watch emails",
                exact=True,
            )
        )

        if watch_texto is not None:
            return True

        # Verificacion alternativa por el componente
        # interno de Make.
        watch_item = pagina.locator(
            "app-search-detail-item"
        ).filter(
            has_text="Watch emails"
        )

        return (
            primero_visible(watch_item)
            is not None
        )


    def _mostrar_gmail_watch_config(
        self,
        pagina: Any,
    ) -> bool:
        # Abrir Gmail y dejar visible Watch emails.
        if not self._mostrar_gmail_watch(
            pagina
        ):
            return False

        # Seleccionar Watch emails mediante el elemento
        # interactivo real de la interfaz actual de Make.
        watch_item = pagina.locator(
            '[data-testid="app-search-module-item"]'
        ).filter(
            has_text="Watch emails"
        )

        watch_visible = None

        for i in range(watch_item.count()):
            try:
                if watch_item.nth(i).is_visible():
                    watch_visible = watch_item.nth(i)
                    break
            except Exception:
                pass

        # Compatibilidad con versiones anteriores de Make.
        if watch_visible is None:
            watch_item = pagina.locator(
                "app-search-detail-item"
            ).filter(
                has_text="Watch emails"
            )

            for i in range(watch_item.count()):
                try:
                    if watch_item.nth(i).is_visible():
                        watch_visible = watch_item.nth(i)
                        break
                except Exception:
                    pass

        if watch_visible is None:
            return False

        # El input de busqueda puede interceptar clics
        # por coordenadas. Ejecutar click DOM directamente.
        try:
            watch_visible.evaluate(
                "(e) => e.click()"
            )
        except Exception:
            return False
        # Esperar realmente a que Make abra el panel.
        # El DOM click cierra el selector inmediatamente,
        # pero el panel puede tardar varios segundos.
        panel = None

        for _ in range(12):
            pagina.wait_for_timeout(400)

            candidatos = pagina.locator(
                ".i-panel.new-panel.in, "
                ".i-panel.in, "
                ".new-panel.in"
            )

            for i in range(candidatos.count()):
                c = candidatos.nth(i)

                try:
                    if not c.is_visible():
                        continue

                    contenido = (
                        c.inner_text(timeout=700)
                        or ""
                    ).lower()

                    if (
                        "gmail" in contenido
                        and "connection" in contenido
                        and "save" in contenido
                    ):
                        panel = c
                        break
                except Exception:
                    pass

            if panel is not None:
                break

        if panel is None:
            return False

        # Dar tiempo a Make para terminar de
        # inicializar los controles del panel.
        pagina.wait_for_timeout(1800)

        # Abrir Advanced settings y verificar realmente
        # que los campos avanzados hayan quedado visibles.
        subject = panel.locator(
            'input[name="subject"]'
        )

        if not (
            subject.count() > 0
            and subject.first.is_visible()
        ):
            avanzado = panel.locator(
                'label.i-advanced-parameters[role="button"]'
            )

            if avanzado.count() == 0:
                avanzado = panel.get_by_text(
                    "Advanced settings",
                    exact=True,
                )

            control = None

            for i in range(avanzado.count()):
                try:
                    if avanzado.nth(i).is_visible():
                        control = avanzado.nth(i)
                        break
                except Exception:
                    pass

            if control is None:
                return False

            abierto = False

            for intento in range(2):
                try:
                    control.click(
                        force=True,
                        timeout=3000,
                    )
                except Exception:
                    try:
                        control.evaluate(
                            "(e) => e.click()"
                        )
                    except Exception:
                        pass

                for _ in range(16):
                    pagina.wait_for_timeout(250)

                    subject = panel.locator(
                        'input[name="subject"]'
                    )

                    if (
                        subject.count() > 0
                        and subject.first.is_visible()
                    ):
                        abierto = True
                        break

                if abierto:
                    break

            if not abierto:
                return False

        # Vaciar posibles datos reales.
        for nombre in (
            "from",
            "subject",
            "includeWords",
            "excludeWords",
        ):
            campo = panel.locator(
                f'input[name="{nombre}"]'
            )

            if campo.count():
                try:
                    if campo.first.is_visible():
                        campo.first.fill("")
                except Exception:
                    pass

        # Contenido ficticio del tutorial.
        subject = panel.locator(
            'input[name="subject"]'
        )

        if subject.count():
            try:
                if subject.first.is_visible():
                    subject.first.fill(
                        "Solicitud de presupuesto"
                    )
            except Exception:
                pass

        include_words = panel.locator(
            'input[name="includeWords"]'
        )

        if include_words.count():
            try:
                if include_words.first.is_visible():
                    include_words.first.fill(
                        "automatizacion IA"
                    )
            except Exception:
                pass

        # Ocultar visualmente la conexion Gmail real.
        cuenta = panel.locator(
            'imt-picker[placeholder="Choose an account"]'
        )

        if cuenta.count() == 0:
            return False

        resultado = panel.evaluate(r"""
        (root) => {
            const ACCOUNT_ID =
                "autotube-demo-gmail-account";

            const LABEL_ID =
                "autotube-demo-gmail-label";

            root.querySelector(
                "#" + ACCOUNT_ID
            )?.remove();

            root.querySelector(
                "#" + LABEL_ID
            )?.remove();

            const account =
                root.querySelector(
                    'imt-picker[placeholder="Choose an account"]'
                );

            if (!account) {
                return {
                    ok: false,
                    motivo: "account_no_encontrado"
                };
            }

            /*
             * El contenido real de la conexion queda
             * completamente invisible antes del screenshot.
             */
            account.style.opacity = "0";
            account.style.pointerEvents = "none";

            const demo =
                document.createElement("div");

            demo.id = ACCOUNT_ID;
            demo.textContent =
                "Conexion Gmail de demostracion";

            Object.assign(
                demo.style,
                {
                    minHeight: "36px",
                    marginTop: "-38px",
                    marginBottom: "8px",
                    padding: "0 12px",
                    display: "flex",
                    alignItems: "center",
                    boxSizing: "border-box",
                    border: "1px solid #b8b8b8",
                    borderRadius: "6px",
                    background: "#ffffff",
                    color: "#333333",
                    fontSize: "13px",
                    position: "relative",
                    zIndex: "100"
                }
            );

            account.insertAdjacentElement(
                "afterend",
                demo
            );

            /*
             * Eliminar cualquier correo visible que Make
             * pudiera haber renderizado fuera del picker.
             */
            const walker =
                document.createTreeWalker(
                    root,
                    NodeFilter.SHOW_TEXT
                );

            const nodos = [];

            while (walker.nextNode()) {
                nodos.push(
                    walker.currentNode
                );
            }

            for (const nodo of nodos) {
                const valor =
                    nodo.nodeValue || "";

                if (valor.includes("@")) {
                    nodo.nodeValue =
                        "Cuenta Gmail de demostracion";
                }
            }

            root.querySelectorAll(
                "[aria-label], [title], [data-tooltip]"
            ).forEach(el => {
                for (
                    const attr
                    of [
                        "aria-label",
                        "title",
                        "data-tooltip"
                    ]
                ) {
                    const valor =
                        el.getAttribute(attr);

                    if (
                        valor
                        && valor.includes("@")
                    ) {
                        el.setAttribute(
                            attr,
                            "Cuenta Gmail de demostracion"
                        );
                    }
                }
            });

            /*
             * No seleccionamos una etiqueta real.
             * Mostramos una etiqueta ficticia.
             */
            const label =
                root.querySelector(
                    'imt-input-select[name="labelIds"]'
                );

            if (label) {
                const demoLabel =
                    document.createElement("div");

                demoLabel.id = LABEL_ID;
                demoLabel.textContent =
                    "Etiqueta demo: Automatizacion";

                Object.assign(
                    demoLabel.style,
                    {
                        marginTop: "6px",
                        marginBottom: "8px",
                        padding: "7px 10px",
                        border: "1px solid #c7c7c7",
                        borderRadius: "6px",
                        background: "#ffffff",
                        color: "#333333",
                        fontSize: "12px",
                        position: "sticky",
                        top: "12px",
                        zIndex: "500",
                        boxShadow: "0 2px 8px rgba(0,0,0,.12)"
                    }
                );

                label.insertAdjacentElement(
                    "afterend",
                    demoLabel
                );
            }

            root.setAttribute(
                "data-autotube-sanitized",
                "true"
            );

            document.body.setAttribute(
                "data-autotube-make-gmail-sanitized",
                "true"
            );

            return {
                ok: true
            };
        }
        """)

        if not resultado:
            return False

        if not resultado.get("ok", False):
            return False

        # Make puede volver a renderizar el panel
        # algunos milisegundos despues. Mantener activa
        # la sanitizacion hasta que se tome el screenshot.
        pagina.evaluate(r"""
        () => {
            if (
                window.__autotubeMakeGmailObserver
            ) {
                try {
                    window
                        .__autotubeMakeGmailObserver
                        .disconnect();
                } catch (_) {}
            }

            let programado = false;
            let ejecutando = false;

            const visible = (el) => {
                if (!el) {
                    return false;
                }

                const r =
                    el.getBoundingClientRect();

                const s =
                    getComputedStyle(el);

                return (
                    r.width > 0
                    && r.height > 0
                    && s.display !== "none"
                    && s.visibility !== "hidden"
                );
            };

            const buscarPanel = () => {
                const candidatos = [
                    ...document.querySelectorAll(
                        ".i-panel.new-panel.in, "
                        + ".i-panel.in, "
                        + ".new-panel.in"
                    )
                ];

                return candidatos.find(el => {
                    if (!visible(el)) {
                        return false;
                    }

                    const t =
                        (el.innerText || "")
                        .toLowerCase();

                    return (
                        t.includes("gmail")
                        && t.includes("connection")
                        && t.includes("save")
                    );
                }) || null;
            };

            const ponerValor = (
                input,
                valor
            ) => {
                if (!input) {
                    return;
                }

                if (input.value === valor) {
                    return;
                }

                const descriptor =
                    Object.getOwnPropertyDescriptor(
                        HTMLInputElement.prototype,
                        "value"
                    );

                if (
                    descriptor
                    && descriptor.set
                ) {
                    descriptor.set.call(
                        input,
                        valor
                    );
                } else {
                    input.value = valor;
                }

                input.dispatchEvent(
                    new Event(
                        "input",
                        {
                            bubbles: true
                        }
                    )
                );

                input.dispatchEvent(
                    new Event(
                        "change",
                        {
                            bubbles: true
                        }
                    )
                );
            };

            const sanitizar = () => {
                if (ejecutando) {
                    return;
                }

                ejecutando = true;

                try {
                    const panel =
                        buscarPanel();

                    if (!panel) {
                        return;
                    }

                    let subject =
                        panel.querySelector(
                            'input[name="subject"]'
                        );

                    /*
                     * Si Make reconstruyo el panel y
                     * cerro Advanced settings, volver
                     * a abrirlo mediante DOM click.
                     */
                    if (
                        !subject
                        || !visible(subject)
                    ) {
                        const avanzado =
                            panel.querySelector(
                                'label.'
                                + 'i-advanced-parameters'
                                + '[role="button"]'
                            );

                        if (
                            avanzado
                            && visible(avanzado)
                        ) {
                            avanzado.click();
                        }

                        return;
                    }

                    const from =
                        panel.querySelector(
                            'input[name="from"]'
                        );

                    const includeWords =
                        panel.querySelector(
                            'input[name="includeWords"]'
                        );

                    const excludeWords =
                        panel.querySelector(
                            'input[name="excludeWords"]'
                        );

                    ponerValor(
                        from,
                        ""
                    );

                    ponerValor(
                        subject,
                        "Solicitud de presupuesto"
                    );

                    ponerValor(
                        includeWords,
                        "automatizacion IA"
                    );

                    ponerValor(
                        excludeWords,
                        ""
                    );

                    const account =
                        panel.querySelector(
                            'imt-picker['
                            + 'placeholder='
                            + '"Choose an account"'
                            + ']'
                        );

                    if (!account) {
                        return;
                    }

                    account.style.setProperty(
                        "opacity",
                        "0",
                        "important"
                    );

                    account.style.setProperty(
                        "pointer-events",
                        "none",
                        "important"
                    );

                    let demo =
                        document.querySelector(
                            "#autotube-demo-gmail-account"
                        );

                    if (!demo) {
                        demo =
                            document.createElement(
                                "div"
                            );

                        demo.id =
                            "autotube-demo-gmail-account";

                        account.insertAdjacentElement(
                            "afterend",
                            demo
                        );
                    }

                    demo.textContent =
                        "Conexion Gmail de demostracion";

                    Object.assign(
                        demo.style,
                        {
                            minHeight: "36px",
                            marginTop: "-38px",
                            marginBottom: "8px",
                            padding: "0 12px",
                            display: "flex",
                            alignItems: "center",
                            boxSizing: "border-box",
                            border:
                                "1px solid #b8b8b8",
                            borderRadius: "6px",
                            background: "#ffffff",
                            color: "#333333",
                            fontSize: "13px",
                            position: "relative",
                            zIndex: "100"
                        }
                    );

                    const label =
                        panel.querySelector(
                            'imt-input-select['
                            + 'name="labelIds"'
                            + ']'
                        );

                    if (label) {
                        let demoLabel =
                            document.querySelector(
                                "#autotube-demo-gmail-label"
                            );

                        if (!demoLabel) {
                            demoLabel =
                                document.createElement(
                                    "div"
                                );

                            demoLabel.id =
                                "autotube-demo-gmail-label";

                            label.insertAdjacentElement(
                                "afterend",
                                demoLabel
                            );
                        }

                        demoLabel.textContent =
                            "Etiqueta demo: Automatizacion";

                        Object.assign(
                            demoLabel.style,
                            {
                                marginTop: "6px",
                                padding: "7px 10px",
                                border:
                                    "1px solid #c7c7c7",
                                borderRadius: "6px",
                                background: "#ffffff",
                                color: "#333333",
                                fontSize: "12px"
                            }
                        );
                    }

                    /*
                     * Eliminar cualquier correo que
                     * Make vuelva a renderizar.
                     */
                    const walker =
                        document.createTreeWalker(
                            panel,
                            NodeFilter.SHOW_TEXT
                        );

                    const nodos = [];

                    while (
                        walker.nextNode()
                    ) {
                        nodos.push(
                            walker.currentNode
                        );
                    }

                    for (
                        const nodo
                        of nodos
                    ) {
                        const valor =
                            nodo.nodeValue || "";

                        if (
                            valor.includes("@")
                        ) {
                            nodo.nodeValue =
                                "Cuenta Gmail "
                                + "de demostracion";
                        }
                    }

                    panel.querySelectorAll(
                        "[aria-label], "
                        + "[title], "
                        + "[data-tooltip]"
                    ).forEach(el => {
                        for (
                            const attr
                            of [
                                "aria-label",
                                "title",
                                "data-tooltip"
                            ]
                        ) {
                            const valor =
                                el.getAttribute(
                                    attr
                                );

                            if (
                                valor
                                && valor.includes("@")
                            ) {
                                el.setAttribute(
                                    attr,
                                    "Cuenta Gmail "
                                    + "de demostracion"
                                );
                            }
                        }
                    });

                    panel.setAttribute(
                        "data-autotube-sanitized",
                        "true"
                    );

                    document.body.setAttribute(
                        "data-autotube-make-"
                        + "gmail-sanitized",
                        "true"
                    );
                } finally {
                    ejecutando = false;
                }
            };

            const programar = () => {
                if (programado) {
                    return;
                }

                programado = true;

                setTimeout(
                    () => {
                        programado = false;
                        sanitizar();
                    },
                    80
                );
            };

            window.__autotubeMakeGmailSanitize =
                sanitizar;

            window.__autotubeMakeGmailObserver =
                new MutationObserver(
                    programar
                );

            window
                .__autotubeMakeGmailObserver
                .observe(
                    document.body,
                    {
                        childList: true,
                        subtree: true
                    }
                );

            sanitizar();
        }
        """)

        # Dar oportunidad a Make de hacer sus
        # re-renderizados y al observador de reparar
        # nuevamente la vista segura.
        pagina.wait_for_timeout(1800)

        try:
            pagina.evaluate(
                "() => "
                "window.__autotubeMakeGmailSanitize"
                "?.()"
            )
        except Exception:
            pass

        pagina.wait_for_timeout(350)

        marca = pagina.get_attribute(
            "body",
            "data-autotube-make-gmail-sanitized",
        )

        demo = pagina.locator(
            "#autotube-demo-gmail-account"
        )

        demo_label = pagina.locator(
            "#autotube-demo-gmail-label"
        )

        subject_final = pagina.locator(
            'input[name="subject"]'
        )

        words_final = pagina.locator(
            'input[name="includeWords"]'
        )

        cuenta_final = pagina.locator(
            'imt-picker['
            'placeholder="Choose an account"'
            ']'
        )

        cuenta_oculta = False

        for i in range(
            cuenta_final.count()
        ):
            try:
                opacidad = (
                    cuenta_final.nth(i).evaluate(
                        "(e) => "
                        "getComputedStyle(e).opacity"
                    )
                )

                if float(opacidad) == 0.0:
                    cuenta_oculta = True
                    break
            except Exception:
                pass

        asunto_ok = False
        palabras_ok = False

        try:
            asunto_ok = (
                subject_final.count() > 0
                and subject_final.first.is_visible()
                and subject_final.first.input_value()
                == "Solicitud de presupuesto"
            )
        except Exception:
            pass

        try:
            palabras_ok = (
                words_final.count() > 0
                and words_final.first.is_visible()
                and words_final.first.input_value()
                == "automatizacion IA"
            )
        except Exception:
            pass

        return (
            marca == "true"
            and demo.count() > 0
            and demo.first.is_visible()
            and demo_label.count() > 0
            and demo_label.first.is_visible()
            and cuenta_oculta
            and asunto_ok
            and palabras_ok
        )


    def _mostrar_openai_app(
        self,
        pagina: Any,
    ) -> bool:
        detalle = pagina.locator(
            ".app-search-detail-container.show"
        )

        if self._visible(detalle):
            try:
                contenido = (
                    detalle.first
                    .inner_text(timeout=1500)
                    .lower()
                )

                if (
                    "openai" in contenido
                    and (
                        "generate a completion" in contenido
                        or "chatgpt" in contenido
                        or "whisper" in contenido
                        or "sora" in contenido
                    )
                ):
                    return True
            except Exception:
                pass

        buscador = pagina.get_by_placeholder(
            "Search all apps or modules"
        )

        if not self._visible(buscador):
            todas = pagina.get_by_text(
                "All apps",
                exact=True,
            )

            self._click_dom(todas)
            pagina.wait_for_timeout(250)

            buscador = pagina.get_by_placeholder(
                "Search all apps or modules"
            )

        if not self._visible(buscador):
            if not self._abrir_selector_modulos(
                pagina
            ):
                return False

            pagina.wait_for_timeout(300)

            buscador = pagina.get_by_placeholder(
                "Search all apps or modules"
            )

        if not self._visible(buscador):
            return False

        todas = pagina.get_by_text(
            "All apps",
            exact=True,
        )
        self._click_dom(todas)

        pagina.wait_for_timeout(250)

        buscador.first.fill("OpenAI")
        pagina.wait_for_timeout(800)

        oficial = pagina.get_by_text(
            "OpenAI (ChatGPT, Sora, Whisper)",
            exact=True,
        )

        if not self._click_dom(oficial):
            alternativas = pagina.get_by_text(
                "OpenAI",
                exact=True,
            )

            if not self._click_dom(alternativas):
                return False

        pagina.wait_for_timeout(800)

        detalle = pagina.locator(
            ".app-search-detail-container.show"
        )

        if not self._visible(detalle):
            return False

        try:
            contenido = (
                detalle.first
                .inner_text(timeout=2000)
                .lower()
            )
        except Exception:
            return False

        return (
            "openai" in contenido
            and (
                "generate a completion" in contenido
                or "chatgpt" in contenido
                or "whisper" in contenido
                or "sora" in contenido
            )
        )


    def _abrir_panel_openai_completion(
        self,
        pagina: Any,
    ) -> Any | None:
        """Abre Generate a completion y devuelve
        el panel real de OpenAI.

        En Make, cuando OpenAI es un modulo posterior
        al primero, seleccionar el modulo entra en modo
        de colocacion. Es necesario colocarlo en el
        canvas antes de que aparezca su panel.
        """

        def buscar_panel() -> Any | None:
            candidatos = pagina.locator(
                ".i-panel.new-panel.in, "
                ".i-panel.in, "
                ".new-panel.in"
            )

            for i in range(
                candidatos.count()
            ):
                try:
                    panel = candidatos.nth(i)

                    if not panel.is_visible():
                        continue

                    contenido = (
                        panel.inner_text(
                            timeout=600
                        )
                        or ""
                    ).lower()

                    if (
                        "openai" in contenido
                        and "connection" in contenido
                        and "select method" in contenido
                    ):
                        return panel

                except Exception:
                    pass

            return None

        # Si ya esta abierto, reutilizarlo.
        panel = buscar_panel()

        if panel is not None:
            return panel

        if not self._mostrar_openai_app(
            pagina
        ):
            return None

        # Usar el elemento interactivo real.
        items = pagina.locator(
            '[data-testid="app-search-module-item"]'
        ).filter(
            has_text="Generate a completion"
        )

        item = None

        for i in range(
            items.count()
        ):
            try:
                if items.nth(i).is_visible():
                    item = items.nth(i)
                    break
            except Exception:
                pass

        # Compatibilidad con interfaces anteriores.
        if item is None:
            anteriores = pagina.get_by_text(
                "Generate a completion",
                exact=True,
            )

            for i in range(
                anteriores.count()
            ):
                try:
                    if anteriores.nth(i).is_visible():
                        item = anteriores.nth(i)
                        break
                except Exception:
                    pass

        if item is None:
            return None

        try:
            item.evaluate(
                "(e) => e.click()"
            )
        except Exception:
            return None

        # A veces Make abre directamente el panel.
        for _ in range(5):
            pagina.wait_for_timeout(400)

            panel = buscar_panel()

            if panel is not None:
                return panel

        # Si no aparecio, estamos en modo de
        # colocacion del segundo modulo.
        canvas = None
        box = None

        canvases = pagina.locator(
            "canvas"
        )

        for i in range(
            canvases.count()
        ):
            try:
                candidato = canvases.nth(i)

                if not candidato.is_visible():
                    continue

                candidato_box = (
                    candidato.bounding_box()
                )

                if (
                    candidato_box
                    and candidato_box["width"] > 500
                    and candidato_box["height"] > 400
                ):
                    canvas = candidato
                    box = candidato_box
                    break

            except Exception:
                pass

        if canvas is None or box is None:
            return None

        # Zona libre validada en el editor actual.
        x = (
            box["x"]
            + box["width"] * 0.72
        )

        y = (
            box["y"]
            + box["height"] * 0.38
        )

        try:
            pagina.mouse.click(
                x,
                y
            )
        except Exception:
            return None

        # Esperar realmente la apertura del panel.
        for _ in range(15):
            pagina.wait_for_timeout(400)

            panel = buscar_panel()

            if panel is not None:
                return panel

        return None

    def _seleccionar_modelo_openai_sol(
        self,
        pagina: Any,
        panel: Any,
    ) -> bool:
        """Selecciona gpt-5.6-sol de forma robusta."""

        modelo = panel.locator(
            'imt-input-select[name="model"]'
        )

        if modelo.count() == 0:
            return False

        modelo = modelo.first

        picker = modelo.locator(
            "imt-picker"
        )

        if picker.count() == 0:
            return False

        picker = picker.first

        # Make puede devolver temporalmente error 522
        # al cargar la lista de modelos.
        try:
            contenido = (
                modelo.inner_text(
                    timeout=1000
                )
                or ""
            )
        except Exception:
            contenido = ""

        if (
            "522" in contenido
            or "Failed to load data"
            in contenido
        ):
            reload_btn = modelo.locator(
                "button.reload"
            )

            if reload_btn.count() == 0:
                return False

            try:
                reload_btn.first.evaluate(
                    "(e) => e.click()"
                )
            except Exception:
                return False

            recuperado = False

            for _ in range(30):
                pagina.wait_for_timeout(500)

                try:
                    contenido = (
                        modelo.inner_text(
                            timeout=700
                        )
                        or ""
                    )

                    clase = (
                        picker.get_attribute(
                            "class"
                        )
                        or ""
                    )

                    if (
                        "522" not in contenido
                        and "Failed to load data"
                        not in contenido
                        and "loading"
                        not in clase.lower()
                        and picker.is_visible()
                    ):
                        recuperado = True
                        break
                except Exception:
                    pass

            if not recuperado:
                return False

        # Esperar hasta que el picker sea realmente
        # visible y tenga coordenadas utilizables.
        box = None

        for _ in range(20):
            try:
                if picker.is_visible():
                    box = picker.bounding_box()

                    if box:
                        break
            except Exception:
                pass

            pagina.wait_for_timeout(250)

        if not box:
            return False

        # IMPORTANTE:
        # En la interfaz actual de Make, e.click()
        # NO abre el selector Model. Requiere clic
        # fisico sobre el picker.
        x = (
            box["x"]
            + box["width"] / 2
        )

        y = (
            box["y"]
            + box["height"] / 2
        )

        try:
            pagina.mouse.click(
                x,
                y
            )
        except Exception:
            return False

        # Esperar las opciones visibles.
        objetivo = None

        for _ in range(12):
            pagina.wait_for_timeout(250)

            opciones = pagina.locator(
                "imt-option"
            )

            for i in range(
                opciones.count()
            ):
                try:
                    opcion = opciones.nth(i)

                    if not opcion.is_visible():
                        continue

                    contenido_opcion = (
                        opcion.inner_text(
                            timeout=300
                        )
                        or ""
                    ).lower()

                    if (
                        "gpt-5.6-sol"
                        in contenido_opcion
                    ):
                        objetivo = opcion
                        break

                except Exception:
                    pass

            if objetivo is not None:
                break

        if objetivo is None:
            try:
                pagina.keyboard.press(
                    "Escape"
                )
            except Exception:
                pass

            return False

        # Una vez abierta la lista, el DOM click
        # sobre la opcion funciona correctamente.
        try:
            objetivo.evaluate(
                "(e) => e.click()"
            )
        except Exception:
            return False

        pagina.wait_for_timeout(
            1800
        )

        # La seleccion correcta debe provocar la
        # aparicion del bloque Messages.
        messages = panel.locator(
            'imt-input-array[name="messages"]'
        )

        for _ in range(12):
            try:
                if (
                    messages.count() > 0
                    and messages.first.is_visible()
                ):
                    return True
            except Exception:
                pass

            pagina.wait_for_timeout(
                250
            )

        return False

    def _mostrar_modal_conexion_openai(
        self,
        pagina: Any,
    ) -> bool:
        api_key = pagina.locator(
            'input[name="apiKey"]'
        )

        # Si el formulario de nueva conexion ya esta abierto,
        # aseguramos que nunca quede una clave escrita.
        if self._visible(api_key):
            try:
                api_key.first.fill("")
            except Exception:
                pass

            return True

        panel = pagina.locator(
            ".i-panel.new-panel.in.i-panel-forman"
        ).filter(
            has_text="OpenAI (ChatGPT, Sora, Whisper)"
        )

        # Si todavia no esta abierto el modulo OpenAI,
        # lo abrimos desde el selector.
        if not self._visible(panel):
            if not self._mostrar_openai_app(
                pagina
            ):
                return False

            modulo = pagina.get_by_text(
                "Generate a completion",
                exact=True,
            )

            if not self._click_dom(
                modulo
            ):
                return False

            pagina.wait_for_timeout(
                900
            )

            panel = pagina.locator(
                ".i-panel.new-panel.in.i-panel-forman"
            ).filter(
                has_text="OpenAI (ChatGPT, Sora, Whisper)"
            )

        if not self._visible(panel):
            return False

        add = panel.locator(
            "button.btn.btn-outline-secondary"
        ).filter(
            has_text="Add"
        )

        if not self._visible(add):
            return False

        try:
            add.first.click(
                force=True,
                timeout=5000,
            )
        except Exception:
            if not self._click_dom(
                add
            ):
                return False

        pagina.wait_for_timeout(
            900
        )

        api_key = pagina.locator(
            'input[name="apiKey"]'
        )

        if not self._visible(api_key):
            return False

        # Seguridad: el capturador nunca conserva
        # contenido dentro del campo API Key.
        try:
            api_key.first.fill("")
        except Exception:
            pass

        return True

    def ejecutar_accion(
        self,
        pagina: Any,
        elemento: dict[str, Any],
    ) -> str:
        texto = " ".join(
            str(elemento.get(clave, ""))
            for clave in (
                "pantalla_objetivo",
                "accion_visual",
                "descripcion_visual",
                "texto_narrado",
            )
        ).lower()

        texto_normalizado = "".join(
            caracter
            for caracter in unicodedata.normalize(
                "NFKD",
                texto,
            )
            if not unicodedata.combining(
                caracter
            )
        )

        es_modal_conexion_openai = (
            "openai" in texto_normalizado
            and (
                "modal de conexion"
                in texto_normalizado
                or "nueva conexion"
                in texto_normalizado
                or "campo api key"
                in texto_normalizado
                or "api key vacio"
                in texto_normalizado
                or "api key vacio o enmascarado"
                in texto_normalizado
            )
        )

        if es_modal_conexion_openai:
            if self._mostrar_modal_conexion_openai(
                pagina
            ):
                return (
                    "modal_conexion_openai_seguro"
                )

            return (
                "modal_conexion_openai_no_abierto"
            )

        es_openai = (
            "openai" in texto_normalizado
            and (
                "buscador de modulos"
                in texto_normalizado
                or "seleccionar la app oficial"
                in texto_normalizado
                or "buscar openai"
                in texto_normalizado
            )
        )

        if es_openai:
            if self._mostrar_openai_app(
                pagina
            ):
                return "selector_openai_app"

            return "selector_make_no_abierto"

        es_gmail_config = (
            "gmail" in texto_normalizado
            and (
                "panel de configuracion"
                in texto_normalizado
                or "etiqueta de busqueda"
                in texto_normalizado
                or "agregar la etiqueta"
                in texto_normalizado
                or (
                    "watch emails"
                    in texto_normalizado
                    and "label"
                    in texto_normalizado
                )
            )
        )

        if es_gmail_config:
            if self._mostrar_gmail_watch_config(
                pagina
            ):
                return (
                    "gmail_watch_config_sanitizado"
                )

            return (
                "gmail_watch_config_no_abierto"
            )

        es_gmail = (
            "gmail" in texto_normalizado
            or "watch emails"
            in texto_normalizado
            or "modulos disparadores"
            in texto_normalizado
        )

        if es_gmail:
            if self._mostrar_gmail_watch(
                pagina
            ):
                return (
                    "selector_gmail_watch_emails"
                )

            return "selector_make_no_abierto"

        return "sin_accion_especifica"

class ChatGPTTutorialDriver(
    TutorialDriverBase
):
    nombre = "chatgpt"
    dominios = (
        "chatgpt.com",
    )


class OpenAITutorialDriver(
    TutorialDriverBase
):
    nombre = "openai"

    dominios = (
        "platform.openai.com",
        "openai.com",
    )

    def _pagina_autenticada(
        self,
        pagina: Any,
    ) -> bool:
        try:
            url = (
                pagina.url or ""
            ).lower()

            host = (
                urlparse(
                    url
                ).hostname
                or ""
            ).lower()

            return (
                host
                == "platform.openai.com"
                and "/login"
                not in url
                and "/signup"
                not in url
            )
        except Exception:
            return False

    def seleccionar_pagina(
        self,
        contexto: Any,
    ) -> Any:
        autenticadas = []

        for pagina in contexto.pages:
            if not self._pagina_autenticada(
                pagina
            ):
                continue

            url = (
                pagina.url or ""
            ).lower()

            puntaje = 100

            if "/home" in url:
                puntaje += 40

            if "/api-keys" in url:
                puntaje += 30

            if "/settings" in url:
                puntaje += 20

            autenticadas.append(
                (
                    puntaje,
                    pagina,
                )
            )

        if autenticadas:
            return max(
                autenticadas,
                key=lambda item: item[0],
            )[1]

        return super().seleccionar_pagina(
            contexto
        )

    def debe_conservar_estado(
        self,
        pagina: Any,
        elemento: dict[str, Any],
    ) -> bool:
        return self._pagina_autenticada(
            pagina
        )

    def preparar(
        self,
        contexto: Any,
        elemento: dict[str, Any],
        url: str,
    ) -> DriverResult:
        pagina = self.seleccionar_pagina(
            contexto
        )

        destino = (
            url or ""
        ).strip()

        destino_lower = destino.lower()

        if (
            not destino
            or "/login"
            in destino_lower
            or "/signup"
            in destino_lower
        ):
            destino = (
                "https://platform.openai.com/home"
            )

        actual = (
            pagina.url or ""
        ).rstrip("/")

        destino_normalizado = (
            destino.rstrip("/")
        )

        if (
            self._pagina_autenticada(
                pagina
            )
            and actual
            == destino_normalizado
        ):
            return DriverResult(
                pagina=pagina,
                url_solicitada=url,
                navegacion_realizada=False,
                driver=self.nombre,
            )

        pagina.goto(
            destino,
            wait_until="domcontentloaded",
            timeout=90000,
        )

        pagina.wait_for_timeout(
            2500
        )

        final = (
            pagina.url or ""
        ).lower()

        if (
            "/login" in final
            or "/signup" in final
        ):
            raise RuntimeError(
                "La sesion de OpenAI no esta "
                "iniciada en el navegador tutorial"
            )

        return DriverResult(
            pagina=pagina,
            url_solicitada=url,
            navegacion_realizada=True,
            driver=self.nombre,
        )


    def _mostrar_billing_seguro(
        self,
        pagina: Any,
    ) -> bool:
        destino = (
            "https://platform.openai.com/"
            "settings/organization/billing/overview"
        )

        if (
            pagina.url or ""
        ).rstrip("/") != destino.rstrip("/"):
            pagina.goto(
                destino,
                wait_until="domcontentloaded",
                timeout=90000,
            )

            pagina.wait_for_timeout(
                2200
            )

        final = (
            pagina.url or ""
        ).lower()

        if (
            "/login" in final
            or "/signup" in final
        ):
            return False

        # Redactor temporal para la captura del tutorial.
        # No modifica ningun dato de la cuenta.
        pagina.evaluate(r"""
        () => {
            const redactar = () => {
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT
                );

                const nodos = [];

                while (walker.nextNode()) {
                    nodos.push(walker.currentNode);
                }

                for (const nodo of nodos) {
                    const original = nodo.nodeValue || "";
                    let texto = original;

                    // Importes monetarios.
                    texto = texto.replace(
                        /[$??]\s*\d[\d,.]*/g,
                        "????"
                    );

                    // Correos electronicos.
                    texto = texto.replace(
                        /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi,
                        "????@????"
                    );

                    // Numeros de tarjeta parcialmente visibles.
                    texto = texto.replace(
                        /(?:visa|mastercard|amex|card)?\s*(?:\*|x|\u2022){2,}\s*\d{2,4}/gi,
                        "???? ????"
                    );

                    texto = texto.replace(
                        /ending\s+in\s+\d{2,4}/gi,
                        "ending in ????"
                    );

                    if (texto !== original) {
                        nodo.nodeValue = texto;
                    }
                }

                document.querySelectorAll("input").forEach(
                    input => {
                        const nombre = (
                            (input.name || "") + " " +
                            (input.id || "") + " " +
                            (input.getAttribute("aria-label") || "")
                        ).toLowerCase();

                        if (
                            nombre.includes("card") ||
                            nombre.includes("payment") ||
                            nombre.includes("address") ||
                            nombre.includes("email")
                        ) {
                            try {
                                input.value = "";
                            } catch (_) {}
                        }
                    }
                );
            };

            redactar();

            if (!window.__autotubeBillingRedactor) {
                window.__autotubeBillingRedactor =
                    new MutationObserver(() => {
                        redactar();
                    });

                window.__autotubeBillingRedactor.observe(
                    document.body,
                    {
                        childList: true,
                        subtree: true,
                        characterData: true
                    }
                );
            }

            return true;
        }
        """)

        pagina.wait_for_timeout(
            500
        )

        return (
            "/settings/organization/billing"
            in (pagina.url or "").lower()
        )

    def ejecutar_accion(
        self,
        pagina: Any,
        elemento: dict[str, Any],
    ) -> str:
        texto = " ".join(
            str(elemento.get(clave, ""))
            for clave in (
                "pantalla_objetivo",
                "accion_visual",
                "descripcion_visual",
                "texto_narrado",
            )
        ).lower()

        texto_normalizado = "".join(
            caracter
            for caracter in unicodedata.normalize(
                "NFKD",
                texto,
            )
            if not unicodedata.combining(
                caracter
            )
        )

        es_billing = (
            "billing" in texto_normalizado
            or "facturacion" in texto_normalizado
            or "saldo disponible" in texto_normalizado
            or "creditos activos" in texto_normalizado
        )

        if es_billing:
            if self._mostrar_billing_seguro(
                pagina
            ):
                return (
                    "billing_openai_sanitizado"
                )

            return (
                "billing_openai_no_abierto"
            )

        return "sin_accion_especifica"


class GmailTutorialDriver(
    TutorialDriverBase
):
    nombre = "gmail"

    dominios = (
        "mail.google.com",
    )

    def _sanitizar_inbox(
        self,
        pagina: Any,
    ) -> bool:
        url = (
            pagina.url or ""
        ).lower()

        if "mail.google.com" not in url:
            return False

        resultado = pagina.evaluate(r"""
        () => {
            const ID = "autotube-gmail-safe-overlay";

            const anterior =
                document.getElementById(ID);

            if (anterior) {
                anterior.remove();
            }

            const main =
                document.querySelector(
                    '[role="main"]'
                );

            if (!main) {
                return {
                    ok: false,
                    motivo: "main_no_encontrado"
                };
            }

            const rect =
                main.getBoundingClientRect();

            if (
                rect.width < 250 ||
                rect.height < 180
            ) {
                return {
                    ok: false,
                    motivo: "main_no_visible"
                };
            }

            /*
             * Elimina correos visibles fuera del inbox,
             * por ejemplo en botones/cuenta superior.
             */
            const walker =
                document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT
                );

            const nodos = [];

            while (walker.nextNode()) {
                nodos.push(
                    walker.currentNode
                );
            }

            for (const nodo of nodos) {
                const valor =
                    nodo.nodeValue || "";

                if (
                    valor.includes("@")
                    && !nodo.parentElement?.closest(
                        "#" + ID
                    )
                ) {
                    nodo.nodeValue =
                        "cuenta-demo";
                }
            }

            /*
             * Limpia atributos que puedan revelar
             * correo o datos de la cuenta.
             */
            document
                .querySelectorAll(
                    "[aria-label], [title], [data-tooltip]"
                )
                .forEach(el => {
                    for (
                        const atributo
                        of [
                            "aria-label",
                            "title",
                            "data-tooltip"
                        ]
                    ) {
                        const valor =
                            el.getAttribute(
                                atributo
                            );

                        if (
                            valor
                            && (
                                valor.includes("@")
                                || valor.toLowerCase()
                                    .includes(
                                        "google account"
                                    )
                                || valor.toLowerCase()
                                    .includes(
                                        "cuenta de google"
                                    )
                            )
                        ) {
                            el.setAttribute(
                                atributo,
                                "Cuenta de demostracion"
                            );
                        }
                    }
                });

            /*
             * Cubrimos totalmente el contenido real del
             * inbox con una capa opaca de demostracion.
             * Los pixels de mensajes reales nunca llegan
             * a Page.captureScreenshot.
             */
            const overlay =
                document.createElement(
                    "div"
                );

            overlay.id = ID;

            Object.assign(
                overlay.style,
                {
                    position: "fixed",
                    left:
                        Math.max(
                            0,
                            rect.left
                        ) + "px",
                    top:
                        Math.max(
                            0,
                            rect.top
                        ) + "px",
                    width:
                        Math.min(
                            window.innerWidth
                                - Math.max(
                                    0,
                                    rect.left
                                ),
                            rect.width
                        ) + "px",
                    height:
                        Math.min(
                            window.innerHeight
                                - Math.max(
                                    0,
                                    rect.top
                                ),
                            rect.height
                        ) + "px",
                    background: "#ffffff",
                    zIndex: "2147483646",
                    overflow: "hidden",
                    boxSizing: "border-box",
                    fontFamily:
                        "Arial, sans-serif",
                    color: "#202124"
                }
            );

            const encabezado =
                document.createElement(
                    "div"
                );

            Object.assign(
                encabezado.style,
                {
                    padding:
                        "18px 22px 14px 22px",
                    fontSize: "20px",
                    fontWeight: "600",
                    borderBottom:
                        "1px solid #e0e0e0"
                }
            );

            encabezado.textContent =
                "Bandeja de entrada";

            overlay.appendChild(
                encabezado
            );

            const toolbar =
                document.createElement(
                    "div"
                );

            Object.assign(
                toolbar.style,
                {
                    height: "46px",
                    borderBottom:
                        "1px solid #eeeeee",
                    display: "flex",
                    alignItems: "center",
                    padding:
                        "0 22px",
                    gap: "22px",
                    fontSize: "14px",
                    color: "#5f6368"
                }
            );

            toolbar.textContent =
                "?    Actualizar    M?s";

            overlay.appendChild(
                toolbar
            );

            const mensajes = [
                [
                    "Equipo de proyecto",
                    "Actualizaci?n semanal",
                    "Resumen de avances y pr?ximos pasos"
                ],
                [
                    "Cliente de demostraci?n",
                    "Consulta sobre el servicio",
                    "Mensaje de ejemplo para la automatizaci?n"
                ],
                [
                    "Soporte",
                    "Solicitud recibida",
                    "Este correo contiene informaci?n ficticia"
                ],
                [
                    "Departamento comercial",
                    "Seguimiento de propuesta",
                    "Ejemplo utilizado ?nicamente para el tutorial"
                ],
                [
                    "Notificaciones",
                    "Nuevo mensaje",
                    "Contenido seguro de demostraci?n"
                ],
                [
                    "Equipo interno",
                    "Reuni?n de ma?ana",
                    "Confirmaci?n de agenda y tareas"
                ]
            ];

            mensajes.forEach(
                (datos, indice) => {
                    const fila =
                        document.createElement(
                            "div"
                        );

                    Object.assign(
                        fila.style,
                        {
                            minHeight: "58px",
                            display: "grid",
                            gridTemplateColumns:
                                "32px 190px 1fr 70px",
                            alignItems: "center",
                            gap: "10px",
                            padding:
                                "0 18px",
                            borderBottom:
                                "1px solid #eeeeee",
                            background:
                                indice < 3
                                    ? "#f2f6fc"
                                    : "#ffffff",
                            fontSize: "14px",
                            boxSizing:
                                "border-box"
                        }
                    );

                    const check =
                        document.createElement(
                            "span"
                        );

                    check.textContent = "?";

                    const remitente =
                        document.createElement(
                            "strong"
                        );

                    remitente.textContent =
                        datos[0];

                    const asunto =
                        document.createElement(
                            "span"
                        );

                    asunto.textContent =
                        datos[1]
                        + " ? "
                        + datos[2];

                    const hora =
                        document.createElement(
                            "span"
                        );

                    hora.textContent =
                        indice < 3
                            ? "10:30"
                            : "Ayer";

                    hora.style.textAlign =
                        "right";

                    fila.append(
                        check,
                        remitente,
                        asunto,
                        hora
                    );

                    overlay.appendChild(
                        fila
                    );
                }
            );

            const aviso =
                document.createElement(
                    "div"
                );

            Object.assign(
                aviso.style,
                {
                    position: "absolute",
                    right: "18px",
                    bottom: "14px",
                    padding:
                        "7px 11px",
                    borderRadius: "8px",
                    background:
                        "rgba(32,33,36,.82)",
                    color: "#ffffff",
                    fontSize: "11px"
                }
            );

            aviso.textContent =
                "Datos de demostraci?n";

            overlay.appendChild(
                aviso
            );

            document.body.appendChild(
                overlay
            );

            document.body.setAttribute(
                "data-autotube-gmail-sanitized",
                "true"
            );

            return {
                ok: true,
                overlay: true
            };
        }
        """)

        if not resultado:
            return False

        if not resultado.get(
            "ok",
            False,
        ):
            return False

        overlay = pagina.locator(
            "#autotube-gmail-safe-overlay"
        )

        if (
            overlay.count() == 0
            or not overlay.first.is_visible()
        ):
            return False

        sanitizado = pagina.get_attribute(
            "body",
            "data-autotube-gmail-sanitized",
        )

        return (
            sanitizado == "true"
        )

    def ejecutar_accion(
        self,
        pagina: Any,
        elemento: dict[str, Any],
    ) -> str:
        texto = " ".join(
            str(
                elemento.get(
                    clave,
                    "",
                )
            )
            for clave in (
                "pantalla_objetivo",
                "accion_visual",
                "descripcion_visual",
                "texto_narrado",
            )
        ).lower()

        texto_normalizado = "".join(
            caracter
            for caracter
            in unicodedata.normalize(
                "NFKD",
                texto,
            )
            if not unicodedata.combining(
                caracter
            )
        )

        es_inbox = (
            "bandeja de entrada"
            in texto_normalizado
            or "inbox"
            in texto_normalizado
            or "lista de correos"
            in texto_normalizado
            or "correos no leidos"
            in texto_normalizado
        )

        if es_inbox:
            if self._sanitizar_inbox(
                pagina
            ):
                return (
                    "gmail_inbox_sanitizado"
                )

            return (
                "gmail_inbox_no_sanitizado"
            )

        return (
            "sin_accion_especifica"
        )

class GenericTutorialDriver(
    TutorialDriverBase
):
    nombre = "generico"


_DRIVERS = {
    "make": MakeTutorialDriver(),
    "chatgpt": ChatGPTTutorialDriver(),
    "openai": OpenAITutorialDriver(),
    "gmail": GmailTutorialDriver(),
}


def obtener_driver(
    plataforma: str,
) -> TutorialDriverBase:
    return _DRIVERS.get(
        str(
            plataforma
        ).strip().lower(),
        GenericTutorialDriver(),
    )

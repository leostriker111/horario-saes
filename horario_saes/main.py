"""
Esta app sirve para realizar horarios del:
Instituto Politecnico Nacional.
"""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from horario_saes.config import get_config
from horario_saes.modulos.colors import Colors
from horario_saes.modulos.document_loader import DocumentLoader, LoadError
from horario_saes.modulos.modelo import Estado, Rama
from horario_saes.modulos.parser_saes import DIAS_LARGO
from horario_saes.modulos.dialogos import (
    DialogoBloque,
    DialogoCheck,
    DialogoExportar,
    DialogoFiltro,
    VistaArbol,
    VistaPlan,
    VistaProfesores,
)
from horario_saes.modulos.iconos import FA, FONT_SOLID, FONT_REGULAR, cargar_fuentes, crear_imagen_icono

RUTA_SESION = Path.home() / "horarios_saes" / "datafiles" / "UPIICSA.txt"
HORA_INI, HORA_FIN = 7, 22


class IconProxy:
    def __init__(self, button):
        self.button = button

    def config(self, text=None, **kwargs):
        if text is not None:
            img = crear_imagen_icono(text, color="#212121")
            self.button.config(image=img)
            self.button.image = img



class App(tk.Tk):
    def __init__(self):
        super().__init__()
        cargar_fuentes(self)
        self.title("Horarios SAES")

        self.config = get_config()
        self.loader = DocumentLoader(self.config)
        self.estado = Estado(RUTA_SESION)
        self.filtros = {
            "texto": "",
            "solo_favoritos": False,
            "ocultar_incompatibles": False,
            "turno": "todos",
            "solo_check": False,
            "ocultar_cursadas": False,
            "dias": [True, True, True, True, True],
            "hora_ini": 7,
            "hora_fin": 22,
        }

        self.geometry("1280x760")
        self.minsize(980, 600)

        self._acciones_lista: dict[str, tuple] = {}
        self._bloques_horario: dict[str, str] = {}

        self._construir_toolbar()
        self._construir_menu_celulares()
        self._construir_cuerpo()
        self._construir_barra_ramas()

        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        cargado = self.estado.cargar_sesion()
        if cargado and self.estado.opciones:
            self.after(50, self.refresh)
        elif self.config.origenes:
            self.after(50, self._auto_cargar_remoto)

    def _construir_toolbar(self) -> None:
        barra = ttk.Frame(self, padding=(8, 6))
        barra.pack(fill="x")

        self._btn(barra, FA.FOLDER_OPEN, "Cargar TXT", self._cargar_txt)
        self._btn(barra, FA.SEARCH, "Filtrar", self._abrir_filtro)
        self._btn(barra, FA.SEEDLING, "Bifurcar", self._bifurcar)
        self._btn(barra, FA.TREE, "Árbol", self._abrir_arbol)
        self._btn(barra, FA.PLUS, "Bloque propio", self._abrir_bloque)
        self._btn(barra, FA.CLIPBOARD, "Plan/Equiv", self._abrir_plan)
        self._btn(barra, FA.CHECK, "Check", self._abrir_check)
        self._btn(barra, FA.UPLOAD, "Exportar", self._abrir_exportar)
        self._btn(barra, FA.TRASH, "Limpiar todo", self._limpiar_todo)
        self.btn_lista_icon, self.btn_lista = self._btn(barra, FA.EYE_SLASH, "Ocultar lista", self._toggle_lista, ret_both=True)

        ttk.Label(barra, text="  Créditos máx:").pack(side="left")
        self.var_max = tk.StringVar()
        ent_max = ttk.Entry(barra, textvariable=self.var_max, width=7)
        ent_max.pack(side="left")
        ent_max.bind("<Return>", self._aplicar_max)
        ent_max.bind("<FocusOut>", self._aplicar_max)

        self.lbl_contadores = ttk.Label(barra, font=("Segoe UI", 10, "bold"))
        self.lbl_contadores.pack(side="right", padx=8)
        self.lbl_check = ttk.Label(barra, font=("Segoe UI", 10, "bold"))
        self.lbl_check.pack(side="right")

    def _btn(self, parent, icon, text, command, ret_both=False):
        img = crear_imagen_icono(icon, color="#212121")
        btn = ttk.Button(parent, text=text, command=command, image=img, compound="left")
        btn.image = img
        btn.pack(side="left", padx=2)
        if ret_both:
            return (IconProxy(btn), btn)
        return btn

    def _construir_menu_celulares(self) -> None:
        if len(self.config.origenes) <= 1:
            return
        options = [o.nombre for o in self.config.origenes]
        labels = ttk.Frame(self)
        labels.pack(fill="x", padx=(8, 6))
        ttk.Label(labels, text="Escuela: ", font=("Segoe UI", 9, "bold")).pack(side="left")
        self.var_school = tk.StringVar(value=options[self.config.active_index])
        combobox = ttk.Combobox(
            labels,
            textvariable=self.var_school,
            values=options,
            state="readonly",
            width=20,
        )
        combobox.pack(side="left")
        combobox.bind("<<ComboboxSelected>>", self._on_school_change)
        self.sync_btn = ttk.Button(
            labels,
            text="☁️ Sincronizar",
            command=self._sync_remote
        )
        self.sync_btn.pack(side="left", padx=6)

    def _on_school_change(self, event=None):
        idx = self.var_school.get()
        for i, o in enumerate(self.config.origenes):
            if o.nombre == idx:
                self.config.active_index = i
                break
        self._sync_remote(force=False)

    def _construir_cuerpo(self) -> None:
        self._lista_visible = True
        self._paned = ttk.PanedWindow(self, orient="horizontal")
        self._paned.pack(fill="both", expand=True, padx=6, pady=(2, 0))

        self._lista_frame = ttk.Frame(self._paned)
        self.canvas_lista = tk.Canvas(self._lista_frame, highlightthickness=0, bg=Colors.WHITE)
        barra_l = ttk.Scrollbar(self._lista_frame, orient="vertical", command=self.canvas_lista.yview)
        self.canvas_lista.configure(yscrollcommand=barra_l.set)
        self.canvas_lista.pack(side="left", fill="both", expand=True)
        barra_l.pack(side="right", fill="y")
        self.canvas_lista.bind("<Button-1>", self._click_lista)
        self.canvas_lista.bind("<Button-3>", self._click_der_lista)
        self.canvas_lista.bind("<Enter>", lambda e: self._activar_rueda(True))
        self.canvas_lista.bind("<Leave>", lambda e: self._activar_rueda(False))
        self.canvas_lista.bind("<Configure>", lambda e: self._refrescar_lista())
        self._paned.add(self._lista_frame, weight=2)

        der = ttk.Frame(self._paned)
        paned_der = ttk.PanedWindow(der, orient="vertical")
        paned_der.pack(fill="both", expand=True)

        hor_frame = ttk.Frame(paned_der)
        self.canvas_horario = tk.Canvas(hor_frame, bg=Colors.WHITE, highlightthickness=0)
        self.canvas_horario.pack(fill="both", expand=True)
        self.canvas_horario.bind("<Configure>", lambda e: self._dibujar_horario())
        self.canvas_horario.bind("<Button-1>", self._click_horario)
        paned_der.add(hor_frame, weight=3)

        self.panel_insc = ttk.Frame(paned_der)
        scroll_insc = ttk.Scrollbar(self.panel_insc, orient="vertical")
        canvas_insc = tk.Canvas(self.panel_insc, highlightthickness=0, yscrollcommand=scroll_insc.set)
        scroll_insc.config(command=canvas_insc.yview)
        canvas_insc.pack(side="left", fill="both", expand=True)
        scroll_insc.pack(side="right", fill="y")
        paned_der.add(self.panel_insc, weight=1)

        self._paned.add(der, weight=5)

    def _construir_barra_ramas(self) -> None:
        barra = ttk.Frame(self, padding=(8, 4))
        barra.pack(fill="x", side="bottom")
        ttk.Separator(barra, orient="horizontal").pack(fill="x", pady=(0, 4))
        self.lbl_rama = ttk.Label(barra, font=("Segoe UI", 10, "bold"))
        self.lbl_rama.pack(side="left", padx=(0, 8))
        self.marco_ramas = ttk.Frame(barra)
        self.marco_ramas.pack(side="left", fill="x", expand=True)

    def _auto_cargar_remoto(self):
        try:
            ruta = self.loader.cargar_escuela_activa()
            if ruta is None:
                return
            self._load_txt_path(ruta)
        except LoadError:
            pass

    def _sync_remote(self, force=True):
        try:
            ruta = self.loader.cargar_escuela_activa(force=force)
            if ruta is None:
                messagebox.showwarning(
                    "Sin datos remotos",
                    f"No se pudo encontrar datos para {self.var_school.get()}.",
                )
                return
            self._load_txt_path(ruta)
        except LoadError as e:
            if messagebox.askyesno(
                "Error de sincronización",
                f"{e}\n\n¿Quieres seleccionar un TXT manualmente?",
            ):
                self._cargar_txt_manual()
            else:
                messagebox.showwarning(
                    "", "No se pudo cargar el archivo TXT"
                )

    def _cargar_txt(self):
        if len(self.config.origenes) > 0:
            self._sync_remote(force=False)
        else:
            self._cargar_txt_manual()

    def _cargar_txt_manual(self):
        ruta = filedialog.askopenfilename(
            title="Selecciona el txt copiado del SAES",
            initialdir=str(Path.home() / "Downloads"),
            filetypes=[("Texto", "*.txt"), ("Todos", "*.*")],
        )
        if not ruta:
            return
        self._load_txt_path(ruta)

    def _load_txt_path(self, ruta: Path):
        try:
            n = self.estado.cargar_txt(str(ruta))
        except OSError as error:
            messagebox.showerror("Error de lectura", str(error))
            return
        if n == 0:
            messagebox.showwarning(
                "Sin datos",
                "No se encontraron grupos en ese archivo. ¿Seguro que es el formato "
                "del SAES con tabuladores?",
            )
        self.refresh()

    def _abrir_filtro(self):
        DialogoFiltro(self, self.filtros, self.refresh)

    def _bifurcar(self):
        nombre = simpledialog.askstring(
            "Bifurcar", "Nombre de la nueva rama (vacío = automático):", parent=self
        )
        if nombre is None:
            return
        self.estado.bifurcar(nombre.strip())
        self.refresh()

    def _abrir_arbol(self):
        VistaArbol(self, self.estado, self.refresh)

    def _abrir_bloque(self):
        DialogoBloque(self, self.estado, self.refresh)

    def _abrir_exportar(self):
        if not self.estado.seleccionadas():
            messagebox.showinfo("Nada que exportar", "Agrega materias al horario primero.")
            return
        DialogoExportar(self, self.estado)

    def _abrir_plan(self):
        VistaPlan(self, self.estado)

    def _abrir_check(self):
        DialogoCheck(self, self.estado, self.refresh)

    def _ver_profesores(self, materia):
        VistaProfesores(self, self.estado, materia, self.refresh)

    def _aplicar_max(self, *_):
        texto = self.var_max.get().strip().replace(",", ".")
        try:
            self.estado.max_creditos = float(texto) if texto else None
        except ValueError:
            self.var_max.set("" if self.estado.max_creditos is None
                             else f"{self.estado.max_creditos:g}")
            return
        self.refresh()

    def _editar_creditos(self, materia):
        actual = self.estado.creditos.get(materia)
        nuevo = simpledialog.askfloat(
            "Créditos",
            f"Créditos {materia} (ahora: {'SN' if actual is None else f'{actual:g}'})\n"
            f"Escribe -1 para regresarla a SN:",
            initialvalue=actual or 0,
            parent=self,
        )
        if nuevo is not None:
            self.estado.fijar_creditos(materia, None if nuevo < 0 else nuevo)
            self.refresh()

    def _confirmar(self, titulo, mensaje):
        dlg = tk.Toplevel(self)
        dlg.title(titulo)
        dlg.resizable(False, False)
        dlg.grab_set()
        respuesta = {"ok": False}
        ttk.Label(dlg, text=mensaje, padding=16, justify="center").pack()
        botones = ttk.Frame(dlg)
        botones.pack(pady=(0, 12))

        def responder(ok):
            respuesta["ok"] = ok
            dlg.destroy()

        ttk.Button(botones, text="Continuar", command=lambda: responder(True)).pack(side="left", padx=6)
        ttk.Button(botones, text="Cancelar", command=lambda: responder(False)).pack(side="left", padx=6)
        dlg.bind("<Escape>", lambda e: responder(False))
        dlg.transient(self)
        self.wait_window(dlg)
        return respuesta["ok"]

    def _toggle_opcion(self, op_id):
        e = self.estado
        if op_id in e.rama().seleccion:
            e.quitar(op_id)
        else:
            op = e.opciones[op_id]
            cred = e.creditos.get(op.materia) or 0
            total, _ = e.total_creditos()
            if e.max_creditos is not None and total + cred > e.max_creditos:
                if not self._confirmar(
                    "Créditos excedidos",
                    f"Estás superando {total + cred:g} de {e.max_creditos:g} permitidos.\n\n¿Quieres continuar?",
                ):
                    return
            e.agregar(op_id)
        self.refresh()

    def _toggle_favorito(self, profesor):
        if profesor in self.estado.favoritos:
            self.estado.favoritos.discard(profesor)
        else:
            self.estado.favoritos.add(profesor)
        self.refresh()

    def _quitar_propia(self, op_id):
        if messagebox.askyesno("Eliminar bloque", "¿Eliminar este bloque propio?"):
            self.estado.quitar_propia(op_id)
            self.refresh()

    def _cambiar_rama(self, rama_id):
        self.estado.rama_actual = rama_id
        self.refresh()

    def _eliminar_rama(self, rama_id):
        if not messagebox.askyesno("Eliminar rama", "¿Eliminar esta rama y todas sus hijas?"):
            return
        self.estado.eliminar_rama(rama_id)
        self.refresh()

    def _limpiar_todo(self):
        if not messagebox.askyesno("Limpiar todo", "Se borrarán todas las selecciones, ramas y favoritos.\n¿Continuar?"):
            return
        e = self.estado
        e.ramas = {1: Rama(1, "Principal")}
        e.rama_actual = 1
        e.favoritos.clear()
        e.necesarias.clear()
        e.colapsadas.clear()
        e.max_creditos = None
        self.var_max.set("")
        self.refresh()

    def _toggle_lista(self):
        if self._lista_visible:
            self._paned.forget(self._lista_frame)
            self.btn_lista.config(text="Mostrar lista")
            self.btn_lista_icon.config(text=FA.EYE)
        else:
            self._paned.insert(0, self._lista_frame, weight=2)
            self.btn_lista.config(text="Ocultar lista")
            self.btn_lista_icon.config(text=FA.EYE_SLASH)
        self._lista_visible = not self._lista_visible

    def _cerrar(self):
        self.estado.guardar()
        self.destroy()

    # ------------------------------------------------------------ refresh
    def refresh(self):
        self.estado.guardar()
        self._refrescar_contadores()
        self._refrescar_lista()
        self._refrescar_inscritos()
        self._dibujar_horario()
        self._refrescar_ramas()

    def _refrescar_inscritos(self):
        for w in self.panel_insc.winfo_children():
            w.destroy()
        e = self.estado
        sel = sorted(e.seleccionadas(), key=lambda o: o.materia)
        ttk.Label(self.panel_insc, text=f"Inscribiendo ({len(sel)})",
                  font=("Segoe UI", 11, "bold"), padding=(8, 6)).pack(anchor="w")

        for op in sel:
            color = e.colores.get(op.materia, Colors.DEFAULT)
            fila = tk.Frame(self.panel_insc, bg=Colors.WHITE, bd=1, relief="solid")
            fila.pack(fill="x", padx=6, pady=2)
            tk.Frame(fila, bg=color, width=6).pack(side="left", fill="y")
            btn_x = tk.Label(fila, text=FA.TIMES, bg=Colors.WHITE, fg=Colors.RED,
                             font=(FONT_SOLID, 10), cursor="hand2", padx=6)
            btn_x.pack(side="right")
            btn_x.bind("<Button-1>", lambda ev, i=op.id: self._toggle_opcion(i))
            marco = tk.Frame(fila, bg=Colors.WHITE)
            marco.pack(side="left", fill="x", expand=True, padx=4, pady=2)
            nombre = op.materia if len(op.materia) < 30 else f"{op.materia[:29]}…"
            tk.Label(marco, text=nombre, bg=Colors.WHITE, anchor="w",
                     font=("Segoe UI", 9, "bold")).pack(fill="x")
            cred = e.creditos.get(op.materia)
            detalle = f"{op.grupo} · {'SN' if cred is None else f'{cred:g} cr'}"
            tk.Label(marco, text=detalle, bg=Colors.WHITE, anchor="w", fg=Colors.GRAY_TEXT,
                     font=("Segoe UI", 8)).pack(fill="x")

        if e.necesarias:
            faltan = e.faltantes()
            ttk.Separator(self.panel_insc).pack(fill="x", padx=6, pady=6)
            if faltan:
                ico = tk.Label(self.panel_insc, text=FA.EXCLAMATION_TRIANGLE,
                               font=(FONT_SOLID, 10), fg=Colors.RED)
                ico.pack(anchor="w", padx=(8, 0))
                lbl = ttk.Label(self.panel_insc, text=f"Faltan del check ({len(faltan)}):",
                          foreground=Colors.RED, font=("Segoe UI", 10, "bold"),
                          padding=(2, 0))
                lbl.pack(anchor="w")
                for m in faltan:
                    nombre = m if len(m) < 32 else f"{m[:31]}…"
                    ttk.Label(self.panel_insc, text=f"• {nombre}",
                              foreground=Colors.RED, font=("Segoe UI", 8),
                              padding=(14, 0)).pack(anchor="w")
            else:
                ttk.Label(self.panel_insc, text="Check completado",
                          foreground=Colors.GREEN, font=("Segoe UI", 10, "bold"),
                          padding=(8, 0)).pack(anchor="w")

    def _refrescar_contadores(self):
        e = self.estado
        sel = e.seleccionadas()
        total, sin_cred = e.total_creditos()
        cred = f"Créditos: {total:g}"
        excedido = False
        if e.max_creditos is not None:
            cred += f" / {e.max_creditos:g}"
            excedido = total > e.max_creditos
        if sin_cred:
            cred += f"  ({sin_cred} materia{'s' if sin_cred > 1 else ''} SN)"
        self.lbl_contadores.config(
            foreground=Colors.RED if excedido else Colors.BLACK,
            text=(f"Opciones disponibles: {len(e.disponibles())}   |   "
                  f"Materias: {len(sel)}   |   {cred}   |   "
                  f"Horas/sem: {e.total_horas():g}"))
        if not e.necesarias:
            self.lbl_check.config(text="")
        else:
            faltan = len(e.faltantes())
            if faltan:
                self.lbl_check.config(text=f"Faltan {faltan} del check   |",
                                      foreground=Colors.RED)
            else:
                self.lbl_check.config(text="Check   |", foreground=Colors.GREEN)
        if self.focus_get() is None or self.focus_get().winfo_class() != "TEntry":
            self.var_max.set("" if e.max_creditos is None else f"{e.max_creditos:g}")

    # ------------------------------------------------------- lista lateral
    def _pasa_filtro(self, op):
        f = self.filtros
        texto = f["texto"].lower().strip()
        if texto and texto not in f"{op.materia} {op.profesor} {op.grupo}".lower():
            return False
        if f["solo_favoritos"] and not op.propia and op.profesor not in self.estado.favoritos:
            return False
        if f["turno"] != "todos" and op.sesiones:
            inicio_min = min(s.inicio for s in op.sesiones)
            if f["turno"] == "mat" and inicio_min >= 15 * 60:
                return False
            if f["turno"] == "vesp" and inicio_min < 15 * 60:
                return False
        if f["ocultar_cursadas"] and not op.propia                 and self.estado.esta_cursada(op.materia):
            return False
        if f["solo_check"] and self.estado.necesarias and not op.propia:
            from horario_saes.modulos.parser_saes import normalizar
            objetivo = {normalizar(n) for n in self.estado.necesarias}
            if normalizar(op.materia) not in objetivo                     and not (self.estado.equivalentes(op.materia) & objetivo):
                return False
        if not all(f["dias"]):
            if any(not f["dias"][s.dia] for s in op.sesiones):
                return False
        if f["hora_ini"] > 7 or f["hora_fin"] < 22:
            if any(s.inicio < f["hora_ini"] * 60 or s.fin > f["hora_fin"] * 60
                   for s in op.sesiones):
                return False
        return True

    def _click_lista(self, evento):
        accion = self._accion_bajo_cursor()
        if not accion:
            return
        tipo, dato = accion
        if tipo == "op":
            self._toggle_opcion(dato)
        elif tipo == "fav":
            self._toggle_favorito(dato)
        elif tipo == "del":
            self._quitar_propia(dato)
        elif tipo == "prof":
            self._ver_profesores(dato)
        elif tipo == "hdr":
            if dato in self.estado.colapsadas:
                self.estado.colapsadas.discard(dato)
            else:
                self.estado.colapsadas.add(dato)
            self._refrescar_lista()

    def _click_der_lista(self, evento):
        accion = self._accion_bajo_cursor()
        if accion and accion[0] in ("hdr", "prof"):
            self._editar_creditos(accion[1])

    def _click_horario(self, evento):
        for item in self.canvas_horario.find_withtag("current"):
            for tag in self.canvas_horario.gettags(item):
                op_id = self._bloques_horario.get(tag)
                if op_id:
                    candados = self.estado.rama().candados
                    if op_id in candados:
                        candados.remove(op_id)
                    else:
                        candados.append(op_id)
                    self.refresh()
                    return

    def _accion_bajo_cursor(self):
        for item in self.canvas_lista.find_withtag("current"):
            for tag in self.canvas_lista.gettags(item):
                if tag in self._acciones_lista:
                    return self._acciones_lista[tag]
        return None

    def _activar_rueda(self, activo):
        if activo:
            self.canvas_lista.bind_all("<MouseWheel>", self._rueda_lista)
        else:
            self.canvas_lista.unbind_all("<MouseWheel>")

    def _rueda_lista(self, evento):
        self.canvas_lista.yview_scroll(-3 if evento.delta > 0 else 3, "units")

    def _refrescar_lista(self):
        cv = self.canvas_lista
        vista_y = cv.yview()[0]
        cv.delete("all")
        self._acciones_lista.clear()
        e = self.estado
        seleccion = set(e.rama().seleccion)
        ancho = max(cv.winfo_width(), 200)

        if not e.opciones:
            cv.create_text(ancho / 2, 60, text="Carga el TXT del SAES\npara empezar",
                           fill=Colors.GRAY_DARK, font=("Segoe UI", 11), justify="center")
            return

        y = 4
        n = 0
        for materia in e.orden_materias:
            ops = [op for op in e.opciones_de(materia) if self._pasa_filtro(op)]
            compatibles = [op for op in ops if op.id in seleccion or e.es_compatible(op)]
            if self.filtros["ocultar_incompatibles"]:
                ops = compatibles
            if not ops:
                continue
            color = e.colores.get(materia, Colors.DEFAULT)
            cred = e.creditos.get(materia)
            etiqueta_cred = "SN" if cred is None else f"{cred:g} cr"

            plegada = materia in e.colapsadas
            tag_h, tag_p = f"h{n}", f"p{n}"
            n += 1
            self._acciones_lista[tag_h] = ("hdr", materia)
            self._acciones_lista[tag_p] = ("prof", materia)
            y += 6
            cv.create_rectangle(4, y, ancho - 4, y + 26, fill=color, outline=color, tags=(tag_h,))
            flecha = "▸" if plegada else "▾"
            texto_h = f"{flecha} {materia}  ({len(compatibles)}/{len(ops)}) · {etiqueta_cred}"
            if len(texto_h) > 42:
                texto_h = f"{texto_h[:41]}..."
            cv.create_text(10, y + 13, text=texto_h, anchor="w",
                           font=("Segoe UI", 9, "bold"), tags=(tag_h,))
            cv.create_text(ancho - 18, y + 13, text=FA.USERS, font=(FONT_SOLID, 10), tags=(tag_p,))
            y += 26
            if plegada:
                continue

            for op in sorted(ops, key=lambda o: o.grupo):
                elegida = op.id in seleccion
                compatible = elegida or e.es_compatible(op)
                if elegida:
                    bg, fg, borde, grosor = color, Colors.BLACK, Colors.BORDER_DARK, 2
                elif compatible:
                    bg, fg, borde, grosor = Colors.WHITE, Colors.BLACK, Colors.BORDER_MED, 1
                else:
                    bg, fg, borde, grosor = Colors.GRAY_LIGHTER, Colors.BORDER_MED, Colors.BORDER_LIGHT, 1

                tag_op = f"o{n}"
                n += 1
                if compatible:
                    self._acciones_lista[tag_op] = ("op", op.id)
                y += 2
                cv.create_rectangle(10, y, ancho - 8, y + 46, fill=bg, outline=borde, width=grosor, tags=(tag_op,))
                marca = "  " if elegida else ("" if compatible else "  ")
                cv.create_text(16, y + 9, text=f"{marca}{op.grupo}", anchor="w",
                               fill=fg, font=("Segoe UI", 9, "bold"), tags=(tag_op,))
                cv.create_text(16, y + 23, text=op.profesor[:46], anchor="w",
                               fill=fg, font=("Segoe UI", 8), tags=(tag_op,))
                cv.create_text(16, y + 36, text=op.resumen_horario()[:48], anchor="w",
                               fill=fg, font=("Segoe UI", 8), tags=(tag_op,))

                tag_ex = f"x{n}"
                n += 1
                if op.propia:
                    self._acciones_lista[tag_ex] = ("del", op.id)
                    cv.create_text(ancho - 22, y + 10, text=FA.TIMES, font=(FONT_SOLID, 9), tags=(tag_ex,))
                else:
                    fav = op.profesor in self.estado.favoritos
                    self._acciones_lista[tag_ex] = ("fav", op.profesor)
                    cv.create_text(ancho - 22, y + 10, text=FA.STAR,
                                   fill=Colors.AMBER if fav else Colors.GRAY_MED,
                                   font=(FONT_SOLID if fav else FONT_REGULAR, 11), tags=(tag_ex,))
                y += 46

        cv.configure(scrollregion=(0, 0, ancho, y + 8))
        cv.yview_moveto(vista_y)

    # ---------------------------------------------------------- horario
    def _dibujar_horario(self, canvas=None, rama=None, mini=False, dims=None):
        cv = canvas or self.canvas_horario
        rama = rama or self.estado.rama()
        if not cv.winfo_exists():
            return
        cv.delete("all")
        ancho, alto = dims or (cv.winfo_width(), cv.winfo_height())
        if ancho < 10 or alto < 10:
            return

        m_izq = 8 if mini else 46
        m_sup = 4 if mini else 30
        m_inf = 4 if mini else 10
        col = (ancho - m_izq - 6) / 5
        total_min = (HORA_FIN - HORA_INI) * 60
        escala = (alto - m_sup - m_inf) / total_min

        def y_de(minutos):
            return m_sup + (minutos - HORA_INI * 60) * escala

        for h in range(HORA_INI, HORA_FIN + 1):
            y = y_de(h * 60)
            cv.create_line(m_izq, y, ancho - 6, y, fill=Colors.GRAY_LIGHT)
            if not mini:
                cv.create_text(m_izq - 6, y, text=f"{h}:00", anchor="e",
                               font=("Segoe UI", 8), fill=Colors.GRAY_DARK)
        for d in range(6):
            x = m_izq + d * col
            cv.create_line(x, m_sup, x, alto - m_inf, fill=Colors.GRAY)
        if not mini:
            for d, nombre in enumerate(DIAS_LARGO):
                cv.create_text(m_izq + d * col + col / 2, m_sup / 2, text=nombre,
                               font=("Segoe UI", 10, "bold"), fill=Colors.TEXT_SECONDARY)

        if not mini:
            self._bloques_horario.clear()
        nb = 0

        for op in self.estado.seleccionadas(rama):
            color = self.estado.colores.get(op.materia, Colors.DEFAULT)
            for s in op.sesiones:
                x1 = m_izq + s.dia * col + 2
                x2 = m_izq + (s.dia + 1) * col - 2
                y1, y2 = y_de(s.inicio), y_de(s.fin)
                extra = {"dash": (4, 2)} if op.propia else {}
                con_candado = op.id in rama.candados
                etiquetas = ()
                if not mini:
                    tag_b = f"blk{nb}"
                    nb += 1
                    self._bloques_horario[tag_b] = op.id
                    etiquetas = (tag_b,)
                cv.create_rectangle(x1, y1, x2, y2, fill=color,
                                    outline=Colors.BORDER_DARK,
                                    width=3 if con_candado else 1,
                                    tags=etiquetas, **extra)
                if not mini and con_candado:
                    cv.create_text(x2 - 11, y1 + 11, text="🔒",
                                   font=("Segoe UI", 10), tags=etiquetas)
                if not mini:
                    lugar = f" · {op.salon}" if op.salon and op.salon != "000" else ""
                    texto = f"{op.grupo}-{op.materia}\n{op.profesor}{lugar}"
                    if op.propia:
                        texto = f"{op.materia}\n{op.nota or ''}{lugar}"
                    cv.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=texto,
                                   font=("Segoe UI", 8), justify="center",
                                   width=x2 - x1 - 6, tags=etiquetas)

    # ------------------------------------------------------------- ramas
    def _refrescar_ramas(self):
        for w in self.marco_ramas.winfo_children():
            w.destroy()
        e = self.estado
        actual = e.rama()
        self.lbl_rama.config(text=f"Rama: {actual.nombre}")
        for rama in e.familia():
            relacion = "actual"
            if rama.id == e.rama_actual:
                relacion = "actual"
            elif rama.padre is None and rama.id != actual.id:
                relacion = "padre" if actual.padre == rama.id else "raíz"
            elif rama.padre == actual.padre:
                relacion = "hermana"
            elif rama.padre == actual.id:
                relacion = "hija"
            elif actual.padre == rama.id:
                relacion = "padre"
            es_actual = rama.id == e.rama_actual
            celda = tk.Frame(self.marco_ramas,
                             highlightthickness=2,
                             highlightbackground=Colors.HIGHLIGHT_OUTLINE if es_actual else Colors.BORDER_LIGHT)
            celda.pack(side="left", padx=3)
            mini = tk.Canvas(celda, width=180, height=112, bg=Colors.WHITE,
                             highlightthickness=0, cursor="hand2")
            mini.pack()
            lbl_nombre = tk.Label(celda, text=f"{rama.nombre} ({relacion})",
                     font=("Segoe UI", 8, "bold" if es_actual else "normal"))
            lbl_nombre.pack()
            mini.bind("<Button-1>", lambda ev, r=rama.id: self._cambiar_rama(r))
            self._dibujar_horario(mini, rama, mini=True, dims=(180, 112))

            if rama.id != 1:
                btn_x = tk.Label(celda, text=FA.TIMES, fg=Colors.RED,
                                 font=(FONT_SOLID, 9), cursor="hand2", padx=4)
                btn_x.place(relx=1.0, rely=0.0, x=-2, y=-2, anchor="ne")
                btn_x.lower()
                btn_x.bind("<Button-1>", lambda ev, r=rama.id: self._eliminar_rama(r))
                celda.bind("<Enter>", lambda ev, b=btn_x: b.lift())
                celda.bind("<Leave>", lambda ev, b=btn_x: b.lower())

def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()

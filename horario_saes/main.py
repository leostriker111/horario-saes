import shutil
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from horario_saes.modulos.dialogos import (DialogoBloque, DialogoCheck, DialogoExportar,
                              DialogoFiltro, VistaArbol, VistaPlan, VistaProfesores)
from horario_saes.modulos.modelo import Estado, Rama
from horario_saes.modulos.parser_saes import DIAS_LARGO
from horario_saes.modulos.iconos import FA, cargar_fuentes, crear_imagen_icono
from horario_saes.config import get_config
from horario_saes.modulos.document_loader import DocumentLoader, LoadError

RUTA_SESION = Path.home() / ".horario_saes" / "sesion.json"
_vieja = Path(__file__).resolve().parent.parent / "datos" / "sesion.json"
if not RUTA_SESION.exists() and _vieja.exists():
    RUTA_SESION.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(_vieja, RUTA_SESION)
HORA_INI, HORA_FIN = 7, 22
GRIS = "#78909C"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Horarios SAES")
        self.geometry("1280x760")
        self.minsize(980, 600)
        cargar_fuentes(self)
        self.config_datos = get_config()
        self.loader = DocumentLoader(self.config_datos)
        self._iconos: dict[str, tk.PhotoImage] = {}   # refs para que no las borre el GC
        self._lista_visible = True

        self.estado = Estado(RUTA_SESION)
        self.filtros = {"texto": "", "solo_favoritos": False,
                        "ocultar_incompatibles": False, "turno": "todos",
                        "solo_check": False, "ocultar_cursadas": False,
                        "dias": [True] * 5, "hora_ini": 7, "hora_fin": 22}
        self._combos_vistos: set[frozenset] = set()   # volátil: randoms ya dados
        self._hist: list[frozenset] = []              # historial ◀ ▶ del random
        self._hist_i = -1
        self._ventanas: dict[str, tk.Toplevel] = {}
        self._ultima_rama: int | None = None

        self._construir_toolbar()
        self._construir_cuerpo()
        self._construir_barra_ramas()

        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        if self.estado.cargar_sesion():
            self.after(50, self.refresh)

    # ------------------------------------------------------------ layout
    def _btn(self, parent, icono, texto, command):
        try:
            img = crear_imagen_icono(icono, color="#212121")
            self._iconos[texto] = img
            b = ttk.Button(parent, text=texto, image=img, compound="left",
                           command=command)
        except Exception:
            b = ttk.Button(parent, text=texto, command=command)
        b.pack(side="left", padx=2)
        return b

    def _construir_toolbar(self) -> None:
        barra = ttk.Frame(self, padding=(8, 6))
        barra.pack(fill="x")

        mb = ttk.Menubutton(barra, text=" Cargar datos")
        try:
            self._iconos["mb"] = crear_imagen_icono(FA.FOLDER_OPEN, color="#212121")
            mb.config(image=self._iconos["mb"], compound="left")
        except Exception:
            pass
        menu = tk.Menu(mb, tearoff=False)
        menu.add_command(label="Desde el SAES (en línea)", command=self._abrir_saes)
        menu.add_command(label="Desde un TXT (escuelas sin SAES)",
                         command=self._cargar_txt)
        if len(self.config_datos.origenes) > 0:
            menu.add_separator()
            for o in self.config_datos.origenes:
                menu.add_command(label=f"Nube: {o.nombre}",
                                 command=lambda n=o.nombre: self._sync_escuela(n))
        mb["menu"] = menu
        mb.pack(side="left", padx=2)

        self._btn(barra, FA.SEARCH, "Filtrar", self._abrir_filtro)
        self._btn(barra, FA.SEEDLING, "Bifurcar", self._bifurcar)
        self._btn(barra, FA.TREE, "Árbol", self._abrir_arbol)
        self._btn(barra, FA.PLUS, "Bloque propio", self._abrir_bloque)
        self._btn(barra, FA.CLIPBOARD, "Plan/Equiv", self._abrir_plan)
        self._btn(barra, FA.CHECK, "Check", self._abrir_check)
        self._btn(barra, FA.CHECK, "Cursadas", self._abrir_cursadas)
        ttk.Button(barra, text="◀", width=2, command=self._rand_prev).pack(side="left", padx=(6, 0))
        ttk.Button(barra, text="🎲", width=3, command=self._aleatorio).pack(side="left")
        ttk.Button(barra, text="▶", width=2, command=self._rand_next).pack(side="left", padx=(0, 2))
        self._btn(barra, FA.UPLOAD, "Exportar", self._abrir_exportar)
        self.btn_lista = self._btn(barra, FA.EYE_SLASH, "Ocultar lista", self._toggle_lista)
        self._btn(barra, FA.TRASH, "Limpiar", self._limpiar_todo)

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

    def _construir_cuerpo(self) -> None:
        cuerpo = ttk.Frame(self)
        cuerpo.pack(fill="both", expand=True)

        # panel lateral: canvas dibujado (mucho más rápido que cientos de widgets)
        self.cuerpo = cuerpo
        lateral = ttk.Frame(cuerpo, width=330)
        self.lista_frame = lateral
        lateral.pack(side="left", fill="y")
        lateral.pack_propagate(False)
        self.canvas_lista = tk.Canvas(lateral, highlightthickness=0, bg="#FAFAFA",
                                      yscrollincrement=24)
        barra = ttk.Scrollbar(lateral, orient="vertical", command=self.canvas_lista.yview)
        self.canvas_lista.configure(yscrollcommand=barra.set)
        self.canvas_lista.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self._acciones_lista: dict[str, tuple[str, str]] = {}
        self.canvas_lista.bind("<Button-1>", self._click_lista)
        self.canvas_lista.bind("<Button-3>", self._click_der_lista)


        # panel derecho: materias que estás inscribiendo (con scroll)
        marco_insc = ttk.Frame(cuerpo, width=235)
        marco_insc.pack(side="right", fill="y")
        marco_insc.pack_propagate(False)
        self.canvas_insc = tk.Canvas(marco_insc, highlightthickness=0)
        barra_insc = ttk.Scrollbar(marco_insc, orient="vertical",
                                   command=self.canvas_insc.yview)
        self.panel_insc = ttk.Frame(self.canvas_insc)
        self.canvas_insc.create_window((0, 0), window=self.panel_insc,
                                       anchor="nw", width=212)
        self.panel_insc.bind("<Configure>", lambda e: self.canvas_insc.configure(
            scrollregion=self.canvas_insc.bbox("all")))
        self.canvas_insc.configure(yscrollcommand=barra_insc.set)
        self.canvas_insc.pack(side="left", fill="both", expand=True)
        barra_insc.pack(side="right", fill="y")
        self.bind_all("<MouseWheel>", self._rueda_global)
        self.bind("<Enter>", lambda e: self.bind_all("<MouseWheel>",
                                                     self._rueda_global))
        for btn, delta in (("<Button-4>", 120), ("<Button-5>", -120)):  # rueda en Linux
            self.bind_all(btn, lambda e, d=delta: (setattr(e, "delta", d),
                                                   self._rueda_global(e)))

        # horario central (redibujo con retardo para no trabarse al redimensionar)
        self.canvas_horario = tk.Canvas(cuerpo, bg="white", highlightthickness=0)
        self.canvas_horario.pack(side="left", fill="both", expand=True)
        self._redibujo_pendiente: str | None = None
        self._bloques_horario: dict[str, str] = {}
        self._bloques_prof: dict[str, str] = {}
        self.canvas_horario.bind("<Configure>", lambda e: self._redibujar_pronto())
        self.canvas_horario.bind("<Button-1>", self._click_horario)

    def _construir_barra_ramas(self) -> None:
        pie = ttk.Frame(self, padding=(8, 4))
        pie.pack(fill="x")
        self.lbl_rama = ttk.Label(pie, font=("Segoe UI", 10, "bold"))
        self.lbl_rama.pack(side="left", padx=(0, 10))
        self.marco_ramas = ttk.Frame(pie)
        self.marco_ramas.pack(side="left", fill="x")

    def _rueda_global(self, ev) -> None:
        w = self.winfo_containing(ev.x_root, ev.y_root)
        while w is not None:
            if w is self.canvas_lista:
                self.canvas_lista.yview_scroll(-3 if ev.delta > 0 else 3, "units")
                return
            if w is self.canvas_insc or w is self.panel_insc:
                self.canvas_insc.yview_scroll(-2 if ev.delta > 0 else 2, "units")
                return
            w = getattr(w, "master", None)

    def _redibujar_pronto(self) -> None:
        if self._redibujo_pendiente:
            self.after_cancel(self._redibujo_pendiente)
        self._redibujo_pendiente = self.after(50, self._redibujo)

    def _redibujo(self) -> None:
        self._redibujo_pendiente = None
        self._dibujar_horario()

    # ----------------------------------------------------------- acciones
    def _cargar_txt(self) -> None:
        ruta = filedialog.askopenfilename(
            title="Selecciona el txt copiado del SAES",
            initialdir=str(Path.home() / "Downloads"),
            filetypes=[("Texto", "*.txt"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            n = self.estado.cargar_txt(ruta)
        except OSError as e:
            messagebox.showerror("Error al leer", str(e))
            return
        if n == 0:
            messagebox.showwarning(
                "Sin datos",
                "No encontré grupos en ese archivo. ¿Seguro que es el formato "
                "del SAES con tabuladores?")
        self.refresh()

    def _sync_escuela(self, nombre: str) -> None:
        """Descarga el datafile de una escuela desde el repo de datos (nube),
        con fallback a la copia local si no hay internet."""
        for i, o in enumerate(self.config_datos.origenes):
            if o.nombre == nombre:
                self.config_datos.active_index = i
                break
        try:
            ruta = self.loader.cargar_escuela_activa(force=True)
        except LoadError as e:
            if self.loader.existe_archivo_local(nombre):
                ruta = self.loader.existe_archivo_local(nombre)
            else:
                messagebox.showerror("Sin datos", f"No pude bajar {nombre}:\n{e}")
                return
        if not ruta:
            messagebox.showwarning("Sin datos", f"No hay datos para {nombre}.")
            return
        try:
            n = self.estado.cargar_txt(str(ruta))
        except OSError as e:
            messagebox.showerror("Error al leer", str(e))
            return
        messagebox.showinfo("Nube", f"{nombre}: {n} grupos cargados.")
        self.refresh()

    def _toggle_lista(self) -> None:
        if self._lista_visible:
            self.lista_frame.pack_forget()
            self.btn_lista.config(text="Mostrar lista")
        else:
            self.lista_frame.pack(side="left", fill="y", before=self.canvas_horario)
            self.btn_lista.config(text="Ocultar lista")
        self._lista_visible = not self._lista_visible

    def _limpiar_todo(self) -> None:
        if not messagebox.askyesno(
                "Limpiar todo",
                "Se borrarán todas las selecciones, ramas, favoritos y el check.\n"
                "¿Continuar?"):
            return
        e = self.estado
        e.ramas = {1: Rama(1, "Principal")}
        e.rama_actual = 1
        e._next_rama = 2
        e.favoritos.clear()
        e.necesarias.clear()
        e.colapsadas.clear()
        self._hist.clear()
        self._hist_i = -1
        self._combos_vistos.clear()
        self.refresh()

    def _unica(self, clave: str, fabrica) -> None:
        v = self._ventanas.get(clave)
        if v is not None and v.winfo_exists():
            v.deiconify()
            v.lift()
            v.focus_set()
            return
        v = fabrica()
        v.transient(self)
        self._ventanas[clave] = v

    def _abrir_saes(self) -> None:
        self._unica("saes", self._crear_dialogo_saes)

    def _crear_dialogo_saes(self) -> tk.Toplevel:
        from horario_saes.modulos.dialogos import DialogoSaes
        return DialogoSaes(self, self.estado, self.refresh)

    def _abrir_filtro(self) -> None:
        self._unica("filtro", lambda: DialogoFiltro(self, self.filtros, self.refresh))

    def _bifurcar(self) -> None:
        nombre = simpledialog.askstring(
            "Bifurcar", "Nombre de la nueva rama (vacío = automático):", parent=self)
        if nombre is None:
            return
        self.estado.bifurcar(nombre.strip())
        self.refresh()

    def _abrir_arbol(self) -> None:
        self._unica("arbol", lambda: VistaArbol(self, self.estado, self.refresh))

    def _abrir_bloque(self) -> None:
        DialogoBloque(self, self.estado, self.refresh)

    def _abrir_exportar(self) -> None:
        if not self.estado.seleccionadas():
            messagebox.showinfo("Nada que exportar",
                                "Agrega materias al horario primero.")
            return
        DialogoExportar(self, self.estado)

    def _abrir_plan(self) -> None:
        self._unica("plan", lambda: VistaPlan(self, self.estado))

    def _abrir_cursadas(self) -> None:
        self._unica("cursadas", lambda: DialogoCheck(self, self.estado, self.refresh,
                     conjunto=self.estado.cursadas,
                     titulo="Materias ya cursadas",
                     ayuda="Palomea las que ya aprobaste. Con el filtro "
                           "'Ocultar ya cursadas' desaparecen de la lista "
                           "(equivalencias incluidas)."))

    def _aplicar_combo(self, combo: frozenset) -> None:
        rama = self.estado.rama()
        rama.seleccion = list(combo)
        rama.candados = [i for i in rama.candados if i in rama.seleccion]
        self.refresh()

    def _rand_prev(self) -> None:
        if self._hist_i > 0:
            self._hist_i -= 1
            self._aplicar_combo(self._hist[self._hist_i])

    def _rand_next(self) -> None:
        if self._hist_i < len(self._hist) - 1:
            self._hist_i += 1
            self._aplicar_combo(self._hist[self._hist_i])
        else:
            self._aleatorio()

    def _click_horario(self, evento) -> None:
        for item in self.canvas_horario.find_withtag("current"):
            for tag in self.canvas_horario.gettags(item):
                profe = self._bloques_prof.get(tag)
                if profe:
                    self._abrir_foros_profesor(profe)
                    return
                op_id = self._bloques_horario.get(tag)
                if op_id:
                    candados = self.estado.rama().candados
                    if op_id in candados:
                        candados.remove(op_id)
                    else:
                        candados.append(op_id)
                    self.refresh()
                    return

    def _abrir_foros_profesor(self, profesor: str) -> None:
        import webbrowser
        from urllib.parse import quote_plus
        for plantilla in self.estado.foros:
            webbrowser.open(plantilla.replace("{profesor}", quote_plus(profesor.strip())))

    def _aleatorio(self) -> None:
        import random as _rnd
        from horario_saes.modulos.parser_saes import normalizar
        e = self.estado
        rama = e.rama()
        sel = e.seleccionadas()
        # fijas: candados + bloques propios seleccionados
        fijas = [op for op in sel if op.id in rama.candados or op.propia]
        cubiertas = set()
        for op in fijas:
            cubiertas.add(normalizar(op.materia))
            cubiertas |= e.equivalentes(op.materia)

        # slots objetivo: cada necesaria del check junta sus materias
        # equivalentes en UN solo slot; sin check, las inscritas ahorita
        slots: dict[str, list[str]] = {}
        if e.necesarias:
            for nec in sorted(e.necesarias):
                nn = normalizar(nec)
                if nn in cubiertas:
                    continue
                slots[nec] = [m for m in e.orden_materias
                              if normalizar(m) == nn or nn in e.equivalentes(m)]
        else:
            for op in sel:
                if not op.propia and normalizar(op.materia) not in cubiertas:
                    slots.setdefault(op.materia, [op.materia])
        if not slots:
            messagebox.showinfo("Random", "No hay materias que sortear: todo "
                                "está con candado o no hay check/selección.")
            return

        pools: dict[str, list] = {}
        sin_opciones = []
        for slot, mats in slots.items():
            pool = [op for m in mats for op in e.opciones_de(m)
                    if self._pasa_filtro(op)]
            if pool:
                pools[slot] = pool
            else:
                sin_opciones.append(slot)
        if not pools:
            messagebox.showinfo("Random", "Con estos filtros ninguna materia "
                                "objetivo tiene opciones.")
            return

        combos = e.combos_posibles(fijas, pools)
        actual = frozenset(rama.seleccion)
        if combos is not None:
            combos = [c for c in set(combos) if c != actual]
            nuevos = [c for c in combos if c not in self._combos_vistos]
            if not combos:
                messagebox.showinfo("Random", "Solo existe la combinación que "
                                    "ya tienes puesta con estos filtros.")
                return
            if not nuevos:
                messagebox.showinfo(
                    "Random",
                    f"¡Ya le diste la vuelta! Con estos filtros y candados hay "
                    f"{len(combos)} combinaciones posibles y ya las viste todas. "
                    f"(cambia filtros o candados para abrir más opciones)")
                return
            elegido = _rnd.choice(nuevos)
        else:
            # demasiadas combinaciones para enumerar: intento aleatorio
            from horario_saes.modulos.parser_saes import chocan
            elegido = None
            for _ in range(300):
                picks = list(fijas)
                for m in sorted(pools, key=lambda x: len(pools[x])):
                    cands = [op for op in pools[m]
                             if all(not chocan(op, otra) for otra in picks)]
                    if cands:
                        picks.append(_rnd.choice(cands))
                combo = frozenset(op.id for op in picks)
                if combo != actual and combo not in self._combos_vistos:
                    elegido = combo
                    break
            if elegido is None:
                messagebox.showinfo("Random", "No encontré una combinación "
                                    "nueva tras 300 intentos; probablemente ya "
                                    "las viste todas.")
                return

        self._combos_vistos.add(actual)
        self._combos_vistos.add(elegido)
        if not self._hist:
            self._hist.append(actual)
            self._hist_i = 0
        self._hist = self._hist[:self._hist_i + 1]
        self._hist.append(elegido)
        self._hist_i = len(self._hist) - 1
        self._aplicar_combo(elegido)
        if sin_opciones:
            self.lbl_check.config(
                text=f"(sin opciones con filtros: {len(sin_opciones)})   |",
                foreground="#E65100")

    def _abrir_check(self) -> None:
        self._unica("check", lambda: DialogoCheck(self, self.estado, self.refresh))

    def _ver_profesores(self, materia: str) -> None:
        self._unica(f"prof|{materia}", lambda: VistaProfesores(
            self, self.estado, materia, self.refresh))

    def _aplicar_max(self, *_):
        texto = self.var_max.get().strip().replace(",", ".")
        try:
            self.estado.max_creditos = float(texto) if texto else None
        except ValueError:
            self.var_max.set("" if self.estado.max_creditos is None
                             else f"{self.estado.max_creditos:g}")
            return
        self.refresh()

    def _editar_creditos(self, materia: str) -> None:
        actual = self.estado.creditos.get(materia)
        nuevo = simpledialog.askfloat(
            "Créditos", f"Créditos de {materia} (ahora: "
            f"{'SN' if actual is None else f'{actual:g}'})\n"
            f"Escribe -1 para regresarla a SN:",
            initialvalue=actual or 0, parent=self)
        if nuevo is not None:
            self.estado.fijar_creditos(materia, None if nuevo < 0 else nuevo)
            self.refresh()

    def _confirmar(self, titulo: str, mensaje: str) -> bool:
        """Diálogo con botones Continuar / Cancelar."""
        dlg = tk.Toplevel(self)
        dlg.title(titulo)
        dlg.resizable(False, False)
        dlg.grab_set()
        respuesta = {"ok": False}
        ttk.Label(dlg, text=mensaje, padding=16, justify="center").pack()
        botones = ttk.Frame(dlg)
        botones.pack(pady=(0, 12))

        def responder(ok: bool):
            respuesta["ok"] = ok
            dlg.destroy()

        ttk.Button(botones, text="Continuar",
                   command=lambda: responder(True)).pack(side="left", padx=6)
        ttk.Button(botones, text="Cancelar",
                   command=lambda: responder(False)).pack(side="left", padx=6)
        dlg.bind("<Escape>", lambda e: responder(False))
        dlg.transient(self)
        self.wait_window(dlg)
        return respuesta["ok"]

    def _toggle_opcion(self, op_id: str) -> None:
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
                        f"Estás superando tus créditos autorizados:\n"
                        f"{total + cred:g} de {e.max_creditos:g} permitidos.\n\n"
                        f"¿Quieres continuar?"):
                    return
            e.agregar(op_id)
        self.refresh()

    def _toggle_favorito(self, profesor: str) -> None:
        if profesor in self.estado.favoritos:
            self.estado.favoritos.discard(profesor)
        else:
            self.estado.favoritos.add(profesor)
        self.refresh()

    def _quitar_propia(self, op_id: str) -> None:
        if messagebox.askyesno("Eliminar bloque", "¿Eliminar este bloque propio?"):
            self.estado.quitar_propia(op_id)
            self.refresh()

    def _cambiar_rama(self, rama_id: int) -> None:
        self.estado.rama_actual = rama_id
        self.refresh()

    def _cerrar(self) -> None:
        self.estado.guardar()
        self.destroy()

    # ------------------------------------------------------------ refresh
    def refresh(self) -> None:
        self.bind_all("<MouseWheel>", self._rueda_global)
        if self.estado.rama_actual != self._ultima_rama:
            self._ultima_rama = self.estado.rama_actual
            self._hist.clear()
            self._hist_i = -1
        self.estado.guardar()
        self._refrescar_contadores()
        self._refrescar_lista()
        self._refrescar_inscritos()
        self._dibujar_horario()
        self._refrescar_ramas()

    def _refrescar_inscritos(self) -> None:
        for w in self.panel_insc.winfo_children():
            w.destroy()
        e = self.estado
        sel = sorted(e.seleccionadas(), key=lambda o: o.materia)
        ttk.Label(self.panel_insc, text=f"Inscribiendo ({len(sel)})",
                  font=("Segoe UI", 11, "bold"), padding=(8, 6)).pack(anchor="w")

        for op in sel:
            color = e.colores.get(op.materia, "#DDD")
            fila = tk.Frame(self.panel_insc, bg="white", bd=1, relief="solid")
            fila.pack(fill="x", padx=6, pady=2)
            tk.Frame(fila, bg=color, width=6).pack(side="left", fill="y")
            btn_x = tk.Label(fila, text="✕", bg="white", fg="#C62828",
                             font=("Segoe UI", 10, "bold"), cursor="hand2", padx=6)
            btn_x.pack(side="right")
            btn_x.bind("<Button-1>", lambda ev, i=op.id: self._toggle_opcion(i))
            marco = tk.Frame(fila, bg="white")
            marco.pack(side="left", fill="x", expand=True, padx=4, pady=2)
            nombre = op.materia if len(op.materia) < 30 else f"{op.materia[:29]}…"
            tk.Label(marco, text=nombre, bg="white", anchor="w",
                     font=("Segoe UI", 9, "bold")).pack(fill="x")
            cred = e.creditos.get(op.materia)
            detalle = f"{op.grupo} · {'SN' if cred is None else f'{cred:g} cr'}"
            tk.Label(marco, text=detalle, bg="white", anchor="w", fg="#546E7A",
                     font=("Segoe UI", 8)).pack(fill="x")

        if e.necesarias:
            faltan = e.faltantes()
            ttk.Separator(self.panel_insc).pack(fill="x", padx=6, pady=6)
            if faltan:
                ttk.Label(self.panel_insc, text=f"⚠ Faltan del check ({len(faltan)}):",
                          foreground="#C62828", font=("Segoe UI", 10, "bold"),
                          padding=(8, 0)).pack(anchor="w")
                for m in faltan:
                    nombre = m if len(m) < 32 else f"{m[:31]}…"
                    ttk.Label(self.panel_insc, text=f"• {nombre}",
                              foreground="#C62828", font=("Segoe UI", 8),
                              padding=(14, 0)).pack(anchor="w")
            else:
                ttk.Label(self.panel_insc, text="✔ Check completo",
                          foreground="#2E7D32", font=("Segoe UI", 10, "bold"),
                          padding=(8, 0)).pack(anchor="w")

    def _refrescar_contadores(self) -> None:
        e = self.estado
        sel = e.seleccionadas()
        total, sin_cred = e.total_creditos()
        cred = f"Créditos: {total:g}"
        excedido = False
        if e.max_creditos is not None:
            cred += f" / {e.max_creditos:g}"
            excedido = total > e.max_creditos
        if sin_cred:
            cred += f"  (⚠ {sin_cred} materia{'s' if sin_cred > 1 else ''} SN)"
        self.lbl_contadores.config(
            foreground="#C62828" if excedido else "#212121",
            text=(f"Opciones disponibles: {len(e.disponibles())}   |   "
                  f"Materias: {len(sel)}   |   {cred}   |   "
                  f"Horas/sem: {e.total_horas():g}"))
        if not e.necesarias:
            self.lbl_check.config(text="")
        else:
            faltan = len(e.faltantes())
            if faltan:
                self.lbl_check.config(text=f"⚠ Faltan {faltan} del check   |",
                                      foreground="#C62828")
            else:
                self.lbl_check.config(text="Check ✔   |", foreground="#2E7D32")
        try:
            foco = self.focus_get()
        except KeyError:
            foco = None
        if foco is None or foco.winfo_class() != "TEntry":
            self.var_max.set("" if e.max_creditos is None else f"{e.max_creditos:g}")

    # ------------------------------------------------------- lista lateral
    def _pasa_filtro(self, op) -> bool:
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

    def _click_lista(self, _evento) -> None:
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

    def _click_der_lista(self, _evento) -> None:
        accion = self._accion_bajo_cursor()
        if accion and accion[0] in ("hdr", "prof"):
            self._editar_creditos(accion[1])

    def _accion_bajo_cursor(self) -> tuple[str, str] | None:
        for item in self.canvas_lista.find_withtag("current"):
            for tag in self.canvas_lista.gettags(item):
                if tag in self._acciones_lista:
                    return self._acciones_lista[tag]
        return None

    def _refrescar_lista(self) -> None:
        cv = self.canvas_lista
        vista_y = cv.yview()[0]
        cv.delete("all")
        self._acciones_lista.clear()
        e = self.estado
        seleccion = set(e.rama().seleccion)
        ancho = max(cv.winfo_width(), 200)

        if not e.opciones:
            cv.create_text(ancho / 2, 60, text="Carga el TXT del SAES\npara empezar 📂",
                           fill=GRIS, font=("Segoe UI", 11), justify="center")
            return

        y = 4
        n = 0
        for materia in e.orden_materias:
            ops = [op for op in e.opciones_de(materia) if self._pasa_filtro(op)]
            compatibles = [op for op in ops
                           if op.id in seleccion or e.es_compatible(op)]
            if self.filtros["ocultar_incompatibles"]:
                ops = compatibles
            if not ops:
                continue
            color = e.colores.get(materia, "#DDD")
            cred = e.creditos.get(materia)
            etiqueta_cred = "SN" if cred is None else f"{cred:g} cr"

            # cabecera de materia (click = plegar/desplegar)
            plegada = materia in e.colapsadas
            tag_h, tag_p = f"h{n}", f"p{n}"
            n += 1
            self._acciones_lista[tag_h] = ("hdr", materia)
            self._acciones_lista[tag_p] = ("prof", materia)
            y += 6
            cv.create_rectangle(4, y, ancho - 4, y + 26, fill=color, outline=color,
                                tags=(tag_h,))
            flecha = "▸" if plegada else "▾"
            texto_h = f"{flecha} {materia}  ({len(compatibles)}/{len(ops)}) · {etiqueta_cred}"
            if len(texto_h) > 42:
                texto_h = f"{texto_h[:41]}…"
            cv.create_text(10, y + 13, text=texto_h, anchor="w",
                           font=("Segoe UI", 9, "bold"), tags=(tag_h,))
            cv.create_text(ancho - 18, y + 13, text="👥", font=("Segoe UI", 10),
                           tags=(tag_p,))
            y += 26
            if plegada:
                continue

            for op in sorted(ops, key=lambda o: o.grupo):
                elegida = op.id in seleccion
                compatible = elegida or e.es_compatible(op)
                if elegida:
                    bg, fg, borde, grosor = color, "#212121", "#455A64", 2
                elif compatible:
                    bg, fg, borde, grosor = "white", "#212121", "#B0BEC5", 1
                else:
                    bg, fg, borde, grosor = "#ECEFF1", "#B0BEC5", "#CFD8DC", 1

                tag_op = f"o{n}"
                n += 1
                if compatible:
                    self._acciones_lista[tag_op] = ("op", op.id)
                y += 2
                cv.create_rectangle(10, y, ancho - 8, y + 46, fill=bg,
                                    outline=borde, width=grosor, tags=(tag_op,))
                marca = "✔ " if elegida else ("" if compatible else "✖ ")
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
                    cv.create_text(ancho - 22, y + 10, text="🗑",
                                   font=("Segoe UI", 9), tags=(tag_ex,))
                else:
                    fav = op.profesor in self.estado.favoritos
                    self._acciones_lista[tag_ex] = ("fav", op.profesor)
                    cv.create_text(ancho - 22, y + 10, text="★" if fav else "☆",
                                   fill="#F9A825" if fav else "#90A4AE",
                                   font=("Segoe UI", 11), tags=(tag_ex,))
                y += 46

        cv.configure(scrollregion=(0, 0, ancho, y + 8))
        cv.yview_moveto(vista_y)

    # ---------------------------------------------------------- horario
    def _dibujar_horario(self, canvas: tk.Canvas | None = None,
                         rama=None, mini: bool = False,
                         dims: tuple[int, int] | None = None) -> None:
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

        def y_de(minutos: int) -> float:
            return m_sup + (minutos - HORA_INI * 60) * escala

        # rejilla
        for h in range(HORA_INI, HORA_FIN + 1):
            y = y_de(h * 60)
            cv.create_line(m_izq, y, ancho - 6, y, fill="#E0E0E0")
            if not mini:
                cv.create_text(m_izq - 6, y, text=f"{h}:00", anchor="e",
                               font=("Segoe UI", 8), fill=GRIS)
        for d in range(6):
            x = m_izq + d * col
            cv.create_line(x, m_sup, x, alto - m_inf, fill="#BDBDBD")
        if not mini:
            for d, nombre in enumerate(DIAS_LARGO):
                cv.create_text(m_izq + d * col + col / 2, m_sup / 2, text=nombre,
                               font=("Segoe UI", 10, "bold"), fill="#37474F")

        # bloques
        if not mini:
            self._bloques_horario.clear()
            self._bloques_prof.clear()
        candados = set(rama.candados)
        nb = 0
        for op in self.estado.seleccionadas(rama):
            color = self.estado.colores.get(op.materia, "#DDD")
            for s in op.sesiones:
                x1 = m_izq + s.dia * col + 2
                x2 = m_izq + (s.dia + 1) * col - 2
                y1, y2 = y_de(s.inicio), y_de(s.fin)
                extra = {"dash": (4, 2)} if op.propia else {}
                con_candado = op.id in candados
                etiquetas = ()
                idx = nb
                if not mini:
                    nb += 1
                    tag_b = f"blk{idx}"
                    self._bloques_horario[tag_b] = op.id
                    etiquetas = (tag_b,)
                cv.create_rectangle(x1, y1, x2, y2, fill=color,
                                    outline="#455A64",
                                    width=3 if con_candado else 1,
                                    tags=etiquetas, **extra)
                if not mini and con_candado:
                    cv.create_text(x2 - 11, y1 + 11, text="🔒",
                                   font=("Segoe UI", 10), tags=etiquetas)
                if not mini:
                    lugar = f" · {op.salon}" if op.salon and op.salon != "000" else ""
                    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                    if op.propia:
                        cv.create_text(cx, cy, text=f"{op.materia}\n{op.nota or ''}{lugar}",
                                       font=("Segoe UI", 8), justify="center",
                                       width=x2 - x1 - 6, tags=etiquetas)
                    else:
                        cv.create_text(cx, cy - 10, text=f"{op.grupo}-{op.materia}",
                                       font=("Segoe UI", 8), justify="center",
                                       width=x2 - x1 - 6, tags=etiquetas)
                        tag_pf = f"pf{idx}"
                        self._bloques_prof[tag_pf] = op.profesor
                        cv.create_text(cx, cy + 12, text=f"{op.profesor}{lugar}",
                                       font=("Segoe UI", 8, "underline"),
                                       fill="#0D47A1", justify="center",
                                       width=x2 - x1 - 6, tags=(tag_pf,), activefill="#1976D2")

    # ------------------------------------------------------------- ramas
    def _refrescar_ramas(self) -> None:
        for w in self.marco_ramas.winfo_children():
            w.destroy()
        e = self.estado
        actual = e.rama()
        self.lbl_rama.config(text=f"Rama: {actual.nombre}")

        for rama in e.familia():
            es_actual = rama.id == e.rama_actual
            if rama.padre is None and rama.id != actual.id:
                relacion = "padre" if actual.padre == rama.id else "raíz"
            elif rama.padre == actual.padre and not es_actual:
                relacion = "hermana"
            elif rama.padre == actual.id:
                relacion = "hija"
            elif actual.padre == rama.id:
                relacion = "padre"
            else:
                relacion = "actual"
            celda = tk.Frame(self.marco_ramas,
                             highlightthickness=2,
                             highlightbackground="#33691E" if es_actual else "#CFD8DC")
            celda.pack(side="left", padx=3)
            mini = tk.Canvas(celda, width=180, height=112, bg="white",
                             highlightthickness=0, cursor="hand2")
            mini.pack()
            tk.Label(celda, text=f"{rama.nombre} ({relacion})",
                     font=("Segoe UI", 8, "bold" if es_actual else "normal")).pack()
            mini.bind("<Button-1>", lambda ev, r=rama.id: self._cambiar_rama(r))
            self._dibujar_horario(mini, rama, mini=True, dims=(180, 112))


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()

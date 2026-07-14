import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from horario_saes.modulos.exportar import exportar_ramas
from horario_saes.modulos.iconos import FA, FONT_SOLID, FONT_REGULAR
from horario_saes.modulos.modelo import Estado
from horario_saes.modulos.parser_saes import DIAS, Sesion, fmt_hora
from horario_saes.modulos.reloj import RelojPicker


class DialogoExportar(tk.Toplevel):
    """Exportar el horario: rama actual, todas o las que elijas,
    en PDF (una página por hoja), PNG, JPG o SVG."""

    FORMATOS = ["PDF — una página por hoja", "PNG — imagen", "JPG — imagen", "SVG — vectorial"]

    def __init__(self, master, estado: Estado):
        super().__init__(master)
        self.title("Exportar horario")
        self.resizable(False, False)
        self.estado = estado
        self.grab_set()

        cuerpo = ttk.Frame(self, padding=14)
        cuerpo.pack(fill="both", expand=True)

        ttk.Label(cuerpo, text="¿Qué quieres exportar?",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.var_que = tk.StringVar(value="actual")
        ttk.Radiobutton(cuerpo, text=f"Solo esta hoja ({estado.rama().nombre})",
                        value="actual", variable=self.var_que,
                        command=self._actualizar).pack(anchor="w")
        ttk.Radiobutton(cuerpo, text=f"Todas las hojas ({len(estado.ramas)})",
                        value="todas", variable=self.var_que,
                        command=self._actualizar).pack(anchor="w")
        ttk.Radiobutton(cuerpo, text="Elegir cuáles:", value="elegir",
                        variable=self.var_que, command=self._actualizar).pack(anchor="w")

        self.marco_ramas = ttk.Frame(cuerpo, padding=(22, 2, 0, 2))
        self.marco_ramas.pack(anchor="w", fill="x")
        self.vars_ramas: dict[int, tk.BooleanVar] = {}
        self.checks: list[ttk.Checkbutton] = []
        for rama in estado.ramas.values():
            var = tk.BooleanVar(value=rama.id == estado.rama_actual)
            self.vars_ramas[rama.id] = var
            chk = ttk.Checkbutton(
                self.marco_ramas, variable=var,
                text=f"{rama.nombre} ({len(rama.seleccion)} materias)")
            chk.pack(anchor="w")
            self.checks.append(chk)

        ttk.Label(cuerpo, text="Formato:",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 2))
        self.var_formato = tk.StringVar(value=self.FORMATOS[0])
        ttk.Combobox(cuerpo, textvariable=self.var_formato, values=self.FORMATOS,
                     state="readonly", width=30).pack(anchor="w")

        botones = ttk.Frame(cuerpo)
        botones.pack(pady=(14, 0))
        ttk.Button(botones, text="Exportar", command=self._exportar).pack(side="left", padx=4)
        ttk.Button(botones, text="Cancelar", command=self.destroy).pack(side="left", padx=4)
        self._actualizar()

    def _actualizar(self) -> None:
        estado_chk = "normal" if self.var_que.get() == "elegir" else "disabled"
        for chk in self.checks:
            chk.configure(state=estado_chk)

    def _ramas_elegidas(self) -> list:
        que = self.var_que.get()
        if que == "actual":
            return [self.estado.rama()]
        if que == "todas":
            return list(self.estado.ramas.values())
        return [self.estado.ramas[i] for i, v in self.vars_ramas.items() if v.get()]

    def _exportar(self) -> None:
        ramas = self._ramas_elegidas()
        if not ramas:
            messagebox.showwarning("Nada que exportar",
                                   "Selecciona al menos una hoja.", parent=self)
            return
        formato = self.var_formato.get().split(" ")[0].lower()
        nombre = f"horario_{ramas[0].nombre}" if len(ramas) == 1 else "horarios"
        ruta = filedialog.asksaveasfilename(
            parent=self, title="Guardar como",
            initialfile=f"{nombre}.{formato}",
            defaultextension=f".{formato}",
            filetypes=[(formato.upper(), f"*.{formato}"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            creados = exportar_ramas(self.estado, ramas, formato, ruta)
        except OSError as e:
            messagebox.showerror("Error al exportar", str(e), parent=self)
            return
        nombres = "\n".join(p.name for p in creados)
        messagebox.showinfo("Exportado",
                            f"Se cre{'ó' if len(creados) == 1 else 'aron'} "
                            f"{len(creados)} archivo(s) en\n"
                            f"{Path(creados[0]).parent}:\n\n{nombres}", parent=self)
        self.destroy()


class VistaPlan(tk.Toplevel):
    """Tablas del plan de estudios: créditos por periodo y equivalencias
    con otras carreras (con los créditos de la materia propia)."""

    def __init__(self, master, estado: Estado):
        super().__init__(master)
        self.title("Plan de estudios y equivalencias")
        self.geometry("860x520")
        self.estado = estado

        if not estado.plan and not estado.equivalencias:
            ttk.Label(self, padding=20, justify="center", text=(
                "El txt cargado no trae tablas de plan/equivalencias.\n"
                "Pégalas al final del txt del SAES y vuelve a cargarlo.")).pack()
            return

        cuaderno = ttk.Notebook(self)
        cuaderno.pack(fill="both", expand=True)
        cuaderno.add(self._tab_creditos(cuaderno), text=" Créditos por periodo ")
        cuaderno.add(self._tab_equivalencias(cuaderno), text=" Equivalencias ")

    def _arbol(self, padre, columnas: list[tuple[str, str, int]]) -> ttk.Treeview:
        marco = ttk.Frame(padre)
        arbol = ttk.Treeview(marco, columns=[c[0] for c in columnas], show="tree headings")
        arbol.column("#0", width=110, stretch=False)
        for clave, titulo, ancho in columnas:
            arbol.heading(clave, text=titulo)
            arbol.column(clave, width=ancho, anchor="w" if ancho > 90 else "center",
                         stretch=ancho > 90)
        barra = ttk.Scrollbar(marco, orient="vertical", command=arbol.yview)
        arbol.configure(yscrollcommand=barra.set)
        arbol.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        return arbol

    def _tab_creditos(self, padre) -> ttk.Frame:
        arbol = self._arbol(padre, [
            ("clave", "Clave", 70), ("nombre", "Materia", 330),
            ("tipo", "Tipo", 100), ("cred", "Créditos", 70),
            ("ht", "H. teoría", 70), ("hp", "H. práctica", 75)])
        periodos: dict[str, str] = {}
        for p in self.estado.plan:
            if p.periodo not in periodos:
                total_p = sum(x.creditos for x in self.estado.plan
                              if x.periodo == p.periodo)
                periodos[p.periodo] = arbol.insert(
                    "", "end", text=f"Periodo {p.periodo}",
                    values=("", "", "", f"Σ {total_p:g}", "", ""), open=True)
            arbol.insert(periodos[p.periodo], "end", text="",
                         values=(p.clave, p.nombre, p.tipo.title(),
                                 f"{p.creditos:g}", f"{p.teoria:g}", f"{p.practica:g}"))
        return arbol.master

    def _tab_equivalencias(self, padre) -> ttk.Frame:
        arbol = self._arbol(padre, [
            ("clave_a", "Clave", 60), ("nombre_a", "Materia (mi plan)", 280),
            ("dir", "⇄", 40), ("clave_b", "Clave eq.", 70),
            ("nombre_b", "Materia equivalente", 280), ("cred", "Créditos", 70)])
        cred_por_clave = {p.clave: p.creditos for p in self.estado.plan}
        carreras: dict[str, str] = {}
        for eq in self.estado.equivalencias:
            letra = eq.clave_b[0]
            if letra not in carreras:
                carreras[letra] = arbol.insert("", "end", text=f"Carrera {letra}",
                                               open=True)
            cred = cred_por_clave.get(eq.clave_a)
            arbol.insert(carreras[letra], "end", text="", values=(
                eq.clave_a, eq.nombre_a, "⇄" if eq.doble else "→",
                eq.clave_b, eq.nombre_b,
                "SN" if cred is None else f"{cred:g}"))
        return arbol.master


class DialogoCheck(tk.Toplevel):
    """Checklist de materias sobre un conjunto del estado (necesarias o
    cursadas): palomea y se guarda al instante."""

    def __init__(self, master, estado: Estado, al_cambiar,
                 conjunto: set | None = None, titulo: str = "Check de materias por inscribir",
                 ayuda: str = "Palomea lo que necesitas meter este semestre. Una materia "
                              "cuenta como cubierta si inscribes su equivalencia."):
        super().__init__(master)
        self.title(titulo)
        self.geometry("520x560")
        self.estado = estado
        self.al_cambiar = al_cambiar
        self.conjunto = estado.necesarias if conjunto is None else conjunto

        ttk.Label(self, padding=(10, 6), justify="left", font=("Segoe UI", 9),
                  text=ayuda).pack(anchor="w")

        contenedor = ttk.Frame(self)
        contenedor.pack(fill="both", expand=True)
        canvas = tk.Canvas(contenedor, highlightthickness=0)
        barra = ttk.Scrollbar(contenedor, orient="vertical", command=canvas.yview)
        interior = ttk.Frame(canvas)
        interior.bind("<Configure>",
                      lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=interior, anchor="nw")
        canvas.configure(yscrollcommand=barra.set)
        canvas.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        canvas.bind("<Enter>", lambda e: canvas.bind_all(
            "<MouseWheel>", lambda ev: canvas.yview_scroll(
                -2 if ev.delta > 0 else 2, "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        estado_previo = set(self.conjunto)
        en_plan: set[str] = set()

        def agregar_check(marco, nombre: str, detalle: str = ""):
            if self.conjunto is estado.necesarias and estado.esta_cursada(nombre):
                self.conjunto.discard(nombre)
                ttk.Label(marco, text=f"✗ {nombre} — ya cursada",
                          font=("Segoe UI", 9, "overstrike"),
                          foreground="#B0BEC5").pack(anchor="w")
                return
            var = tk.BooleanVar(value=nombre in estado_previo)

            def cambio():
                if var.get():
                    self.conjunto.add(nombre)
                else:
                    self.conjunto.discard(nombre)
                self.al_cambiar()

            texto = f"{nombre}" + (f"   ({detalle})" if detalle else "")
            ttk.Checkbutton(marco, text=texto, variable=var,
                            command=cambio).pack(anchor="w")

        from horario_saes.modulos.parser_saes import normalizar
        periodos: dict[str, ttk.Labelframe] = {}
        for p in self.estado.plan:
            if p.periodo not in periodos:
                periodos[p.periodo] = ttk.Labelframe(
                    interior, text=f"Periodo {p.periodo}", padding=(8, 2))
                periodos[p.periodo].pack(fill="x", padx=8, pady=4)
            en_plan.add(normalizar(p.nombre))
            agregar_check(periodos[p.periodo], p.nombre,
                          f"{p.clave} · {p.creditos:g} cr")

        extras = [m for m in estado.orden_materias
                  if normalizar(m) not in en_plan
                  and not any(a in en_plan for a in estado.equivalentes(m))
                  and not any(op.propia for op in estado.opciones_de(m))]
        if extras:
            marco_ex = ttk.Labelframe(interior, text="Otras del horario", padding=(8, 2))
            marco_ex.pack(fill="x", padx=8, pady=4)
            for m in extras:
                agregar_check(marco_ex, m)

        ttk.Button(self, text="Cerrar", command=self.destroy).pack(pady=6)


class DialogoBloque(tk.Toplevel):
    """Alta de un bloque propio: nombre, días, horario con reloj, salón y nota."""

    def __init__(self, master, estado: Estado, al_aceptar):
        super().__init__(master)
        self.title("Nuevo bloque propio")
        self.resizable(False, False)
        self.estado = estado
        self.al_aceptar = al_aceptar
        self.grab_set()

        cuerpo = ttk.Frame(self, padding=12)
        cuerpo.pack(fill="both", expand=True)

        ttk.Label(cuerpo, text="Nombre del bloque:").grid(row=0, column=0, sticky="w")
        self.ent_nombre = ttk.Entry(cuerpo, width=34)
        self.ent_nombre.grid(row=0, column=1, sticky="we", pady=2)

        ttk.Label(cuerpo, text="Días:").grid(row=1, column=0, sticky="w")
        marco_dias = ttk.Frame(cuerpo)
        marco_dias.grid(row=1, column=1, sticky="w", pady=2)
        self.vars_dias = [tk.BooleanVar() for _ in DIAS]
        for i, dia in enumerate(DIAS):
            ttk.Checkbutton(marco_dias, text=dia, variable=self.vars_dias[i]
                            ).pack(side="left", padx=3)

        relojes = ttk.Frame(cuerpo)
        relojes.grid(row=2, column=0, columnspan=2, pady=8)
        self.reloj_ini = RelojPicker(relojes, "Inicio", 7 * 60)
        self.reloj_ini.pack(side="left", padx=8)
        self.reloj_fin = RelojPicker(relojes, "Fin", 9 * 60)
        self.reloj_fin.pack(side="left", padx=8)

        ttk.Label(cuerpo, text="Salón / lugar:").grid(row=3, column=0, sticky="w")
        self.ent_salon = ttk.Entry(cuerpo, width=34)
        self.ent_salon.grid(row=3, column=1, sticky="we", pady=2)

        ttk.Label(cuerpo, text="Nota / profesor:").grid(row=4, column=0, sticky="w")
        self.ent_nota = ttk.Entry(cuerpo, width=34)
        self.ent_nota.grid(row=4, column=1, sticky="we", pady=2)

        botones = ttk.Frame(cuerpo)
        botones.grid(row=5, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(botones, text="Agregar", command=self._aceptar).pack(side="left", padx=4)
        ttk.Button(botones, text="Cancelar", command=self.destroy).pack(side="left", padx=4)
        self.ent_nombre.focus_set()

    def _aceptar(self) -> None:
        nombre = self.ent_nombre.get().strip()
        dias = [i for i, v in enumerate(self.vars_dias) if v.get()]
        ini, fin = self.reloj_ini.get_minutos(), self.reloj_fin.get_minutos()
        if not nombre:
            messagebox.showwarning("Falta nombre", "Ponle nombre al bloque.", parent=self)
            return
        if not dias:
            messagebox.showwarning("Faltan días", "Selecciona al menos un día.", parent=self)
            return
        if fin <= ini:
            messagebox.showwarning("Horario inválido",
                                   "La hora de fin debe ser mayor a la de inicio.", parent=self)
            return
        sesiones = [Sesion(d, ini, fin) for d in dias]
        self.estado.agregar_propia(nombre, sesiones, self.ent_salon.get().strip(),
                                   self.ent_nota.get().strip())
        self.al_aceptar()
        self.destroy()


class DialogoFiltro(tk.Toplevel):
    """Filtros de la lista lateral, con actualización inmediata."""

    def __init__(self, master, filtros: dict, al_cambiar):
        super().__init__(master)
        self.title("Filtrar opciones")
        self.resizable(False, False)
        self.attributes("-topmost", True)

        cuerpo = ttk.Frame(self, padding=12)
        cuerpo.pack(fill="both", expand=True)

        ttk.Label(cuerpo, text="Buscar (materia / profe / grupo):").pack(anchor="w")
        self.var_texto = tk.StringVar(value=filtros["texto"])
        ent = ttk.Entry(cuerpo, textvariable=self.var_texto, width=32)
        ent.pack(fill="x", pady=(0, 8))
        ent.focus_set()

        self.var_fav = tk.BooleanVar(value=filtros["solo_favoritos"])
        self.var_incomp = tk.BooleanVar(value=filtros["ocultar_incompatibles"])
        self.var_check = tk.BooleanVar(value=filtros["solo_check"])
        self.var_cursadas = tk.BooleanVar(value=filtros["ocultar_cursadas"])
        ttk.Checkbutton(cuerpo, text="Solo profesores favoritos",
                        variable=self.var_fav).pack(anchor="w")
        ttk.Checkbutton(cuerpo, text="Ocultar opciones incompatibles",
                        variable=self.var_incomp).pack(anchor="w")
        ttk.Checkbutton(cuerpo, text="Solo materias del check ✅",
                        variable=self.var_check).pack(anchor="w")
        ttk.Checkbutton(cuerpo, text="Ocultar ya cursadas 🎓",
                        variable=self.var_cursadas).pack(anchor="w")

        ttk.Label(cuerpo, text="Días:").pack(anchor="w", pady=(8, 0))
        marco_dias = ttk.Frame(cuerpo)
        marco_dias.pack(anchor="w")
        self.vars_dias = [tk.BooleanVar(value=v) for v in filtros["dias"]]
        for i, d in enumerate(("Lun", "Mar", "Mie", "Jue", "Vie")):
            ttk.Checkbutton(marco_dias, text=d, variable=self.vars_dias[i]
                            ).pack(side="left", padx=2)

        ttk.Label(cuerpo, text="Rango de horas:").pack(anchor="w", pady=(8, 0))
        self.var_hini = tk.IntVar(value=filtros["hora_ini"])
        self.var_hfin = tk.IntVar(value=filtros["hora_fin"])
        for var, texto in ((self.var_hini, "desde"), (self.var_hfin, "hasta")):
            fila = ttk.Frame(cuerpo)
            fila.pack(fill="x")
            ttk.Label(fila, text=texto, width=6).pack(side="left")
            etiqueta = ttk.Label(fila, text=f"{var.get()}:00", width=6)
            escala = ttk.Scale(fila, from_=7, to=22, variable=var,
                               command=lambda v, va=var, et=etiqueta: (
                                   va.set(round(float(v))),
                                   et.config(text=f"{va.get()}:00")))
            escala.pack(side="left", fill="x", expand=True, padx=4)
            etiqueta.pack(side="left")

        ttk.Label(cuerpo, text="Turno:").pack(anchor="w", pady=(8, 0))
        self.var_turno = tk.StringVar(value=filtros["turno"])
        for texto, valor in (("Todos", "todos"), ("Matutino (antes de 15:00)", "mat"),
                             ("Vespertino (15:00 en adelante)", "vesp")):
            ttk.Radiobutton(cuerpo, text=texto, value=valor,
                            variable=self.var_turno).pack(anchor="w")

        def aplicar(*_):
            filtros["texto"] = self.var_texto.get()
            filtros["solo_favoritos"] = self.var_fav.get()
            filtros["ocultar_incompatibles"] = self.var_incomp.get()
            filtros["turno"] = self.var_turno.get()
            filtros["solo_check"] = self.var_check.get()
            filtros["ocultar_cursadas"] = self.var_cursadas.get()
            filtros["dias"] = [v.get() for v in self.vars_dias]
            if self.var_hfin.get() < self.var_hini.get():
                self.var_hfin.set(self.var_hini.get())
            filtros["hora_ini"] = self.var_hini.get()
            filtros["hora_fin"] = self.var_hfin.get()
            al_cambiar()

        for var in (self.var_texto, self.var_fav, self.var_incomp, self.var_turno,
                    self.var_check, self.var_cursadas, self.var_hini, self.var_hfin,
                    *self.vars_dias):
            var.trace_add("write", aplicar)

        def limpiar():
            self.var_texto.set("")
            self.var_fav.set(False)
            self.var_incomp.set(False)
            self.var_turno.set("todos")
            self.var_check.set(False)
            self.var_cursadas.set(False)
            for v in self.vars_dias:
                v.set(True)
            self.var_hini.set(7)
            self.var_hfin.set(22)

        botones = ttk.Frame(cuerpo)
        botones.pack(pady=(10, 0))
        ttk.Button(botones, text="Limpiar", command=limpiar).pack(side="left", padx=4)
        ttk.Button(botones, text="Cerrar", command=self.destroy).pack(side="left", padx=4)


class VistaProfesores(tk.Toplevel):
    """Qué profesores dan una materia, con sus grupos y estrella de favorito."""

    def __init__(self, master, estado: Estado, materia: str, al_cambiar):
        super().__init__(master)
        self.title(f"Profesores — {materia}")
        self.geometry("560x420")
        self.estado = estado
        self.materia = materia
        self.al_cambiar = al_cambiar

        color = estado.colores.get(materia, "#DDD")
        tk.Label(self, text=materia, bg=color, font=("Segoe UI", 12, "bold"),
                 pady=6).pack(fill="x")

        contenedor = ttk.Frame(self)
        contenedor.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(contenedor, highlightthickness=0)
        barra = ttk.Scrollbar(contenedor, orient="vertical", command=self.canvas.yview)
        self.interior = ttk.Frame(self.canvas)
        self.interior.bind("<Configure>",
                           lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.interior, anchor="nw")
        self.canvas.configure(yscrollcommand=barra.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", self._rueda)
        self.bind("<Destroy>", lambda e: self.canvas.unbind_all("<MouseWheel>")
                  if e.widget is self else None)
        self._llenar()

    def _rueda(self, evento) -> None:
        self.canvas.yview_scroll(-1 if evento.delta > 0 else 1, "units")

    def _llenar(self) -> None:
        for w in self.interior.winfo_children():
            w.destroy()
        profes = self.estado.profesores_de(self.materia)
        ordenados = sorted(profes.items(),
                           key=lambda kv: (kv[0] not in self.estado.favoritos, kv[0]))
        for profesor, ops in ordenados:
            fila = ttk.Frame(self.interior, padding=(8, 4))
            fila.pack(fill="x")
            fav = profesor in self.estado.favoritos
            estrella = tk.Label(fila, text=FA.STAR, cursor="hand2",
                                font=(FONT_SOLID if fav else FONT_REGULAR, 13),
                                fg="#F9A825" if fav else "#B0BEC5")
            estrella.pack(side="left")
            estrella.bind("<Button-1>", lambda e, p=profesor: self._toggle(p))
            marco = ttk.Frame(fila)
            marco.pack(side="left", fill="x", expand=True, padx=6)
            ttk.Label(marco, text=profesor, font=("Segoe UI", 10, "bold")).pack(anchor="w")
            for op in ops:
                ttk.Label(marco, text=f"   {op.grupo} · {op.resumen_horario()}",
                          font=("Segoe UI", 9), foreground="#546E7A").pack(anchor="w")
        total = len(profes)
        ttk.Label(self.interior, text=f"{total} profesor(es)",
                  font=("Segoe UI", 9, "italic")).pack(anchor="w", padx=8, pady=6)

    def _toggle(self, profesor: str) -> None:
        if profesor in self.estado.favoritos:
            self.estado.favoritos.discard(profesor)
        else:
            self.estado.favoritos.add(profesor)
        self._llenar()
        self.al_cambiar()


class VistaArbol(tk.Toplevel):
    """Vista macro del árbol de ramas. Click = cambiar, doble click = renombrar,
    click derecho = eliminar rama."""

    def __init__(self, master, estado: Estado, al_cambiar):
        super().__init__(master)
        self.title("Árbol de ramas")
        self.geometry("640x440")
        self.estado = estado
        self.al_cambiar = al_cambiar
        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self._dibujar())
        ttk.Label(self, text="Click: cambiar a rama · Doble click: renombrar · "
                             "Click derecho: eliminar").pack(pady=3)

    def _dibujar(self) -> None:
        cv = self.canvas
        cv.delete("all")
        estado = self.estado

        niveles: dict[int, list] = {}

        def recorrer(rama, prof: int):
            niveles.setdefault(prof, []).append(rama)
            for hijo in estado.hijos(rama.id):
                recorrer(hijo, prof + 1)

        raices = [r for r in estado.ramas.values() if r.padre is None]
        for raiz in raices:
            recorrer(raiz, 0)

        ancho = max(cv.winfo_width(), 400)
        pos: dict[int, tuple[float, float]] = {}
        for prof, ramas in niveles.items():
            paso = ancho / (len(ramas) + 1)
            for i, rama in enumerate(ramas):
                pos[rama.id] = ((i + 1) * paso, 60 + prof * 95)

        for rama in estado.ramas.values():
            if rama.padre in pos and rama.id in pos:
                x1, y1 = pos[rama.padre]
                x2, y2 = pos[rama.id]
                cv.create_line(x1, y1 + 28, x2, y2 - 28, fill="#90A4AE", width=2)

        for rama in estado.ramas.values():
            x, y = pos[rama.id]
            actual = rama.id == estado.rama_actual
            n_mat = len(rama.seleccion)
            caja = cv.create_rectangle(
                x - 62, y - 28, x + 62, y + 28,
                fill="#C5E1A5" if actual else "#ECEFF1",
                outline="#33691E" if actual else "#90A4AE",
                width=3 if actual else 1,
            )
            texto = cv.create_text(x, y, text=f"{rama.nombre}\n{n_mat} materias",
                                   font=("Segoe UI", 9, "bold" if actual else "normal"),
                                   justify="center")
            for item in (caja, texto):
                cv.tag_bind(item, "<Button-1>", lambda e, r=rama.id: self._cambiar(r))
                cv.tag_bind(item, "<Double-Button-1>", lambda e, r=rama.id: self._renombrar(r))
                cv.tag_bind(item, "<Button-3>", lambda e, r=rama.id: self._eliminar(r))

    def _cambiar(self, rama_id: int) -> None:
        self.estado.rama_actual = rama_id
        self._dibujar()
        self.al_cambiar()

    def _renombrar(self, rama_id: int) -> None:
        rama = self.estado.ramas[rama_id]
        nombre = simpledialog.askstring("Renombrar rama", "Nuevo nombre:",
                                        initialvalue=rama.nombre, parent=self)
        if nombre and nombre.strip():
            rama.nombre = nombre.strip()
            self._dibujar()
            self.al_cambiar()

    def _eliminar(self, rama_id: int) -> None:
        if rama_id == 1:
            messagebox.showinfo("No se puede", "La rama principal no se elimina.",
                                parent=self)
            return
        rama = self.estado.ramas[rama_id]
        if messagebox.askyesno("Eliminar rama", f"¿Eliminar '{rama.nombre}'?",
                               parent=self):
            self.estado.eliminar_rama(rama_id)
            self._dibujar()
            self.al_cambiar()

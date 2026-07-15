import json
from dataclasses import dataclass, field
from pathlib import Path

from horario_saes.modulos.parser_saes import (Equivalencia, MateriaPlan, Opcion, Sesion,
                                 chocan, emparejar_credito, normalizar, parsear)

PALETA = [
    "#80DEEA", "#F06292", "#CE93D8", "#EF5350", "#B39DDB",
    "#7986CB", "#AED581", "#FFB74D", "#FFAB91", "#4FC3F7",
    "#FFF176", "#A5D6A7", "#F48FB1", "#90CAF9", "#BCAAA4",
    "#E6EE9C", "#80CBC4", "#FFCC80", "#9FA8DA", "#EF9A9A",
]


@dataclass
class Rama:
    id: int
    nombre: str
    padre: int | None = None
    seleccion: list[str] = field(default_factory=list)
    candados: list[str] = field(default_factory=list)


class Estado:
    def __init__(self, ruta_sesion: Path):
        self.ruta_sesion = ruta_sesion
        self.opciones: dict[str, Opcion] = {}
        self.orden_materias: list[str] = []
        self.colores: dict[str, str] = {}
        self.favoritos: set[str] = set()
        self.creditos: dict[str, float | None] = {}   # None = SN (sin créditos)
        self.creditos_manuales: set[str] = set()
        self.creditos_txt: dict[str, float] = {}      # normalizado -> créditos
        self.max_creditos: float | None = None
        self.colapsadas: set[str] = set()             # materias plegadas en la lista
        self.plan: list[MateriaPlan] = []
        self.equivalencias: list[Equivalencia] = []
        self.necesarias: set[str] = set()             # checklist de materias por inscribir
        self.cursadas: set[str] = set()               # materias ya aprobadas
        self.foros: list[str] = [
            "https://foroupiicsa.net/diccionario/buscar/{profesor}",
            "https://www.misprofesores.com/Buscar?buscar=Profesores&q={profesor}"]
        self.ramas: dict[int, Rama] = {1: Rama(1, "Principal")}
        self.rama_actual = 1
        self._next_rama = 2
        self._next_propia = 1
        self.ruta_txt: str | None = None

    # ------------------------------------------------------------- carga
    def cargar_txt(self, ruta: str) -> int:
        nuevas, self.creditos_txt, self.plan, self.equivalencias = parsear(ruta)
        propias = [op for op in self.opciones.values() if op.propia]
        self.opciones = {op.id: op for op in nuevas}
        for op in propias:
            self.opciones[op.id] = op
        self.ruta_txt = ruta
        self._reindexar_materias()
        # limpiar selecciones que ya no existen
        for rama in self.ramas.values():
            rama.seleccion = [i for i in rama.seleccion if i in self.opciones]
        return len(nuevas)

    def _reindexar_materias(self) -> None:
        self.orden_materias = []
        for op in self.opciones.values():
            if op.materia not in self.orden_materias:
                self.orden_materias.append(op.materia)
        for i, mat in enumerate(self.orden_materias):
            self.colores.setdefault(mat, PALETA[i % len(PALETA)])
            if mat in self.creditos_manuales:
                continue
            self.creditos[mat] = self._credito_con_equivalencias(mat)

    def _credito_con_equivalencias(self, materia: str) -> float | None:
        valor = emparejar_credito(materia, self.creditos_txt)
        if valor is not None:
            return valor
        for alt in self.equivalentes(materia):
            valor = emparejar_credito(alt, self.creditos_txt)
            if valor is not None:
                return valor
        return None

    def equivalentes(self, materia: str) -> set[str]:
        """Nombres (normalizados) equivalentes a la materia en ambas direcciones."""
        nombre = normalizar(materia)
        res: set[str] = set()
        for eq in self.equivalencias:
            na, nb = normalizar(eq.nombre_a), normalizar(eq.nombre_b)
            if nombre == na:
                res.add(nb)
            elif nombre == nb:
                res.add(na)
        return res

    def clave_de(self, materia: str) -> str | None:
        nombre = normalizar(materia)
        for p in self.plan:
            if normalizar(p.nombre) == nombre:
                return p.clave
        return None

    def faltantes(self, rama: Rama | None = None) -> list[str]:
        """Materias del check que la selección aún no cubre (directo o por
        equivalencia)."""
        cubiertas: set[str] = set()
        for op in self.seleccionadas(rama):
            cubiertas.add(normalizar(op.materia))
            cubiertas |= self.equivalentes(op.materia)
        return [m for m in sorted(self.necesarias)
                if normalizar(m) not in cubiertas]

    def fijar_creditos(self, materia: str, valor: float | None) -> None:
        self.creditos[materia] = valor
        if valor is None:
            self.creditos_manuales.discard(materia)
        else:
            self.creditos_manuales.add(materia)

    def opciones_de(self, materia: str) -> list[Opcion]:
        return [op for op in self.opciones.values() if op.materia == materia]

    def profesores_de(self, materia: str) -> dict[str, list[Opcion]]:
        profes: dict[str, list[Opcion]] = {}
        for op in self.opciones_de(materia):
            profes.setdefault(op.profesor, []).append(op)
        return profes

    # ------------------------------------------------------------- ramas
    def rama(self) -> Rama:
        return self.ramas[self.rama_actual]

    def hijos(self, rama_id: int) -> list[Rama]:
        return [r for r in self.ramas.values() if r.padre == rama_id]

    def bifurcar(self, nombre: str = "") -> Rama:
        actual = self.rama()
        nombre = nombre or f"{actual.nombre}.{len(self.hijos(actual.id)) + 1}"
        nueva = Rama(self._next_rama, nombre, actual.id, list(actual.seleccion),
                     list(actual.candados))
        self.ramas[nueva.id] = nueva
        self._next_rama += 1
        self.rama_actual = nueva.id
        return nueva

    def eliminar_rama(self, rama_id: int) -> bool:
        if rama_id == 1:
            return False
        rama = self.ramas.pop(rama_id)
        for hijo in self.hijos(rama_id):
            hijo.padre = rama.padre
        if self.rama_actual == rama_id:
            self.rama_actual = rama.padre or 1
        return True

    def familia(self) -> list[Rama]:
        """Ramas aledañas: padre, hermanas (incluida la actual) e hijas."""
        actual = self.rama()
        vistas: list[Rama] = []
        if actual.padre is not None:
            vistas.append(self.ramas[actual.padre])
            vistas.extend(self.hijos(actual.padre))
        else:
            vistas.append(actual)
        vistas.extend(self.hijos(actual.id))
        unicas: list[Rama] = []
        for r in vistas:
            if r not in unicas:
                unicas.append(r)
        return unicas

    # ---------------------------------------------------------- seleccion
    def seleccionadas(self, rama: Rama | None = None) -> list[Opcion]:
        rama = rama or self.rama()
        return [self.opciones[i] for i in rama.seleccion if i in self.opciones]

    def es_compatible(self, op: Opcion, rama: Rama | None = None) -> bool:
        for sel in self.seleccionadas(rama):
            if sel.id == op.id:
                continue
            if sel.materia == op.materia or chocan(sel, op):
                return False
        return True

    def disponibles(self, rama: Rama | None = None) -> list[Opcion]:
        rama = rama or self.rama()
        tomadas = {op.materia for op in self.seleccionadas(rama)}
        return [
            op for op in self.opciones.values()
            if op.materia not in tomadas and self.es_compatible(op, rama)
        ]

    def agregar(self, op_id: str) -> bool:
        op = self.opciones[op_id]
        if op_id in self.rama().seleccion or not self.es_compatible(op):
            return False
        self.rama().seleccion.append(op_id)
        return True

    def quitar(self, op_id: str) -> None:
        if op_id in self.rama().seleccion:
            self.rama().seleccion.remove(op_id)
        if op_id in self.rama().candados:
            self.rama().candados.remove(op_id)

    def esta_cursada(self, materia: str) -> bool:
        cursadas_n = {normalizar(c) for c in self.cursadas}
        if normalizar(materia) in cursadas_n:
            return True
        return bool(self.equivalentes(materia) & cursadas_n)

    def combos_posibles(self, fijas: list[Opcion], pools: dict[str, list[Opcion]],
                        cap: int = 4000) -> list[frozenset[str]] | None:
        """Enumera todas las combinaciones completas (una opcion por materia de
        pools, compatibles entre si y con fijas). None si supera cap combos."""
        materias = sorted(pools, key=lambda m: len(pools[m]))
        combos: list[frozenset[str]] = []
        base = [op.id for op in fijas]

        def rec(i: int, elegidas: list) -> bool:
            if len(combos) > cap:
                return False
            if i == len(materias):
                combos.append(frozenset(base + [op.id for op in elegidas]))
                return True
            for op in pools[materias[i]]:
                if all(not chocan(op, o) for o in elegidas)                         and all(not chocan(op, f) for f in fijas):
                    if not rec(i + 1, elegidas + [op]):
                        return False
            return True

        completo = rec(0, [])
        return combos if completo else None

    # ------------------------------------------------------------ propias
    def agregar_propia(self, nombre: str, sesiones: list[Sesion],
                       salon: str, nota: str) -> Opcion:
        op = Opcion(
            grupo=f"PROPIO{self._next_propia}", materia=nombre, profesor=nota or "—",
            edificio="", salon=salon, sesiones=sesiones, propia=True, nota=nota,
        )
        self._next_propia += 1
        self.opciones[op.id] = op
        self._reindexar_materias()
        if self.es_compatible(op):
            self.rama().seleccion.append(op.id)
        return op

    def quitar_propia(self, op_id: str) -> None:
        op = self.opciones.get(op_id)
        if not op or not op.propia:
            return
        del self.opciones[op_id]
        for rama in self.ramas.values():
            if op_id in rama.seleccion:
                rama.seleccion.remove(op_id)
        self._reindexar_materias()

    # ----------------------------------------------------------- metricas
    def total_creditos(self, rama: Rama | None = None) -> tuple[float, int]:
        """Devuelve (suma de créditos, materias SN sin créditos asignados)."""
        total, sin_creditos = 0.0, 0
        for op in self.seleccionadas(rama):
            cred = self.creditos.get(op.materia)
            if cred is None:
                if not op.propia:
                    sin_creditos += 1
            else:
                total += cred
        return total, sin_creditos

    def total_horas(self, rama: Rama | None = None) -> float:
        return sum(op.horas_semana() for op in self.seleccionadas(rama))

    # -------------------------------------------------------- persistencia
    def guardar(self) -> None:
        propias = [
            {
                "grupo": op.grupo, "materia": op.materia, "profesor": op.profesor,
                "salon": op.salon, "nota": op.nota,
                "sesiones": [[s.dia, s.inicio, s.fin] for s in op.sesiones],
            }
            for op in self.opciones.values() if op.propia
        ]
        datos = {
            "ruta_txt": self.ruta_txt,
            "favoritos": sorted(self.favoritos),
            "creditos": self.creditos,
            "creditos_manuales": sorted(self.creditos_manuales),
            "max_creditos": self.max_creditos,
            "colapsadas": sorted(self.colapsadas),
            "necesarias": sorted(self.necesarias),
            "cursadas": sorted(self.cursadas),
            "foros": self.foros,
            "colores": self.colores,
            "propias": propias,
            "rama_actual": self.rama_actual,
            "next_rama": self._next_rama,
            "next_propia": self._next_propia,
            "ramas": [
                {"id": r.id, "nombre": r.nombre, "padre": r.padre,
                 "seleccion": r.seleccion, "candados": r.candados}
                for r in self.ramas.values()
            ],
        }
        self.ruta_sesion.parent.mkdir(parents=True, exist_ok=True)
        self.ruta_sesion.write_text(json.dumps(datos, indent=1, ensure_ascii=False),
                                    encoding="utf-8")

    def cargar_sesion(self) -> bool:
        if not self.ruta_sesion.exists():
            return False
        datos = json.loads(self.ruta_sesion.read_text(encoding="utf-8"))
        self.favoritos = set(datos.get("favoritos", []))
        self.creditos = datos.get("creditos", {})
        self.creditos_manuales = set(datos.get("creditos_manuales", []))
        self.max_creditos = datos.get("max_creditos")
        self.colapsadas = set(datos.get("colapsadas", []))
        self.necesarias = set(datos.get("necesarias", []))
        self.cursadas = set(datos.get("cursadas", []))
        self.foros = datos.get("foros") or self.foros
        self.colores = datos.get("colores", {})
        self._next_rama = datos.get("next_rama", 2)
        self._next_propia = datos.get("next_propia", 1)
        ruta = datos.get("ruta_txt")
        if ruta and Path(ruta).exists():
            self.cargar_txt(ruta)
        for p in datos.get("propias", []):
            op = Opcion(
                grupo=p["grupo"], materia=p["materia"], profesor=p["profesor"],
                edificio="", salon=p["salon"], propia=True, nota=p["nota"],
                sesiones=[Sesion(*s) for s in p["sesiones"]],
            )
            self.opciones[op.id] = op
        self._reindexar_materias()
        ramas = datos.get("ramas", [])
        if ramas:
            self.ramas = {
                r["id"]: Rama(r["id"], r["nombre"], r["padre"],
                              [i for i in r["seleccion"] if i in self.opciones],
                              [i for i in r.get("candados", []) if i in self.opciones])
                for r in ramas
            }
            self.rama_actual = datos.get("rama_actual", 1)
            if self.rama_actual not in self.ramas:
                self.rama_actual = next(iter(self.ramas))
        return True

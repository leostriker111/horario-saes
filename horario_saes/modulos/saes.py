"""Scraper del SAES (beta): login con captcha y descarga de horarios,
equivalencias, kardex (cursadas) y mapa curricular.

El SAES es ASP.NET WebForms: cada página exige __VIEWSTATE/__EVENTVALIDATION,
por eso todo va sobre una misma sesión de requests. Las rutas son iguales en
casi todas las escuelas; algunas agregan o quitan pestañas.
"""
import re

import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

RE_CLAVE = re.compile(r"^[A-Z]\d{3}$")


def _a_num(celda: str):
    try:
        return float(celda.replace(",", ".").strip())
    except (ValueError, AttributeError):
        return None

# Rutas conocidas del SAES (relativas a la base de cada escuela)
RUTA_LOGIN = "/"
RUTA_HORARIOS = "/Academica/horarios.aspx"
RUTA_EQUIVALENCIAS = "/Academica/Equivalencias.aspx"
RUTA_MAPA = "/Academica/mapa_curricular.aspx"
RUTA_KARDEX = "/Alumnos/boleta/kardex.aspx"

# Superior (NS)
ESCUELAS_NS = {
    "UPIICSA": "https://www.saes.upiicsa.ipn.mx",
    "ESCA Sto. Tomás": "https://www.saes.escasto.ipn.mx",
    "ESCA Tepepan": "https://www.saes.escatep.ipn.mx",
    "ESCOM": "https://www.saes.escom.ipn.mx",
    "ESIME Zacatenco": "https://www.saes.esimez.ipn.mx",
    "ESIME Culhuacán": "https://www.saes.esimecu.ipn.mx",
    "ESIME Azcapotzalco": "https://www.saes.esimeazc.ipn.mx",
    "ESIME Ticomán": "https://www.saes.esimetic.ipn.mx",
    "ESIA Zacatenco": "https://www.saes.esiaz.ipn.mx",
    "ESIA Tecamachalco": "https://www.saes.esiatec.ipn.mx",
    "ESIA Ticomán": "https://www.saes.esiatic.ipn.mx",
    "ESIQIE": "https://www.saes.esiqie.ipn.mx",
    "ESFM": "https://www.saes.esfm.ipn.mx",
    "ESIT": "https://www.saes.esit.ipn.mx",
    "ENCB": "https://www.saes.encb.ipn.mx",
    "ENMH": "https://www.saes.enmh.ipn.mx",
    "ENBA": "https://www.saes.enba.ipn.mx",
    "ESM": "https://www.saes.esm.ipn.mx",
    "ESEO": "https://www.saes.eseo.ipn.mx",
    "ESE (Economía)": "https://www.saes.ese.ipn.mx",
    "EST": "https://www.saes.est.ipn.mx",
    "UPIBI": "https://www.saes.upibi.ipn.mx",
    "UPIITA": "https://www.saes.upiita.ipn.mx",
    "UPIEM": "https://www.saes.upiem.ipn.mx",
    "UPIIG": "https://www.saes.upiig.ipn.mx",
    "UPIIH": "https://www.saes.upiih.ipn.mx",
    "UPIIT": "https://www.saes.upiit.ipn.mx",
    "UPIIP": "https://www.saes.upiip.ipn.mx",
    "UPIIZ": "https://www.saes.upiiz.ipn.mx",
    "UPIIC": "https://www.saes.upiic.ipn.mx",
    "CICS Sto. Tomás": "https://www.saes.cicsst.ipn.mx",
    "CICS Milpa Alta": "https://www.saes.cicsma.ipn.mx",
}

# Medio superior (NMS)
ESCUELAS_NMS = {
    f"CECyT {n}": f"https://www.saes.cecyt{n}.ipn.mx" for n in range(1, 20)
}
ESCUELAS_NMS["CET 1"] = "https://www.saes.cet1.ipn.mx"

ESCUELAS = {**ESCUELAS_NS, **ESCUELAS_NMS}


class ErrorSaes(Exception):
    pass


class SesionSaes:
    def __init__(self, escuela: str):
        if escuela not in ESCUELAS:
            raise ErrorSaes(f"Escuela desconocida: {escuela}")
        self.base = ESCUELAS[escuela].rstrip("/")
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "Mozilla/5.0"
        self._campos: dict[str, str] = {}

    # ------------------------------------------------------------- helpers
    def _url(self, ruta: str) -> str:
        return f"{self.base}{ruta}"

    def _get(self, ruta: str) -> str:
        r = self.s.get(self._url(ruta), timeout=25, verify=False)
        r.raise_for_status()
        return r.text

    def _hidden(self, html: str) -> dict[str, str]:
        """__VIEWSTATE, __EVENTVALIDATION, etc. de la página actual."""
        sopa = BeautifulSoup(html, "html.parser")
        return {i["name"]: i.get("value", "")
                for i in sopa.find_all("input", {"type": "hidden"}) if i.get("name")}

    # -------------------------------------------------------------- login
    def captcha(self) -> bytes:
        """Abre el login y devuelve los bytes de la imagen del captcha."""
        html = self._get(RUTA_LOGIN)
        self._campos = self._hidden(html)
        sopa = BeautifulSoup(html, "html.parser")
        img = sopa.find("img", src=lambda s: s and "captcha" in s.lower())
        if img is None:
            raise ErrorSaes("No encontré el captcha en el login")
        url = img["src"]
        if not url.startswith("http"):
            url = f"{self.base}/{url.lstrip('/')}"
        return self.s.get(url, timeout=25, verify=False).content

    def login(self, boleta: str, contrasena: str, captcha: str) -> bool:
        datos = dict(self._campos)
        datos.update({
            "ctl00$leftColumn$LoginUser$UserName": boleta,
            "ctl00$leftColumn$LoginUser$Password": contrasena,
            "ctl00$leftColumn$LoginUser$CampoDinamico": captcha,
            "ctl00$leftColumn$LoginUser$LoginButton": "Entrar",
        })
        r = self.s.post(self._url(RUTA_LOGIN), data=datos, timeout=25, verify=False)
        ok = "default.aspx" in r.url.lower() or "cerrar" in r.text.lower()
        if not ok and ("incorrecto" in r.text.lower() or "captcha" in r.text.lower()):
            raise ErrorSaes("Boleta, contraseña o captcha incorrectos")
        return ok

    # ------------------------------------------------- descarga (parseo)
    def _tablas(self, html: str) -> list[list[list[str]]]:
        """Todas las tablas de la página como listas de filas de celdas."""
        sopa = BeautifulSoup(html, "html.parser")
        tablas = []
        for t in sopa.find_all("table"):
            filas = []
            for tr in t.find_all("tr"):
                celdas = [td.get_text(" ", strip=True)
                          for td in tr.find_all(["td", "th"])]
                if celdas:
                    filas.append(celdas)
            if filas:
                tablas.append(filas)
        return tablas

    # Filtros de la página de horarios (nombres reales verificados en UPIICSA)
    F_CARRERA = "ctl00$mainCopy$Filtro$cboCarrera"
    F_TURNO = "ctl00$mainCopy$Filtro$cboTurno"
    F_PLAN = "ctl00$mainCopy$Filtro$cboPlanEstud"
    F_PERIODOS = "ctl00$mainCopy$Filtro$lsNoPeriodos"
    F_SECUENCIAS = "ctl00$mainCopy$lsSecuencias"
    F_VISUALIZAR = "ctl00$mainCopy$cmdVisalizar"

    def _post(self, ruta: str, base_html: str, extra: dict[str, str]) -> str:
        datos = self._hidden(base_html)
        datos.update(extra)
        r = self.s.post(self._url(ruta), data=datos, timeout=25, verify=False)
        r.raise_for_status()
        return r.text

    def carreras_horarios(self) -> list[tuple[str, str]]:
        """(valor, nombre) de las carreras disponibles en horarios."""
        html = self._get(RUTA_HORARIOS)
        sopa = BeautifulSoup(html, "html.parser")
        sel = sopa.find("select", {"name": self.F_CARRERA})
        if not sel:
            return []
        return [(o.get("value", ""), o.get_text(strip=True))
                for o in sel.find_all("option") if o.get("value")]

    def horarios_txt(self, carrera: str = "", turno: str = "M",
                     plan: str = "", periodo: str = "1") -> str:
        """Descarga la ocupabilidad de horarios y la vuelve al formato txt
        (tabs) que ya parsea la app. El SAES exige elegir carrera, turno, plan
        y periodo; carrera se auto-detecta si no se pasa.

        NOTA: es un ASP.NET WebForms multi-postback; los nombres de campo están
        verificados pero la estructura de la tabla renderizada puede variar por
        escuela. Si algo no cuadra, usa 📂 Cargar TXT."""
        html = self._get(RUTA_HORARIOS)
        if not carrera:
            cs = self.carreras_horarios()
            carrera = cs[0][0] if cs else ""
        # paso 1: elegir carrera (autopostback que carga plan/periodos/grupos)
        h1 = self._post(RUTA_HORARIOS, html, {
            "__EVENTTARGET": self.F_CARRERA, "__EVENTARGUMENT": "",
            self.F_CARRERA: carrera})
        # paso 2: visualizar con todos los filtros
        h2 = self._post(RUTA_HORARIOS, h1, {
            self.F_CARRERA: carrera, self.F_TURNO: turno,
            self.F_PLAN: plan, self.F_PERIODOS: periodo,
            self.F_SECUENCIAS: "Todo", self.F_VISUALIZAR: "Visualizar información"})
        lineas = []
        for tabla in self._tablas(h2):
            for fila in tabla:
                if len(fila) >= 7:
                    lineas.append("\t".join(fila))
        return "\n".join(lineas)

    def equivalencias_txt(self) -> str:
        html = self._get(RUTA_EQUIVALENCIAS)
        lineas = []
        for tabla in self._tablas(html):
            for fila in tabla:
                lineas.append("\t".join(fila))
        return "\n".join(lineas)

    def kardex_cursadas(self) -> list[str]:
        """Materias aprobadas en el kardex. Estructura real (UPIICSA, verificada):
        cada semestre es una tabla; las filas de materia son
        [clave, materia, fecha, periodo, forma_eval, calificación].
        La clave es tipo N101 y la calificación es la última celda."""
        html = self._get(RUTA_KARDEX)
        cursadas = []
        for tabla in self._tablas(html):
            for fila in tabla:
                if len(fila) < 3 or not RE_CLAVE.match(fila[0].strip()):
                    continue
                nombre = fila[1].strip()
                nota = _a_num(fila[-1])
                if nombre and nota is not None and nota >= 6:
                    cursadas.append(nombre)
        return cursadas

    def mapa_txt(self) -> str:
        return self._get(RUTA_MAPA)

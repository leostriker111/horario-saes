# Horario SAES

Armador de horarios para estudiantes del IPN. Carga los grupos del SAES y arma
tu horario ideal: ramas alternativas, choques automáticos, créditos, checklist
y export a PDF/PNG.

## Instalar

- **Sin Python**: descarga el ejecutable de tu sistema en
  [Releases](https://github.com/leostriker111/horario-saes/releases).
- **Con Python 3.10+**: `pip install git+https://github.com/leostriker111/horario-saes`
  y corre `horario`.

## Uso

1. Copia del SAES los horarios (y opcionalmente plan de créditos y
   equivalencias) a un `.txt` — texto plano con tabuladores.
2. **📂 Cargar TXT** y arma tu horario picando grupos en la lista.

Funciones: filtros (texto, profe favorito ★, turno, días, horas, check,
cursadas), ramas con bifurcación y árbol, candados 🔒 + generador 🎲 sin
repetir, bloques propios con reloj, créditos con equivalencias entre carreras,
checklist ✅ y cursadas 🎓, export 📤 a PDF/PNG/JPG/SVG.

Tu sesión se guarda sola en `~/.horario_saes/`.

## Contribuir

Trabaja sobre la rama `dev` y abre un Pull Request a `master`.

## Licencia

[GPL-3.0](LICENSE): úsalo, estúdialo y modifícalo libremente — las
modificaciones distribuidas deben seguir siendo software libre.

## Descargar horarios del SAES

El **kardex** (materias cursadas) y el **login** funcionan directo desde
`📥 Cargar datos → Desde el SAES`. Los **horarios disponibles**, en cambio, el
SAES los rinde tras una cadena de filtros ASP.NET difícil de automatizar de
forma confiable, así que el camino robusto es el bookmarklet:

1. Crea un marcador en tu navegador y pega como URL la versión `javascript:...`
   de [`bookmarklet_saes.js`](bookmarklet_saes.js).
2. En el SAES, página de horarios: elige carrera, turno, plan y periodo, y pica
   **Visualizar información**.
3. Pica el marcador → copia la tabla al portapapeles.
4. Pégala en un `.txt` y cárgalo en la app. Para incluir **materias
   equivalentes de otras carreras**, repite por cada carrera (Informática,
   Ciencias, etc.) y pega todo en el mismo `.txt`.

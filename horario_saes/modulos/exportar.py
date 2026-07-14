import os
import re
import sys
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont

from horario_saes.modulos.modelo import Estado, Rama
from horario_saes.modulos.parser_saes import DIAS_LARGO

HORA_INI, HORA_FIN = 7, 22
FORMATOS = ("pdf", "png", "jpg", "svg")


def _find_font_file(negrita: bool = False) -> str | None:
    # 1. Windows: check Segoe UI
    if sys.platform.startswith("win"):
        nombre = "segoeuib.ttf" if negrita else "segoeui.ttf"
        path = Path(os.environ.get("SystemRoot", "C:/Windows")) / "Fonts" / nombre
        if path.exists():
            return str(path)

    # 2. Linux: use fc-match
    if sys.platform.startswith("linux"):
        pattern = "sans-serif:bold" if negrita else "sans-serif"
        try:
            res = subprocess.run(["fc-match", "-f", "%{file}", pattern],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0 and res.stdout.strip():
                p = res.stdout.strip()
                if Path(p).exists():
                    return p
        except Exception:
            pass
        # Fallback standard paths on Linux
        fallbacks = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if negrita else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if negrita else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/liberation/LiberationSans-Bold.ttf" if negrita else "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf" if negrita else "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        ]
        for p in fallbacks:
            if Path(p).exists():
                return p

    # 3. macOS (darwin): check standard paths
    if sys.platform.startswith("darwin"):
        fallbacks = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Arial.ttf",
            "/Library/Fonts/Arial.ttf",
        ]
        for p in fallbacks:
            if Path(p).exists():
                return p

    return None


def _fuente(tam: int, negrita: bool = False) -> ImageFont.FreeTypeFont:
    path = _find_font_file(negrita)
    if path:
        try:
            return ImageFont.truetype(path, tam)
        except OSError:
            pass
    return ImageFont.load_default(tam)



def _envolver(draw: ImageDraw.ImageDraw, texto: str, fuente, max_ancho: float) -> list[str]:
    lineas = []
    for parte in texto.split("\n"):
        linea = ""
        for palabra in parte.split():
            prueba = f"{linea} {palabra}".strip()
            if draw.textlength(prueba, font=fuente) <= max_ancho:
                linea = prueba
            else:
                if linea:
                    lineas.append(linea)
                linea = palabra
        if linea:
            lineas.append(linea)
    return lineas


def _subtitulo(estado: Estado, rama: Rama) -> str:
    sel = estado.seleccionadas(rama)
    total, sin_cred = estado.total_creditos(rama)
    partes = [f"{len(sel)} materias", f"{total:g} créditos"]
    if sin_cred:
        partes.append(f"{sin_cred} SN")
    partes.append(f"{estado.total_horas(rama):g} h/sem")
    return " · ".join(partes)


def render_rama(estado: Estado, rama: Rama,
                ancho: int = 1754, alto: int = 1240) -> Image.Image:
    img = Image.new("RGB", (ancho, alto), "white")
    d = ImageDraw.Draw(img)
    f_titulo, f_sub = _fuente(34, True), _fuente(20)
    f_dia, f_hora = _fuente(22, True), _fuente(16)
    f_bloque, f_bloque_b = _fuente(16), _fuente(17, True)

    m_izq, m_sup, m_inf, m_der = 90, 140, 40, 30
    d.text((m_izq, 26), f"Horario — {rama.nombre}", font=f_titulo, fill="#212121")
    d.text((m_izq, 72), _subtitulo(estado, rama), font=f_sub, fill="#546E7A")

    col = (ancho - m_izq - m_der) / 5
    escala = (alto - m_sup - m_inf) / ((HORA_FIN - HORA_INI) * 60)

    def y_de(minutos: int) -> float:
        return m_sup + (minutos - HORA_INI * 60) * escala

    for h in range(HORA_INI, HORA_FIN + 1):
        y = y_de(h * 60)
        d.line([(m_izq, y), (ancho - m_der, y)], fill="#E0E0E0", width=1)
        d.text((m_izq - 10, y), f"{h}:00", font=f_hora, fill="#78909C", anchor="rm")
    for dia in range(6):
        x = m_izq + dia * col
        d.line([(x, m_sup), (x, alto - m_inf)], fill="#B0BEC5", width=1)
    for dia, nombre in enumerate(DIAS_LARGO):
        d.text((m_izq + dia * col + col / 2, m_sup - 22), nombre,
               font=f_dia, fill="#37474F", anchor="mm")

    for op in estado.seleccionadas(rama):
        color = estado.colores.get(op.materia, "#DDDDDD")
        for s in op.sesiones:
            x1 = m_izq + s.dia * col + 3
            x2 = m_izq + (s.dia + 1) * col - 3
            y1, y2 = y_de(s.inicio), y_de(s.fin)
            d.rectangle([x1, y1, x2, y2], fill=color, outline="#455A64", width=2)
            if op.propia:
                lugar = f" · {op.salon}" if op.salon else ""
                lineas = _envolver(d, op.materia, f_bloque_b, x2 - x1 - 16)
                lineas += _envolver(d, f"{op.nota}{lugar}".strip(" ·"),
                                    f_bloque, x2 - x1 - 16)
            else:
                lugar = f" · {op.salon}" if op.salon and op.salon != "000" else ""
                lineas = _envolver(d, f"{op.grupo} — {op.materia}",
                                   f_bloque_b, x2 - x1 - 16)
                lineas += _envolver(d, f"{op.profesor}{lugar}", f_bloque, x2 - x1 - 16)
            alto_linea = 22
            total_alto = len(lineas) * alto_linea
            y_texto = (y1 + y2) / 2 - total_alto / 2 + alto_linea / 2
            for i, linea in enumerate(lineas):
                d.text(((x1 + x2) / 2, y_texto), linea,
                       font=f_bloque_b if i == 0 else f_bloque,
                       fill="#212121", anchor="mm")
                y_texto += alto_linea
    return img


def render_svg(estado: Estado, rama: Rama, ancho: int = 1170, alto: int = 827) -> str:
    m_izq, m_sup, m_inf, m_der = 60, 95, 28, 20
    col = (ancho - m_izq - m_der) / 5
    escala = (alto - m_sup - m_inf) / ((HORA_FIN - HORA_INI) * 60)

    def y_de(minutos: int) -> float:
        return m_sup + (minutos - HORA_INI * 60) * escala

    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{ancho}" height="{alto}" '
         f'viewBox="0 0 {ancho} {alto}" font-family="Segoe UI, sans-serif">',
         f'<rect width="{ancho}" height="{alto}" fill="white"/>',
         f'<text x="{m_izq}" y="34" font-size="24" font-weight="bold" '
         f'fill="#212121">Horario — {escape(rama.nombre)}</text>',
         f'<text x="{m_izq}" y="58" font-size="14" fill="#546E7A">'
         f'{escape(_subtitulo(estado, rama))}</text>']

    for h in range(HORA_INI, HORA_FIN + 1):
        y = y_de(h * 60)
        p.append(f'<line x1="{m_izq}" y1="{y:.1f}" x2="{ancho - m_der}" y2="{y:.1f}" '
                 f'stroke="#E0E0E0"/>')
        p.append(f'<text x="{m_izq - 6}" y="{y + 4:.1f}" font-size="11" fill="#78909C" '
                 f'text-anchor="end">{h}:00</text>')
    for dia in range(6):
        x = m_izq + dia * col
        p.append(f'<line x1="{x:.1f}" y1="{m_sup}" x2="{x:.1f}" y2="{alto - m_inf}" '
                 f'stroke="#B0BEC5"/>')
    for dia, nombre in enumerate(DIAS_LARGO):
        p.append(f'<text x="{m_izq + dia * col + col / 2:.1f}" y="{m_sup - 12}" '
                 f'font-size="14" font-weight="bold" fill="#37474F" '
                 f'text-anchor="middle">{nombre}</text>')

    for op in estado.seleccionadas(rama):
        color = estado.colores.get(op.materia, "#DDDDDD")
        for s in op.sesiones:
            x1 = m_izq + s.dia * col + 2
            y1, y2 = y_de(s.inicio), y_de(s.fin)
            w = col - 4
            extra = ' stroke-dasharray="6,3"' if op.propia else ""
            p.append(f'<rect x="{x1:.1f}" y="{y1:.1f}" width="{w:.1f}" '
                     f'height="{y2 - y1:.1f}" fill="{color}" stroke="#455A64" '
                     f'stroke-width="1.5"{extra}/>')
            cx = x1 + w / 2
            cy = (y1 + y2) / 2
            if op.propia:
                l1, l2 = op.materia, f"{op.nota} {op.salon}".strip()
            else:
                lugar = f" · {op.salon}" if op.salon and op.salon != "000" else ""
                l1, l2 = f"{op.grupo} — {op.materia}", f"{op.profesor}{lugar}"
            p.append(f'<text x="{cx:.1f}" y="{cy - 3:.1f}" font-size="11" '
                     f'font-weight="bold" fill="#212121" text-anchor="middle">'
                     f'{escape(l1)}</text>')
            p.append(f'<text x="{cx:.1f}" y="{cy + 12:.1f}" font-size="10" '
                     f'fill="#212121" text-anchor="middle">{escape(l2)}</text>')
    p.append("</svg>")
    return "\n".join(p)


def _sanear(nombre: str) -> str:
    return re.sub(r"[^\w\-]+", "_", nombre).strip("_") or "rama"


def exportar_ramas(estado: Estado, ramas: list[Rama], formato: str,
                   ruta: str | Path) -> list[Path]:
    """Exporta las ramas dadas. PDF: un archivo con página por rama.
    PNG/JPG/SVG: un archivo por rama (con sufijo si son varias)."""
    Image.init()  # el plugin PDF exige los códecs ya registrados
    ruta = Path(ruta)
    creados: list[Path] = []

    if formato == "pdf":
        paginas = [render_rama(estado, r) for r in ramas]
        paginas[0].save(ruta, save_all=True, append_images=paginas[1:],
                        resolution=150)
        return [ruta]

    usados: set[str] = set()
    for rama in ramas:
        base = _sanear(rama.nombre)
        if base in usados:
            base = f"{base}{rama.id}"
        usados.add(base)
        destino = ruta if len(ramas) == 1 else \
            ruta.with_stem(f"{ruta.stem}_{base}")
        if formato == "svg":
            destino.write_text(render_svg(estado, rama), encoding="utf-8")
        else:
            img = render_rama(estado, rama)
            if formato == "jpg":
                img.save(destino, quality=92)
            else:
                img.save(destino)
        creados.append(destino)
    return creados

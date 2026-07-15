import re
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont

from horario_saes.modulos.modelo import Estado, Rama
from horario_saes.modulos.parser_saes import DIAS_LARGO

HORA_INI, HORA_FIN = 7, 22
FORMATOS = ("pdf", "png", "jpg", "svg")


def _fuente(tam: int, negrita: bool = False) -> ImageFont.FreeTypeFont:
    nombre = "segoeuib.ttf" if negrita else "segoeui.ttf"
    try:
        return ImageFont.truetype(f"C:/Windows/Fonts/{nombre}", tam)
    except OSError:
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


def _pdf_wrap(c, texto, font, size, maxw):
    lineas, cur = [], ""
    for w in texto.split():
        prueba = (cur + " " + w).strip()
        if c.stringWidth(prueba, font, size) <= maxw or not cur:
            cur = prueba
        else:
            lineas.append(cur)
            cur = w
    if cur:
        lineas.append(cur)
    return lineas


def render_pdf(estado: Estado, ramas: list[Rama], ruta: Path) -> None:
    """PDF vectorial: texto real (seleccionable/buscable), hipervínculos en el
    nombre del profe (a tus foros) y adaptable a cualquier visor. Una página
    por rama. Usa fuentes estándar (Helvetica) → corre igual en Win/Mac/Linux."""
    from urllib.parse import quote_plus

    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas as rlcanvas

    W, H = landscape(A4)
    c = rlcanvas.Canvas(str(ruta), pagesize=(W, H))
    m_izq, m_der, m_sup, m_inf = 55, 22, 60, 26
    col = (W - m_izq - m_der) / 5
    area_alto = (H - m_sup) - m_inf
    total_min = (HORA_FIN - HORA_INI) * 60
    foro = estado.foros[0] if estado.foros else ""

    def y_de(minutos: int) -> float:  # reportlab: origen abajo-izquierda
        frac = (minutos - HORA_INI * 60) / total_min
        return (H - m_sup) - frac * area_alto

    def texto_seguro(s: str) -> str:
        return s.replace("—", "-").replace("–", "-")

    for rama in ramas:
        c.setTitle(f"Horario - {rama.nombre}")
        c.setFont("Helvetica-Bold", 16)
        c.drawString(m_izq, H - 34, texto_seguro(f"Horario — {rama.nombre}"))
        c.setFont("Helvetica", 10)
        c.setFillColor(HexColor("#546E7A"))
        c.drawString(m_izq, H - 50, texto_seguro(_subtitulo(estado, rama)))
        c.setFillColor(HexColor("#000000"))

        # rejilla
        c.setFont("Helvetica", 8)
        for h in range(HORA_INI, HORA_FIN + 1):
            y = y_de(h * 60)
            c.setStrokeColor(HexColor("#E0E0E0"))
            c.line(m_izq, y, W - m_der, y)
            c.setFillColor(HexColor("#78909C"))
            c.drawRightString(m_izq - 6, y - 3, f"{h}:00")
        c.setFillColor(HexColor("#000000"))
        for d in range(6):
            x = m_izq + d * col
            c.setStrokeColor(HexColor("#B0BEC5"))
            c.line(x, H - m_sup, x, m_inf)
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(HexColor("#37474F"))
        for d, nombre in enumerate(DIAS_LARGO):
            c.drawCentredString(m_izq + d * col + col / 2, H - m_sup + 8, nombre)
        c.setFillColor(HexColor("#000000"))

        # bloques
        for op in estado.seleccionadas(rama):
            color = estado.colores.get(op.materia, "#DDDDDD")
            for s in op.sesiones:
                x1 = m_izq + s.dia * col + 2
                x2 = m_izq + (s.dia + 1) * col - 2
                yt, yb = y_de(s.inicio), y_de(s.fin)
                c.setFillColor(HexColor(color))
                c.setStrokeColor(HexColor("#455A64"))
                c.rect(x1, yb, x2 - x1, yt - yb, fill=1, stroke=1)
                c.setFillColor(HexColor("#212121"))
                cx = (x1 + x2) / 2
                lugar = f" · {op.salon}" if op.salon and op.salon != "000" else ""
                if op.propia:
                    l1 = _pdf_wrap(c, op.materia, "Helvetica-Bold", 7, x2 - x1 - 8)
                    l2 = _pdf_wrap(c, f"{op.nota}{lugar}".strip(" ·"),
                                   "Helvetica", 6.5, x2 - x1 - 8)
                    prof = None
                else:
                    l1 = _pdf_wrap(c, f"{op.grupo} - {op.materia}",
                                   "Helvetica-Bold", 7, x2 - x1 - 8)
                    l2 = _pdf_wrap(c, f"{op.profesor}{lugar}", "Helvetica", 6.5,
                                   x2 - x1 - 8)
                    prof = op.profesor
                alto_l = 9
                total_alto = len(l1) * alto_l + len(l2) * alto_l
                y = (yt + yb) / 2 + total_alto / 2 - alto_l + 2
                for ln in l1:
                    c.setFont("Helvetica-Bold", 7)
                    c.drawCentredString(cx, y, texto_seguro(ln))
                    y -= alto_l
                y_prof_top = y + alto_l - 2
                c.setFont("Helvetica", 6.5)
                if prof and foro:
                    c.setFillColor(HexColor("#0D47A1"))
                for ln in l2:
                    c.drawCentredString(cx, y, texto_seguro(ln))
                    y -= alto_l
                c.setFillColor(HexColor("#212121"))
                # hipervínculo sobre el nombre del profe -> foro
                if prof and foro:
                    url = foro.replace("{profesor}", quote_plus(prof.strip()))
                    c.linkURL(url, (x1, y + alto_l - 2, x2, y_prof_top),
                              relative=0, thickness=0)
        c.showPage()
    c.save()


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
        try:
            render_pdf(estado, ramas, ruta)   # vectorial: texto real + links
        except ImportError:
            paginas = [render_rama(estado, r) for r in ramas]  # fallback raster
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

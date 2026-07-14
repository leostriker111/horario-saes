# 🎓 Horarios SAES

> Armador de horarios para el SAES (Sistema de Administración de Estudios).  
> Carga los grupos copiados del SAES, administra ramas de horarios, créditos, equivalencias y exporta el resultado a PDF, PNG, JPG o SVG.

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Tkinter](https://img.shields.io/badge/Tkinter-GUI-FF6F00?style=for-the-badge&logo=python&logoColor=white)
![Pillow](https://img.shields.io/badge/Pillow-10%2B-2D72D2?style=for-the-badge&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-555555?style=for-the-badge)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

</div>

## Tecnologías

| Tecnología | Versión | Propósito |
|---|---|---|
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/python/python-original.svg" width="16"/> **Python** | ≥ 3.10 | Lenguaje base |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/python/python-original.svg" width="16"/> **Tkinter** | stdlib | Interfaz gráfica (incluida con Python) |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/python/python-original.svg" width="16"/> **Pillow** | ≥ 10 | Renderizado de horarios a imagen/PDF |
| **setuptools** | ≥ 61 | Empaquetado y distribución |

> Tkinter viene incluido con Python; solo es necesario instalar Pillow como dependencia externa.

---

## Estructura del proyecto

```
horario-saes/
├── pyproject.toml          # Configuración del proyecto y empaquetado
├── requirements.txt        # Dependencia: pillow>=10
├── horario.cmd             # Lanzador para Windows (ventana oculta con pythonw)
├── AGENTS.md               # Instrucciones para asistentes de IA
├── horario_saes/           # Código fuente
│   ├── __init__.py
│   ├── main.py             # Punto de entrada: App (tk.Tk), toolbar, layout, refresh
│   └── modulos/
│       ├── __init__.py
│       ├── parser_saes.py  # Parsing del TXT del SAES: Opcion, Sesion, plan/equivalencias
│       ├── modelo.py       # Estado global, persistencia JSON, ramas, créditos
│       ├── dialogos.py     # Diálogos modales: exportar, plan, check, bloques, filtros, árbol
│       ├── exportar.py     # Renderizado a Pillow (imagen/PDF) y SVG
│       └── reloj.py        # Selector de hora estilo reloj circular
```

---

### Módulos

| Archivo | Función |
|---|---|
| `main.py` | Punto de entrada. Clase `App` (tk.Tk) que arma la interfaz: toolbar con botones, canvas de horario, lista lateral de opciones, panel de inscritos y barra de ramas. |
| `parser_saes.py` | Parsea el archivo TXT copiado del SAES. Extrae grupos (`Opcion`), horarios (`Sesion`), tablas de plan de estudios y equivalencias. Detecta conflictos de horario (`chocan()`). Empareja créditos por nombre difuso. |
| `modelo.py` | Clase `Estado` con toda la lógica de negocio: opciones, ramas, favoritos, créditos, selección. Persiste en `~/.horario_saes/sesion.json`. Soporta bifurcación de ramas. |
| `dialogos.py` | Ventanas modales: exportación (PDF/PNG/JPG/SVG), vista de plan de estudios, checklist de materias, alta de bloques propios, filtros de lista, vista de profesores y árbol de ramas. |
| `exportar.py` | Renderiza el horario a imagen PIL (`render_rama()`) o string SVG (`render_svg()`). Exporta a PDF (Pillow multipágina), PNG, JPG o SVG. |
| `reloj.py` | Widget selector de hora tipo reloj circular (como Android). Dos modos: hora (anillo exterior 1-12, interior 13-00) y minutos (pasos de 5). |

---

## Instalación

### Requisitos

- Python 3.10 o superior
- pip

### Desde el código fuente

```bash
# Clonar o copiar el proyecto
cd horario-saes

# Crear y activar un entorno virtual (opcional pero recomendado)
python -m venv venv
source venv/bin/activate      # Linux / macOS
venv\Scripts\activate         # Windows

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar
python -m horario_saes.main
```

### Instalación como paquete

```bash
pip install .
```

Luego ejecutar con (si el comando queda disponible en el PATH):

```bash
python -m horario_saes.main
```

También puedes ejecutar directamente el comando instalado:

```bash
horario
```

### Windows

Puedes usar `horario.cmd` (doble clic): lanza la app con `pythonw` para que no se muestre la terminal.

---

## Compilación (Generación de Ejecutables)

Para crear ejecutables independientes (`HorarioSAES.exe`, `HorarioSAES.app`, etc.) que no requieran instalar Python, se utiliza **PyInstaller**. 

> ⚠️ **Nota:** PyInstaller no soporta compilación cruzada. Para compilar para Windows debes ejecutar el comando en Windows; para Linux, en Linux; y para macOS, en macOS.

### 1. Compilación local

Asegúrate de instalar PyInstaller en tu entorno virtual (`pip install pyinstaller`) y ejecuta el comando según tu sistema desde la raíz del proyecto:

#### 🐧 Linux:
```bash
pyinstaller --noconsole --onefile --name="HorarioSAES" --paths=. --hidden-import=PIL._tkinter_finder --add-data "horario_saes/fonts:horario_saes/fonts" horario_saes/main.py
```

#### 🪟 Windows:
```powershell
pyinstaller --noconsole --onefile --name="HorarioSAES" --paths=. --hidden-import=PIL._tkinter_finder --add-data "horario_saes/fonts;horario_saes/fonts" horario_saes/main.py
```

#### 🍎 macOS:
```bash
pyinstaller --windowed --onefile --name="HorarioSAES" --paths=. --hidden-import=PIL._tkinter_finder --add-data "horario_saes/fonts:horario_saes/fonts" horario_saes/main.py
```

### 2. Automatización en la nube (GitHub Actions)

El proyecto cuenta con un flujo de trabajo preconfigurado en [.github/workflows/build.yml](file:///.github/workflows/build.yml). Cada vez que haces un `push` a las ramas `main` o `master`, o lo ejecutas manualmente desde la pestaña **Actions** en GitHub:
1. Se compilarán los ejecutables en paralelo para Linux, Windows y macOS.
2. Los ejecutables listos para usar se subirán como artefactos de la compilación para su descarga directa.

---

## Características Avanzadas e Integraciones

### 🎨 Carga Dinámica de Fuentes (Multiplataforma)
Para evitar dependencias externas problemáticas como `tkfontawesome`, la app incluye un cargador nativo de bajo nivel en [iconos.py](file:///horario_saes/modulos/iconos.py):
* **Windows**: Registra las fuentes en la sesión del proceso mediante `AddFontResourceExW` (GDI).
* **Linux**: Las registra temporalmente en la sesión de Fontconfig mediante `FcConfigAppFontAddFile`.
* **macOS**: Registra las fuentes usando la API de CoreText `CTFontManagerRegisterFontsForURL`.
* **Compatibilidad con PyInstaller**: Resuelve dinámicamente el directorio temporal `sys._MEIPASS` para encontrar las fuentes al ejecutar desde el binario compilado.

### 🌐 Sincronización Remota y Caché Offline
La app descarga el catálogo de materias directamente de tus repositorios GitHub en base a la escuela activa seleccionada (UPIICSA, ESCOM, ESIME). 
* **Carga instantánea**: Utiliza una caché local en disco para arrancar instantáneamente sin bloquear la interfaz por peticiones de red.
* **Sincronización**: Al pulsar **Sincronizar**, se fuerza la descarga de los datos actualizados. Si no hay conexión a internet, se usa la copia local de respaldo sin interrumpir el flujo.

### 🖥️ Interfaz Unificada y Diseño Adaptativo
* **Botones Nativos con Iconos**: Se utiliza el comportamiento nativo `compound="left"` de `ttk.Button` para incrustar iconos vectoriales rasterizados al vuelo en lugar de usar etiquetas separadas.
* **Redimensionado Adaptativo**: El lienzo del horario principal y el listado de materias tienen manejadores del evento `<Configure>`. Se redibujan automáticamente y se adaptan a cualquier cambio en el tamaño de la ventana o al colapsar los paneles.

---

## Uso básico

1. Abre el SAES, busca las materias y **copia todo el contenido** (Ctrl+E, Ctrl+C).
2. Pégalo en un archivo de texto (`datos.txt`) y guárdalo (o usa la **Sincronización remota** si tu escuela ya tiene los datos publicados en GitHub).
3. En la app, haz clic en **Cargar TXT** y selecciona el archivo.
4. Haz clic en las opciones de la lista lateral para agregarlas al horario.
5. Usa **Filtrar** para buscar por materia, profesor o grupo.
6. Usa **Bifurcar** para crear variantes del horario actual.
7. Exporta con **Exportar** a PDF, imagen o SVG.


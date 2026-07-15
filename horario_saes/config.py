"""
Configuracion de donde estan los origenes a descargar los documentos
ademas de la exportacion del singleton del config
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ServicioOrigen:
    """Declaracion del tipo para los origenes"""
    nombre: str
    repo_url: str
    prefijo: str = "datafile-"


@dataclass
class Config:
    """Configuracion de los origenes y todo eso"""
    origenes: list[ServicioOrigen] = field(default_factory=lambda: [
        ServicioOrigen(
            nombre="UPIICSA",
            repo_url="https://raw.githubusercontent.com/UrielCandelasMeza/horarios-saes-data/main/UPIICSA/datafile-latest.txt",
            prefijo="datafile-",
        ),
        ServicioOrigen(
            nombre="ESCOM",
            repo_url="https://raw.githubusercontent.com/UrielCandelasMeza/horarios-saes-data/main/ESCOM/datafile-latest.txt",
            prefijo="datafile-",
        ),
        ServicioOrigen(
            nombre="ESIME",
            repo_url="https://raw.githubusercontent.com/UrielCandelasMeza/horarios-saes-data/main/ESIME/datafile-latest.txt",
            prefijo="datafile-",
        ),
    ])
    cache_dir: Path = Path.home() / "horarios_saes" / "datafiles"
    active_index: int = 0


_driver: Config | None = None


def get_config() -> Config:
    """Obtiene un singleton de la configuracion"""
    global _driver
    if _driver is None:
        _driver = Config()
    return _driver

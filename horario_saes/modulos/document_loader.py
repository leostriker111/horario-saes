"""
Este documento obtiene todos los documentos de un repositorio de github
para ello descarga el raw y lo importa aqui
"""

import logging
import re
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.request import urlopen, Request

from horario_saes.config import Config, ServicioOrigen


class LoadError(Exception):
    pass


LATEST = "latest.txt"

PATTERN = re.compile(r"datafile-(\d+)-(\d+)\.")


def _semestre_key(filename: str) -> tuple[int, int]:
    match = PATTERN.search(filename)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    return (0, 0)


class DocumentLoader:

    def __init__(self, config: Config):
        self.config = config

    def _descargar_a(self, url: str, destino: Path) -> Path:
        logging.info(f"Descargando %s", url)
        try:
            req = Request(url, headers={"User-Agent": "horario-saes/1.0"})
            with urlopen(req, timeout=30) as conn:
                data = conn.read()
        except URLError as e:
            raise LoadError(f"No se pudo descargar {url}") from e
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(data)
        return destino

    def cargar_escuela_activa(self, force: bool = False) -> Optional[Path]:
        config = self.config
        if config.active_index < 0 or config.active_index >= len(config.origenes):
            raise LoadError("No hay una escuela activa")
        servicio = config.origenes[config.active_index]

        filename = servicio.repo_url.split("/")[-1] or "datafile-latest.txt"
        destination = config.cache_dir / servicio.nombre / filename

        if not force and destination.exists():
            return destination

        try:
            return self._descargar_a(servicio.repo_url, destination)
        except LoadError as e:
            if destination.exists():
                logging.warning("Offline: usando copia local de %s", destination)
                return destination
            raise e

    def cargar_todo(self) -> list[Path]:
        origenes = self.config.origenes
        paths = []
        for i, servicio in enumerate(origenes):
            try:
                idx = self.config.active_index
                self.config.active_index = i
                result = self.cargar_escuela_activa()
                if result:
                    paths.append(Path(result))
            except LoadError:
                continue
            finally:
                self.config.active_index = idx
        return paths

    def existe_archivo_local(self, nombre: str) -> Path | None:
        path = self.config.cache_dir / nombre
        return path if path.exists() else None


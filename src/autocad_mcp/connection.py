"""Conexion COM a AutoCAD: reintentos con backoff y circuit breaker.

Toda la interaccion con la Application/Document de AutoCAD vive aqui. El resto
del codigo usa ``AutoCADConnection`` y nunca importa ``win32com`` directamente.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, TypeVar

import pythoncom
import win32com.client
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from win32com.client import constants

from autocad_mcp.config import AutoCADMCPConfig, get_config
from autocad_mcp.obs import log

T = TypeVar("T")


def safe_operation(operation: Callable[[], T], delay: float = 1.0) -> T | None:
    """Ejecuta una operacion COM con una pausa (necesaria para estabilidad) y loguea fallos."""
    try:
        result = operation()
        time.sleep(delay)
        return result
    except Exception as exc:  # noqa: BLE001 - se reporta y se degrada a None
        log.warning("com_operation_failed", error=str(exc))
        time.sleep(delay)
        return None


class AutoCADConnection:
    """Gestiona el ciclo de vida de la conexion COM con AutoCAD."""

    def __init__(self, config: AutoCADMCPConfig | None = None) -> None:
        self.config = config or get_config()
        self.app: Any = None
        self.doc: Any = None
        self.connected = False
        self._doc_name: str | None = None
        self._circuit_failures = 0
        self._circuit_open_until = 0.0

    # --- circuit breaker -------------------------------------------------
    def _circuit_breaker_open(self) -> bool:
        now = time.time()
        if now < self._circuit_open_until:
            return True
        self._circuit_failures = 0
        self._circuit_open_until = 0.0
        return False

    def _record_failure(self) -> None:
        self._circuit_failures += 1
        if self._circuit_failures >= self.config.retry_max_attempts:
            self._circuit_open_until = time.time() + min(60.0, self.config.retry_wait_max * 2)

    # --- connection ------------------------------------------------------
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _do_connect(self) -> None:
        """Intento de conexion COM (reintentado por tenacity).

        Nunca crea un dibujo nuevo si ya hay una instancia de AutoCAD abierta:
        solo resuelve el documento activo (con reintentos) y, si de verdad no
        hubiera ninguno, agrega uno sobre la instancia existente. Crear un
        ``Documents.Add()`` tras un fallo transitorio dejaba dibujos huerfanos.
        """
        last_error: Exception | None = None

        # 1) Instancia ya abierta
        try:
            self.app = win32com.client.GetActiveObject(self.config.autocad_progid)
            self.app.Visible = True
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            self.app = None

        if self.app is not None:
            # Resolver el documento activo sin crear uno nuevo.
            for _ in range(5):
                try:
                    self.doc = self.app.ActiveDocument
                    if self.doc:
                        self._doc_name = str(self.doc.Name)
                        return
                except Exception as exc:  # noqa: BLE001 - AutoCAD puede estar ocupado
                    last_error = exc
                    time.sleep(0.5)
            # La instancia existe pero sin documento activo: agregar uno.
            try:
                self.doc = self.app.Documents.Add()
                if self.doc:
                    self._doc_name = str(self.doc.Name)
                    return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
            raise last_error if last_error else RuntimeError("No active document")

        # 2) Crear nueva instancia
        try:
            self.app = win32com.client.Dispatch(self.config.autocad_progid)
            self.app.Visible = True
            time.sleep(2)
            self.doc = self.app.Documents.Add()
            if self.doc:
                self._doc_name = str(self.doc.Name)
                return
            raise RuntimeError("No active document after Dispatch")
        except Exception as exc:  # noqa: BLE001
            last_error = exc

        raise last_error if last_error else RuntimeError("Cannot connect to AutoCAD")

    def connect(self) -> bool:
        """Conecta a AutoCAD aplicando circuit breaker y reintentos."""
        pythoncom.CoInitialize()
        if self._circuit_breaker_open():
            log.warning("circuit_breaker_open", action="connect")
            return False

        try:
            self._do_connect()
            self.connected = True
            self._circuit_failures = 0
            log.info(
                "connected_to_autocad",
                document=str(self.doc.Name) if self.doc else None,
            )
            return True
        except Exception as exc:  # noqa: BLE001
            self.connected = False
            self.app = None
            self.doc = None
            self._record_failure()
            log.error("connect_failed", error=str(exc), action="connect")
            return False

    def ensure(self) -> bool:
        """Garantiza una conexion valida y vuelve al documento propio de la sesion."""
        bound = self._doc_name  # capturar antes de reconectar (connect lo sobrescribe)
        if not self.connected or self.doc is None:
            if not self.connect():
                return False
            self._reactivate_bound_document(bound)
            return True
        try:
            _ = str(self.doc.Name)
            return True
        except Exception:  # noqa: BLE001
            self.connected = False
            if not self.connect():
                return False
            self._reactivate_bound_document(bound)
            return True

    def _reactivate_bound_document(self, name: str | None = None) -> None:
        """Tras reconectar, se reengancha al documento con el que inicio la sesion."""
        if name is None:
            name = self._doc_name
        if not name or self.app is None:
            return
        try:
            if self.doc is not None and str(self.doc.Name) == name:
                return
        except Exception:  # noqa: BLE001
            pass
        try:
            docs = self.app.Documents
            for i in range(int(docs.Count)):
                doc = docs.Item(i)
                if str(doc.Name) == name:
                    try:
                        doc.Activate()
                    except Exception:  # noqa: BLE001 - activar ventana es best-effort
                        pass
                    self.doc = doc
                    self._doc_name = name
                    return
        except Exception as exc:  # noqa: BLE001
            log.warning("reactivate_bound_document_failed", document=name, error=str(exc))

    def regen(self) -> None:
        """Regenera la vista activa, ignorando errores."""
        try:
            self.doc.Regen(constants.acActiveViewport)
        except Exception:  # noqa: BLE001
            pass

    def model_space(self) -> Any:
        """Devuelve el ModelSpace del documento activo.

        Reintenta si AutoCAD rechaza la llamada por estar ocupado
        (``RPC_E_CALL_REJECTED``), frecuente al encadenar muchas operaciones.
        """
        last: Exception | None = None
        for _ in range(12):
            try:
                return self.doc.ModelSpace
            except Exception as exc:  # noqa: BLE001 - AutoCAD momentaneamente ocupado
                last = exc
                time.sleep(0.25)
        assert last is not None
        raise last

    def document_name(self) -> str:
        """Nombre del documento activo o cadena vacia."""
        try:
            return str(self.doc.Name)
        except Exception:  # noqa: BLE001
            return ""

    def list_documents(self) -> list[dict[str, Any]]:
        """Lista los documentos abiertos: nombre, ruta y marca de activo."""
        if not self.ensure():
            return []
        active_name = self.document_name()
        documents: list[dict[str, Any]] = []
        try:
            docs = self.app.Documents
            for i in range(int(docs.Count)):
                try:
                    doc = docs.Item(i)
                    name = str(doc.Name)
                    try:
                        path = str(doc.Path) if doc.Path else ""
                    except Exception:  # noqa: BLE001
                        path = ""
                    documents.append({"name": name, "path": path, "active": name == active_name})
                except Exception:  # noqa: BLE001
                    continue
        except Exception as exc:  # noqa: BLE001
            log.warning("list_documents_failed", error=str(exc))
        return documents

    def set_active_document(self, name: str) -> bool:
        """Engancha el servidor a un documento por nombre y lo activa."""
        if not self.ensure():
            return False
        try:
            docs = self.app.Documents
            for i in range(int(docs.Count)):
                doc = docs.Item(i)
                if str(doc.Name) == name:
                    try:
                        doc.Activate()
                    except Exception:  # noqa: BLE001 - activar ventana es best-effort
                        pass
                    self.doc = doc
                    self._doc_name = name
                    log.info("active_document_changed", document=name)
                    return True
        except Exception as exc:  # noqa: BLE001
            log.warning("set_active_document_failed", error=str(exc))
        return False

"""Tests de la conexion COM sin AutoCAD.

Cubren el arreglo de reconexion: si ya hay una instancia abierta no debe crear
un dibujo nuevo (antes ``Documents.Add()`` se disparaba ante un fallo
transitorio y dejaba documentos huerfanos).
"""

from __future__ import annotations

from typing import Any

import pytest

from autocad_mcp.connection import AutoCADConnection


class _FakeDoc:
    def __init__(self, name: str) -> None:
        self.Name = name


class _FakeDocs:
    def __init__(self) -> None:
        self.added = 0

    def Add(self) -> _FakeDoc:
        self.added += 1
        return _FakeDoc("Nuevo.dwg")


class _FakeApp:
    """Imita AutoCAD.Application: ActiveDocument puede fallar y luego responder."""

    def __init__(self, doc: Any, fail_times: int = 0, always_fail: bool = False) -> None:
        self.Visible = False
        self.Documents = _FakeDocs()
        self._doc = doc
        self._fail = fail_times
        self._always_fail = always_fail

    @property
    def ActiveDocument(self) -> Any:
        if self._always_fail:
            raise RuntimeError("busy")
        if self._fail > 0:
            self._fail -= 1
            raise RuntimeError("busy")
        return self._doc


@pytest.fixture()
def quiet_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("autocad_mcp.connection.time.sleep", lambda *_: None)


def _patch(monkeypatch: pytest.MonkeyPatch, app: _FakeApp) -> dict[str, int]:
    calls = {"dispatch": 0}

    def _gao(_progid: str) -> _FakeApp:
        return app

    def _dispatch(_progid: str) -> _FakeApp:
        calls["dispatch"] += 1
        return app

    monkeypatch.setattr("autocad_mcp.connection.win32com.client.GetActiveObject", _gao)
    monkeypatch.setattr("autocad_mcp.connection.win32com.client.Dispatch", _dispatch)
    return calls


def test_reuses_active_document(monkeypatch: pytest.MonkeyPatch, quiet_sleep: None) -> None:
    app = _FakeApp(_FakeDoc("Drawing5.dwg"))
    calls = _patch(monkeypatch, app)
    conn = AutoCADConnection()
    conn._do_connect()
    assert conn.doc.Name == "Drawing5.dwg"
    assert app.Documents.added == 0
    assert calls["dispatch"] == 0


def test_retries_active_document_before_adding(
    monkeypatch: pytest.MonkeyPatch, quiet_sleep: None
) -> None:
    app = _FakeApp(_FakeDoc("Drawing5.dwg"), fail_times=2)
    _patch(monkeypatch, app)
    conn = AutoCADConnection()
    conn._do_connect()
    assert conn.doc.Name == "Drawing5.dwg"
    assert app.Documents.added == 0


def test_adds_document_only_when_none_active(
    monkeypatch: pytest.MonkeyPatch, quiet_sleep: None
) -> None:
    app = _FakeApp(None, always_fail=True)
    calls = _patch(monkeypatch, app)
    conn = AutoCADConnection()
    conn._do_connect()
    assert conn.doc.Name == "Nuevo.dwg"
    assert app.Documents.added == 1
    # El documento se agrega sobre la instancia existente, sin re-dispatch.
    assert calls["dispatch"] == 0


class _Docs:
    def __init__(self, items: list[Any]) -> None:
        self._items = items
        self.added = 0

    @property
    def Count(self) -> int:
        return len(self._items)

    def Item(self, index: int) -> Any:
        return self._items[index]

    def Add(self) -> _FakeDoc:
        self.added += 1
        return _FakeDoc("Nuevo.dwg")


class _ActiveDocApp:
    def __init__(self, docs: _Docs, active: Any) -> None:
        self.Visible = False
        self.Documents = docs
        self._active = active

    @property
    def ActiveDocument(self) -> Any:
        return self._active


class _DeadDoc:
    """Simula un documento cerrado: su nombre ya no se puede leer."""

    @property
    def Name(self) -> str:
        raise RuntimeError("documento cerrado")

    def Activate(self) -> None:
        pass


def test_rebinds_to_bound_document_after_reconnect(
    monkeypatch: pytest.MonkeyPatch, quiet_sleep: None
) -> None:
    bound = _FakeDoc("Drawing5.dwg")
    other = _FakeDoc("Drawing9.dwg")
    app = _ActiveDocApp(_Docs([bound, other]), other)
    _patch(monkeypatch, app)

    conn = AutoCADConnection()
    conn.app = app
    conn.connected = True
    conn.doc = _DeadDoc()
    conn._doc_name = "Drawing5.dwg"

    # Aunque el documento activo sea otro, la sesion recupera el suyo.
    assert conn.ensure() is True
    assert conn.doc is bound
    assert conn._doc_name == "Drawing5.dwg"


class _FlakyModelSpaceDoc:
    """ModelSpace rechaza la llamada unas veces (RPC ocupada) y luego responde."""

    def __init__(self, fail_times: int) -> None:
        self._fail = fail_times
        self.calls = 0
        self.space = object()

    @property
    def Name(self) -> str:
        return "Drawing5.dwg"

    @property
    def ModelSpace(self) -> Any:
        self.calls += 1
        if self._fail > 0:
            self._fail -= 1
            raise RuntimeError("RPC_E_CALL_REJECTED")
        return self.space


def test_model_space_retries_when_busy(quiet_sleep: None) -> None:
    doc = _FlakyModelSpaceDoc(fail_times=3)
    conn = AutoCADConnection()
    conn.connected = True
    conn.doc = doc
    assert conn.model_space() is doc.space
    assert doc.calls == 4

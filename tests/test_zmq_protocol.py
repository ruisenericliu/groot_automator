"""In-process round-trip tests for the wire protocol.

We spin up a minimal REP server in a thread that mirrors the upstream
``PolicyServer`` framing (same msgpack envelope, same endpoint dispatch) and
drive it through ``PolicyClient``. These tests catch encoding regressions
without needing the real GR00T container.
"""

from __future__ import annotations

import socket
import threading
from contextlib import closing
from typing import Any

import numpy as np
import pytest
import zmq

from src.shared.zmq_protocol import MsgSerializer, PolicyClient


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _FakeServer:
    """Minimal REP-side mirror of upstream PolicyServer for tests."""

    def __init__(self, port: int, handlers: dict[str, Any]):
        self.port = port
        self.handlers = handlers
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind(f"tcp://127.0.0.1:{port}")
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def _run(self):
        poller = zmq.Poller()
        poller.register(self.socket, zmq.POLLIN)
        while not self._stop.is_set():
            socks = dict(poller.poll(timeout=100))
            if self.socket not in socks:
                continue
            msg = self.socket.recv()
            req = MsgSerializer.from_bytes(msg)
            endpoint = req.get("endpoint", "get_action")
            handler = self.handlers[endpoint]
            data = req.get("data")
            try:
                result = handler(data) if data is not None else handler()
                self.socket.send(MsgSerializer.to_bytes(result))
            except Exception as e:  # pragma: no cover -- defensive
                self.socket.send(MsgSerializer.to_bytes({"error": str(e)}))

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)
        self.socket.close(linger=0)
        self.context.term()


@pytest.fixture
def server_factory():
    started: list[_FakeServer] = []

    def _make(handlers: dict[str, Any]) -> int:
        port = _free_port()
        server = _FakeServer(port, handlers)
        server.start()
        started.append(server)
        return port

    yield _make

    for s in started:
        s.stop()


def test_ndarray_round_trip_via_msgpack():
    arr = np.arange(12, dtype=np.float32).reshape(3, 4)
    blob = MsgSerializer.to_bytes({"x": arr})
    out = MsgSerializer.from_bytes(blob)
    assert isinstance(out["x"], np.ndarray)
    assert out["x"].dtype == np.float32
    assert out["x"].shape == (3, 4)
    np.testing.assert_array_equal(out["x"], arr)


def test_modality_config_decodes_to_plain_dict():
    # Mirrors what upstream's encoder emits for ModalityConfig.
    payload = {
        "__ModalityConfig_class__": True,
        "as_json": {"modality_keys": ["video.front"], "delta_indices": [0]},
    }
    blob = MsgSerializer.to_bytes({"cfg": payload})
    out = MsgSerializer.from_bytes(blob)
    assert out["cfg"] == {"modality_keys": ["video.front"], "delta_indices": [0]}


def test_ping(server_factory):
    port = server_factory({"ping": lambda: {"status": "ok", "message": "Server is running"}})
    with PolicyClient(host="127.0.0.1", port=port, timeout_ms=2000) as client:
        assert client.ping() is True


def test_get_action_round_trip(server_factory):
    captured: dict = {}

    def handle_get_action(data):
        captured.update(data)
        action = {"joint_pos": np.linspace(0, 1, 7, dtype=np.float32)}
        info = {"step": 1}
        return [action, info]

    port = server_factory({"get_action": handle_get_action})

    obs = {"image": np.zeros((2, 3, 4), dtype=np.uint8)}
    with PolicyClient(host="127.0.0.1", port=port, timeout_ms=2000) as client:
        action, info = client.get_action(obs, options={"deterministic": True})

    assert isinstance(action, dict)
    assert action["joint_pos"].shape == (7,)
    assert action["joint_pos"].dtype == np.float32
    assert info == {"step": 1}

    np.testing.assert_array_equal(captured["observation"]["image"], obs["image"])
    assert captured["options"] == {"deterministic": True}


def test_get_modality_config_passthrough(server_factory):
    def handle_cfg():
        # Server encodes via the ModalityConfig branch; client receives a dict.
        return {
            "video.front": {
                "__ModalityConfig_class__": True,
                "as_json": {"modality_keys": ["video.front"], "delta_indices": [0]},
            }
        }

    port = server_factory({"get_modality_config": handle_cfg})
    with PolicyClient(host="127.0.0.1", port=port, timeout_ms=2000) as client:
        cfg = client.get_modality_config()
    assert cfg["video.front"] == {
        "modality_keys": ["video.front"],
        "delta_indices": [0],
    }


def test_server_error_raises():
    # Server sends a dict with "error" -> client raises RuntimeError.
    port = _free_port()
    ctx = zmq.Context()
    sock = ctx.socket(zmq.REP)
    sock.bind(f"tcp://127.0.0.1:{port}")

    def run_once():
        msg = sock.recv()
        _ = MsgSerializer.from_bytes(msg)
        sock.send(MsgSerializer.to_bytes({"error": "boom"}))

    t = threading.Thread(target=run_once, daemon=True)
    t.start()
    try:
        with PolicyClient(host="127.0.0.1", port=port, timeout_ms=2000) as client:
            with pytest.raises(RuntimeError, match="boom"):
                client.call_endpoint("get_action", {"observation": {}, "options": None})
    finally:
        t.join(timeout=2)
        sock.close(linger=0)
        ctx.term()


def test_timeout_rebuilds_socket():
    # Connect to a port nobody is listening on -> recv times out -> ping returns False.
    port = _free_port()
    with PolicyClient(host="127.0.0.1", port=port, timeout_ms=200) as client:
        assert client.ping() is False
        # After timeout, socket should be usable again (no stuck REQ state).
        assert client.ping() is False

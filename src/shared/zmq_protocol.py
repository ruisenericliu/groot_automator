# Wire protocol for talking to the GR00T inference server.
#
# Byte-for-byte compatible with upstream Isaac-GR00T's
# ``gr00t/policy/server_client.py`` at commit
# ``23ace64f17aa5015259b8609d371eb61a357c776`` (n1.7-release).
#
# A frozen copy of the upstream file lives at
# ``docs/references/upstream-server-client.py`` -- diff this module against it
# when bumping the Isaac-GR00T pin.
#
# Differences from upstream, by design:
#   * Client side only -- no ``PolicyServer`` (lives in the container).
#   * No dependency on the ``gr00t`` package. ``ModalityConfig`` payloads are
#     passed through as plain dicts on decode; we never need to reconstruct the
#     dataclass on this side.
#   * No ``BasePolicy`` subclassing. The Isaac client calls ``PolicyClient``
#     directly; we don't need the strict-mode observation/action validation.

from __future__ import annotations

import io
from typing import Any

import msgpack
import numpy as np
import zmq

DEFAULT_MODEL_SERVER_PORT = 5555
DEFAULT_TIMEOUT_MS = 15000


class MsgSerializer:
    @staticmethod
    def to_bytes(data: Any) -> bytes:
        return msgpack.packb(data, default=MsgSerializer.encode_custom_classes)

    @staticmethod
    def from_bytes(data: bytes) -> Any:
        return msgpack.unpackb(data, object_hook=MsgSerializer.decode_custom_classes)

    @staticmethod
    def decode_custom_classes(obj):
        if not isinstance(obj, dict):
            return obj
        if "__ModalityConfig_class__" in obj:
            # Upstream reconstructs ``ModalityConfig(**obj["as_json"])`` here;
            # client side only needs the dict, so pass it through.
            return obj["as_json"]
        if "__ndarray_class__" in obj:
            return np.load(io.BytesIO(obj["as_npy"]), allow_pickle=False)
        return obj

    @staticmethod
    def encode_custom_classes(obj):
        if isinstance(obj, np.ndarray):
            output = io.BytesIO()
            np.save(output, obj, allow_pickle=False)
            return {"__ndarray_class__": True, "as_npy": output.getvalue()}
        return obj


class PolicyClient:
    def __init__(
        self,
        host: str = "localhost",
        port: int = DEFAULT_MODEL_SERVER_PORT,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
        api_token: str | None = None,
    ):
        self.context = zmq.Context()
        self.host = host
        self.port = port
        self.timeout_ms = timeout_ms
        self.api_token = api_token
        self._init_socket()

    def _init_socket(self):
        # Close any previous socket so context.term() can return cleanly later.
        # ``linger=0`` discards undelivered messages (REQ socket may be stuck
        # mid-handshake after a timeout).
        old = getattr(self, "socket", None)
        if old is not None:
            old.close(linger=0)
        self.socket = self.context.socket(zmq.REQ)
        self.socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        self.socket.connect(f"tcp://{self.host}:{self.port}")

    def ping(self) -> bool:
        try:
            self.call_endpoint("ping", requires_input=False)
            return True
        except zmq.error.ZMQError:
            self._init_socket()
            return False

    def kill_server(self):
        self.call_endpoint("kill", requires_input=False)

    def call_endpoint(
        self,
        endpoint: str,
        data: dict | None = None,
        requires_input: bool = True,
    ) -> Any:
        request: dict = {"endpoint": endpoint}
        if requires_input:
            request["data"] = data
        if self.api_token:
            request["api_token"] = self.api_token

        try:
            self.socket.send(MsgSerializer.to_bytes(request))
            message = self.socket.recv()
        except zmq.error.Again:
            # REQ socket is now stuck waiting for a reply that will never come.
            # Rebuild it so the next call can send, then re-raise.
            self._init_socket()
            raise

        if message == b"ERROR":
            raise RuntimeError("Server error. Make sure we are running the correct policy server.")
        response = MsgSerializer.from_bytes(message)
        if isinstance(response, dict) and "error" in response:
            raise RuntimeError(f"Server error: {response['error']}")
        return response

    def get_action(
        self,
        observation: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        response = self.call_endpoint(
            "get_action", {"observation": observation, "options": options}
        )
        return tuple(response)

    def reset(self, options: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.call_endpoint("reset", {"options": options})

    def get_modality_config(self) -> dict[str, Any]:
        return self.call_endpoint("get_modality_config", requires_input=False)

    def close(self):
        if getattr(self, "socket", None) is not None:
            self.socket.close(linger=0)
            self.socket = None
        if getattr(self, "context", None) is not None:
            self.context.term()
            self.context = None

    def __enter__(self) -> PolicyClient:
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

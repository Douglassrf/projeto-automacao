from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import ssl
import struct
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings
from app.schemas.deriv import DerivProposalRequest


class DerivIntegrationError(RuntimeError):
    """Falha controlada da integração com a Deriv API."""


@dataclass(frozen=True)
class DerivConnectionConfig:
    endpoint: str
    app_id: str
    token: str | None
    timeout_seconds: float
    mock_enabled: bool

    @property
    def websocket_url(self) -> str:
        return f"wss://{self.endpoint}/websockets/v3?app_id={self.app_id}"


class DerivClient:
    """Cliente mínimo para a WebSocket API da Deriv.

    Fluxo baseado na documentação oficial da Deriv: conexão WebSocket em
    /websockets/v3 com app_id, `authorize` antes de chamadas privadas, `ticks`
    para preço em tempo real, `proposal` antes de uma eventual compra e `buy`
    somente fora do modo dry-run.
    """

    def __init__(self, settings: Settings | None = None):
        settings = settings or get_settings()
        self.config = DerivConnectionConfig(
            endpoint=settings.deriv_endpoint,
            app_id=settings.deriv_app_id,
            token=settings.deriv_api_token,
            timeout_seconds=settings.deriv_timeout_seconds,
            mock_enabled=settings.deriv_mock_enabled,
        )
        self.default_symbol = settings.deriv_default_symbol
        self.default_currency = settings.deriv_default_currency

    def status(self) -> dict[str, Any]:
        notes = [
            "Use DERIV_MOCK_ENABLED=false para chamadas reais de ping/ticks/proposal.",
            "Compra real fica bloqueada por padrão: envie dry_run=false somente após validar token e risco.",
        ]
        if not self.config.token:
            notes.append("DERIV_API_TOKEN ausente; chamadas privadas como proposal/buy exigem token com escopos corretos.")
        return {
            "configured": bool(self.config.app_id and self.config.endpoint),
            "mode": "mock" if self.config.mock_enabled else "real",
            "endpoint": self.config.endpoint,
            "app_id": self.config.app_id,
            "default_symbol": self.default_symbol,
            "can_trade": bool(self.config.token) and not self.config.mock_enabled,
            "notes": notes,
        }

    def ping(self) -> dict[str, Any]:
        return self._send({"ping": 1}, needs_auth=False)

    def tick(self, symbol: str | None = None) -> dict[str, Any]:
        selected_symbol = symbol or self.default_symbol
        return self._send({"ticks": selected_symbol, "subscribe": 0}, needs_auth=False)

    def proposal(self, payload: DerivProposalRequest) -> dict[str, Any]:
        request = self.build_proposal_payload(payload)
        if payload.dry_run:
            return {
                "status": "ready",
                "mode": "dry_run",
                "dry_run": True,
                "request": request,
                "response": None,
                "warnings": ["Dry-run ativo: nenhuma ordem foi comprada na Deriv."],
            }
        response = self._send(request, needs_auth=True)
        return {
            "status": "sent",
            "mode": "real",
            "dry_run": False,
            "request": request,
            "response": response,
            "warnings": ["Proposal enviada; compra ainda requer chamada buy separada e aprovação humana."],
        }

    def build_proposal_payload(self, payload: DerivProposalRequest) -> dict[str, Any]:
        return {
            "proposal": 1,
            "amount": payload.amount,
            "basis": payload.basis,
            "contract_type": payload.contract_type,
            "currency": payload.currency or self.default_currency,
            "duration": payload.duration,
            "duration_unit": payload.duration_unit,
            "symbol": payload.symbol or self.default_symbol,
        }

    def _send(self, request: dict[str, Any], *, needs_auth: bool) -> dict[str, Any]:
        if self.config.mock_enabled:
            return {"mock": True, "echo_req": request, "msg_type": next(iter(request))}
        try:
            ws = _StdlibWebSocketClient(
                host=self.config.endpoint,
                path=f"/websockets/v3?app_id={self.config.app_id}",
                timeout_seconds=self.config.timeout_seconds,
            )
            try:
                if needs_auth:
                    if not self.config.token:
                        raise DerivIntegrationError("DERIV_API_TOKEN obrigatório para esta chamada.")
                    ws.send_json({"authorize": self.config.token})
                    auth_response = ws.recv_json()
                    self._raise_for_deriv_error(auth_response)
                ws.send_json(request)
                response = ws.recv_json()
                self._raise_for_deriv_error(response)
                return response
            finally:
                ws.close()
        except DerivIntegrationError:
            raise
        except Exception as exc:
            raise DerivIntegrationError(f"Falha ao comunicar com Deriv API: {exc}") from exc

    @staticmethod
    def _raise_for_deriv_error(response: dict[str, Any]) -> None:
        error = response.get("error")
        if error:
            raise DerivIntegrationError(error.get("message") or "Erro retornado pela Deriv API.")


class _StdlibWebSocketClient:
    """Cliente WebSocket TLS mínimo (texto JSON) para evitar dependência runtime extra."""

    def __init__(self, *, host: str, path: str, timeout_seconds: float):
        self.host = host
        raw = socket.create_connection((host, 443), timeout=timeout_seconds)
        self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
        self.sock.settimeout(timeout_seconds)
        self._handshake(path)

    def _handshake(self, path: str) -> None:
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {self.host}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode("ascii"))
        response = self._read_until(b"\r\n\r\n").decode("iso-8859-1")
        expected = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        ).decode("ascii")
        if " 101 " not in response or expected not in response:
            raise DerivIntegrationError("Handshake WebSocket com Deriv API falhou.")

    def send_json(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        mask = os.urandom(4)
        header = bytearray([0x81])
        length = len(data)
        if length < 126:
            header.append(0x80 | length)
        elif length <= 0xFFFF:
            header.extend([0x80 | 126, *struct.pack("!H", length)])
        else:
            header.extend([0x80 | 127, *struct.pack("!Q", length)])
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
        self.sock.sendall(bytes(header) + mask + masked)

    def recv_json(self) -> dict[str, Any]:
        first, second = self._read_exact(2)
        opcode = first & 0x0F
        if opcode == 0x8:
            raise DerivIntegrationError("Deriv API fechou a conexão WebSocket.")
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._read_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read_exact(8))[0]
        if second & 0x80:
            mask = self._read_exact(4)
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(self._read_exact(length)))
        else:
            payload = self._read_exact(length)
        return json.loads(payload.decode("utf-8"))

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass

    def _read_exact(self, size: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < size:
            chunk = self.sock.recv(size - len(chunks))
            if not chunk:
                raise DerivIntegrationError("Conexão WebSocket encerrada antes da resposta completa.")
            chunks.extend(chunk)
        return bytes(chunks)

    def _read_until(self, marker: bytes) -> bytes:
        chunks = bytearray()
        while marker not in chunks:
            chunk = self.sock.recv(1)
            if not chunk:
                raise DerivIntegrationError("Conexão WebSocket encerrada durante handshake.")
            chunks.extend(chunk)
        return bytes(chunks)

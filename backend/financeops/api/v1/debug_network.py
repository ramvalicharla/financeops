from __future__ import annotations

import asyncio
import socket
import ssl
from typing import Any

from fastapi import APIRouter

router = APIRouter(tags=["Debug"])

_TARGET_HOST = "aws-1-ap-southeast-2.pooler.supabase.com"
_TARGET_PORT = 5432


def _error_payload(exc: BaseException) -> dict[str, str]:
    message = str(exc).strip() or repr(exc)
    return {
        "type": exc.__class__.__name__,
        "message": message,
    }


@router.get("/debug-network-full")
async def debug_network_full() -> dict[str, Any]:
    """
    Deep outbound network diagnostics for Railway runtime.
    """
    result: dict[str, Any] = {
        "target": {"host": _TARGET_HOST, "port": _TARGET_PORT},
        "dns": {"status": "failure", "ip": None},
        "tcp": {"status": "failure"},
        "tls": {"status": "failure"},
        "error": None,
    }

    error_details: dict[str, Any] = {}

    # 1) DNS resolution
    try:
        ip = await asyncio.to_thread(socket.gethostbyname, _TARGET_HOST)
        result["dns"] = {"status": "success", "ip": ip}
    except Exception as exc:
        payload = _error_payload(exc)
        result["dns"] = {"status": "failure", "ip": None, "error": payload}
        error_details["dns"] = payload

    # 2) TCP connect
    tcp_writer = None
    try:
        _, tcp_writer = await asyncio.wait_for(
            asyncio.open_connection(_TARGET_HOST, _TARGET_PORT),
            timeout=8.0,
        )
        result["tcp"] = {"status": "success"}
    except Exception as exc:
        payload = _error_payload(exc)
        result["tcp"] = {"status": "failure", "error": payload}
        error_details["tcp"] = payload
    finally:
        if tcp_writer is not None:
            tcp_writer.close()
            await tcp_writer.wait_closed()

    # 3) TLS connect (optional)
    tls_writer = None
    try:
        ssl_context = ssl.create_default_context()
        _, tls_writer = await asyncio.wait_for(
            asyncio.open_connection(
                _TARGET_HOST,
                _TARGET_PORT,
                ssl=ssl_context,
                server_hostname=_TARGET_HOST,
            ),
            timeout=10.0,
        )
        result["tls"] = {"status": "success"}
    except Exception as exc:
        payload = _error_payload(exc)
        result["tls"] = {"status": "failure", "error": payload}
        error_details["tls"] = payload
    finally:
        if tls_writer is not None:
            tls_writer.close()
            await tls_writer.wait_closed()

    result["error"] = error_details or None
    return result

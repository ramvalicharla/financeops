from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage
from typing import Any

import httpx


def create_textract_client(region: str) -> Any:
    import boto3

    return boto3.client("textract", region_name=region)


async def send_smtp_message(
    message: EmailMessage,
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    timeout: int = 30,
) -> None:
    def _send() -> None:
        with smtplib.SMTP(host=host, port=port, timeout=timeout) as smtp:
            smtp.ehlo()
            try:
                smtp.starttls()
                smtp.ehlo()
            except smtplib.SMTPException:
                pass
            if user and password:
                smtp.login(user, password)
            smtp.send_message(message)

    await asyncio.to_thread(_send)


async def post_bytes(
    *,
    url: str,
    body: bytes,
    headers: dict[str, str],
    timeout: float = 30.0,
) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(url=url, content=body, headers=headers)


async def get_request(
    *,
    url: str,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.get(url, headers=headers, params=params or {})


async def post_form_request(
    *,
    url: str,
    data: dict[str, Any],
    timeout: float = 30.0,
) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(url, data=data)


async def request_with_client(
    method: str,
    *,
    url: str,
    timeout: float = 30.0,
    client_kwargs: dict[str, Any] | None = None,
    request_kwargs: dict[str, Any] | None = None,
) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout, **(client_kwargs or {})) as client:
        return await client.request(method, url, **(request_kwargs or {}))


async def probe_smtp_connection(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    timeout: int = 15,
) -> None:
    def _probe() -> None:
        with smtplib.SMTP(host=host, port=port, timeout=timeout) as smtp:
            smtp.ehlo()
            try:
                smtp.starttls()
                smtp.ehlo()
            except smtplib.SMTPException:
                pass
            smtp.login(user, password)

    await asyncio.to_thread(_probe)

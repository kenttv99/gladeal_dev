from __future__ import annotations

import asyncio
import base64
import json
import ssl
import time
import unittest
from collections import Counter
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

from sqlalchemy import delete, select

from api.utils.jwt_methods import generate_access_token
from database.config import AsyncSessionLocal
from database.models.orders import Order, OrderStatusHistory
from database.models.users import User


USERS_CONFIG: dict[str, Any] = {
    # ID реальных пользователей из БД.
    "user_ids": (9,11),
    # Минимальное количество пользователей для запуска теста.
    "min_users": 2,
}

REQUEST_CONFIG: dict[str, Any] = {
    # Базовый адрес уже запущенного uvicorn-сервера.
    "base_url": "http://127.0.0.1:8000",
    # HTTP-метод тестируемого API-запроса.
    "method": "GET",
    # Путь endpoint, который выполняет реальные запросы к БД.
    "path": "/api/v1/client/deals",
    # JSON-тело запроса; для GET-запросов оставляем None.
    "json": None,
    # Ожидаемый HTTP-статус успешного ответа.
    "expected_status": 200,
    # Если True, в JSON-тело каждого запроса будет подставлен user_id текущего пользователя.
    "inject_user_id": False,
}

LOAD_CONFIG: dict[str, Any] = {
    # Общее количество запросов за один прогон теста.
    "total_requests": 500,
    # Максимальное количество запросов, одновременно находящихся в обработке.
    "concurrency": 500,
    # Таймаут одного запроса в секундах.
    "request_timeout_seconds": 10.0,
}

REPORT_CONFIG: dict[str, Any] = {
    # Файл, в который записывается полный отчет по каждому запросу.
    "path": Path(__file__).with_name("api_db_load_report.json"),
    # Количество самых медленных и ошибочных запросов, выводимых отдельными списками.
    "slowest_requests": 20,
}

CLEANUP_CONFIG: dict[str, Any] = {
    # Удаление сделок после завершения теста.
    "enabled": True,
    # Если True, удаляются только сделки, созданные после старта текущего теста.
    "created_during_test_only": True,
}

PERFORMANCE_LIMITS: dict[str, Any] = {
    # Максимально допустимая доля ошибочных запросов.
    "max_error_rate": 0.0,
    # Максимально допустимый p95 в секундах; None отключает проверку.
    "max_p95_seconds": None,
    # Максимально допустимое общее время теста в секундах; None отключает проверку.
    "max_total_seconds": None,
}


def _auth_header(user_id: int) -> str:
    """Формирует Basic Authorization header с JWT-токеном для реального user_id."""
    token = generate_access_token(user_id)
    encoded = base64.b64encode(f"{user_id}:{token}".encode()).decode()
    return f"Basic {encoded}"


def _request_url() -> str:
    """Собирает полный URL запроса из base_url и path."""
    path = str(REQUEST_CONFIG["path"])
    if urlsplit(path).scheme:
        return path
    return urljoin(f"{REQUEST_CONFIG['base_url']}/", path.lstrip("/"))


async def _http_request(method: str, url: str, user_id: int, payload: dict[str, Any] | None):
    """Выполняет реальный HTTP-запрос к запущенному uvicorn-серверу."""
    parsed_url = urlsplit(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
        raise ValueError(f"Invalid request URL: {url}")

    port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
    target = parsed_url.path or "/"
    if parsed_url.query:
        target = f"{target}?{parsed_url.query}"

    body = b"" if payload is None else json.dumps(payload, default=str).encode()
    host = parsed_url.hostname
    if parsed_url.port:
        host = f"{host}:{parsed_url.port}"

    headers = [
        f"{method.upper()} {target} HTTP/1.1",
        f"Host: {host}",
        f"Authorization: {_auth_header(user_id)}",
        "Accept: application/json",
        "Connection: close",
    ]
    if body:
        headers += ["Content-Type: application/json", f"Content-Length: {len(body)}"]

    context = ssl.create_default_context() if parsed_url.scheme == "https" else None
    reader, writer = await asyncio.open_connection(parsed_url.hostname, port, ssl=context)
    try:
        writer.write(("\r\n".join(headers) + "\r\n\r\n").encode() + body)
        await writer.drain()
        response = await reader.read()
    finally:
        writer.close()
        await writer.wait_closed()

    response_head, _, response_body = response.partition(b"\r\n\r\n")
    status_line = response_head.splitlines()[0].decode("iso-8859-1")
    return int(status_line.split()[1]), response_body


def _request_payload(user_id: int) -> dict[str, Any] | None:
    """Возвращает JSON-тело запроса и при необходимости подставляет user_id."""
    payload = REQUEST_CONFIG["json"]
    if payload is None:
        return None
    payload = dict(payload)
    if REQUEST_CONFIG["inject_user_id"]:
        payload["user_id"] = user_id
    return payload


async def _timed_request(
    index: int,
    user_id: int,
    start: asyncio.Event,
    ready: asyncio.Queue,
    semaphore: asyncio.Semaphore,
):
    """Ожидает общий старт, выполняет один запрос и возвращает его метрики."""
    async with semaphore:
        ready.put_nowait(None)
        await start.wait()
        started_at = time.perf_counter()
        try:
            status, body = await asyncio.wait_for(
                _http_request(
                    REQUEST_CONFIG["method"],
                    _request_url(),
                    user_id,
                    _request_payload(user_id),
                ),
                timeout=LOAD_CONFIG["request_timeout_seconds"],
            )
            error = None
        except Exception as exc:
            status, body, error = None, b"", repr(exc)
        duration = time.perf_counter() - started_at
        return {
            "index": index,
            "user_id": user_id,
            "status_code": status,
            "duration_seconds": round(duration, 6),
            "ok": status == REQUEST_CONFIG["expected_status"] and error is None,
            "error": error,
            "body_preview": (
                "" if status == REQUEST_CONFIG["expected_status"] else body[:300].decode(errors="replace")
            ),
        }


def _percentile(values: list[float], percentile: float) -> float:
    """Считает percentile по отсортированному списку длительностей запросов."""
    values = sorted(values)
    index = max(0, min(ceil(len(values) * percentile / 100) - 1, len(values) - 1))
    return values[index]


class ApiDbLoadTest(unittest.IsolatedAsyncioTestCase):
    async def test_1000_concurrent_api_db_requests(self):
        """Запускает 1000 конкурентных API-запросов и фиксирует время каждого обращения к БД."""
        user_ids = tuple(int(user_id) for user_id in USERS_CONFIG["user_ids"])
        if not user_ids:
            self.skipTest("Set real user ids in USERS_CONFIG['user_ids'].")
        if len(user_ids) < USERS_CONFIG["min_users"]:
            self.fail(f"Expected at least {USERS_CONFIG['min_users']} configured users, got {len(user_ids)}.")
        if LOAD_CONFIG["total_requests"] <= 0 or LOAD_CONFIG["concurrency"] <= 0:
            self.fail("LOAD_CONFIG['total_requests'] and LOAD_CONFIG['concurrency'] must be positive.")
        await self._assert_users_exist(user_ids)
        await self._assert_server_available()

        test_started_at = datetime.now(timezone.utc)
        try:
            start = asyncio.Event()
            ready = asyncio.Queue()
            semaphore = asyncio.Semaphore(LOAD_CONFIG["concurrency"])
            tasks = [
                asyncio.create_task(_timed_request(index, user_ids[index % len(user_ids)], start, ready, semaphore))
                for index in range(LOAD_CONFIG["total_requests"])
            ]
            for _ in range(min(LOAD_CONFIG["total_requests"], LOAD_CONFIG["concurrency"])):
                await ready.get()
            started_at = time.perf_counter()
            start.set()
            results = await asyncio.gather(*tasks)
            total_seconds = time.perf_counter() - started_at

            report = self._build_report(results, total_seconds)
            REPORT_CONFIG["path"].write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(report["summary"], ensure_ascii=False, indent=2))

            limits = PERFORMANCE_LIMITS
            self.assertLessEqual(report["summary"]["error_rate"], limits["max_error_rate"])
            if limits["max_p95_seconds"] is not None:
                self.assertLessEqual(report["summary"]["p95_seconds"], limits["max_p95_seconds"])
            if limits["max_total_seconds"] is not None:
                self.assertLessEqual(report["summary"]["total_seconds"], limits["max_total_seconds"])
        finally:
            deleted_orders = await self._cleanup_orders(user_ids, test_started_at)
            if deleted_orders:
                print(f"Deleted test orders: {deleted_orders}")

    async def _assert_users_exist(self, user_ids: tuple[int, ...]) -> None:
        """Проверяет наличие всех пользователей из USERS_CONFIG в текущей БД."""
        async with AsyncSessionLocal() as session:
            existing = set((await session.scalars(select(User.id).where(User.id.in_(user_ids)))).all())
        missing = sorted(set(user_ids) - existing)
        if missing:
            self.fail(f"Configured users do not exist in database: {missing}")

    async def _assert_server_available(self) -> None:
        """Проверяет, что uvicorn-сервер доступен по REQUEST_CONFIG['base_url']."""
        url = urlsplit(_request_url())
        if url.scheme not in {"http", "https"} or not url.hostname:
            self.fail(f"Invalid request URL: {_request_url()}")
        port = url.port or (443 if url.scheme == "https" else 80)
        context = ssl.create_default_context() if url.scheme == "https" else None
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(url.hostname, port, ssl=context),
                timeout=LOAD_CONFIG["request_timeout_seconds"],
            )
        except Exception as exc:
            self.fail(f"Uvicorn server is not available at {REQUEST_CONFIG['base_url']}: {exc!r}")
        else:
            writer.close()
            await writer.wait_closed()

    async def _cleanup_orders(self, user_ids: tuple[int, ...], test_started_at: datetime) -> int:
        """Удаляет тестовые сделки и связанные записи истории статусов после прогона."""
        if not CLEANUP_CONFIG["enabled"]:
            return 0

        orders_query = select(Order.id).where(Order.client_id.in_(user_ids))
        if CLEANUP_CONFIG["created_during_test_only"]:
            orders_query = orders_query.where(Order.created_at >= test_started_at)

        async with AsyncSessionLocal() as session:
            async with session.begin():
                order_ids = list((await session.scalars(orders_query)).all())
                if not order_ids:
                    return 0
                await session.execute(delete(OrderStatusHistory).where(OrderStatusHistory.order_id.in_(order_ids)))
                await session.execute(delete(Order).where(Order.id.in_(order_ids)))
                return len(order_ids)

    def _build_report(self, results: list[dict[str, Any]], total_seconds: float) -> dict[str, Any]:
        """Собирает JSON-отчет с общей статистикой и деталями по каждому запросу."""
        durations = [result["duration_seconds"] for result in results]
        failures = [result for result in results if not result["ok"]]
        summary = {
            "total_requests": len(results),
            "concurrency": LOAD_CONFIG["concurrency"],
            "total_seconds": round(total_seconds, 6),
            "requests_per_second": round(len(results) / total_seconds, 3),
            "min_seconds": min(durations),
            "p50_seconds": _percentile(durations, 50),
            "p95_seconds": _percentile(durations, 95),
            "p99_seconds": _percentile(durations, 99),
            "max_seconds": max(durations),
            "error_count": len(failures),
            "error_rate": round(len(failures) / len(results), 6),
            "status_counts": dict(Counter(str(result["status_code"]) for result in results)),
        }
        slowest = sorted(results, key=lambda result: result["duration_seconds"], reverse=True)[
            : REPORT_CONFIG["slowest_requests"]
        ]
        return {
            "config": {
                "users": USERS_CONFIG,
                "request": {
                    "full_url": _request_url(),
                    **{
                        key: str(value) if isinstance(value, Path) else value
                        for key, value in REQUEST_CONFIG.items()
                    },
                },
                "load": LOAD_CONFIG,
                "cleanup": CLEANUP_CONFIG,
                "performance_limits": PERFORMANCE_LIMITS,
            },
            "summary": summary,
            "slowest_requests": slowest,
            "failures": failures[: REPORT_CONFIG["slowest_requests"]],
            "requests": results,
        }


if __name__ == "__main__":
    unittest.main(verbosity=2)

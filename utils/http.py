import asyncio
import json
from typing import Any

import aiohttp

from utils.config import HEADERS
from utils.logger import logger


async def fetch_json_with_retry(
    session: aiohttp.ClientSession,
    url: str,
    *,
    retries: int = 3,
    timeout_seconds: int = 20,
    retry_delay: float = 2.0,
) -> dict[str, Any] | None:
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    for attempt in range(1, retries + 1):
        try:
            async with session.get(url, headers=HEADERS, timeout=timeout) as response:
                if response.status == 429:
                    logger.warning("429 bei %s (Versuch %s/%s)", url, attempt, retries)
                    if attempt < retries:
                        await asyncio.sleep(retry_delay * attempt)
                        continue
                    return None

                if 500 <= response.status < 600:
                    logger.warning("Serverfehler %s bei %s (Versuch %s/%s)", response.status, url, attempt, retries)
                    if attempt < retries:
                        await asyncio.sleep(retry_delay * attempt)
                        continue
                    return None

                response.raise_for_status()

                # Text explizit lesen, nicht über response.json()
                text = await response.text()
                try:
                    return json.loads(text)
                except json.JSONDecodeError as je:
                    logger.warning("JSON-Decode-Fehler bei %s (Versuch %s/%s): %s", url, attempt, retries, je)
                    if attempt < retries:
                        await asyncio.sleep(retry_delay * attempt)
                    else:
                        logger.error("JSON-Request dauerhaft fehlgeschlagen fuer %s", url)
                        return None

        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.warning("Request fehlgeschlagen fuer %s (Versuch %s/%s): %s", url, attempt, retries, exc)
            if attempt < retries:
                await asyncio.sleep(retry_delay * attempt)
            else:
                logger.error("Request dauerhaft fehlgeschlagen fuer %s", url)
                return None

    return None


async def fetch_text_with_retry(
    session: aiohttp.ClientSession,
    url: str,
    *,
    retries: int = 3,
    timeout_seconds: int = 20,
    retry_delay: float = 2.0,
) -> str | None:
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    for attempt in range(1, retries + 1):
        try:
            async with session.get(url, headers=HEADERS, timeout=timeout) as response:
                if response.status == 429:
                    logger.warning("429 bei %s (Versuch %s/%s)", url, attempt, retries)
                    if attempt < retries:
                        await asyncio.sleep(retry_delay * attempt)
                        continue
                    return None

                if 500 <= response.status < 600:
                    logger.warning("Serverfehler %s bei %s (Versuch %s/%s)", response.status, url, attempt, retries)
                    if attempt < retries:
                        await asyncio.sleep(retry_delay * attempt)
                        continue
                    return None

                response.raise_for_status()
                return await response.text()

        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.warning("Text-Request fehlgeschlagen fuer %s (Versuch %s/%s): %s", url, attempt, retries, exc)
            if attempt < retries:
                await asyncio.sleep(retry_delay * attempt)
            else:
                logger.error("Text-Request dauerhaft fehlgeschlagen fuer %s", url)
                return None

    return None
"""Airport lookup against the OurAirports public-domain dataset.

Used by the config flow only, to turn a user-entered airport code (ICAO ident
like KPIR, or IATA like PIR) into the field's elevation and coordinates.  The
CSV is downloaded once per Home Assistant process and indexed in memory; the
integration does not poll OurAirports at runtime.

Dataset: https://davidmegginson.github.io/ourairports-data/airports.csv
License: Public domain.
"""
from __future__ import annotations

import asyncio
import csv
import logging
from io import StringIO
from typing import Any

import aiohttp

from .const import OURAIRPORTS_CSV_URL, OURAIRPORTS_FETCH_TIMEOUT

_LOGGER = logging.getLogger(__name__)

_INDEX: dict[str, dict[str, Any]] | None = None
_INDEX_LOCK = asyncio.Lock()


async def lookup_airport(
    session: aiohttp.ClientSession, code: str
) -> dict[str, Any] | None:
    """Resolve an ICAO (``KPIR``) or IATA (``PIR``) code to an airport record.

    Returns a dict with ``ident``, ``iata``, ``name``, ``elevation_ft``,
    ``latitude_deg``, ``longitude_deg``, or ``None`` if no match / fetch failed.
    """
    key = (code or "").strip().upper()
    if not key:
        return None
    try:
        index = await _ensure_index(session)
    except (aiohttp.ClientError, TimeoutError, asyncio.TimeoutError) as err:
        _LOGGER.warning("OurAirports fetch failed: %s", err)
        return None
    return index.get(key)


async def _ensure_index(session: aiohttp.ClientSession) -> dict[str, dict[str, Any]]:
    global _INDEX
    async with _INDEX_LOCK:
        if _INDEX is not None:
            return _INDEX

        async with asyncio.timeout(OURAIRPORTS_FETCH_TIMEOUT):
            resp = await session.get(OURAIRPORTS_CSV_URL)
            resp.raise_for_status()
            text = await resp.text()

        index: dict[str, dict[str, Any]] = {}
        for row in csv.DictReader(StringIO(text)):
            rec = {
                "ident": (row.get("ident") or "").strip(),
                "iata": (row.get("iata_code") or "").strip(),
                "name": (row.get("name") or "").strip(),
                "elevation_ft": _as_int(row.get("elevation_ft")),
                "latitude_deg": _as_float(row.get("latitude_deg")),
                "longitude_deg": _as_float(row.get("longitude_deg")),
                "type": (row.get("type") or "").strip(),
            }
            if rec["ident"]:
                # ICAO idents are globally unique in this dataset.
                index[rec["ident"].upper()] = rec
            if rec["iata"]:
                # IATA codes are not unique (heliports reuse them); keep the
                # first hit and prefer whatever ICAO row may share the string.
                index.setdefault(rec["iata"].upper(), rec)
        _INDEX = index
        return index


def _as_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

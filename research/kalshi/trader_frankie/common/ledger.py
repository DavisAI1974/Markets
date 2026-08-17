"""SQLite-backed append-only trading ledger with immutable row enforcement."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping

from .hashing import canonical_json, hash_payload, new_id, utc_now

LEDGER_TABLES = (
    "forecast_envelopes",
    "kalshi_market_snapshots",
    "tasty_market_snapshots",
    "contract_mappings",
    "instrument_mappings",
    "trade_intents",
    "risk_decisions",
    "orders",
    "order_events",
    "fills",
    "positions",
    "pnl_snapshots",
    "settlements",
    "stand_downs",
    "incidents",
    "forecaster_scorecards",
    "trader_scorecards",
    "learning_proposals",
)


class LedgerError(RuntimeError):
    pass


class ImmutableTradingLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            for table in LEDGER_TABLES:
                connection.execute(
                    f"""CREATE TABLE IF NOT EXISTS {table} (
                        record_id TEXT PRIMARY KEY,
                        created_at TEXT NOT NULL,
                        correlation_id TEXT NOT NULL,
                        source_id TEXT NOT NULL,
                        source_hash TEXT NOT NULL,
                        version TEXT NOT NULL,
                        venue TEXT NOT NULL,
                        payload_json TEXT NOT NULL
                    )"""
                )
                connection.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{table}_source ON {table}(source_id)"
                )
                connection.execute(
                    f"""CREATE TRIGGER IF NOT EXISTS {table}_no_update
                    BEFORE UPDATE ON {table}
                    BEGIN SELECT RAISE(ABORT, 'immutable ledger rows cannot be updated'); END"""
                )
                connection.execute(
                    f"""CREATE TRIGGER IF NOT EXISTS {table}_no_delete
                    BEFORE DELETE ON {table}
                    BEGIN SELECT RAISE(ABORT, 'immutable ledger rows cannot be deleted'); END"""
                )

    def append(
        self,
        table: str,
        payload: Mapping[str, Any],
        *,
        correlation_id: str,
        source_id: str,
        source_hash: str | None = None,
        version: str = "1.0",
        venue: str = "COMMON",
    ) -> str:
        if table not in LEDGER_TABLES:
            raise LedgerError(f"unknown ledger table: {table}")
        if not correlation_id or not source_id:
            raise LedgerError("correlation_id and source_id are required")
        detached = json.loads(canonical_json(payload))
        observed_hash = hash_payload(detached)
        if source_hash is not None and source_hash != observed_hash:
            raise LedgerError("provided source_hash does not match immutable payload")
        record_id = new_id(table.rstrip("s"))
        created_at = utc_now().isoformat().replace("+00:00", "Z")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                f"INSERT INTO {table} VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record_id, created_at, correlation_id, source_id, observed_hash, version,
                    venue, json.dumps(detached, sort_keys=True, separators=(",", ":")),
                ),
            )
        return record_id

    def contains_source(self, table: str, source_id: str) -> bool:
        if table not in LEDGER_TABLES:
            raise LedgerError(f"unknown ledger table: {table}")
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT 1 FROM {table} WHERE source_id = ? LIMIT 1", (source_id,)
            ).fetchone()
        return row is not None

    def read(self, table: str, *, source_id: str | None = None) -> Iterable[dict[str, Any]]:
        if table not in LEDGER_TABLES:
            raise LedgerError(f"unknown ledger table: {table}")
        query = f"SELECT * FROM {table}"
        parameters: tuple[Any, ...] = ()
        if source_id is not None:
            query += " WHERE source_id = ?"
            parameters = (source_id,)
        query += " ORDER BY created_at, record_id"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        for row in rows:
            value = dict(row)
            value["payload"] = json.loads(value.pop("payload_json"))
            yield value

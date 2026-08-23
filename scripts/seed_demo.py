"""
Seed demo — generates fictional operational data for the portfolio dashboard.

Creates the `abiertas` and `completas` databases and tables (if missing),
then fills them with ~120 days of realistic but entirely FICTIONAL work
orders across the 5 demo hubs (ZAP, VIL, TUX, SOT, GRA).

No real operational data is generated or referenced. Coordinates, order
types and volumes are invented purely to make the dashboard and the
executive report render with non-empty, plausible numbers.

If using Docker compose:

    docker compose up -d db
    docker compose run --rm seed python scripts/seed_demo.py

Or directly with a local PostgreSQL:

    python scripts/seed_demo.py
"""

from __future__ import annotations

import os
import random
from datetime import date, timedelta

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# ─── Demo hubs (fictional) ────────────────────────────────────────────
HUBS = ["ZAP", "VIL", "TUX", "SOT", "GRA"]
DAYS = 120

# (tipo, metric) — metric is what the report maps each type to.
ORDER_TYPES: list[tuple[str, str]] = [
    ("Instalacion", "IN"),
    ("Cambio de Domicilio", "IN"),
    ("Cambio de Equipo", "IN"),
    ("Cambio de Servicios", "IN"),
    ("Cambio de Ubicacion", "IN"),
    ("Trouble Call Telefonia", "TC"),
    ("Trouble Call Cablemodem", "TC"),
    ("Trouble Call Video", "TC"),
    ("Trouble Call House Check", "TC"),
    ("Trouble Call", "TC"),
    ("Reconexion Pago", "Rx"),
    ("No Pago - Filtro de Video", "Dx"),
    ("Recoleccion Acometida", "RA"),
]

# Relative weights per metric → realistic volume distribution.
METRIC_WEIGHTS = {"IN": 6, "TC": 5, "Rx": 2, "Dx": 2, "RA": 1}

TECNICOS = [f"TEC{i:03d}" for i in range(1, 14)]


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _params() -> dict:
    return {
        "host": _env("DB_HOST", "localhost"),
        "port": int(_env("DB_PORT", "5432")),
        "user": _env("DB_USER", "postgres"),
        "password": _env("DB_PASS", "changeme"),
    }


def _connect(dbname: str | None = None, autocommit: bool = False):
    conn = psycopg2.connect(dbname=dbname or "postgres", **_params())
    if autocommit:
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    return conn


def _ensure_database(admin, dbname: str) -> None:
    cur = admin.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
    if cur.fetchone() is None:
        # CREATE DATABASE cannot run inside a transaction block.
        cur.execute(f'CREATE DATABASE "{dbname}"')
        print(f"  created database: {dbname}")
    else:
        print(f"  database exists:  {dbname}")
    cur.close()


def _ensure_tables(conn, dbname: str) -> None:
    cur = conn.cursor()
    if dbname == "abiertas":
        cur.execute("DROP TABLE IF EXISTS abiertas")
        cur.execute("""
            CREATE TABLE abiertas (
                id              SERIAL PRIMARY KEY,
                dia             DATE NOT NULL,
                hub             TEXT NOT NULL,
                tipo            TEXT NOT NULL,
                fechaorden      DATE,
                fechasolicitada DATE,
                tecnico         TEXT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_abiertas_dia_hub ON abiertas (dia, hub)")
    else:  # completas
        cur.execute("DROP TABLE IF EXISTS completas")
        cur.execute("""
            CREATE TABLE completas (
                id              SERIAL PRIMARY KEY,
                fechasolicitada DATE NOT NULL,
                hub             TEXT NOT NULL,
                tipo            TEXT NOT NULL
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_completas_fecha_hub ON completas (fechasolicitada, hub)"
        )
    conn.commit()
    cur.close()


def _pick_tipo(rng: random.Random) -> tuple[str, str]:
    metrics = [m for _, m in ORDER_TYPES]
    weights = [METRIC_WEIGHTS[m] for m in metrics]
    return rng.choices(ORDER_TYPES, weights=weights, k=1)[0]


def _gen_day_rows(rng, day: date, hub: str, start_id: int) -> list[tuple]:
    """One hub, one day → list of (id, dia, hub, tipo, fechaorden, fechasolicitada, tecnico)."""
    rows: list[tuple] = []
    weekday_factor = 0.55 if day.weekday() >= 5 else 1.0
    base = int(rng.randint(8, 18) * weekday_factor)
    n_orders = max(3, base + rng.randint(-2, 3))

    for idx in range(n_orders):
        tipo, _ = _pick_tipo(rng)
        fechaorden = day - timedelta(days=rng.randint(0, 14))
        fechasolicitada = day - timedelta(days=rng.randint(0, 5))
        tecnico = rng.choice(TECNICOS) if rng.random() < 0.85 else None
        rows.append((start_id + idx, day, hub, tipo, fechaorden, fechasolicitada, tecnico))
    return rows


def _seed_abiertas(conn, rng) -> int:
    cur = conn.cursor()
    last_day = date.today() - timedelta(days=1)
    start_id = 1
    total = 0
    for offset in range(DAYS):
        day = last_day - timedelta(days=DAYS - 1 - offset)
        for hub in HUBS:
            rows = _gen_day_rows(rng, day, hub, start_id)
            if rows:
                cur.executemany(
                    """
                    INSERT INTO abiertas (id, dia, hub, tipo, fechaorden, fechasolicitada, tecnico)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    rows,
                )
                start_id += len(rows)
                total += len(rows)
    conn.commit()
    cur.close()
    return total


def _seed_completas(conn, rng) -> int:
    cur = conn.cursor()
    total = 0
    today = date.today()
    for offset in range(DAYS):
        day = today - timedelta(days=DAYS - 1 - offset)
        for hub in HUBS:
            n = max(1, int(rng.randint(2, 9) * (0.5 if day.weekday() >= 5 else 1.0)))
            rows = [(day, hub, "Instalacion") for _ in range(n)]
            cur.executemany(
                "INSERT INTO completas (fechasolicitada, hub, tipo) VALUES (%s, %s, %s)",
                rows,
            )
            total += len(rows)
    conn.commit()
    cur.close()
    return total


def main() -> None:
    rng = random.Random(2026)  # reproducible demo data
    dbname = _env("DB_NAME", "abiertas")

    print("== Seed demo: fictional operational data ==")
    print(f"  hubs: {', '.join(HUBS)}")
    print(f"  days: {DAYS}")

    print("\n[1/3] Ensuring databases exist...")
    admin = _connect(autocommit=True)
    _ensure_database(admin, dbname)
    _ensure_database(admin, "completas")
    admin.close()

    print("\n[2/3] Ensuring tables exist...")
    conn_a = _connect(dbname)
    _ensure_tables(conn_a, "abiertas")
    conn_a.close()

    conn_c = _connect("completas")
    _ensure_tables(conn_c, "completas")
    conn_c.close()

    print("\n[3/3] Seeding data...")
    conn_a = _connect(dbname)
    total_abiertas = _seed_abiertas(conn_a, rng)
    conn_a.close()

    conn_c = _connect("completas")
    total_completas = _seed_completas(conn_c, rng)
    conn_c.close()

    print(f"\nDone! Inserted {total_abiertas:,} rows in abiertas, "
          f"{total_completas:,} rows in completas.")
    print("Demo data is fictional — no real operational information.")


if __name__ == "__main__":
    main()
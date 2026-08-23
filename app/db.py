"""
Configuración de base de datos.
"""
import os
import socket
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env desde la raíz del proyecto
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path, encoding="latin-1")


def _resolve_host() -> str:
    """Resuelve el host de la base de datos.

    Si el .env apunta a localhost/127.0.0.1, lo dejamos como está
    porque WSL2 redirige localhost a Windows automáticamente.
    host.docker.internal se usa solo desde Docker.
    """
    return os.getenv("DB_HOST", "localhost")
    return host


DB_CONFIG = {
    "host": _resolve_host(),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS")
}

DB_CONFIG_COMPLETAS = {
    "host": _resolve_host(),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": "completas",
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS")
}


def get_db_connection():
    """Retorna una conexión a la base de datos (abiertas)."""
    import psycopg2
    return psycopg2.connect(**DB_CONFIG)


def get_db_completas_connection():
    """Retorna una conexión a la base de datos completas."""
    import psycopg2
    return psycopg2.connect(**DB_CONFIG_COMPLETAS)
"""
Router para endpoints de métricas.
"""
from fastapi import APIRouter, Query
from typing import Optional, List
from datetime import datetime
import psycopg2
import os
import socket
import csv
import json
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env desde la raíz del proyecto
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path, encoding="latin-1")

router = APIRouter()


def _resolve_host() -> str:
    """Resuelve el host de la base de datos.

    Si el .env apunta a localhost/127.0.0.1 desde WSL2,
    usa la IP del gateway de Windows para llegar a PostgreSQL.
    """
    host = os.getenv("DB_HOST", "localhost")
    if host in ("localhost", "127.0.0.1"):
        try:
            # Obtener la IP del gateway de WSL (Windows host)
            gw_ip = socket.gethostbyname("host.docker.internal")
            return gw_ip
        except socket.gaierror:
            return host
    return host


# Configuración de DB - resuelva el host para WSL -> Windows
DB_CONFIG = {
    "host": _resolve_host(),
    "port": int(os.getenv("DB_PORT", "5432")),
    "database": os.getenv("DB_NAME", "abiertas"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASS", "changeme")
}

# Clasificación de tipos de órdenes
TIPO_CLASIFICACION = {
    # IN - Instalaciones
    "Nuevo Servicio": "IN",
    "Reemplazo Equipo": "IN",
    "Modif. Plan": "IN",
    "Cambio Direccion": "IN",
    "Instalacion": "IN",
    # Rx - Reconexión
    "Conexion": "Rx",
    # Dx - Desconexión
    "Suspension Servicio": "Dx",
    # RA - Retiro Equipo
    "Retiro Equipo": "RA",
    # TC - Falla General
    "Falla Telefonia": "TC",
    "Falla Internet": "TC",
    "Falla Video": "TC",
    "Verif. Domicilio": "TC",
    "Falla General": "TC",
}

# Tipos IN y TC para queries
TIPOS_IN = ["Nuevo Servicio", "Reemplazo Equipo", "Modif. Plan", 
            "Cambio Direccion", "Instalacion"]
TIPOS_TC = ["Falla Telefonia", "Falla Internet", 
            "Falla Video", "Verif. Domicilio", "Falla General"]


def clasificar_tipo(tipo: str) -> str:
    """Clasifica un tipo de orden en su categoría."""
    if not tipo or tipo.strip() == "":
        return None  # Descartamos "Otro"
    return TIPO_CLASIFICACION.get(tipo)


def get_db_connection():
    """Retorna una conexión a la base de datos."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"DB Connection error: {e}")
        return None


def require_db_connection():
    """Decorator to ensure DB connection is available."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            conn = get_db_connection()
            if not conn:
                return {"error": "No se pudo conectar a la base de datos"}
            return func(conn, *args, **kwargs)
        return wrapper
    return decorator


def get_default_dia() -> str:
    """Retorna la fecha más reciente con datos en la tabla."""
    conn = get_db_connection()
    if not conn:
        return "2026-04-04"  # fallback
    
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT MAX(dia) FROM abiertas WHERE hub IS NOT NULL AND hub != ''")
        result = cursor.fetchone()
        if result and result[0]:
            return result[0].strftime("%Y-%m-%d")
        return "2026-04-04"  # fallback
    except Exception:
        return "2026-04-04"
    finally:
        cursor.close()
        conn.close()


# Cache para datos de ruido (demo: ruta relativa, archivos opcionales)
_ruido_csv_path = os.path.join(os.path.dirname(__file__), "..", "..", "ruido_clean", "todas_zonas_ruido.csv")
_nodos_ruidosos_path = os.path.join(os.path.dirname(__file__), "..", "..", "ruido_clean", "nodos_ruidosos.json")
_cached_ruido_cuentas = None


def _load_noisy_nodes() -> set:
    """
    Carga la lista de nodos ruidosos desde nodos_ruidosos.json
    (generado por scripts/import_snr.py desde el reporte SNR diario).
    """
    try:
        with open(_nodos_ruidosos_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        nodes = set(data.get("noisy_nodes", []))
        print(f"📡 Nodos ruidosos SNR: {len(nodes)} (reporte {data.get('fecha', 'desconocida')})")
        return nodes
    except FileNotFoundError:
        print(f"⚠ nodos_ruidosos.json no encontrado: {_nodos_ruidosos_path}")
        return set()
    except Exception as e:
        print(f"⚠ Error al cargar nodos_ruidosos.json: {e}")
        return set()


def _load_ruido_cuentas() -> set:
    """
    Carga las cuentas con ruido desde el CSV, filtradas por nodos
    clasificados como ruidosos en el reporte SNR diario.
    """
    global _cached_ruido_cuentas
    if _cached_ruido_cuentas is not None:
        return _cached_ruido_cuentas

    noisy_nodes = _load_noisy_nodes()
    cuentas = set()

    if not noisy_nodes:
        print("⚠ Sin datos de nodos ruidosos — no se filtrarán cuentas por ruido.")
        _cached_ruido_cuentas = cuentas
        return _cached_ruido_cuentas

    try:
        with open(_ruido_csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cuenta = row.get("cuenta", "").strip()
                nodo = row.get("nodo_cmts", "").strip().upper()
                if cuenta and nodo in noisy_nodes:
                    cuentas.add(cuenta)
        _cached_ruido_cuentas = cuentas
        print(f"📊 Cuentas en zonas ruidosas: {len(cuentas)}")
    except FileNotFoundError:
        print(f"⚠ CSV de ruido no encontrado: {_ruido_csv_path}")
        _cached_ruido_cuentas = cuentas
    except Exception as e:
        print(f"⚠ Error al cargar CSV de ruido: {e}")
        _cached_ruido_cuentas = cuentas

    return _cached_ruido_cuentas


# Cache para ruido agregado por código postal
_cached_noise_por_cp = None


def _load_noise_por_cp() -> dict:
    """Carga y agrega datos de ruido por código postal, cacheando el resultado GeoJSON."""
    global _cached_noise_por_cp
    if _cached_noise_por_cp is not None:
        return _cached_noise_por_cp

    cp_data = {}
    try:
        with open(_ruido_csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            for row in reader:
                cp = row[4].strip()
                if not cp:
                    continue

                try:
                    cer = float(row[12])
                    snr = float(row[30])
                except (ValueError, IndexError):
                    continue

                nodo = row[-1].strip().upper()
                if nodo.startswith("HU"):
                    hub = "HUI"
                elif nodo.startswith("AP"):
                    hub = "APO"
                else:
                    continue

                if cp not in cp_data:
                    cp_data[cp] = {
                        "hubs": set(),
                        "count": 0,
                        "noisy_count": 0,
                        "cer_sum": 0.0,
                        "snr_sum": 0.0,
                    }

                entry = cp_data[cp]
                entry["hubs"].add(hub)
                entry["count"] += 1
                if cer > 1.0:
                    entry["noisy_count"] += 1
                entry["cer_sum"] += cer
                entry["snr_sum"] += snr

        features = []
        for cp, data in cp_data.items():
            count = data["count"]
            noisy = data["noisy_count"]
            pct = round((noisy / count) * 100, 2)
            avg_cer = round(data["cer_sum"] / count, 4)
            avg_snr = round(data["snr_sum"] / count, 2)

            hubs = data["hubs"]
            hub_label = "/".join(sorted(hubs))

            # Mapa de zonas por prefijo de CP en área metropolitana de Monterrey
            # Formato: prefijo: (lat_base, lng_base, spread_km)
            CP_ZONES = {
                640: (25.665, -100.315, 0.01),
                642: (25.668, -100.330, 0.02),
                643: (25.670, -100.310, 0.02),
                644: (25.672, -100.295, 0.02),
                645: (25.675, -100.285, 0.02),
                646: (25.678, -100.275, 0.02),
                647: (25.673, -100.305, 0.02),
                648: (25.668, -100.320, 0.02),
                649: (25.665, -100.335, 0.02),
                655: (25.790, -100.140, 0.03),  # Apodaca
                656: (25.795, -100.135, 0.03),
                657: (25.780, -100.350, 0.03),  # García
                658: (25.800, -100.380, 0.03),
                660: (25.680, -100.420, 0.03),  # Santa Catarina oeste
                661: (25.690, -100.430, 0.03),
                662: (25.685, -100.440, 0.03),
                663: (25.695, -100.400, 0.03),
                664: (25.750, -100.390, 0.03),  # Santa Catarina
                665: (25.720, -100.360, 0.03),
                666: (25.700, -100.320, 0.03),  # Santa Catarina centro
                667: (25.715, -100.290, 0.03),  # Santa Catarina este
                670: (25.730, -100.260, 0.03),  # Guadalupe
                671: (25.720, -100.240, 0.03),
                672: (25.700, -100.230, 0.03),
                673: (25.710, -100.250, 0.03),
                674: (25.725, -100.235, 0.03),
                675: (25.735, -100.245, 0.03),
                678: (25.695, -100.210, 0.03),  # Guadalupe sur
                680: (25.660, -100.150, 0.03),  # Juárez
                681: (25.650, -100.140, 0.03),
                682: (25.640, -100.160, 0.03),
            }
            cp_int = int(cp)
            prefix = cp_int // 100
            suffix = cp_int % 100
            base_lat, base_lng, spread = CP_ZONES.get(prefix, (25.720, -100.280, 0.03))
            # Desplazar cada CP dentro de su zona usando los últimos 2 dígitos
            offset_lat = (suffix % 10 - 4.5) * spread / 10
            offset_lng = (suffix // 10 - 4.5) * spread / 10
            lat = base_lat + offset_lat
            lng = base_lng + offset_lng

            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lng, lat],
                },
                "properties": {
                    "codigo_postal": cp,
                    "hub": hub_label,
                    "total_modems": count,
                    "noisy_modems": noisy,
                    "pct_noisy": pct,
                    "avg_cer": avg_cer,
                    "avg_snr": avg_snr,
                },
            })

        _cached_noise_por_cp = {
            "type": "FeatureCollection",
            "features": features,
        }
    except Exception as e:
        print(f"⚠ Error al cargar ruido por CP: {e}")
        _cached_noise_por_cp = {"type": "FeatureCollection", "features": []}

    return _cached_noise_por_cp


@router.get("/noise/por-cp")
def get_noise_por_cp():
    """
    Retorna datos de ruido agregados por código postal en formato GeoJSON.
    Cada feature es un punto con propiedades: codigo_postal, hub, total_modems,
    noisy_modems, pct_noisy, avg_cer, avg_snr.
    """
    return _load_noise_por_cp()


@router.get("/metrics/tc-con-ruido")
def get_tc_con_ruido(
    hub: Optional[str] = Query(None, description="Código del hub (opcional)"),
    dia: Optional[str] = Query(None, description="Fecha en formato YYYY-MM-DD (default: fecha más reciente)")
):
    """
    Cruza órdenes TC contra zonas de ruido y retorna métricas
    de cuántas TC están en zonas ruidosas.
    """
    if not dia:
        dia = get_default_dia()

    conn = get_db_connection()
    if not conn:
        return {"error": "No se pudo conectar a la base de datos"}

    cursor = conn.cursor()

    try:
        if hub:
            query = """
                SELECT cuenta, hub
                FROM abiertas
                WHERE hub = %s AND hub IS NOT NULL AND hub != ''
                  AND dia::date = %s AND tipo = ANY(%s)
                  AND cuenta IS NOT NULL AND cuenta != ''
            """
            cursor.execute(query, (hub.upper(), dia, TIPOS_TC))
        else:
            query = """
                SELECT cuenta, hub
                FROM abiertas
                WHERE hub IS NOT NULL AND hub != ''
                  AND dia::date = %s AND tipo = ANY(%s)
                  AND cuenta IS NOT NULL AND cuenta != ''
            """
            cursor.execute(query, (dia, TIPOS_TC))

        rows = cursor.fetchall()
        ruido_cuentas = _load_ruido_cuentas()

        total_tc = 0
        total_con_ruido = 0
        por_hub: dict = {}

        for row in rows:
            cuenta_val = str(row[0]).strip()
            hub_code = row[1]
            total_tc += 1

            if hub_code not in por_hub:
                por_hub[hub_code] = {"total_tc": 0, "tc_con_ruido": 0}

            en_ruido = cuenta_val in ruido_cuentas

            por_hub[hub_code]["total_tc"] += 1
            if en_ruido:
                por_hub[hub_code]["tc_con_ruido"] += 1
                total_con_ruido += 1

        resultado_por_hub = {}
        for hub_code, data in por_hub.items():
            pct = round((data["tc_con_ruido"] / data["total_tc"]) * 100, 2) if data["total_tc"] > 0 else 0.0
            resultado_por_hub[hub_code] = {
                "total_tc": data["total_tc"],
                "tc_con_ruido": data["tc_con_ruido"],
                "porcentaje": pct,
            }

        # Si hay filtro de hub, limitar respuesta a ese hub
        if hub:
            hub_code = hub.upper()
            hub_data = resultado_por_hub.get(hub_code, {"total_tc": 0, "tc_con_ruido": 0, "porcentaje": 0.0})
            total_tc = hub_data["total_tc"]
            total_con_ruido = hub_data["tc_con_ruido"]
            resultado_por_hub = {hub_code: hub_data}

        porcentaje = round((total_con_ruido / total_tc) * 100, 2) if total_tc > 0 else 0.0

        return {
            "dia": dia,
            "total_tc": total_tc,
            "tc_con_ruido": total_con_ruido,
            "porcentaje": porcentaje,
            "por_hub": resultado_por_hub,
        }

    except Exception as e:
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()


@router.get("/metrics/dias")
def get_dias_disponibles():
    """Retorna las fechas disponibles en la base de datos."""
    conn = get_db_connection()
    if not conn:
        return {"error": "No se pudo conectar a la base de datos"}
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT DISTINCT dia::date as fecha 
            FROM abiertas 
            WHERE hub IS NOT NULL AND hub != ''
            ORDER BY fecha DESC
        """)
        rows = cursor.fetchall()
        return {"dias": [row[0].strftime("%Y-%m-%d") for row in rows]}
    except Exception as e:
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()


@router.get("/metrics/summary")
def get_metrics_summary(
    hub: Optional[str] = Query(None, description="Código del hub (opcional)"),
    dia: Optional[str] = Query(None, description="Fecha en formato YYYY-MM-DD (default: fecha más reciente)")
):
    """
    Retorna métricas resumen de órdenes abiertas desde la base de datos.
    Clasificadas por: IN, Rx, Dx, RA, TC (descartamos Otros)
    """
    # Usar fecha por defecto si no se especifica
    if not dia:
        dia = get_default_dia()
    
    conn = get_db_connection()
    if not conn:
        return {"error": "No se pudo conectar a la base de datos"}
    
    cursor = conn.cursor()
    
    try:
        # Query para métricas por hub con clasificación correcta
        if hub:
            query = """
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN tipo IN ('Nuevo Servicio', 'Reemplazo Equipo', 
                            'Modif. Plan', 'Cambio Direccion', 'Instalacion') THEN 1 ELSE 0 END) as in_count,
                    SUM(CASE WHEN tipo IN ('Falla Telefonia', 'Falla Internet', 
                            'Falla Video', 'Verif. Domicilio', 'Falla General') THEN 1 ELSE 0 END) as tc_count,
                    SUM(CASE WHEN tipo = 'Conexion' THEN 1 ELSE 0 END) as rx_count,
                    SUM(CASE WHEN tipo = 'Suspension Servicio' THEN 1 ELSE 0 END) as dx_count,
                    SUM(CASE WHEN tipo = 'Retiro Equipo' THEN 1 ELSE 0 END) as ra_count
                FROM abiertas 
                WHERE hub = %s AND hub IS NOT NULL AND hub != '' AND dia::date = %s
            """
            cursor.execute(query, (hub.upper(), dia))
            row = cursor.fetchone()
            
            return {
                "hub": hub.upper(),
                "dia": dia,
                "total": row[0] or 0,
                "in": row[1] or 0,
                "tc": row[2] or 0,
                "rx": row[3] or 0,
                "dx": row[4] or 0,
                "ra": row[5] or 0
            }
        
        # Sin hub específico - devolver por todos los hubs
        query_hub = """
            SELECT 
                hub,
                COUNT(*) as total,
                SUM(CASE WHEN tipo IN ('Nuevo Servicio', 'Reemplazo Equipo', 
                        'Modif. Plan', 'Cambio Direccion', 'Instalacion') THEN 1 ELSE 0 END) as in_count,
                SUM(CASE WHEN tipo IN ('Falla Telefonia', 'Falla Internet', 
                        'Falla Video', 'Verif. Domicilio', 'Falla General') THEN 1 ELSE 0 END) as tc_count,
                SUM(CASE WHEN tipo = 'Conexion' THEN 1 ELSE 0 END) as rx_count,
                SUM(CASE WHEN tipo = 'Suspension Servicio' THEN 1 ELSE 0 END) as dx_count,
                SUM(CASE WHEN tipo = 'Retiro Equipo' THEN 1 ELSE 0 END) as ra_count
            FROM abiertas 
            WHERE hub IS NOT NULL AND hub != '' AND dia::date = %s
            GROUP BY hub
            ORDER BY hub
        """
        cursor.execute(query_hub, (dia,))
        rows = cursor.fetchall()
        
        por_hub = {}
        total_ordenes = 0
        total_in = 0
        total_tc = 0
        total_rx = 0
        total_dx = 0
        total_ra = 0
        
        for row in rows:
            hub_code = row[0]
            hub_total = row[1]
            hub_in = row[2] or 0
            hub_tc = row[3] or 0
            hub_rx = row[4] or 0
            hub_dx = row[5] or 0
            hub_ra = row[6] or 0
            
            por_hub[hub_code] = {
                "total": hub_total,
                "in": hub_in,
                "tc": hub_tc,
                "rx": hub_rx,
                "dx": hub_dx,
                "ra": hub_ra
            }
            total_ordenes += hub_total
            total_in += hub_in
            total_tc += hub_tc
            total_rx += hub_rx
            total_dx += hub_dx
            total_ra += hub_ra
        
        return {
            "dia": dia,
            "total_ordenes": total_ordenes,
            "in": total_in,
            "tc": total_tc,
            "rx": total_rx,
            "dx": total_dx,
            "ra": total_ra,
            "por_hub": por_hub
        }
        
    except Exception as e:
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()


@router.get("/metrics/tipos")
def get_metrics_by_tipo(
    hub: Optional[str] = Query(None, description="Código del hub (opcional)"),
    dia: Optional[str] = Query(None, description="Fecha en formato YYYY-MM-DD (default: fecha más reciente)")
):
    """
    Retorna el desglose de órdenes por tipo con su clasificación.
    Descarta tipos que no coinciden con la clasificación.
    """
    if not dia:
        dia = get_default_dia()
    
    conn = get_db_connection()
    if not conn:
        return {"error": "No se pudo conectar a la base de datos"}
    
    cursor = conn.cursor()
    
    try:
        if hub:
            query = """
                SELECT tipo, COUNT(*) as total
                FROM abertas 
                WHERE hub = %s AND hub IS NOT NULL AND hub != '' AND dia::date = %s
                GROUP BY tipo
                ORDER BY total DESC
            """
            cursor.execute(query, (hub.upper(), dia))
        else:
            query = """
                SELECT tipo, COUNT(*) as total
                FROM abiertas 
                WHERE hub IS NOT NULL AND hub != '' AND dia::date = %s
                GROUP BY tipo
                ORDER BY total DESC
            """
            cursor.execute(query, (dia,))
        
        rows = cursor.fetchall()
        tipos = []
        
        for row in rows:
            tipo = row[0]
            total = row[1]
            clasificacion = clasificar_tipo(tipo)
            # Solo incluimos tipos clasificados
            if clasificacion:
                tipos.append({
                    "tipo": tipo,
                    "clasificacion": clasificacion,
                    "total": total
                })
        
        # Calcular totales por clasificación
        por_clasificacion = {}
        for item in tipos:
            cls = item["clasificacion"]
            if cls not in por_clasificacion:
                por_clasificacion[cls] = 0
            por_clasificacion[cls] += item["total"]
        
        return {
            "dia": dia,
            "tipos": tipos,
            "por_clasificacion": por_clasificacion
        }
        
    except Exception as e:
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()


@router.get("/metrics/clasificacion")
def get_metrics_by_clasificacion(
    hub: Optional[str] = Query(None, description="Código del hub (opcional)"),
    dia: Optional[str] = Query(None, description="Fecha en formato YYYY-MM-DD (default: fecha más reciente)")
):
    """
    Retorna métricas agrupadas por clasificación: IN, Rx, Dx, RA, TC
    """
    if not dia:
        dia = get_default_dia()
    
    conn = get_db_connection()
    if not conn:
        return {"error": "No se pudo conectar a la base de datos"}
    
    cursor = conn.cursor()
    
    try:
        if hub:
            query = """
                SELECT 
                    SUM(CASE WHEN tipo = ANY(%s) THEN 1 ELSE 0 END) as in_count,
                    SUM(CASE WHEN tipo = 'Conexion' THEN 1 ELSE 0 END) as rx_count,
                    SUM(CASE WHEN tipo = 'Suspension Servicio' THEN 1 ELSE 0 END) as dx_count,
                    SUM(CASE WHEN tipo = 'Retiro Equipo' THEN 1 ELSE 0 END) as ra_count,
                    SUM(CASE WHEN tipo = ANY(%s) THEN 1 ELSE 0 END) as tc_count,
                    COUNT(*) as total
                FROM abiertas 
                WHERE hub = %s AND hub IS NOT NULL AND hub != '' AND dia::date = %s
                GROUP BY hub
            """
            cursor.execute(query, (TIPOS_IN, TIPOS_TC, hub.upper(), dia))
            row = cursor.fetchone()
            
            if not row:
                return {"error": f"Hub '{hub.upper()}' no encontrado para la fecha {dia}"}
            
            return {
                "hub": hub.upper(),
                "dia": dia,
                "in": row[0] or 0,
                "rx": row[1] or 0,
                "dx": row[2] or 0,
                "ra": row[3] or 0,
                "tc": row[4] or 0,
                "total": row[5]
            }
        else:
            query = """
                SELECT 
                    hub,
                    SUM(CASE WHEN tipo = ANY(%s) THEN 1 ELSE 0 END) as in_count,
                    SUM(CASE WHEN tipo = 'Conexion' THEN 1 ELSE 0 END) as rx_count,
                    SUM(CASE WHEN tipo = 'Suspension Servicio' THEN 1 ELSE 0 END) as dx_count,
                    SUM(CASE WHEN tipo = 'Retiro Equipo' THEN 1 ELSE 0 END) as ra_count,
                    SUM(CASE WHEN tipo = ANY(%s) THEN 1 ELSE 0 END) as tc_count,
                    COUNT(*) as total
                FROM abiertas 
                WHERE hub IS NOT NULL AND hub != '' AND dia::date = %s
                GROUP BY hub
                ORDER BY hub
            """
            cursor.execute(query, (TIPOS_IN, TIPOS_TC, dia))
            rows = cursor.fetchall()
            
            por_hub = {}
            totales = {"in": 0, "rx": 0, "dx": 0, "ra": 0, "tc": 0, "total": 0}
            
            for row in rows:
                hub_code = row[0]
                in_c = row[1] or 0
                rx_c = row[2] or 0
                dx_c = row[3] or 0
                ra_c = row[4] or 0
                tc_c = row[5] or 0
                total = row[6]
                
                por_hub[hub_code] = {
                    "in": in_c, "rx": rx_c, "dx": dx_c, "ra": ra_c, "tc": tc_c, 
                    "total": total
                }
                totales["in"] += in_c
                totales["rx"] += rx_c
                totales["dx"] += dx_c
                totales["ra"] += ra_c
                totales["tc"] += tc_c
                totales["total"] += total
            
            return {"dia": dia, "totales": totales, "por_hub": por_hub}
        
    except Exception as e:
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()


@router.get("/metrics/rx-por-fecha")
def get_rx_por_fecha(
    hub: Optional[str] = Query(None, description="Código del hub (opcional)"),
    dia: Optional[str] = Query(None, description="Fecha en formato YYYY-MM-DD (default: fecha más reciente)")
):
    """Retorna el historial de órdenes tipo Reconexión por fecha."""
    if not dia:
        dia = get_default_dia()
    
    conn = get_db_connection()
    if not conn:
        return {"error": "No se pudo conectar a la base de datos"}
    
    cursor = conn.cursor()
    
    try:
        if hub:
            query = """
                SELECT fechaorden as fecha, COUNT(*) as total
                FROM abiertas 
                WHERE hub = %s AND hub IS NOT NULL AND hub != '' 
                  AND dia::date = %s AND tipo = 'Conexion'
                  AND fechaorden IS NOT NULL
                GROUP BY fechaorden ORDER BY fechaorden
            """
            cursor.execute(query, (hub.upper(), dia))
        else:
            query = """
                SELECT fechaorden as fecha, COUNT(*) as total
                FROM abiertas 
                WHERE hub IS NOT NULL AND hub != '' 
                  AND dia::date = %s AND tipo = 'Conexion'
                  AND fechaorden IS NOT NULL
                GROUP BY fechaorden ORDER BY fechaorden
            """
            cursor.execute(query, (dia,))
        
        rows = cursor.fetchall()
        resultado = []
        for row in rows:
            if row[0]:
                resultado.append({
                    "fecha": row[0].strftime("%Y-%m-%d") if hasattr(row[0], 'strftime') else str(row[0]),
                    "total": row[1]
                })
        
        return {"dia": dia, "hub": hub.upper() if hub else None, "data": resultado}
        
    except Exception as e:
        return {"error": str(e)}
    finally:
        cursor.close()
        conn.close()
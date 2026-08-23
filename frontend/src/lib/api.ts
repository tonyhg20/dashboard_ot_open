// API utility functions for OS Open Dashboard
import { 
  CreateHubPayload,
  HubsResponse, 
  Hub,
  MetricsSummary, 
  MetricsSummaryByHub,
  DiasResponse,
  HubWithMetrics,
  RxPorFechaData,
  TcConRuidoData,
  NoisePorCpData
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

// Create a new hub
export async function createHub(payload: CreateHubPayload): Promise<Hub> {
  const res = await fetch(`${API_BASE}/hubs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw { status: res.status, body: errorBody };
  }

  return res.json();
}

// Fetch all hubs with coordinates
export async function fetchHubs(): Promise<HubWithMetrics[]> {
  try {
    const res = await fetch(`${API_BASE}/hubs`);
    if (!res.ok) throw new Error("Failed to fetch hubs");
    const data: HubsResponse = await res.json();
    return data.hubs.map(h => ({ ...h, metrics: null }));
  } catch (error) {
    console.error("Error fetching hubs:", error);
    return [];
  }
}

// Fetch metrics summary for a specific date (and optional hub)
export async function fetchMetricsSummary(dia?: string, hub?: string): Promise<MetricsSummary | MetricsSummaryByHub | null> {
  try {
    const params = new URLSearchParams();
    if (dia) params.set("dia", dia);
    if (hub) params.set("hub", hub);
    
    const res = await fetch(`${API_BASE}/metrics/summary?${params}`);
    if (!res.ok) throw new Error("Failed to fetch metrics");
    return await res.json();
  } catch (error) {
    console.error("Error fetching metrics:", error);
    return null;
  }
}

// Fetch available dates
export async function fetchDias(): Promise<string[]> {
  try {
    const res = await fetch(`${API_BASE}/metrics/dias`);
    if (!res.ok) throw new Error("Failed to fetch dias");
    const data: DiasResponse = await res.json();
    console.log("API /metrics/dias response:", data.dias);
    return data.dias;
  } catch (error) {
    console.error("Error fetching dias:", error);
    return [];
  }
}

// Fetch Rx por fecha (historial de reconexiones)
export async function fetchRxPorFecha(dia?: string, hub?: string): Promise<RxPorFechaData | null> {
  try {
    const params = new URLSearchParams();
    if (dia) params.set("dia", dia);
    if (hub) params.set("hub", hub);
    
    const res = await fetch(`${API_BASE}/metrics/rx-por-fecha?${params}`);
    if (!res.ok) throw new Error("Failed to fetch rx-por-fecha");
    return await res.json();
  } catch (error) {
    console.error("Error fetching rx-por-fecha:", error);
    return null;
  }
}

// Fetch TC con ruido cross-reference
export async function fetchTcConRuido(dia?: string, hub?: string): Promise<TcConRuidoData | null> {
  try {
    const params = new URLSearchParams();
    if (dia) params.set("dia", dia);
    if (hub) params.set("hub", hub);
    const res = await fetch(`${API_BASE}/metrics/tc-con-ruido?${params}`);
    if (!res.ok) throw new Error("Failed to fetch tc-con-ruido");
    return await res.json();
  } catch (error) {
    console.error("Error fetching tc-con-ruido:", error);
    return null;
  }
}

// Fetch noise data aggregated by postal code (GeoJSON)
export async function fetchNoisePorCp(): Promise<NoisePorCpData | null> {
  try {
    const res = await fetch(`${API_BASE}/noise/por-cp`);
    if (!res.ok) throw new Error("Failed to fetch noise por cp");
    return await res.json();
  } catch (error) {
    console.error("Error fetching noise por cp:", error);
    return null;
  }
}

// Abrir reporte ejecutivo v2 en nueva pestaña (GET)
export function abrirReporteEjecutivoV2(): void {
  window.open(`${API_BASE}/reportes/executive/generate-v2`, "_blank");
}

// Combine hubs with their metrics for a specific date
export async function fetchHubsWithMetrics(dia?: string): Promise<HubWithMetrics[]> {
  const [hubs, metrics] = await Promise.all([
    fetchHubs(),
    fetchMetricsSummary(dia)
  ]);
  
  if (!metrics || !("por_hub" in metrics)) {
    return hubs;
  }
  
  return hubs.map(hub => ({
    ...hub,
    metrics: metrics.por_hub[hub.code] || null
  }));
}
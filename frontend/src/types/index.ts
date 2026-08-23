// Hub geolocation from hubs.json
export interface Hub {
  code: string;
  name: string;
  lat: number;
  lng: number;
}

export interface CreateHubPayload {
  code: string;
  name: string;
  lat: number;
  lng: number;
}

export interface HubsResponse {
  hubs: Hub[];
}

// Metrics by classification
export interface HubMetrics {
  total: number;
  in: number;
  tc: number;
  rx: number;
  dx: number;
  ra: number;
}

export interface MetricsSummary {
  dia: string;
  total_ordenes: number;
  in: number;
  tc: number;
  rx: number;
  dx: number;
  ra: number;
  por_hub: Record<string, HubMetrics>;
}

export interface MetricsSummaryByHub {
  hub: string;
  dia: string;
  total: number;
  in: number;
  tc: number;
  rx: number;
  dx: number;
  ra: number;
}

// Classification breakdown
export interface TipoOrden {
  tipo: string;
  clasificacion: string;
  total: number;
}

export interface MetricsTipos {
  dia: string;
  tipos: TipoOrden[];
  por_clasificacion: Record<string, number>;
}

// Dates available
export interface DiasResponse {
  dias: string[];
}

// Hub with metrics combined (for map markers)
export interface HubWithMetrics extends Hub {
  metrics: HubMetrics | null;
}

// Rx por fecha data
export interface RxFechaItem {
  fecha: string;
  total: number;
}

export interface RxPorFechaData {
  dia: string;
  hub: string | null;
  data: RxFechaItem[];
}

// TC con ruido cross-reference
export interface TcConRuidoPorHub {
  total_tc: number;
  tc_con_ruido: number;
  porcentaje: number;
}

export interface TcConRuidoData {
  dia: string;
  total_tc: number;
  tc_con_ruido: number;
  porcentaje: number;
  por_hub: Record<string, TcConRuidoPorHub>;
}

// Noise by postal code (GeoJSON)
export interface NoisePorCpProperties {
  codigo_postal: string;
  hub: string;
  total_modems: number;
  noisy_modems: number;
  pct_noisy: number;
  avg_cer: number;
  avg_snr: number;
}

export interface NoisePorCpFeature {
  type: "Feature";
  geometry: {
    type: "Point";
    coordinates: [number, number];
  };
  properties: NoisePorCpProperties;
}

export interface NoisePorCpData {
  type: "FeatureCollection";
  features: NoisePorCpFeature[];
}
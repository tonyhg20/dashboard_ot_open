"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { HubWithMetrics, MetricsSummary, TcConRuidoData, NoisePorCpData } from "@/types";
import {
  fetchHubsWithMetrics,
  fetchMetricsSummary,
  fetchDias,
  abrirReporteEjecutivoV2,
  fetchTcConRuido,
  fetchNoisePorCp,
} from "@/lib/api";

// Components
import { MapView } from "@/components/MapView";
import { NoiseMap } from "@/components/NoiseMap";
import { DateSelector } from "@/components/DateSelector";
import { HubPanel } from "@/components/HubPanel";
import { HubFilter } from "@/components/HubFilter";

const LS_KEY = "os_open_selected_hubs";

export default function Dashboard() {
  const [dia, setDia] = useState<string | null>(null);
  const [dias, setDias] = useState<string[]>([]);
  const [hubs, setHubs] = useState<HubWithMetrics[]>([]);
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [tcConRuido, setTcConRuido] = useState<TcConRuidoData | null>(null);
  const [selectedHub, setSelectedHub] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add hub creation state
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Report generation state
  const [execLoading, setExecLoading] = useState(false);

  // View mode: orders map vs noise map
  const [viewMode, setViewMode] = useState<"orders" | "noise">("orders");
  const [noiseMapData, setNoiseMapData] = useState<NoisePorCpData | null>(null);

  // Hub filter state (persisted in localStorage)
  const [selectedHubCodes, setSelectedHubCodes] = useState<string[]>(() => {
    if (typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem(LS_KEY);
        return stored ? JSON.parse(stored) : [];
      } catch {
        return [];
      }
    }
    return [];
  });
  const filterInitialized = useRef(false);

  // First time: if no stored selection, select all hubs
  useEffect(() => {
    if (filterInitialized.current || hubs.length === 0) return;
    const stored = localStorage.getItem(LS_KEY);
    if (!stored || JSON.parse(stored).length === 0) {
      setSelectedHubCodes(hubs.map((h) => h.code));
    }
    filterInitialized.current = true;
  }, [hubs]);

  const handleFilterChange = useCallback((codes: string[]) => {
    setSelectedHubCodes(codes);
    localStorage.setItem(LS_KEY, JSON.stringify(codes));
  }, []);

  const filteredHubs = hubs.filter((h) => selectedHubCodes.includes(h.code));

  // Load available dates on mount
  useEffect(() => {
    async function loadDias() {
      try {
        const diasData = await fetchDias();
        const validDias = diasData.filter(d => d && d.match(/^\d{4}-\d{2}-\d{2}$/));
        setDias(validDias);
        
        if (validDias.length > 0) {
          setDia(validDias[0]);
        } else {
          // Si no hay días, dejamos de cargar para que no se quede colgado
          setLoading(false);
          setError("NO_HAY_DATOS_DISPONIBLES");
        }
      } catch (err) {
        setLoading(false);
        setError("ERROR_AL_CARGAR_FECHAS");
      }
    }
    loadDias();
  }, []);

  // Load data when dia changes
  useEffect(() => {
    if (!dia) return;
    
    async function loadData() {
      setLoading(true);
      setError(null);
      
      try {
        const [hubsData, metricsData, tcData] = await Promise.all([
          fetchHubsWithMetrics(dia || undefined),
          fetchMetricsSummary(dia || undefined),
          fetchTcConRuido(dia || undefined)
        ]);
        
        setHubs(hubsData);
        setMetrics(metricsData as MetricsSummary);
        setTcConRuido(tcData);
      } catch (err) {
        setError("ERROR_DE_CONEXION");
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    
    loadData();
  }, [dia]);

  const handleHubClick = (hubCode: string) => {
    setSelectedHub(hubCode === selectedHub ? null : hubCode);
  };

  const handleToggleView = useCallback(async () => {
    if (viewMode === "orders") {
      setViewMode("noise");
      setSelectedHub(null);
      if (!noiseMapData) {
        const data = await fetchNoisePorCp();
        setNoiseMapData(data);
      }
    } else {
      setViewMode("orders");
    }
  }, [viewMode, noiseMapData]);

  const handleDescargarEjecutivo = useCallback(() => {
    abrirReporteEjecutivoV2();
    setSuccessMsg("Reporte ejecutivo abierto — capturá la pantalla con tu herramienta favorita");
    setTimeout(() => setSuccessMsg(null), 4000);
  }, []);

  const selectedHubMetrics = selectedHub && metrics?.por_hub[selectedHub] 
    ? metrics.por_hub[selectedHub] 
    : null;

  const hubTcConRuido = selectedHub && tcConRuido?.por_hub[selectedHub]
    ? tcConRuido.por_hub[selectedHub]
    : null;

  // Calculate total classified
  const totalClassified = metrics 
    ? metrics.in + metrics.tc + metrics.rx + metrics.dx + metrics.ra 
    : 0;

  return (
    <div className="min-h-screen bg-[#020617] flex flex-col">
      {/* Header - MONARCH STYLE */}
      <header className="bg-slate-950/90 backdrop-blur-md flex justify-between items-center w-full px-6 h-16 border-b border-[#00c0ff]/30 fixed top-0 z-50 shadow-[0_5px_30px_rgba(0,192,255,0.15)]">
        <div className="flex items-center gap-8">
          <span className="text-xl font-black text-[#00c0ff] tracking-[0.2em] italic uppercase drop-shadow-[0_0_12px_#00c0ff]">
            CENTRO DE MANDO<span className="text-[#ff0040]">-OS ABIERTAS</span>
          </span>
          <div className="hidden md:flex items-center gap-4 text-xs font-mono">
            <span className="text-[#00ff80]">◆ SISTEMA_ACTIVO</span>
            <span className="text-[#94a3b8]">|</span>
            <span className="text-[#94a3b8]">SECTOR: <span className="text-[#00c0ff]">NORESTE</span></span>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <HubFilter
            hubs={hubs}
            selected={selectedHubCodes}
            onChange={handleFilterChange}
          />

          <button
            onClick={handleToggleView}
            className="flex items-center gap-2 px-4 py-1.5 text-xs font-bold tracking-[0.2em] uppercase transition-all"
            style={{
              color: viewMode === "noise" ? "#00c0ff" : "#b000ff",
              border: `1px solid ${viewMode === "noise" ? "rgba(0,192,255,0.4)" : "rgba(176,0,255,0.4)"}`,
              background: viewMode === "noise" ? "rgba(0,192,255,0.08)" : "rgba(176,0,255,0.08)",
              fontFamily: "'Rajdhani', 'Orbitron', sans-serif",
            }}
            onMouseEnter={(e) => {
              const isNoise = viewMode === "noise";
              e.currentTarget.style.background = isNoise ? "rgba(0,192,255,0.15)" : "rgba(176,0,255,0.15)";
              e.currentTarget.style.borderColor = isNoise ? "rgba(0,192,255,0.7)" : "rgba(176,0,255,0.7)";
              e.currentTarget.style.boxShadow = isNoise ? "0 0 20px rgba(0,192,255,0.25)" : "0 0 20px rgba(176,0,255,0.25)";
            }}
            onMouseLeave={(e) => {
              const isNoise = viewMode === "noise";
              e.currentTarget.style.background = isNoise ? "rgba(0,192,255,0.08)" : "rgba(176,0,255,0.08)";
              e.currentTarget.style.borderColor = isNoise ? "rgba(0,192,255,0.4)" : "rgba(176,0,255,0.4)";
              e.currentTarget.style.boxShadow = "none";
            }}
          >
            <span className="text-base leading-none">◆</span>
            <span>{viewMode === "noise" ? "MAPA ÓRDENES" : "MAPA RUIDO"}</span>
          </button>

          <button
            onClick={handleDescargarEjecutivo}
            disabled={execLoading}
            className="flex items-center gap-2 px-4 py-1.5 text-xs font-bold tracking-[0.2em] uppercase transition-all"
            style={{
              color: execLoading ? "#475569" : "#ff9f1c",
              border: `1px solid ${execLoading ? "rgba(71,85,105,0.3)" : "rgba(255,159,28,0.4)"}`,
              background: execLoading ? "rgba(71,85,105,0.08)" : "rgba(255,159,28,0.08)",
              fontFamily: "'Rajdhani', 'Orbitron', sans-serif",
            }}
            onMouseEnter={(e) => {
              if (execLoading) return;
              e.currentTarget.style.background = "rgba(255,159,28,0.15)";
              e.currentTarget.style.borderColor = "rgba(255,159,28,0.7)";
              e.currentTarget.style.boxShadow = "0 0 20px rgba(255,159,28,0.25)";
            }}
            onMouseLeave={(e) => {
              if (execLoading) return;
              e.currentTarget.style.background = "rgba(255,159,28,0.08)";
              e.currentTarget.style.borderColor = "rgba(255,159,28,0.4)";
              e.currentTarget.style.boxShadow = "none";
            }}
          >
            <span className={`text-base leading-none ${execLoading ? "animate-pulse" : ""}`}>
              {execLoading ? "⟳" : "◈"}
            </span>
            <span>{execLoading ? "GENERANDO..." : "EJECUTIVO"}</span>
          </button>

          <DateSelector 
            dias={dias} 
            dia={dia} 
            onDiaChange={setDia}
          />
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex pt-20 px-6 pb-8">
        {/* Map Area */}
        <div className="flex-1 relative">
          {loading ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-[#00c0ff] text-lg font-mono animate-pulse">
                INICIALIZANDO_TELEMETRIA...
              </div>
            </div>
          ) : error ? (
            <div className="absolute inset-0 flex items-center justify-center glitch-edge-magenta p-8">
              <div className="text-[#ff0040] text-lg font-mono">{error}</div>
            </div>
          ) : viewMode === "noise" ? (
            <NoiseMap data={noiseMapData} />
          ) : (
            <MapView 
              hubs={filteredHubs}
              selectedHub={selectedHub}
              onHubClick={handleHubClick}
            />
          )}
        </div>

        {/* Sidebar Panel */}
        {selectedHub && selectedHubMetrics && (
          <HubPanel 
            hub={selectedHub}
            metrics={selectedHubMetrics}
            dia={dia}
            onClose={() => setSelectedHub(null)}
            tcConRuido={hubTcConRuido}
          />
        )}
      </main>

      {/* Success Notification Toast */}
      {successMsg && (
        <div className="fixed top-20 left-1/2 -translate-x-1/2 z-[60] animate-in fade-in slide-in-from-top-2 duration-300">
          <div
            className="px-6 py-3 text-xs font-mono tracking-wider uppercase flex items-center gap-3"
            style={{
              color: "#00ff80",
              border: "1px solid rgba(0, 255, 128, 0.4)",
              background: "rgba(2, 6, 23, 0.95)",
              boxShadow: "0 0 30px rgba(0, 255, 128, 0.2), 0 0 60px rgba(0, 255, 128, 0.08)",
              clipPath: "polygon(0 0, 100% 0, 100% calc(100% - 6px), calc(100% - 6px) 100%, 0 100%)",
            }}
          >
            <span className="text-base">◆</span>
            <span>{successMsg}</span>
          </div>
        </div>
      )}

      {/* Status Bar */}
      <div className="fixed bottom-0 left-0 w-full bg-slate-950/80 border-t border-[#00c0ff]/20 px-6 py-2 flex items-center justify-between text-[10px] font-mono z-40">
        <div className="flex items-center gap-4">
          <span className="text-[#00c0ff]">◆ CONEXION_ESTABLE</span>
          <span className="text-[#94a3b8]">API: <span className="text-[#00ff80]">ONLINE</span></span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-[#94a3b8]">HUBS: <span className="text-[#00c0ff]">{filteredHubs.length}</span><span className="text-[#475569]">/{hubs.length}</span></span>
          <span className="text-[#94a3b8]">FECHA: <span className="text-[#00c0ff]">{dia}</span></span>
        </div>
      </div>
    </div>
  );
}
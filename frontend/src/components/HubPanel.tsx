"use client";

import { useState, useEffect } from "react";
import { HubMetrics, RxPorFechaData, TcConRuidoPorHub } from "@/types";
import { fetchRxPorFecha } from "@/lib/api";

interface HubPanelProps {
  hub: string;
  metrics: HubMetrics;
  dia: string | null;
  onClose: () => void;
  tcConRuido?: TcConRuidoPorHub | null;
}

const METRIC_LABELS: Record<keyof HubMetrics, { label: string; color: string; glow: string; border: string }> = {
  total: { label: "O.S.", color: "#00c0ff", glow: "rgba(0,192,255,0.5)", border: "#00c0ff" },
  in: { label: "IN", color: "#00c0ff", glow: "rgba(0,192,255,0.5)", border: "#00c0ff" },
  tc: { label: "TC", color: "#ff0040", glow: "rgba(255,0,64,0.5)", border: "#ff0040" },
  rx: { label: "Rx", color: "#00ff80", glow: "rgba(0,255,128,0.5)", border: "#00ff80" },
  dx: { label: "Dx", color: "#ff00aa", glow: "rgba(255,0,170,0.5)", border: "#ff00aa" },
  ra: { label: "RA", color: "#8b5cf6", glow: "rgba(139,92,246,0.5)", border: "#8b5cf6" },
};

// Mini chart component con tooltip simplificado
function RxMiniChart({ data }: { data: RxPorFechaData | null }) {
  const [hoveredPoint, setHoveredPoint] = useState<{fecha: string, total: number} | null>(null);

  useEffect(() => {
    // Reset hover state when data changes
    setHoveredPoint(null);
  }, [data]);

  if (!data?.data?.length) return null;

  const chartData = data.data;
  const max = Math.max(...chartData.map(d => d.total));

  return (
    <div 
      className="relative w-full h-10"
      onMouseLeave={() => setHoveredPoint(null)}
    >
      {/* Chart bars */}
      <div className="flex items-end justify-between h-8 gap-0.5">
        {chartData.map((point, i) => {
          const height = (point.total / max) * 100;
          const isHovered = hoveredPoint?.fecha === point.fecha;
          
          return (
            <div 
              key={i}
              className="flex-1 min-h-[4px] relative cursor-pointer group"
              onMouseEnter={() => setHoveredPoint({ fecha: point.fecha, total: point.total })}
            >
              <div 
                className={`absolute bottom-0 w-full rounded-t-sm transition-all ${isHovered ? 'bg-lime-400' : 'bg-lime-500/70'}`}
                style={{ 
                  height: `${Math.max(height, 20)}%`,
                  boxShadow: isHovered ? '0 0 8px #00ff80' : 'none'
                }}
              />
            </div>
          );
        })}
      </div>
      
      {/* Labels */}
      <div className="flex justify-between mt-0.5 px-0.5">
        {chartData.map((point, i) => (
          <span 
            key={i} 
            className={`text-[6px] font-mono ${hoveredPoint?.fecha === point.fecha ? 'text-lime-400' : 'text-slate-500'}`}
          >
            {point.fecha.slice(5)}
          </span>
        ))}
      </div>

      {/* Tooltip */}
      {hoveredPoint && (
        <div 
          className="absolute -top-7 left-1/2 transform -translate-x-1/2 bg-slate-900 border border-lime-500 px-2 py-0.5 rounded text-[8px] font-mono z-50"
          style={{ boxShadow: '0 0 10px rgba(0,255,128,0.5)' }}
        >
          <span className="text-lime-400">{hoveredPoint.fecha}</span>
          <span className="text-slate-300 ml-1">→ {hoveredPoint.total}</span>
        </div>
      )}
    </div>
  );
}

export function HubPanel({ hub, metrics, dia, onClose, tcConRuido }: HubPanelProps) {
  const [rxData, setRxData] = useState<RxPorFechaData | null>(null);
  
  useEffect(() => {
    if (hub && dia) {
      fetchRxPorFecha(dia, hub).then(setRxData);
    }
  }, [hub, dia]);
  
  const classifiedTotal = metrics.in + metrics.tc + metrics.rx + metrics.dx + metrics.ra;
  const displayMetrics = { ...metrics, total: classifiedTotal };
  
  return (
    <aside 
      className="w-80 flex flex-col border-l border-cyan-500/30 shadow-[0_0_40px_rgba(0,192,255,0.15)]"
      style={{
        background: `
          linear-gradient(180deg, rgba(2,6,23,0.85) 0%, rgba(2,6,23,0.95) 100%),
          url('/radar1.gif') center/cover no-repeat
        `,
      }}
    >
      {/* Header con efecto glitch */}
      <div className="px-6 py-5 border-b border-cyan-500/20 relative overflow-hidden bg-slate-900/50">
        {/* Background glow */}
        <div 
          className="absolute inset-0 opacity-20" 
          style={{ background: `linear-gradient(135deg, ${METRIC_LABELS.total.glow}, transparent)` }}
        />
        
        <div className="relative flex items-center justify-between">
          <div className="flex items-center gap-4">
            {/* Icono decorativo */}
            <div className="relative">
              <div className="w-10 h-10 rounded-lg bg-cyan-500/20 border border-cyan-500/50 flex items-center justify-center">
                <span className="text-cyan-400 text-lg">◆</span>
              </div>
              <div className="absolute -inset-1 border border-cyan-500/30 rounded-lg animate-pulse" />
            </div>
            
            <div>
              <h2 className="text-2xl font-black italic tracking-[0.15em] text-cyan-400 drop-shadow-[0_0_10px_rgba(0,192,255,0.8)]">
                {hub}
              </h2>
              <p className="text-[10px] text-slate-400 mt-1 font-mono tracking-wider uppercase">
                Centro de Operaciones
              </p>
            </div>
          </div>
          
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center text-slate-400 hover:text-cyan-400 hover:bg-cyan-500/20 rounded transition-all border border-transparent hover:border-cyan-500/30"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Grid de métricas */}
      <div className="flex-1 p-4 space-y-3">
        {/* Total highlight */}
        <div 
          className="p-3 rounded-lg border relative overflow-hidden"
          style={{ 
            background: `linear-gradient(135deg, rgba(0,192,255,0.1), rgba(0,192,255,0.02))`,
            borderColor: 'rgba(0,192,255,0.4)'
          }}
        >
          <div className="absolute top-0 right-0 w-16 h-16 bg-cyan-500/10 rounded-full blur-2xl" />
          
          <div className="relative flex items-center justify-between">
            <div>
              <div className="text-[9px] uppercase tracking-[0.2em] text-cyan-400 font-mono mb-0.5">
                Total O.S.
              </div>
              <div className="text-3xl font-black text-cyan-400 drop-shadow-[0_0_15px_rgba(0,192,255,0.8)] tabular-nums">
                {classifiedTotal}
              </div>
            </div>
            <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_10px_#00c0ff]" />
          </div>
        </div>
        
        {/* Classification cards */}
        <div className="grid grid-cols-3 gap-2">
          {Object.entries(displayMetrics).filter(([key]) => key !== 'total').map(([key, value]) => {
            const config = METRIC_LABELS[key as keyof HubMetrics];
            if (!config) return null;
            
            return (
              <div 
                key={key}
                className="p-2 rounded-lg border relative overflow-hidden transition-all hover:scale-[1.02]"
                style={{ 
                  background: `linear-gradient(135deg, ${config.glow}15, transparent)`,
                  borderColor: `${config.border}40`
                }}
              >
                {/* Corner accent */}
                <div 
                  className="absolute top-0 left-0 w-1 h-full"
                  style={{ background: config.color }}
                />
                
                <div className="relative pl-2">
                  <div 
                    className="text-[10px] uppercase tracking-wider font-mono mb-0.5"
                    style={{ color: config.color }}
                  >
                    {config.label}
                  </div>
                  <div 
                    className="text-3xl font-bold tabular-nums"
                    style={{ 
                      color: config.color,
                      textShadow: `0 0 20px ${config.glow}`
                    }}
                  >
                    {value.toLocaleString()}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* TC + Ruido card */}
        {tcConRuido && (
          <div 
            className="p-3 rounded-lg border relative overflow-hidden transition-all hover:scale-[1.02]"
            style={{ 
              background: 'linear-gradient(135deg, rgba(255,159,28,0.1), transparent)',
              borderColor: 'rgba(255,159,28,0.4)'
            }}
          >
            {/* Corner accent */}
            <div 
              className="absolute top-0 left-0 w-1 h-full"
              style={{ background: '#ff9f1c' }}
            />
            
            <div className="relative pl-2">
              <div 
                className="text-[10px] uppercase tracking-wider font-mono mb-0.5"
                style={{ color: '#ff9f1c' }}
              >
                TC+Ruido
              </div>
              <div 
                className="text-2xl font-bold tabular-nums"
                style={{ 
                  color: '#ff9f1c',
                  textShadow: '0 0 20px rgba(255,159,28,0.5)'
                }}
              >
                {tcConRuido.tc_con_ruido.toLocaleString()}
                <span className="text-sm font-mono ml-1 opacity-80">
                  ({tcConRuido.porcentaje.toFixed(1)}%)
                </span>
              </div>
              <div className="text-[9px] text-slate-400 font-mono mt-0.5">
                de {tcConRuido.total_tc.toLocaleString()} TC totales
              </div>
            </div>
          </div>
        )}

        {/* Rx Mini Chart */}
        {rxData && rxData.data.length > 0 && (
          <div className="mt-3 p-2 rounded-lg border" style={{ borderColor: 'rgba(0,255,128,0.3)' }}>
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-lime-400 animate-pulse" />
                <span className="text-[9px] uppercase tracking-wider text-lime-400 font-mono">
                  Histórico Rx
                </span>
              </div>
              <span className="text-[9px] text-lime-400 font-bold">
                Total: {rxData.data.reduce((sum, d) => sum + d.total, 0)}
              </span>
            </div>
            <RxMiniChart data={rxData} />
          </div>
        )}
      </div>

      {/* Footer con más efectos */}
      <div className="px-4 py-3 border-t border-cyan-500/20 bg-slate-900/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="relative">
              <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
              <div className="absolute inset-0 w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
            </div>
            <span className="text-[10px] text-cyan-400/80 font-mono tracking-wider uppercase">
              Sistema Activo
            </span>
          </div>
          
          <div className="text-[9px] text-slate-500 font-mono">
            v1.0.0
          </div>
        </div>
      </div>
    </aside>
  );
}
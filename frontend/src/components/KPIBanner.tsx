"use client";

import { MetricsSummary } from "@/types";

interface KPIBannerProps {
  metrics: MetricsSummary | null;
  loading: boolean;
}

interface KPICardProps {
  label: string;
  value: number;
  color: string;
}

function KPICard({ label, value, color }: KPICardProps) {
  return (
    <div className="flex flex-col items-center px-6 py-3 border-r border-[#444852] last:border-r-0">
      <span className="text-xs uppercase tracking-wider text-[#a7abb7] mb-1 font-display">
        {label}
      </span>
      <span 
        className="text-2xl font-bold tabular-nums"
        style={{ color }}
      >
        {value.toLocaleString()}
      </span>
    </div>
  );
}

export function KPIBanner({ metrics, loading }: KPIBannerProps) {
  if (loading) {
    return (
      <div className="max-w-[1920px] mx-auto">
        <div className="flex justify-center items-center h-16">
          <div className="text-[#00f2ff] animate-pulse font-display">
            CARGANDO MÉTRICAS...
          </div>
        </div>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="max-w-[1920px] mx-auto">
        <div className="flex justify-center items-center h-16">
          <div className="text-[#a7abb7]">Sin datos disponibles</div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-[1920px] mx-auto">
      <div className="flex items-center justify-center h-16">
        <KPICard label="TOTAL" value={metrics.total_ordenes} color="#00f2ff" />
        <KPICard label="IN" value={metrics.in} color="#99f7ff" />
        <KPICard label="TC" value={metrics.tc} color="#ac89ff" />
        <KPICard label="Rx" value={metrics.rx} color="#00f1fe" />
        <KPICard label="Dx" value={metrics.dx} color="#ff59e3" />
        <KPICard label="RA" value={metrics.ra} color="#874cff" />
      </div>
      
      {/* Date indicator */}
      <div className="text-center pb-2">
        <span className="text-xs text-[#a7abb7] font-mono">
          Fecha: {metrics.dia}
        </span>
      </div>
    </div>
  );
}
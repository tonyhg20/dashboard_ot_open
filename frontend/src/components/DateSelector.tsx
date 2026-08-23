"use client";

interface DateSelectorProps {
  dias: string[];
  dia: string | null;
  onDiaChange: (dia: string) => void;
}

export function DateSelector({ dias, dia, onDiaChange }: DateSelectorProps) {
  const validDias = Array.isArray(dias) ? dias : [];
  const valueToUse = (dia && validDias.includes(dia)) ? dia : (validDias.length > 0 ? validDias[0] : "");
  
  if (validDias.length === 0) {
    return (
      <div className="flex items-center gap-2">
        <div className="px-4 py-2 bg-slate-900/80 border border-lime-500/30 text-lime-400 font-mono text-sm rounded animate-pulse">
          INICIALIZANDO...
        </div>
      </div>
    );
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr + 'T00:00:00');
    return date.toLocaleDateString("es-MX", {
      day: "2-digit",
      month: "short", 
      year: "numeric"
    }).toUpperCase();
  };

  return (
    <div className="flex items-center gap-3">
      {/* Label con efecto neon */}
      <span className="text-xs uppercase tracking-[0.2em] text-lime-400 font-mono drop-shadow-[0_0_8px_rgba(132,204,22,0.6)]">
        ◆ FECHA
      </span>
      
      {/* Select con estilos neon */}
      <div className="relative group">
        {/* Glow de fondo */}
        <div className="absolute -inset-0.5 bg-gradient-to-r from-lime-500/30 to-yellow-500/30 rounded opacity-0 group-hover:opacity-100 transition-opacity blur-sm" />
        
        <select
          value={valueToUse}
          onChange={(e) => onDiaChange(e.target.value)}
          className="
            relative
            bg-slate-950/90 
            border border-lime-500/50 
            text-lime-400 
            px-5 py-2.5 
            font-mono text-sm
            rounded
            cursor-pointer
            appearance-none
            outline-none
            transition-all
            hover:border-lime-400
            hover:shadow-[0_0_20px_rgba(132,204,22,0.4)]
            focus:border-lime-400
            focus:shadow-[0_0_25px_rgba(132,204,22,0.5)]
          "
          style={{
            boxShadow: '0 0 10px rgba(132,204,22,0.2)',
          }}
        >
          {dias.map((d) => (
            <option key={d} value={d} className="bg-slate-900 text-lime-400">
              {formatDate(d)}
            </option>
          ))}
        </select>
        
        {/* Flecha custom */}
        <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
          <svg 
            className="w-4 h-4 text-lime-400" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>
      
      {/* Indicador de estado */}
      <div className="flex items-center gap-1.5">
        <div className="w-1.5 h-1.5 rounded-full bg-lime-400 animate-pulse shadow-[0_0_8px_#84cc16]" />
        <span className="text-[9px] text-lime-500/70 font-mono uppercase tracking-wider">
          ACTIVO
        </span>
      </div>
    </div>
  );
}
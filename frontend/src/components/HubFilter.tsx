"use client";

import { useState, useRef, useEffect } from "react";
import { Hub } from "@/types";

interface HubFilterProps {
  hubs: Hub[];
  selected: string[];
  onChange: (selected: string[]) => void;
}

export function HubFilter({ hubs, selected, onChange }: HubFilterProps) {
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const allSelected = hubs.length > 0 && selected.length === hubs.length;
  const noneSelected = selected.length === 0;

  const handleToggle = (code: string) => {
    const next = selected.includes(code)
      ? selected.filter((c) => c !== code)
      : [...selected, code];
    onChange(next);
  };

  const handleSelectAll = () => {
    onChange(hubs.map((h) => h.code));
  };

  const handleDeselectAll = () => {
    onChange([]);
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Trigger button */}
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-1.5 text-xs font-mono tracking-wider uppercase transition-all border"
        style={{
          color: "#00c0ff",
          borderColor: "rgba(0, 192, 255, 0.3)",
          background: open ? "rgba(0, 192, 255, 0.1)" : "rgba(0, 192, 255, 0.05)",
          fontFamily: "'JetBrains Mono', 'Roboto Mono', monospace",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = "rgba(0, 192, 255, 0.12)";
          e.currentTarget.style.borderColor = "rgba(0, 192, 255, 0.5)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = open
            ? "rgba(0, 192, 255, 0.1)"
            : "rgba(0, 192, 255, 0.05)";
          e.currentTarget.style.borderColor = "rgba(0, 192, 255, 0.3)";
        }}
      >
        <span>◈</span>
        <span>
          HUBS:{" "}
          <span
            style={{
              color: noneSelected ? "#ff0040" : "#00ff80",
            }}
          >
            {selected.length}
          </span>
          /{hubs.length}
        </span>
      </button>

      {/* Dropdown */}
      {open && (
        <div
          className="absolute right-0 top-full mt-1 z-50 w-64"
          style={{
            background: "linear-gradient(180deg, rgba(2,6,23,0.98), rgba(2,6,23,0.99))",
            border: "1px solid rgba(0, 192, 255, 0.25)",
            boxShadow: "0 0 30px rgba(0, 192, 255, 0.1), 0 10px 40px rgba(0, 0, 0, 0.5)",
            clipPath: "polygon(0 0, 100% 0, 100% calc(100% - 6px), calc(100% - 6px) 100%, 0 100%)",
          }}
        >
          {/* Header */}
          <div className="px-3 py-2 border-b border-[#00c0ff]/15 flex items-center justify-between">
            <span
              className="text-[10px] font-mono tracking-[0.15em] uppercase"
              style={{ color: "#ff9f1c" }}
            >
              Filtrar Hubs
            </span>
            <div className="flex gap-2">
              <button
                onClick={handleSelectAll}
                disabled={allSelected}
                className="text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 transition-all"
                style={{
                  color: allSelected ? "#666" : "#00ff80",
                  border: `1px solid ${allSelected ? "rgba(255,255,255,0.05)" : "rgba(0,255,128,0.3)"}`,
                }}
              >
                Todo
              </button>
              <button
                onClick={handleDeselectAll}
                disabled={noneSelected}
                className="text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 transition-all"
                style={{
                  color: noneSelected ? "#666" : "#ff0040",
                  border: `1px solid ${noneSelected ? "rgba(255,255,255,0.05)" : "rgba(255,0,64,0.3)"}`,
                }}
              >
                Nada
              </button>
            </div>
          </div>

          {/* List */}
          <div className="max-h-60 overflow-y-auto">
            {hubs.map((hub) => {
              const isSelected = selected.includes(hub.code);
              return (
                <label
                  key={hub.code}
                  className="flex items-center gap-3 px-3 py-2 cursor-pointer transition-all border-b border-[#00c0ff]/5 last:border-b-0"
                  style={{
                    background: isSelected
                      ? "rgba(0, 192, 255, 0.06)"
                      : "transparent",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = isSelected
                      ? "rgba(0, 192, 255, 0.1)"
                      : "rgba(255, 255, 255, 0.03)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = isSelected
                      ? "rgba(0, 192, 255, 0.06)"
                      : "transparent";
                  }}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => handleToggle(hub.code)}
                    className="w-3.5 h-3.5 accent-[#00c0ff]"
                    style={{
                      accentColor: "#00c0ff",
                    }}
                  />
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      className="text-xs font-bold font-mono"
                      style={{
                        color: isSelected ? "#00c0ff" : "#94a3b8",
                      }}
                    >
                      {hub.code}
                    </span>
                    <span
                      className="text-[10px] truncate"
                      style={{
                        color: isSelected ? "#cbd5e1" : "#64748b",
                      }}
                    >
                      {hub.name}
                    </span>
                  </div>
                </label>
              );
            })}
          </div>

          {/* Footer */}
          <div
            className="px-3 py-1.5 border-t border-[#00c0ff]/15 text-[9px] font-mono text-right"
            style={{ color: "#64748b" }}
          >
            {selected.length} de {hubs.length} visible
          </div>
        </div>
      )}
    </div>
  );
}

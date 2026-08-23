"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { NoisePorCpData } from "@/types";

interface NoiseMapProps {
  data: NoisePorCpData | null;
}

function getColor(pct: number): string {
  if (pct >= 10) return "#b000ff";
  if (pct >= 5) return "#ff0040";
  if (pct >= 2) return "#ff9f1c";
  return "#00ff80";
}

function getRadius(total: number): number {
  const r = Math.sqrt(total) * 1.5;
  return Math.max(8, Math.min(30, r));
}

export function NoiseMap({ data }: NoiseMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const markers = useRef<maplibregl.Marker[]>([]);
  const initialized = useRef(false);

  // Initialize map
  useEffect(() => {
    if (!mapContainer.current || map.current || initialized.current) return;
    initialized.current = true;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
      center: [-100.25, 25.73],
      zoom: 11,
    });

    map.current.addControl(new maplibregl.NavigationControl(), "top-right");

    return () => {
      markers.current.forEach(m => m.remove());
      markers.current = [];
      map.current?.remove();
      map.current = null;
      initialized.current = false;
    };
  }, []);

  // Update markers when data changes
  useEffect(() => {
    if (!map.current || !data || data.features.length === 0) return;

    const mapInstance = map.current;

    // Clear existing markers
    markers.current.forEach(m => m.remove());
    markers.current = [];

    // Wait for map style to be ready before adding markers
    const addMarkers = () => {
      data.features.forEach(f => {
        const p = f.properties;
        const [lng, lat] = f.geometry.coordinates;
        const pct = p.pct_noisy;
        const color = getColor(pct);
        const radius = getRadius(p.total_modems);
        const size = radius * 2;

        // Create circle marker element
        const el = document.createElement("div");
        el.style.width = `${size}px`;
        el.style.height = `${size}px`;
        el.style.borderRadius = "50%";
        el.style.background = color;
        el.style.border = "2px solid rgba(255,255,255,0.6)";
        el.style.boxShadow = `0 0 15px ${color}80, inset 0 0 10px rgba(0,0,0,0.3)`;
        el.style.cursor = "pointer";
        el.title = `CP ${p.codigo_postal}: ${p.noisy_modems}/${p.total_modems} ruidosos (${pct}%)`;

        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([lng, lat])
          .addTo(mapInstance);

        // Popup on click
        const popupHtml = `
          <div style="
            background: linear-gradient(135deg, #0d1220 0%, #080c16 100%);
            padding: 14px;
            border: 1px solid ${color};
            font-family: 'Inter', sans-serif;
            color: #e8ecf2;
            min-width: 180px;
            box-shadow: 0 0 25px ${color}40;
          ">
            <div style="font-weight: bold; color: ${color}; margin-bottom: 10px; font-size: 15px;">
              CP: ${p.codigo_postal}
            </div>
            <div style="font-size: 12px; display: grid; gap: 5px;">
              <div style="display: flex; justify-content: space-between;">
                <span style="color: #94a3b8;">Hub:</span>
                <span style="color: #00ff80;">${p.hub}</span>
              </div>
              <div style="display: flex; justify-content: space-between;">
                <span style="color: #94a3b8;">Módems:</span>
                <span style="color: ${color}; font-weight: bold;">${p.total_modems}</span>
              </div>
              <div style="display: flex; justify-content: space-between;">
                <span style="color: #94a3b8;">Ruidosos:</span>
                <span style="color: ${pct > 5 ? '#ff0040' : pct > 2 ? '#ff9f1c' : '#00ff80'};">${p.noisy_modems} (${pct}%)</span>
              </div>
              <div style="display: flex; justify-content: space-between;">
                <span style="color: #94a3b8;">CER prom:</span>
                <span style="color: #e8ecf2;">${p.avg_cer}</span>
              </div>
              <div style="display: flex; justify-content: space-between;">
                <span style="color: #94a3b8;">SNR prom:</span>
                <span style="color: #e8ecf2;">${p.avg_snr}</span>
              </div>
            </div>
          </div>
        `;

        const popup = new maplibregl.Popup({
          closeButton: true,
          closeOnClick: true,
          maxWidth: "280px",
          offset: [0, -radius],
        }).setHTML(popupHtml);

        marker.setPopup(popup);
        markers.current.push(marker);
      });
    };

    if (!mapInstance.isStyleLoaded()) {
      const onLoad = () => {
        addMarkers();
        mapInstance.off("style.load", onLoad);
      };
      mapInstance.on("style.load", onLoad);
      setTimeout(addMarkers, 1500);
    } else {
      addMarkers();
    }
  }, [data]);

  return (
    <div className="relative w-full h-full">
      <div ref={mapContainer} className="w-full h-full" />

      {/* Legend */}
      <div
        className="absolute top-4 right-4 z-10 text-[10px] font-mono tracking-wider"
        style={{
          background: "rgba(2, 6, 23, 0.9)",
          border: "1px solid rgba(0, 192, 255, 0.3)",
          padding: "10px 14px",
          boxShadow: "0 0 20px rgba(0, 192, 255, 0.1)",
        }}
      >
        <div style={{ color: "#00c0ff", fontWeight: "bold", fontSize: "10px", marginBottom: "8px", letterSpacing: "0.15em" }}>
          ◆ NIVEL RUIDO
        </div>
        <div style={{ display: "grid", gap: "4px" }}>
          {[
            { color: "#00ff80", label: "Bajo ruido (< 1%)" },
            { color: "#ff9f1c", label: "Medio (1-3%)" },
            { color: "#ff0040", label: "Alto (3-8%)" },
            { color: "#b000ff", label: "Crítico (> 8%)" },
          ].map(item => (
            <div key={item.label} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: "50%", background: item.color, border: "1px solid rgba(255,255,255,0.3)" }} />
              <span style={{ color: "#94a3b8" }}>{item.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Vignette overlay */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: "radial-gradient(ellipse at center, transparent 20%, #050810 70%)",
        }}
      />
    </div>
  );
}

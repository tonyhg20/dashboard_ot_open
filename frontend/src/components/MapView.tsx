"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { HubWithMetrics } from "@/types";

interface MapViewProps {
  hubs: HubWithMetrics[];
  selectedHub: string | null;
  onHubClick: (hubCode: string) => void;
}

export function MapView({ hubs, selectedHub, onHubClick }: MapViewProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const markers = useRef<maplibregl.Marker[]>([]);
  const popups = useRef<maplibregl.Popup[]>([]);
  const initialized = useRef(false);

  // Initialize map
  useEffect(() => {
    if (!mapContainer.current || map.current || initialized.current) return;
    initialized.current = true;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
      center: [-93.12, 18.2],
      zoom: 10,
    });

    map.current.addControl(new maplibregl.NavigationControl(), "top-right");

    return () => {
      map.current?.remove();
      map.current = null;
      initialized.current = false;
    };
  }, []);

  // Fit bounds when hubs change
  useEffect(() => {
    if (!map.current || hubs.length === 0) return;

    // Wait for map to be ready
    if (!map.current.isStyleLoaded()) {
      map.current.once("style.load", () => {
        fitBoundsToHubs();
      });
    } else {
      fitBoundsToHubs();
    }

    function fitBoundsToHubs() {
      const bounds = new maplibregl.LngLatBounds();
      hubs.forEach(hub => {
        bounds.extend([hub.lng, hub.lat]);
      });
      map.current?.fitBounds(bounds, { padding: 40, maxZoom: 13 });
    }
  }, [hubs]);

  // Update markers when hubs or selection changes
  useEffect(() => {
    if (!map.current || hubs.length === 0) return;

    // Clear existing markers and popups
    popups.current.forEach(p => p.remove());
    popups.current = [];
    markers.current.forEach(m => m.remove());
    markers.current = [];

    // Add new markers
    hubs.forEach(hub => {
      const color = selectedHub === hub.code ? '#ff00aa' : '#00f0ff';
      
      // Create marker element
      const el = document.createElement("div");
      el.className = "hub-marker marker-with-pulse";
      el.textContent = hub.code;
      
      // Apply styles
      Object.assign(el.style, {
        background: color,
        color: "#050810",
        padding: "4px 8px",
        fontFamily: "'Space Grotesk', sans-serif",
        fontWeight: "bold",
        fontSize: "11px",
        borderRadius: "4px",
        boxShadow: `0 0 15px ${color}80`,
        border: `2px solid ${color}`,
        "--pulse-color": color,
      } as React.CSSProperties);
      
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        onHubClick(hub.code);
      });

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([hub.lng, hub.lat])
        .addTo(map.current!);
      
      markers.current.push(marker);
      
      if (hub.metrics) {
        const popup = new maplibregl.Popup({ 
          offset: [0, -25],
          closeButton: false,
          closeOnClick: false,
          anchor: "bottom"
        }).setHTML(`
          <div style="
            background: linear-gradient(135deg, #0d1220 0%, #080c16 100%);
            padding: 16px;
            border: 1px solid #00f0ff;
            border-radius: 0;
            font-family: 'Inter', sans-serif;
            color: #e8ecf2;
            min-width: 160px;
            box-shadow: 0 0 25px rgba(0,240,255,0.4);
          ">
            <div style="font-weight: bold; color: #00f0ff; margin-bottom: 12px; font-size: 16px; font-family: 'Space Grotesk', sans-serif;">
              📍 ${hub.code}
            </div>
            <div style="font-size: 13px; display: grid; gap: 6px;">
              <div style="display: flex; justify-content: space-between;">
                <span style="color: #9ca3b0;">Total:</span>
                <span style="color: #00f0ff; font-weight: bold;">${hub.metrics.total}</span>
              </div>
              <div style="display: flex; justify-content: space-between;">
                <span style="color: #9ca3b0;">IN:</span>
                <span style="color: #00f0ff;">${hub.metrics.in}</span>
              </div>
              <div style="display: flex; justify-content: space-between;">
                <span style="color: #9ca3b0;">TC:</span>
                <span style="color: #8b00ff;">${hub.metrics.tc}</span>
              </div>
              <div style="display: flex; justify-content: space-between;">
                <span style="color: #9ca3b0;">Rx:</span>
                <span style="color: #00f0ff;">${hub.metrics.rx}</span>
              </div>
              <div style="display: flex; justify-content: space-between;">
                <span style="color: #9ca3b0;">Dx:</span>
                <span style="color: #ff00aa;">${hub.metrics.dx}</span>
              </div>
              <div style="display: flex; justify-content: space-between;">
                <span style="color: #9ca3b0;">RA:</span>
                <span style="color: #8b00ff;">${hub.metrics.ra}</span>
              </div>
            </div>
          </div>
        `);
        
        marker.setPopup(popup);
        
        if (selectedHub === hub.code) {
          popup.addTo(map.current!);
          popups.current.push(popup);
        }
      }
    });
  }, [hubs, selectedHub, onHubClick]);

  return (
    <div className="relative w-full h-full">
      <div ref={mapContainer} className="w-full h-full" />
      <div 
        className="absolute inset-0 pointer-events-none"
        style={{
          background: "radial-gradient(ellipse at center, transparent 20%, #050810 70%)",
        }}
      />
    </div>
  );
}
// 2D map: hillshade tiles served by titiler over the precomputed COG (R4).
// Interaction is fully client-side; the backend only handed out URLs.
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";

export default function Map2D({ tileUrlTemplate }: { tileUrlTemplate: string }) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: {
        version: 8,
        sources: {
          hillshade: {
            type: "raster",
            tiles: [tileUrlTemplate],
            tileSize: 256,
          },
        },
        layers: [
          { id: "bg", type: "background", paint: { "background-color": "#e8e8e8" } },
          { id: "hillshade", type: "raster", source: "hillshade" },
        ],
      },
    });
    return () => map.remove();
  }, [tileUrlTemplate]);

  return <div ref={container} style={{ width: "100%", height: 480 }} />;
}

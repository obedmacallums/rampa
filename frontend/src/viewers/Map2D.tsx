// 2D map: hillshade tiles served by titiler over the precomputed COG (R4).
// The camera must land on the survey: we read bounds from titiler's tilejson
// and fit the view to them — without this the map opens at (0,0) showing
// nothing, since tiles only exist over the site.
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";

interface TileJson {
  tiles: string[];
  bounds?: [number, number, number, number];
  minzoom?: number;
  maxzoom?: number;
}

export default function Map2D({ tilejsonUrl }: { tilejsonUrl: string }) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = container.current;
    if (!el) return;
    let map: maplibregl.Map | null = null;
    let cancelled = false;

    void (async () => {
      const tj = (await (await fetch(tilejsonUrl)).json()) as TileJson;
      if (cancelled) return;
      map = new maplibregl.Map({
        container: el,
        style: {
          version: 8,
          sources: {
            hillshade: {
              type: "raster",
              tiles: tj.tiles,
              tileSize: 256,
              ...(tj.bounds ? { bounds: tj.bounds } : {}),
              ...(tj.maxzoom ? { maxzoom: tj.maxzoom } : {}),
            },
          },
          layers: [
            { id: "bg", type: "background", paint: { "background-color": "#e8e8e8" } },
            { id: "hillshade", type: "raster", source: "hillshade" },
          ],
        },
      });
      if (tj.bounds) {
        map.fitBounds(tj.bounds, { padding: 40, animate: false });
      }
    })();

    return () => {
      cancelled = true;
      map?.remove();
    };
  }, [tilejsonUrl]);

  return <div ref={container} style={{ width: "100%", height: 480 }} />;
}

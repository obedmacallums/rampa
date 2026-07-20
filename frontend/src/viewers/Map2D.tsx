// 2D map: survey layers served by titiler over precomputed COGs (R4).
// The camera must land on the survey: we read bounds from titiler's tilejson
// and fit the view to them — without this the map opens at (0,0) showing
// nothing, since tiles only exist over the site.
//
// The elevation layer is the DEM colorized on the fly by titiler
// (rescale to the 2–98 elevation percentiles + turbo colormap); combined with
// a semi-transparent hillshade it reads like Metashape's DEM view. If the
// statistics fetch fails, the viewer degrades to hillshade-only.
//
// Base layers (OSM / Esri imagery) are public XYZ services fetched by the
// user's browser, never by the backend; on restricted mine-site networks they
// silently fail and the plain background remains, so the survey stays usable.
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

interface TileJson {
  tiles: string[];
  bounds?: [number, number, number, number];
  minzoom?: number;
  maxzoom?: number;
}

interface DemStatistics {
  b1?: { min?: number; max?: number; percentile_2?: number; percentile_98?: number };
}

type Basemap = "none" | "map" | "satellite" | "hybrid";
type SurveyLayer = "relief" | "elevation" | "elevation_relief";

const BASEMAPS: Basemap[] = ["none", "map", "satellite", "hybrid"];
const SURVEY_LAYERS: SurveyLayer[] = ["relief", "elevation", "elevation_relief"];

// Which base layers are visible under each basemap choice.
const BASE_LAYERS: Record<string, Basemap[]> = {
  osm: ["map"],
  "esri-imagery": ["satellite", "hybrid"],
  "esri-labels": ["hybrid"],
};

function visibility(layerId: string, choice: Basemap): "visible" | "none" {
  return BASE_LAYERS[layerId].includes(choice) ? "visible" : "none";
}

function applyBasemap(map: maplibregl.Map, choice: Basemap) {
  for (const layerId of Object.keys(BASE_LAYERS)) {
    map.setLayoutProperty(layerId, "visibility", visibility(layerId, choice));
  }
}

function applySurveyLayer(map: maplibregl.Map, choice: SurveyLayer) {
  if (map.getLayer("dem-color")) {
    map.setLayoutProperty("dem-color", "visibility", choice === "relief" ? "none" : "visible");
  }
  map.setLayoutProperty("hillshade", "visibility", choice === "elevation" ? "none" : "visible");
  map.setPaintProperty("hillshade", "raster-opacity", choice === "elevation_relief" ? 0.45 : 1);
}

async function fetchDemTilejson(
  demStatisticsUrl: string,
  demTilejsonUrl: string,
): Promise<TileJson | null> {
  try {
    const stats = (await (await fetch(demStatisticsUrl)).json()) as DemStatistics;
    const lo = stats.b1?.percentile_2 ?? stats.b1?.min;
    const hi = stats.b1?.percentile_98 ?? stats.b1?.max;
    if (lo == null || hi == null || lo >= hi) return null;
    const styled = `${demTilejsonUrl}&rescale=${lo},${hi}&colormap_name=turbo`;
    return (await (await fetch(styled)).json()) as TileJson;
  } catch {
    return null;
  }
}

interface Map2DProps {
  tilejsonUrl: string;
  demTilejsonUrl: string;
  demStatisticsUrl: string;
}

export default function Map2D({ tilejsonUrl, demTilejsonUrl, demStatisticsUrl }: Map2DProps) {
  const { t } = useTranslation();
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [basemap, setBasemap] = useState<Basemap>("satellite");
  const [surveyLayer, setSurveyLayer] = useState<SurveyLayer>("elevation_relief");
  const [demAvailable, setDemAvailable] = useState(true);
  const basemapRef = useRef(basemap);
  const surveyLayerRef = useRef(surveyLayer);

  useEffect(() => {
    const el = container.current;
    if (!el) return;
    let cancelled = false;

    void (async () => {
      const [tj, demTj] = await Promise.all([
        fetch(tilejsonUrl).then((r) => r.json()) as Promise<TileJson>,
        fetchDemTilejson(demStatisticsUrl, demTilejsonUrl),
      ]);
      if (cancelled) return;
      if (!demTj) {
        surveyLayerRef.current = "relief";
        setDemAvailable(false);
        setSurveyLayer("relief");
      }
      const layer = surveyLayerRef.current;
      const map = new maplibregl.Map({
        container: el,
        style: {
          version: 8,
          sources: {
            osm: {
              type: "raster",
              tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
              tileSize: 256,
              maxzoom: 19,
              attribution:
                '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            },
            "esri-imagery": {
              type: "raster",
              tiles: [
                "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
              ],
              tileSize: 256,
              maxzoom: 19,
              attribution: "Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics",
            },
            "esri-labels": {
              type: "raster",
              tiles: [
                "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
              ],
              tileSize: 256,
              maxzoom: 19,
            },
            ...(demTj
              ? {
                  dem: {
                    type: "raster" as const,
                    tiles: demTj.tiles,
                    tileSize: 256,
                    ...(demTj.bounds ? { bounds: demTj.bounds } : {}),
                    ...(demTj.maxzoom ? { maxzoom: demTj.maxzoom } : {}),
                  },
                }
              : {}),
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
            {
              id: "osm",
              type: "raster",
              source: "osm",
              layout: { visibility: visibility("osm", basemapRef.current) },
            },
            {
              id: "esri-imagery",
              type: "raster",
              source: "esri-imagery",
              layout: { visibility: visibility("esri-imagery", basemapRef.current) },
            },
            {
              id: "esri-labels",
              type: "raster",
              source: "esri-labels",
              layout: { visibility: visibility("esri-labels", basemapRef.current) },
            },
            ...(demTj
              ? [
                  {
                    id: "dem-color",
                    type: "raster" as const,
                    source: "dem",
                    layout: {
                      visibility: (layer === "relief" ? "none" : "visible") as "visible" | "none",
                    },
                  },
                ]
              : []),
            {
              id: "hillshade",
              type: "raster",
              source: "hillshade",
              layout: { visibility: layer === "elevation" ? "none" : "visible" },
              paint: { "raster-opacity": layer === "elevation_relief" ? 0.45 : 1 },
            },
          ],
        },
      });
      mapRef.current = map;
      if (tj.bounds) {
        map.fitBounds(tj.bounds, { padding: 40, animate: false });
      }
    })();

    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [tilejsonUrl, demTilejsonUrl, demStatisticsUrl]);

  useEffect(() => {
    basemapRef.current = basemap;
    const map = mapRef.current;
    if (!map) return;
    if (map.isStyleLoaded()) {
      applyBasemap(map, basemap);
    } else {
      map.once("styledata", () => applyBasemap(map, basemap));
    }
  }, [basemap]);

  useEffect(() => {
    surveyLayerRef.current = surveyLayer;
    const map = mapRef.current;
    if (!map) return;
    if (map.isStyleLoaded()) {
      applySurveyLayer(map, surveyLayer);
    } else {
      map.once("styledata", () => applySurveyLayer(map, surveyLayer));
    }
  }, [surveyLayer]);

  return (
    <div className="relative h-full w-full">
      {/* h-full, not absolute: maplibre-gl.css loads after Tailwind and forces
          position:relative on .maplibregl-map, which would collapse an
          absolutely-positioned container to zero height. */}
      <div ref={container} className="h-full w-full" />
      <div className="absolute left-3 top-3 z-10 grid gap-3 rounded-lg border border-surface-2 bg-surface-1/95 p-3 shadow-lg">
        <div role="radiogroup" aria-label={t("viewer.basemap_label")} className="grid gap-1">
          <strong className="text-xs font-semibold text-text-muted">
            {t("viewer.basemap_label")}
          </strong>
          {BASEMAPS.map((option) => (
            <label key={option} className="flex items-center gap-1.5 text-xs">
              <input
                type="radio"
                name="basemap"
                checked={basemap === option}
                onChange={() => setBasemap(option)}
              />
              {t(`viewer.basemap_${option}`)}
            </label>
          ))}
        </div>
        <div role="radiogroup" aria-label={t("viewer.layer_label")} className="grid gap-1">
          <strong className="text-xs font-semibold text-text-muted">
            {t("viewer.layer_label")}
          </strong>
          {SURVEY_LAYERS.filter((option) => demAvailable || option === "relief").map((option) => (
            <label key={option} className="flex items-center gap-1.5 text-xs">
              <input
                type="radio"
                name="survey-layer"
                checked={surveyLayer === option}
                onChange={() => setSurveyLayer(option)}
              />
              {t(`viewer.layer_${option}`)}
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}

// 3D viewer: Potree 1.8.2 (static assets under /potree) streams the COPC
// octree via HTTP range requests with camera-driven progressive LOD. The
// presigned URL is probed before loading so an expired link triggers
// onUrlExpired and the parent can remount with a fresh product set.
//
// Potree ships as classic scripts (global namespace), not an npm module, so
// its build and support libraries are served from public/potree and loaded
// on first use. Potree.Viewer has no dispose API; a single viewer instance is
// created once and re-parented across mounts instead of recreated.
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import Alert from "../ui/Alert";

interface Props {
  copcUrl: string;
  onUrlExpired?: () => void;
}

interface PotreePointCloud {
  material: { size: number; pointSizeType: number };
}

interface PotreeScene {
  addPointCloud(pointcloud: PotreePointCloud): void;
  pointclouds: PotreePointCloud[];
  scenePointCloud: { remove(object: PotreePointCloud): void };
}

interface PotreeViewer {
  setEDLEnabled(enabled: boolean): void;
  setFOV(fov: number): void;
  setPointBudget(budget: number): void;
  setLanguage(lang: string): void;
  loadGUI(callback?: () => void): void;
  scene: PotreeScene;
  fitToScreen(factor?: number): void;
}

interface PotreeGlobal {
  Viewer: new (element: HTMLElement) => PotreeViewer;
  PointSizeType: { ADAPTIVE: number };
  loadPointCloud(
    path: string,
    name: string,
    callback: (event: { pointcloud: PotreePointCloud }) => void,
  ): void;
}

const POINT_BUDGET = 2_000_000;

const POTREE_STYLES = [
  "/potree/build/potree/potree.css",
  "/potree/libs/jquery-ui/jquery-ui.min.css",
  "/potree/libs/openlayers3/ol.css",
  "/potree/libs/spectrum/spectrum.css",
  "/potree/libs/jstree/themes/mixed/style.css",
];

// Order matters: Potree expects these globals; laslaz loads after potree.js,
// mirroring the upstream examples.
const POTREE_SCRIPTS = [
  "/potree/libs/jquery/jquery-3.1.1.min.js",
  "/potree/libs/spectrum/spectrum.js",
  "/potree/libs/jquery-ui/jquery-ui.min.js",
  "/potree/libs/other/BinaryHeap.js",
  "/potree/libs/tween/tween.min.js",
  "/potree/libs/d3/d3.js",
  "/potree/libs/proj4/proj4.js",
  "/potree/libs/openlayers3/ol.js",
  "/potree/libs/i18next/i18next.js",
  "/potree/libs/jstree/jstree.js",
  "/potree/libs/copc/index.js",
  "/potree/build/potree/potree.js",
  "/potree/libs/plasio/js/laslaz.js",
];

let assetsPromise: Promise<void> | undefined;

function loadStyle(href: string): void {
  if (document.querySelector(`link[href="${href}"]`)) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  document.head.appendChild(link);
}

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`failed to load ${src}`));
    document.head.appendChild(script);
  });
}

function ensurePotreeAssets(): Promise<void> {
  return (assetsPromise ??= (async () => {
    POTREE_STYLES.forEach(loadStyle);
    for (const src of POTREE_SCRIPTS) await loadScript(src);
  })());
}

// Singleton viewer, re-parented across mounts (Potree has no dispose API).
let shared:
  | { host: HTMLDivElement; viewer: PotreeViewer; loadedObject?: string }
  | undefined;

export default function Cloud3D({ copcUrl, onUrlExpired }: Props) {
  const { t, i18n } = useTranslation();
  const container = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const el = container.current;
    if (!el) return;
    let disposed = false;

    void (async () => {
      try {
        // Probe the presigned URL before handing it to Potree: an expired
        // link should surface as a refresh, not a broken scene.
        const probe = await fetch(copcUrl, { headers: { Range: "bytes=0-0" } });
        if (!probe.ok) {
          throw Object.assign(new Error(`copc probe failed: ${probe.status}`), {
            status: probe.status,
          });
        }
        await ensurePotreeAssets();
        if (disposed) return;

        const Potree = (window as unknown as { Potree: PotreeGlobal }).Potree;
        if (!shared) {
          const host = document.createElement("div");
          host.className = "potree_container";
          host.style.cssText = "position:relative;width:100%;height:100%";
          const renderArea = document.createElement("div");
          renderArea.id = "potree_render_area";
          renderArea.style.cssText = "position:absolute;inset:0";
          const sidebar = document.createElement("div");
          sidebar.id = "potree_sidebar_container";
          host.appendChild(renderArea);
          host.appendChild(sidebar);
          el.appendChild(host);
          const viewer = new Potree.Viewer(renderArea);
          viewer.setEDLEnabled(true);
          viewer.setFOV(60);
          viewer.setPointBudget(POINT_BUDGET);
          viewer.loadGUI(() => {
            viewer.setLanguage(i18n.language.startsWith("es") ? "es" : "en");
          });
          shared = { host, viewer };
        } else {
          el.appendChild(shared.host);
        }

        // Same object under a refreshed signature needs no reload.
        const objectKey = copcUrl.split("?")[0];
        if (shared.loadedObject === objectKey) {
          setState("ready");
          return;
        }
        const current = shared;
        // The shared viewer is re-parented, not recreated, across surveys
        // (Potree has no dispose API) — addPointCloud only ever appends, so
        // a previously viewed survey's cloud must be explicitly dropped or
        // it stays rendered underneath/alongside the new one.
        for (const stale of current.viewer.scene.pointclouds.splice(0)) {
          current.viewer.scene.scenePointCloud.remove(stale);
        }
        Potree.loadPointCloud(copcUrl, "survey", (event) => {
          if (disposed) return;
          current.viewer.scene.addPointCloud(event.pointcloud);
          event.pointcloud.material.size = 1;
          event.pointcloud.material.pointSizeType = Potree.PointSizeType.ADAPTIVE;
          current.viewer.fitToScreen(0.5);
          current.loadedObject = objectKey;
          setState("ready");
        });
      } catch (error) {
        if (disposed) return;
        console.error("Cloud3D load failed:", error);
        setState("error");
        if ((error as { status?: number }).status === 403) onUrlExpired?.();
      }
    })();

    return () => {
      disposed = true;
      if (shared && shared.host.parentElement === el) el.removeChild(shared.host);
    };
  }, [copcUrl, onUrlExpired]);

  return (
    <div className="relative h-full w-full">
      <div ref={container} className="h-full w-full" />
      {state === "loading" && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <p className="animate-pulse text-sm text-text-muted">{t("viewer.loading_3d")}</p>
        </div>
      )}
      {state === "error" && (
        <div className="absolute inset-x-0 top-4 mx-auto max-w-md px-4">
          <Alert>{t("viewer.error_3d")}</Alert>
        </div>
      )}
    </div>
  );
}

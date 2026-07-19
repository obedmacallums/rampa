// 3D viewer: streams the COPC octree via HTTP range requests (copc.js) and
// renders with three.js. Progressive detail: octree nodes load coarse-to-fine
// (by depth) and appear as they arrive, up to a point budget. When the
// presigned URL expires mid-session, the parent re-fetches the ArtifactSet
// (onUrlExpired) and remounts with a fresh URL.
import { Copc, Getter, Hierarchy } from "copc";
import { createLazPerf, type LazPerf } from "laz-perf";
import lazPerfWasmUrl from "laz-perf/lib/web/laz-perf.wasm?url";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

const POINT_BUDGET = 4_000_000;

// laz-perf resolves its .wasm relative to the current page URL, which under the
// SPA router returns index.html; point it at the Vite-bundled asset instead.
let lazPerfPromise: Promise<LazPerf> | undefined;
function getLazPerf(): Promise<LazPerf> {
  return (lazPerfPromise ??= createLazPerf({
    locateFile: (file: string) => (file.endsWith(".wasm") ? lazPerfWasmUrl : file),
  }));
}

interface Props {
  copcUrl: string;
  onUrlExpired?: () => void;
}

function makeGetter(url: string): Getter {
  return async (begin, end) => {
    const response = await fetch(url, {
      headers: { Range: `bytes=${begin}-${end - 1}` },
    });
    if (!response.ok) {
      throw Object.assign(new Error(`range fetch failed: ${response.status}`), {
        status: response.status,
      });
    }
    return new Uint8Array(await response.arrayBuffer());
  };
}

export default function Cloud3D({ copcUrl, onUrlExpired }: Props) {
  const { t } = useTranslation();
  const container = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const el = container.current;
    if (!el) return;
    let disposed = false;
    let frame = 0;

    const width = el.clientWidth || 800;
    const height = 480;
    const renderer = new THREE.WebGLRenderer({ antialias: false });
    renderer.setSize(width, height);
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1a22);
    const camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 100_000);
    const controls = new OrbitControls(camera, renderer.domElement);

    const animate = () => {
      frame = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };

    void (async () => {
      try {
        const getter = makeGetter(copcUrl);
        const lazPerf = await getLazPerf();
        const copc = await Copc.create(getter);
        const cube = copc.info.cube;
        const center = new THREE.Vector3(
          (cube[0] + cube[3]) / 2,
          (cube[1] + cube[4]) / 2,
          (cube[2] + cube[5]) / 2,
        );
        const size = Math.max(cube[3] - cube[0], cube[4] - cube[1]);
        const zMin = copc.header.min[2];
        const zMax = copc.header.max[2];

        camera.up.set(0, 0, 1); // z-up: geospatial convention
        camera.position.set(0, -size * 0.9, size * 0.6);
        controls.target.set(0, 0, 0);
        animate();

        // Collect the hierarchy (root page + any nested pages).
        let nodes: Hierarchy.Node.Map = {};
        let pending: Hierarchy.Page[] = [copc.info.rootHierarchyPage];
        while (pending.length > 0) {
          const page = pending.shift()!;
          const loaded = await Copc.loadHierarchyPage(getter, page);
          nodes = { ...nodes, ...loaded.nodes };
          pending = pending.concat(
            Object.values(loaded.pages).filter((p): p is Hierarchy.Page => p !== undefined),
          );
        }

        // Coarse-to-fine: depth order gives progressive detail as nodes land.
        const keys = Object.keys(nodes).sort(
          (a, b) => parseInt(a.split("-")[0]) - parseInt(b.split("-")[0]),
        );
        let budget = POINT_BUDGET;
        for (const key of keys) {
          if (disposed || budget <= 0) break;
          const node = nodes[key];
          if (!node || node.pointCount === 0 || node.pointCount > budget) continue;
          const view = await Copc.loadPointDataView(getter, copc, node, { lazPerf });
          const [gx, gy, gz] = ["X", "Y", "Z"].map((d) => view.getter(d));
          const positions = new Float32Array(view.pointCount * 3);
          const colors = new Float32Array(view.pointCount * 3);
          const color = new THREE.Color();
          for (let i = 0; i < view.pointCount; i++) {
            positions[i * 3] = gx(i) - center.x;
            positions[i * 3 + 1] = gy(i) - center.y;
            positions[i * 3 + 2] = gz(i) - center.z;
            const tz = zMax > zMin ? (gz(i) - zMin) / (zMax - zMin) : 0.5;
            color.setHSL(0.66 - 0.66 * tz, 0.85, 0.35 + 0.3 * tz); // blue→red by elevation
            colors[i * 3] = color.r;
            colors[i * 3 + 1] = color.g;
            colors[i * 3 + 2] = color.b;
          }
          if (disposed) break;
          const geometry = new THREE.BufferGeometry();
          geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
          geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
          const material = new THREE.PointsMaterial({ size: 0.6, vertexColors: true });
          scene.add(new THREE.Points(geometry, material));
          budget -= view.pointCount;
          setState("ready");
        }
        if (!disposed) setState("ready");
      } catch (error) {
        if (disposed) return;
        console.error("Cloud3D load failed:", error);
        setState("error");
        if ((error as { status?: number }).status === 403) onUrlExpired?.();
      }
    })();

    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      controls.dispose();
      scene.traverse((obj) => {
        if (obj instanceof THREE.Points) {
          obj.geometry.dispose();
          (obj.material as THREE.Material).dispose();
        }
      });
      renderer.dispose();
      el.removeChild(renderer.domElement);
    };
  }, [copcUrl, onUrlExpired]);

  return (
    <div>
      <div ref={container} style={{ width: "100%" }} />
      {state === "loading" && <p>{t("viewer.loading_3d")}</p>}
      {state === "error" && <p role="alert">{t("viewer.error_3d")}</p>}
    </div>
  );
}

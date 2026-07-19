// 3D viewer: Potree (potree-core) rendering the COPC with progressive LOD via
// HTTP range requests against a presigned URL (R2/R10). When the presigned URL
// expires mid-session, the parent re-fetches the ArtifactSet (onUrlExpired) and
// remounts with a fresh URL (analysis remediation I2).
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import * as THREE from "three";

interface Props {
  copcUrl: string;
  onUrlExpired?: () => void;
}

export default function Cloud3D({ copcUrl, onUrlExpired }: Props) {
  const { t } = useTranslation();
  const container = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    let disposed = false;
    let frame = 0;
    const el = container.current;
    if (!el) return;

    const renderer = new THREE.WebGLRenderer();
    renderer.setSize(el.clientWidth, 480);
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, el.clientWidth / 480, 0.1, 10_000);
    camera.position.set(0, -50, 40);
    camera.lookAt(0, 0, 0);

    (async () => {
      try {
        const potreeCore = await import("potree-core");
        const potree = new potreeCore.Potree();
        // potree-core >= 2.1 loads COPC directly; older builds expose loadPointCloud.
        const load =
          (potree as unknown as { loadCopc?: (url: string) => Promise<unknown> }).loadCopc ??
          ((url: string) => potree.loadPointCloud(url, ""));
        const cloud = (await load(copcUrl)) as THREE.Object3D & { material?: unknown };
        if (disposed) return;
        scene.add(cloud);
        setState("ready");

        const clouds = [cloud];
        const animate = () => {
          frame = requestAnimationFrame(animate);
          // progressive LOD: potree updates visible octree nodes per frame
          (potree as unknown as {
            updatePointClouds: (c: unknown[], cam: THREE.Camera, r: THREE.WebGLRenderer) => void;
          }).updatePointClouds(clouds, camera, renderer);
          renderer.render(scene, camera);
        };
        animate();
      } catch (error) {
        if (disposed) return;
        setState("error");
        const status = (error as { status?: number }).status;
        if (status === 403) onUrlExpired?.();
      }
    })();

    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
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

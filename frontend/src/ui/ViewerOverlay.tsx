import { ReactNode, useEffect } from "react";
import { useTranslation } from "react-i18next";

import Button from "./Button";

export type ViewerOverlayProps = {
  title: string;
  onClose: () => void;
  actions?: ReactNode; // rendered in the header, next to the close button
  controls?: ReactNode;
  children: ReactNode;
};

// Full-viewport stage for the 2D/3D viewers (US3): the page underneath stays
// mounted, so closing restores it exactly as left. Esc also closes.
export default function ViewerOverlay({
  title,
  onClose,
  actions,
  controls,
  children,
}: ViewerOverlayProps) {
  const { t } = useTranslation();

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    // Inline !important so the lock also beats the body override in
    // index.css that neutralizes potree.css's global body rules.
    document.body.style.setProperty("overflow", "hidden", "important");
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.removeProperty("overflow");
    };
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-surface-0">
      <div className="flex h-12 shrink-0 items-center justify-between gap-4 border-b border-surface-2 bg-surface-1 px-4">
        <span className="truncate text-sm font-semibold text-text-strong">{title}</span>
        <div className="flex items-center gap-3">
          {actions}
          <Button variant="secondary" onClick={onClose} aria-label={t("viewer.close")}>
            {t("common.close")}
          </Button>
        </div>
      </div>
      <div className="relative flex-1 overflow-hidden">
        {children}
        {controls && <div className="absolute left-3 top-3 z-10">{controls}</div>}
      </div>
    </div>
  );
}

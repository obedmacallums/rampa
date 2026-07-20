import { useTranslation } from "react-i18next";

export type ViewerMode = "2d" | "3d";

function MapIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="size-4">
      <path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2z" />
      <path d="M9 4v14M15 6v14" />
    </svg>
  );
}

function CubeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="size-4">
      <path d="M12 2 3 7v10l9 5 9-5V7l-9-5z" />
      <path d="m3 7 9 5 9-5M12 12v10" />
    </svg>
  );
}

export type ViewerModeSwitchProps = {
  mode: ViewerMode;
  onChange: (mode: ViewerMode) => void;
};

export default function ViewerModeSwitch({ mode, onChange }: ViewerModeSwitchProps) {
  const { t } = useTranslation();
  const options = [
    { value: "2d" as const, label: "2D", title: t("surveys.view_2d"), icon: <MapIcon /> },
    { value: "3d" as const, label: "3D", title: t("surveys.view_3d"), icon: <CubeIcon /> },
  ];

  return (
    <div
      role="group"
      aria-label={t("viewer.mode_label")}
      className="flex overflow-hidden rounded-md border border-surface-2 text-xs font-medium"
    >
      {options.map((option) => {
        const active = mode === option.value;
        return (
          <button
            key={option.value}
            type="button"
            title={option.title}
            aria-label={option.title}
            aria-pressed={active}
            onClick={() => onChange(option.value)}
            className={
              active
                ? "flex items-center gap-1.5 bg-accent px-2.5 py-1.5 text-on-accent"
                : "flex items-center gap-1.5 px-2.5 py-1.5 text-text-muted transition-colors hover:bg-surface-2"
            }
          >
            {option.icon}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

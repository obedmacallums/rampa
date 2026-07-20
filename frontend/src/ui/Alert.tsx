import { ReactNode } from "react";

const KIND_CLASSES = {
  error: "border-status-failed/40 bg-status-failed/10 text-status-failed",
  info: "border-status-processing/40 bg-status-processing/10 text-status-processing",
} as const;

export type AlertProps = {
  kind?: keyof typeof KIND_CLASSES;
  children: ReactNode;
};

export default function Alert({ kind = "error", children }: AlertProps) {
  return (
    <p role="alert" className={`rounded-md border px-3 py-2 text-sm ${KIND_CLASSES[kind]}`}>
      {children}
    </p>
  );
}

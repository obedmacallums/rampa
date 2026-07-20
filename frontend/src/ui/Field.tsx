import { ReactNode } from "react";

export type FieldProps = {
  label: string;
  error?: string | null;
  htmlFor?: string;
  children: ReactNode;
};

export default function Field({ label, error, htmlFor, children }: FieldProps) {
  return (
    <label htmlFor={htmlFor} className="grid gap-1 text-sm">
      <span className="font-medium text-text-muted">{label}</span>
      {children}
      {error && (
        <span role="alert" className="text-xs text-status-failed">
          {error}
        </span>
      )}
    </label>
  );
}

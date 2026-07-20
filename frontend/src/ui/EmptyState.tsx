import { ReactNode } from "react";

export type EmptyStateProps = {
  message: string;
  action?: ReactNode;
};

export default function EmptyState({ message, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-surface-2 px-6 py-10 text-center">
      <p className="text-sm text-text-muted">{message}</p>
      {action}
    </div>
  );
}

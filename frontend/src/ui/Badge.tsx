const STATUS_CLASSES = {
  queued: "border-status-queued/40 bg-status-queued/10 text-status-queued",
  processing: "border-status-processing/40 bg-status-processing/10 text-status-processing",
  completed: "border-status-completed/40 bg-status-completed/10 text-status-completed",
  failed: "border-status-failed/40 bg-status-failed/10 text-status-failed",
} as const;

export type BadgeProps = {
  status: keyof typeof STATUS_CLASSES;
  label: string;
};

export default function Badge({ status, label }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${STATUS_CLASSES[status]}`}
    >
      <span aria-hidden className="size-1.5 rounded-full bg-current" />
      {label}
    </span>
  );
}

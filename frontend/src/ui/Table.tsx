import { ReactNode, TdHTMLAttributes, ThHTMLAttributes } from "react";

export function Table({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-surface-2">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  );
}

export function Th({ children, ...rest }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className="border-b border-surface-2 bg-surface-1 px-3 py-2 text-left font-medium text-text-muted"
      {...rest}
    >
      {children}
    </th>
  );
}

export function Td({ children, ...rest }: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td className="border-b border-surface-2/50 px-3 py-2" {...rest}>
      {children}
    </td>
  );
}

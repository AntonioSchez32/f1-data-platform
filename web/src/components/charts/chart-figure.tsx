import type { ReactNode } from "react";

/**
 * Gráfico accesible: título, resumen en texto (lo que un lector de pantalla necesita saber) y los
 * datos completos en una tabla desplegable.
 */
export function ChartFigure({
  title,
  summary,
  tableLabel,
  table,
  children,
}: {
  title: ReactNode;
  summary: ReactNode;
  tableLabel: string;
  table: ReactNode;
  children: ReactNode;
}) {
  return (
    <figure className="grid min-w-0 gap-3 rounded-lg border border-line bg-surface p-4">
      <figcaption className="grid gap-1">
        <span className="font-display text-lg font-bold">{title}</span>
        <span className="text-sm text-muted">{summary}</span>
      </figcaption>
      <div className="min-w-0">{children}</div>
      <details className="group">
        <summary className="cursor-pointer text-sm font-semibold text-muted hover:text-ink">
          {tableLabel}
        </summary>
        <div className="mt-3">{table}</div>
      </details>
    </figure>
  );
}

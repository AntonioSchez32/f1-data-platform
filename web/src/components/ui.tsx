import Link from "next/link";
import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  lede,
  children,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  lede?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <header className="mb-8 grid gap-3 border-t-4 border-red pt-4">
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <h1 className="text-3xl font-bold sm:text-4xl">{title}</h1>
      {lede && <p className="max-w-[68ch] text-muted">{lede}</p>}
      {children}
    </header>
  );
}

export function Section({
  title,
  lede,
  id,
  action,
  children,
}: {
  title: ReactNode;
  lede?: ReactNode;
  id?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  const headingId = id ? `${id}-titulo` : undefined;
  return (
    <section aria-labelledby={headingId} id={id} className="mb-12 grid min-w-0 content-start gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id={headingId} className="text-2xl font-bold">
          {title}
        </h2>
        {action}
      </div>
      {lede && <p className="-mt-2 max-w-[68ch] text-muted">{lede}</p>}
      {children}
    </section>
  );
}

export type Column<T> = {
  header: ReactNode;
  cell: (row: T, index: number) => ReactNode;
  align?: "left" | "right" | "center";
  /** Celda de cabecera de fila (th scope="row"): el identificador de la fila. */
  rowHeader?: boolean;
  className?: string;
  /** Orden aplicado a esta columna (aria-sort en la cabecera). */
  sort?: "ascending" | "descending";
};

const ALIGN = { left: "text-left", right: "text-right", center: "text-center" };

/** Tabla accesible: caption, cabeceras con scope y desplazamiento horizontal navegable con teclado. */
export function DataTable<T>({
  caption,
  captionHidden = false,
  columns,
  rows,
  rowKey,
  rowClassName,
  compact = false,
}: {
  caption: ReactNode;
  captionHidden?: boolean;
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string | number;
  rowClassName?: (row: T) => string | undefined;
  compact?: boolean;
}) {
  const pad = compact ? "px-2 py-1" : "px-3 py-2";
  return (
    <div
      className="relative min-w-0 overflow-x-auto rounded-lg border border-line bg-surface"
      role="region"
      aria-label={typeof caption === "string" ? caption : undefined}
      tabIndex={0}
    >
      <table className="w-full border-collapse text-sm">
        <caption className={captionHidden ? "sr-only" : "px-3 pt-3 text-left font-semibold"}>
          {caption}
        </caption>
        <thead>
          <tr className="border-b border-line text-xs uppercase tracking-wider text-muted">
            {columns.map((column, i) => (
              <th
                key={i}
                scope="col"
                aria-sort={column.sort}
                className={`${pad} font-semibold whitespace-nowrap ${ALIGN[column.align ?? "left"]}`}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr
              key={rowKey(row, rowIndex)}
              className={`border-b border-line last:border-0 ${rowClassName?.(row) ?? ""}`}
            >
              {columns.map((column, i) => {
                const Cell = column.rowHeader ? "th" : "td";
                return (
                  <Cell
                    key={i}
                    scope={column.rowHeader ? "row" : undefined}
                    className={`${pad} ${ALIGN[column.align ?? "left"]} ${
                      column.rowHeader ? "font-medium" : ""
                    } ${column.className ?? ""}`}
                  >
                    {column.cell(row, rowIndex)}
                  </Cell>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Pill({
  tone = "neutral",
  children,
  title,
}: {
  tone?: "neutral" | "good" | "bad" | "info" | "best";
  children: ReactNode;
  title?: string;
}) {
  const tones = {
    neutral: "bg-surface-2 text-muted",
    good: "bg-green-soft text-green",
    bad: "bg-amber-soft text-amber",
    info: "bg-surface-2 text-ink",
    best: "bg-purple-soft text-purple",
  };
  return (
    <span
      title={title}
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-dashed border-line bg-surface px-4 py-6 text-muted">
      {children}
    </p>
  );
}

/** Cifra destacada de una ficha (solo donde la cifra es el dato principal). */
export function Stat({ label, value }: { label: ReactNode; value: ReactNode }) {
  return (
    <div className="grid gap-0.5 rounded-lg border border-line bg-surface px-4 py-3">
      <dt className="text-xs font-semibold uppercase tracking-wider text-muted">{label}</dt>
      <dd className="font-display text-2xl font-bold tabular-nums">{value}</dd>
    </div>
  );
}

/** Tarjeta destacada con un dato en grande (tarjetas de la página de temporada del TFG). */
export function Highlight({ label, value, href }: { label: ReactNode; value: ReactNode; href?: string }) {
  return (
    <div className="grid content-start gap-1 rounded-lg border border-line bg-surface px-4 py-3">
      <dt className="text-xs font-semibold uppercase tracking-wider text-muted">{label}</dt>
      <dd className="font-display text-2xl font-bold sm:text-3xl">
        {href ? <Link href={href}>{value}</Link> : value}
      </dd>
    </div>
  );
}

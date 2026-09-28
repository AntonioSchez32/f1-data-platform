import { compoundStyle } from "@/lib/tyres";

export type MatrixRow = {
  driverId: string;
  name: string;
  /** Por vuelta (índice = vuelta - 1): compuesto y si entró a boxes al final de esa vuelta. */
  laps: ({ compound: string | null; pit: boolean } | null)[];
};

/**
 * Matriz piloto × vuelta con el compuesto de cada vuelta (página «Neumáticos usados» del TFG).
 * Es una tabla: cada celda lleva la letra del compuesto y las vueltas de entrada a boxes van
 * recuadradas y anunciadas en texto para lectores de pantalla.
 */
export function CompoundMatrix({
  rows,
  caption,
  driverLabel,
  lapLabel,
  pitLabel,
  compoundName,
}: {
  rows: MatrixRow[];
  caption: string;
  driverLabel: string;
  lapLabel: string;
  pitLabel: string;
  compoundName: (compound: string | null) => string;
}) {
  const laps = Math.max(...rows.map((r) => r.laps.length));
  return (
    <div
      className="min-w-0 overflow-x-auto rounded-lg border border-line bg-surface"
      role="region"
      aria-label={caption}
      tabIndex={0}
    >
      <table className="border-separate border-spacing-0.5 text-xs">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col" className="sticky left-0 z-10 bg-surface px-2 py-1 text-left font-semibold text-muted">
              {driverLabel}
            </th>
            {Array.from({ length: laps }, (_, i) => (
              <th key={i} scope="col" className="min-w-6 px-0 py-1 text-center font-normal text-muted tabular">
                <span className="sr-only">{lapLabel} </span>
                {i + 1}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.driverId}>
              <th
                scope="row"
                className="sticky left-0 z-10 whitespace-nowrap bg-surface px-2 py-0.5 text-left font-medium"
              >
                {row.name}
              </th>
              {Array.from({ length: laps }, (_, i) => {
                const lap = row.laps[i];
                if (!lap) return <td key={i} />;
                const style = compoundStyle(lap.compound);
                const name = compoundName(lap.compound);
                return (
                  <td
                    key={i}
                    title={`${row.name} · ${lapLabel} ${i + 1}: ${name}${lap.pit ? ` · ${pitLabel}` : ""}`}
                    className={`h-6 min-w-6 rounded-sm text-center font-mono font-semibold ${
                      lap.pit ? "outline outline-2 -outline-offset-2 outline-ink" : ""
                    }`}
                    style={{ backgroundColor: style.color, color: style.text }}
                  >
                    <span aria-hidden="true">{style.letter}</span>
                    <span className="sr-only">
                      {name}
                      {lap.pit ? `, ${pitLabel}` : ""}
                    </span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

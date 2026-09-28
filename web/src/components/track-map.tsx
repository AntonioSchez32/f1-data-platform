/** Trazado del circuito coloreado por velocidad, en SVG estático con las proporciones reales. */

const STOPS = ["#2F6FDE", "#56B4E9", "#E69F00", "#D55E00"];

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** Color de la escala secuencial (azul = lento, naranja = rápido) para t en [0, 1]. */
function colorAt(t: number): string {
  const scaled = Math.min(Math.max(t, 0), 1) * (STOPS.length - 1);
  const i = Math.min(Math.floor(scaled), STOPS.length - 2);
  const [a, b] = [hexToRgb(STOPS[i]), hexToRgb(STOPS[i + 1])];
  const f = scaled - i;
  const mix = a.map((v, k) => Math.round(v + (b[k] - v) * f));
  return `rgb(${mix.join(",")})`;
}

export function TrackMap({
  x,
  y,
  speed,
  title,
  description,
  slowLabel,
  fastLabel,
}: {
  x: (number | null)[];
  y: (number | null)[];
  speed: (number | null)[];
  title: string;
  description: string;
  slowLabel: string;
  fastLabel: string;
}) {
  const points = x
    .map((px, i) => ({ x: px, y: y[i], v: speed[i] }))
    .filter((p): p is { x: number; y: number; v: number } => p.x !== null && p.y !== null && p.v !== null);
  if (points.length < 2) return null;

  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const vs = points.map((p) => p.v);
  const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const [minV, maxV] = [Math.min(...vs), Math.max(...vs)];
  const pad = 0.04 * Math.max(maxX - minX, maxY - minY);
  const width = maxX - minX + 2 * pad;
  const height = maxY - minY + 2 * pad;
  // La Y de la telemetría crece hacia arriba; en SVG crece hacia abajo.
  const sx = (v: number) => v - minX + pad;
  const sy = (v: number) => maxY - v + pad;
  const stroke = width / 110;

  return (
    <div className="grid gap-2">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-labelledby="trazado-titulo trazado-desc"
        className="mx-auto h-auto max-h-[420px] w-full"
      >
        <title id="trazado-titulo">{title}</title>
        <desc id="trazado-desc">{description}</desc>
        <g strokeWidth={stroke} strokeLinecap="round">
          {points.slice(1).map((p, i) => {
            const prev = points[i];
            return (
              <line
                key={i}
                x1={sx(prev.x)}
                y1={sy(prev.y)}
                x2={sx(p.x)}
                y2={sy(p.y)}
                stroke={colorAt((p.v - minV) / (maxV - minV || 1))}
              />
            );
          })}
        </g>
      </svg>
      <div className="mx-auto flex items-center gap-2 text-xs text-muted" aria-hidden="true">
        <span className="tabular">{slowLabel}</span>
        <span
          className="h-2 w-40 rounded"
          style={{ background: `linear-gradient(to right, ${STOPS.join(", ")})` }}
        />
        <span className="tabular">{fastLabel}</span>
      </div>
    </div>
  );
}

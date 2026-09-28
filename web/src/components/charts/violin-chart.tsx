"use client";

import { type CSSProperties, useMemo, useState } from "react";

import { lapTime } from "@/lib/format";

import { DARK_SERIES, LIGHT_SERIES } from "./echart";

export type ViolinDriver = {
  id: string;
  name: string;
  code: string;
  /** Posición en la paleta (orden de llegada), para usar el mismo color que en los demás gráficos. */
  colorIndex: number;
  /** Densidad estimada (KDE) en puntos [tiempo ms, densidad]. */
  density: [number, number][];
  q1: number;
  median: number;
  q3: number;
  whiskerLow: number;
  whiskerHigh: number;
};

type Labels = { title: string; time: string; drivers: string; all: string; none: string; median: string };

const HEIGHT = 440;
const MARGIN = { top: 12, right: 12, bottom: 56, left: 72 };
const BAND = 46;

/**
 * Gráfico de violín del ritmo de carrera (página «Ritmo de carrera» del TFG): la forma muestra
 * dónde se concentran los tiempos de cada piloto y la caja interior, P25–P75 y la mediana.
 */
export function ViolinChart({ drivers, labels }: { drivers: ViolinDriver[]; labels: Labels }) {
  const [selected, setSelected] = useState(() => new Set(drivers.map((d) => d.id)));
  const visible = useMemo(() => drivers.filter((d) => selected.has(d.id)), [drivers, selected]);

  const times = visible.flatMap((d) => d.density.map(([t]) => t));
  const minT = Math.min(...times);
  const maxT = Math.max(...times);
  const width = MARGIN.left + MARGIN.right + Math.max(visible.length, 1) * BAND;
  const plotHeight = HEIGHT - MARGIN.top - MARGIN.bottom;
  const y = (t: number) => MARGIN.top + ((maxT - t) / (maxT - minT || 1)) * plotHeight;
  const ticks = Array.from({ length: 6 }, (_, i) => minT + ((maxT - minT) * i) / 5);

  const toggle = (id: string) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_15rem]">
      <div className="relative min-w-0 overflow-x-auto" tabIndex={0} role="region" aria-label={labels.title}>
        {visible.length > 0 && (
          <svg
            viewBox={`0 0 ${width} ${HEIGHT}`}
            role="img"
            aria-label={labels.title}
            className="h-auto w-full text-muted"
            style={{ minWidth: Math.min(width, visible.length * 30 + MARGIN.left) }}
          >
            {/* Eje de tiempos */}
            <g className="text-[10px]">
              {ticks.map((t) => (
                <g key={t}>
                  <line x1={MARGIN.left} x2={width - MARGIN.right} y1={y(t)} y2={y(t)} className="stroke-line" strokeDasharray="3 3" />
                  <text x={MARGIN.left - 6} y={y(t)} dy="0.32em" textAnchor="end" className="fill-muted font-mono">
                    {lapTime(t)}
                  </text>
                </g>
              ))}
              <text
                transform={`translate(14 ${MARGIN.top + plotHeight / 2}) rotate(-90)`}
                textAnchor="middle"
                className="fill-muted"
              >
                {labels.time}
              </text>
            </g>
            {visible.map((driver, i) => {
              const cx = MARGIN.left + BAND * i + BAND / 2;
              const maxD = Math.max(...driver.density.map(([, d]) => d));
              const half = (d: number) => (d / maxD) * (BAND / 2 - 4);
              const right = driver.density.map(([t, d]) => `${cx + half(d)},${y(t)}`);
              const left = [...driver.density].reverse().map(([t, d]) => `${cx - half(d)},${y(t)}`);
              const index = driver.colorIndex;
              return (
                <g key={driver.id}>
                  <title>
                    {`${driver.name}: ${labels.median} ${lapTime(driver.median)} · P25–P75 ${lapTime(driver.q1)} – ${lapTime(driver.q3)}`}
                  </title>
                  <polygon
                    points={[...right, ...left].join(" ")}
                    className="violin"
                    style={
                      {
                        "--light": LIGHT_SERIES[index % LIGHT_SERIES.length],
                        "--dark": DARK_SERIES[index % DARK_SERIES.length],
                      } as CSSProperties
                    }
                    fillOpacity={0.55}
                    strokeWidth={1}
                  />
                  <line x1={cx} x2={cx} y1={y(driver.whiskerHigh)} y2={y(driver.whiskerLow)} className="stroke-ink" strokeWidth={1} />
                  <rect x={cx - 4} width={8} y={y(driver.q3)} height={Math.max(1, y(driver.q1) - y(driver.q3))} className="fill-ink" />
                  <circle cx={cx} cy={y(driver.median)} r={2.5} className="fill-surface" />
                  <text x={cx} y={HEIGHT - MARGIN.bottom + 16} textAnchor="middle" className="fill-ink font-mono text-[10px]">
                    {driver.code}
                  </text>
                </g>
              );
            })}
          </svg>
        )}
      </div>
      <fieldset className="grid content-start gap-2 text-sm">
        <legend className="mb-1 font-semibold">{labels.drivers}</legend>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setSelected(new Set(drivers.map((d) => d.id)))}
            className="rounded border border-line px-2 py-1 hover:bg-surface-2"
          >
            {labels.all}
          </button>
          <button
            type="button"
            onClick={() => setSelected(new Set())}
            className="rounded border border-line px-2 py-1 hover:bg-surface-2"
          >
            {labels.none}
          </button>
        </div>
        <ul className="grid max-h-[22rem] gap-1 overflow-y-auto pr-1" aria-label={labels.drivers}>
          {drivers.map((driver) => (
            <li key={driver.id}>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={selected.has(driver.id)} onChange={() => toggle(driver.id)} />
                <span
                  aria-hidden="true"
                  className="violin inline-block h-3 w-3 rounded-full"
                  style={
                    {
                      "--light": LIGHT_SERIES[driver.colorIndex % LIGHT_SERIES.length],
                      "--dark": DARK_SERIES[driver.colorIndex % DARK_SERIES.length],
                    } as CSSProperties
                  }
                />
                {driver.name}
              </label>
            </li>
          ))}
        </ul>
      </fieldset>
    </div>
  );
}

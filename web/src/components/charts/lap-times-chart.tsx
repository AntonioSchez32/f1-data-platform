"use client";

import { useCallback, useId, useMemo, useState } from "react";

import { lapTime } from "@/lib/format";

import { axisStyle, baseOption, type ChartTheme, DARK_SERIES, EChart, LIGHT_SERIES, seriesStyle, tooltipStyle } from "./echart";

export type LapTimesDriver = {
  id: string;
  name: string;
  /** Tiempo de cada vuelta en ms (índice = vuelta - 1). */
  times: (number | null)[];
  /** Vueltas no representativas: boxes, Safety Car, VSC o bandera roja. */
  neutralized: number[];
};

type Labels = {
  title: string;
  lap: string;
  time: string;
  drivers: string;
  all: string;
  none: string;
  hideNeutralized: string;
};

/**
 * Tiempos por vuelta de cada piloto (página «Ritmo de carrera» del TFG): selección de pilotos con
 * casillas, zoom por vueltas y opción de ocultar las vueltas de boxes y neutralizadas.
 */
export function LapTimesChart({
  drivers,
  labels,
  hideNeutralizedByDefault = false,
}: {
  drivers: LapTimesDriver[];
  labels: Labels;
  /** Empezar ocultando las vueltas neutralizadas (cuando hay alguna tan lenta que aplana el resto). */
  hideNeutralizedByDefault?: boolean;
}) {
  const [selected, setSelected] = useState(() => new Set(drivers.map((d) => d.id)));
  const [hideNeutralized, setHideNeutralized] = useState(hideNeutralizedByDefault);
  const groupId = useId();
  const laps = Math.max(...drivers.map((d) => d.times.length));
  const visible = useMemo(() => drivers.filter((d) => selected.has(d.id)), [drivers, selected]);

  const toggle = (id: string) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const build = useCallback(
    (theme: ChartTheme) => ({
      ...baseOption(theme),
      grid: { left: 64, right: 48, top: 16, bottom: 88 },
      tooltip: {
        ...tooltipStyle(theme),
        trigger: "axis",
        order: "valueAsc",
        valueFormatter: (v: number | null) => (v === null ? "—" : lapTime(v)),
      },
      xAxis: {
        type: "category",
        data: Array.from({ length: laps }, (_, i) => String(i + 1)),
        name: labels.lap,
        nameLocation: "middle",
        nameGap: 28,
        boundaryGap: false,
        ...axisStyle(theme),
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        scale: true,
        name: labels.time,
        ...axisStyle(theme),
        axisLabel: { ...axisStyle(theme).axisLabel, formatter: (v: number) => lapTime(v) },
      },
      // Como en el TFG: una barra para acotar las vueltas y otra para el rango de tiempos.
      dataZoom: [
        { type: "slider", xAxisIndex: 0, bottom: 12, height: 22, textStyle: { color: theme.muted } },
        {
          type: "slider",
          yAxisIndex: 0,
          right: 8,
          width: 18,
          filterMode: "none",
          labelFormatter: (v: number) => lapTime(v),
          textStyle: { color: theme.muted },
        },
        { type: "inside", xAxisIndex: 0 },
      ],
      series: visible.map((driver) => {
        const style = seriesStyle(theme, drivers.indexOf(driver));
        const skip = new Set(driver.neutralized);
        return {
          type: "line",
          name: driver.name,
          data: driver.times.map((t, i) => (hideNeutralized && skip.has(i + 1) ? null : t)),
          color: style.color,
          showSymbol: false,
          connectNulls: false,
          lineStyle: { width: 1.6, type: style.lineType },
          emphasis: { focus: "series", lineStyle: { width: 3 } },
        };
      }),
    }),
    [drivers, visible, hideNeutralized, laps, labels],
  );

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_15rem]">
      <div className="min-w-0">
        <EChart build={build} label={labels.title} height={460} />
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
        <label className="flex items-center gap-2 border-b border-line pb-2">
          <input
            type="checkbox"
            checked={hideNeutralized}
            onChange={(e) => setHideNeutralized(e.target.checked)}
          />
          {labels.hideNeutralized}
        </label>
        <ul className="grid max-h-[22rem] gap-1 overflow-y-auto pr-1" aria-label={labels.drivers}>
          {drivers.map((driver, i) => (
            <li key={driver.id}>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id={`${groupId}-${driver.id}`}
                  checked={selected.has(driver.id)}
                  onChange={() => toggle(driver.id)}
                />
                <DriverSwatch index={i} />
                {driver.name}
              </label>
            </li>
          ))}
        </ul>
      </fieldset>
    </div>
  );
}

/** Muestra del color y tipo de línea del piloto (mismo orden que las series). */
function DriverSwatch({ index }: { index: number }) {
  const n = LIGHT_SERIES.length;
  const style = { borderTopStyle: ["solid", "dashed", "dotted"][Math.floor(index / n) % 3] as "solid" };
  return (
    <>
      <span
        aria-hidden="true"
        className="inline-block w-5 border-t-[3px] dark:hidden"
        style={{ ...style, borderTopColor: LIGHT_SERIES[index % n] }}
      />
      <span
        aria-hidden="true"
        className="hidden w-5 border-t-[3px] dark:inline-block"
        style={{ ...style, borderTopColor: DARK_SERIES[index % n] }}
      />
    </>
  );
}

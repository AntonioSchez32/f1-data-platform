"use client";

import { useCallback } from "react";

import { axisStyle, baseOption, type ChartTheme, EChart, seriesStyle, tooltipStyle } from "./echart";

export type LapChartDriver = {
  id: string;
  name: string;
  code: string;
  /** Posición al final de cada vuelta; el índice 0 es la parrilla de salida. */
  positions: (number | null)[];
};

/** Gráfico de posiciones vuelta a vuelta (bump chart). Etiqueta directa al final de cada línea. */
export function LapChart({
  drivers,
  label,
  lapLabel,
  gridLabel,
}: {
  drivers: LapChartDriver[];
  label: string;
  lapLabel: string;
  gridLabel: string;
}) {
  const build = useCallback(
    (theme: ChartTheme) => {
      const laps = Math.max(...drivers.map((d) => d.positions.length)) - 1;
      const size = Math.max(...drivers.flatMap((d) => d.positions.map((p) => p ?? 0)), drivers.length);
      return {
        ...baseOption(theme),
        grid: { left: 40, right: 56, top: 16, bottom: 48 },
        tooltip: {
          ...tooltipStyle(theme),
          trigger: "item",
          formatter: (p: { seriesName: string; dataIndex: number; value: number }) =>
            `${p.seriesName}<br/>${p.dataIndex === 0 ? gridLabel : `${lapLabel} ${p.dataIndex}`}: P${p.value}`,
        },
        xAxis: {
          type: "category",
          data: Array.from({ length: laps + 1 }, (_, i) => (i === 0 ? gridLabel : String(i))),
          name: lapLabel,
          nameLocation: "middle",
          nameGap: 30,
          boundaryGap: false,
          ...axisStyle(theme),
          splitLine: { show: false },
        },
        yAxis: {
          type: "value",
          inverse: true,
          min: 1,
          max: size,
          interval: 1,
          ...axisStyle(theme),
        },
        series: drivers.map((driver, i) => {
          const style = seriesStyle(theme, i);
          return {
            type: "line",
            name: driver.name,
            data: driver.positions,
            color: style.color,
            showSymbol: false,
            connectNulls: false,
            lineStyle: { width: 2, type: style.lineType },
            emphasis: { focus: "series", lineStyle: { width: 4 } },
            blur: { lineStyle: { opacity: 0.15 } },
            endLabel: {
              show: true,
              formatter: driver.code,
              color: theme.ink,
              fontFamily: theme.mono,
              fontSize: 11,
            },
          };
        }),
      };
    },
    [drivers, lapLabel, gridLabel],
  );
  return <EChart build={build} label={label} height={Math.max(420, drivers.length * 26)} />;
}

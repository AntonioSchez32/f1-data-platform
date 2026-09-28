"use client";

import { useCallback } from "react";

import { compoundStyle } from "@/lib/tyres";

import { axisStyle, baseOption, type ChartTheme, EChart, tooltipStyle } from "./echart";

export type StintRow = {
  driverId: string;
  name: string;
  stints: { stint: number; compound: string | null; label: string; start: number; end: number; laps: number }[];
};

/** Estrategia de neumáticos: una barra por piloto dividida en tramos (color + letra del compuesto). */
export function StintChart({
  rows,
  label,
  lapLabel,
  stintLabel,
}: {
  rows: StintRow[];
  label: string;
  lapLabel: string;
  stintLabel: string;
}) {
  const build = useCallback(
    (theme: ChartTheme) => {
      const maxStints = Math.max(...rows.map((r) => r.stints.length));
      return {
        ...baseOption(theme),
        grid: { left: 150, right: 24, top: 8, bottom: 40 },
        tooltip: {
          ...tooltipStyle(theme),
          trigger: "item",
          formatter: (p: { dataIndex: number; seriesIndex: number }) => {
            const row = rows[p.dataIndex];
            const stint = row.stints[p.seriesIndex];
            return `${row.name}<br/>${stintLabel} ${stint.stint}: ${stint.label}<br/>${lapLabel} ${stint.start}–${stint.end} (${stint.laps})`;
          },
        },
        xAxis: { type: "value", name: lapLabel, nameLocation: "middle", nameGap: 26, ...axisStyle(theme) },
        yAxis: {
          type: "category",
          inverse: true,
          data: rows.map((r) => r.name),
          axisLabel: { color: theme.ink, fontFamily: theme.sans },
          axisLine: { lineStyle: { color: theme.line } },
          axisTick: { show: false },
        },
        series: Array.from({ length: maxStints }, (_, k) => ({
          type: "bar",
          stack: "stints",
          barWidth: "62%",
          data: rows.map((row) => {
            const stint = row.stints[k];
            if (!stint) return null;
            const style = compoundStyle(stint.compound);
            return {
              value: stint.laps,
              // El duro es casi blanco: lleva contorno para verse sobre fondo claro.
              itemStyle: {
                color: style.color,
                borderColor: style.letter === "H" ? theme.muted : theme.surface,
                borderWidth: style.letter === "H" ? 1 : 1.5,
              },
              label: {
                show: stint.laps >= 3,
                formatter: style.letter,
                color: style.text,
                fontWeight: 600,
                fontFamily: theme.mono,
              },
            };
          }),
        })),
      };
    },
    [rows, lapLabel, stintLabel],
  );
  return <EChart build={build} label={label} height={Math.max(260, rows.length * 28 + 60)} />;
}

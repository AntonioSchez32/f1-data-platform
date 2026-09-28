"use client";

import { useCallback } from "react";

import { axisStyle, baseOption, type ChartTheme, EChart, seriesStyle, tooltipStyle } from "./echart";

export type ProgressionRow = {
  round: number;
  grand_prix_name: string;
  id: string;
  name: string;
  points: number;
};

/** Puntos acumulados por ronda; cada línea lleva su nombre al final (sin depender de la leyenda). */
export function ProgressionChart({
  rows,
  label,
  roundLabel,
  pointsLabel,
}: {
  rows: ProgressionRow[];
  label: string;
  roundLabel: string;
  pointsLabel: string;
}) {
  const build = useCallback(
    (theme: ChartTheme) => {
      const rounds = [...new Set(rows.map((r) => r.round))].sort((a, b) => a - b);
      const gpByRound = new Map(rows.map((r) => [r.round, r.grand_prix_name]));
      const ids = [...new Set(rows.map((r) => r.id))];
      return {
        ...baseOption(theme),
        grid: { left: 48, right: 150, top: 16, bottom: 40 },
        tooltip: { ...tooltipStyle(theme), trigger: "axis", order: "valueDesc" },
        xAxis: {
          type: "category",
          data: rounds.map(String),
          name: roundLabel,
          nameLocation: "middle",
          nameGap: 28,
          axisLabel: { ...axisStyle(theme).axisLabel },
          axisLine: axisStyle(theme).axisLine,
          axisPointer: {
            label: { formatter: ({ value }: { value: string }) => `${roundLabel} ${value} · ${gpByRound.get(Number(value))}` },
          },
        },
        yAxis: { type: "value", name: pointsLabel, ...axisStyle(theme) },
        series: ids.map((id, i) => {
          const style = seriesStyle(theme, i);
          const points = new Map(rows.filter((r) => r.id === id).map((r) => [r.round, r.points]));
          const name = rows.find((r) => r.id === id)!.name;
          return {
            type: "line",
            name,
            data: rounds.map((round) => points.get(round) ?? null),
            color: style.color,
            symbol: style.symbol,
            symbolSize: 6,
            lineStyle: { width: 2, type: style.lineType },
            emphasis: { focus: "series" },
            endLabel: { show: true, formatter: "{a}", color: theme.ink, fontFamily: theme.sans },
            labelLayout: { moveOverlap: "shiftY" },
          };
        }),
      };
    },
    [rows, roundLabel, pointsLabel],
  );
  return <EChart build={build} label={label} height={460} />;
}

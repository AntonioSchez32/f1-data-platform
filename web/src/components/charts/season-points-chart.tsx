"use client";

import { useCallback } from "react";

import { axisStyle, baseOption, type ChartTheme, EChart, tooltipStyle } from "./echart";

export type SeasonPoints = { season: number; points: number; position: string | null; champion: boolean };

/** Puntos por temporada; las temporadas con título, en morado y con la posición final encima. */
export function SeasonPointsChart({
  rows,
  label,
  pointsLabel,
}: {
  rows: SeasonPoints[];
  label: string;
  pointsLabel: string;
}) {
  const build = useCallback(
    (theme: ChartTheme) => ({
      ...baseOption(theme),
      grid: { left: 48, right: 16, top: 28, bottom: 32 },
      tooltip: {
        ...tooltipStyle(theme),
        trigger: "item",
        formatter: (p: { dataIndex: number }) => {
          const row = rows[p.dataIndex];
          return `${row.season}: ${row.points} ${pointsLabel}${row.position ? ` · ${/^\d+$/.test(row.position) ? `P${row.position}` : row.position}` : ""}`;
        },
      },
      xAxis: { type: "category", data: rows.map((r) => String(r.season)), ...axisStyle(theme), splitLine: { show: false } },
      yAxis: { type: "value", name: pointsLabel, ...axisStyle(theme) },
      series: [
        {
          type: "bar",
          data: rows.map((r) => ({
            value: r.points,
            itemStyle: { color: r.champion ? theme.purple : theme.series[0] },
            label: {
              show: rows.length <= 25,
              position: "top",
              formatter: !r.position ? "" : /^\d+$/.test(r.position) ? `P${r.position}` : r.position,
              color: theme.muted,
              fontFamily: theme.mono,
              fontSize: 10,
            },
          })),
          barMaxWidth: 36,
        },
      ],
    }),
    [rows, pointsLabel],
  );
  return <EChart build={build} label={label} height={300} />;
}

"use client";

import { useCallback } from "react";

import { axisStyle, baseOption, EChart, tooltipStyle, type ChartTheme } from "./echart";

export type TeammateSeason = {
  season: number;
  points: number;
  teammatePoints: number;
  raceShare: number | null;
  qualiShare: number | null;
};

/** Puntos del piloto frente a los de sus compañeros, por temporada (barras agrupadas). */
export function TeammatePointsChart({
  rows,
  label,
  driverLabel,
  teammateLabel,
}: {
  rows: TeammateSeason[];
  label: string;
  driverLabel: string;
  teammateLabel: string;
}) {
  const build = useCallback(
    (theme: ChartTheme) => ({
      ...baseOption(theme),
      legend: { top: 0, left: 0, textStyle: { color: theme.ink } },
      grid: { left: 48, right: 16, top: 36, bottom: 32 },
      tooltip: { ...tooltipStyle(theme), trigger: "axis" },
      xAxis: { type: "category", data: rows.map((r) => String(r.season)), ...axisStyle(theme), splitLine: { show: false } },
      yAxis: { type: "value", ...axisStyle(theme) },
      series: [
        { name: driverLabel, type: "bar", data: rows.map((r) => r.points), color: theme.series[5], barMaxWidth: 18 },
        {
          name: teammateLabel,
          type: "bar",
          data: rows.map((r) => r.teammatePoints),
          color: theme.series[0],
          barMaxWidth: 18,
          // Trama diagonal: la serie se distingue también sin color.
          itemStyle: { decal: { symbol: "rect", dashArrayX: [1, 0], dashArrayY: [2, 4], rotation: Math.PI / 4, color: "rgba(255,255,255,0.35)" } },
        },
      ],
    }),
    [rows, driverLabel, teammateLabel],
  );
  return <EChart build={build} label={label} height={300} />;
}

/** Porcentaje de veces por delante del compañero (barras apiladas al 100 %). */
export function TeammateShareChart({
  rows,
  field,
  label,
  driverLabel,
  teammateLabel,
}: {
  rows: TeammateSeason[];
  field: "raceShare" | "qualiShare";
  label: string;
  driverLabel: string;
  teammateLabel: string;
}) {
  const build = useCallback(
    (theme: ChartTheme) => {
      const share = rows.map((r) => r[field]);
      return {
        ...baseOption(theme),
        legend: { top: 0, left: 0, textStyle: { color: theme.ink } },
        grid: { left: 48, right: 16, top: 36, bottom: 32 },
        tooltip: {
          ...tooltipStyle(theme),
          trigger: "axis",
          valueFormatter: (v: number | null) => (v === null ? "—" : `${v.toFixed(1)} %`),
        },
        xAxis: { type: "category", data: rows.map((r) => String(r.season)), ...axisStyle(theme), splitLine: { show: false } },
        yAxis: {
          type: "value",
          max: 100,
          ...axisStyle(theme),
          axisLabel: { ...axisStyle(theme).axisLabel, formatter: "{value} %" },
        },
        series: [
          {
            name: driverLabel,
            type: "bar",
            stack: "share",
            data: share.map((v) => (v === null ? null : v)),
            color: theme.series[5],
            barMaxWidth: 22,
          },
          {
            name: teammateLabel,
            type: "bar",
            stack: "share",
            data: share.map((v) => (v === null ? null : 100 - v)),
            color: theme.series[0],
            barMaxWidth: 22,
            itemStyle: { decal: { symbol: "rect", dashArrayX: [1, 0], dashArrayY: [2, 4], rotation: Math.PI / 4, color: "rgba(255,255,255,0.35)" } },
          },
        ],
      };
    },
    [rows, field, driverLabel, teammateLabel],
  );
  return <EChart build={build} label={label} height={280} />;
}

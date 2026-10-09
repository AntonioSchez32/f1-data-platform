"use client";

import { useCallback } from "react";

import { axisStyle, baseOption, EChart, tooltipStyle, type ChartTheme } from "./echart";

/** Trama diagonal: la serie del compañero se distingue también sin color. */
const DECAL = { symbol: "rect", dashArrayX: [1, 0], dashArrayY: [2, 4], rotation: Math.PI / 4, color: "rgba(255,255,255,0.35)" };

export type TeammateSeason = {
  season: number;
  points: number;
  teammatePoints: number;
  raceShare: number | null;
  qualiShare: number | null;
};

/**
 * Puntos del piloto frente a los del mejor compañero de cada carrera, sumados por temporada
 * (barras agrupadas, decisión 45).
 */
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
          itemStyle: { decal: DECAL },
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
            itemStyle: { decal: DECAL },
          },
        ],
      };
    },
    [rows, field, driverLabel, teammateLabel],
  );
  return <EChart build={build} label={label} height={280} />;
}

export type TeammateCumulativeRow = {
  label: string;
  race: string;
  points: number;
  teammatePoints: number;
};

/**
 * Puntos acumulados carrera a carrera del piloto y del mejor compañero de cada carrera (decisión
 * 45). Las dos líneas se distinguen sin color: continua con círculos frente a discontinua con
 * cuadrados, también en la leyenda.
 */
export function TeammateCumulativeChart({
  rows,
  label,
  driverLabel,
  teammateLabel,
}: {
  rows: TeammateCumulativeRow[];
  label: string;
  driverLabel: string;
  teammateLabel: string;
}) {
  const build = useCallback(
    (theme: ChartTheme) => {
      const line = (name: string, data: number[], color: string, type: "solid" | "dashed", symbol: string) => ({
        type: "line",
        name,
        data,
        color,
        symbol,
        symbolSize: 5,
        showAllSymbol: "auto",
        lineStyle: { width: 2, type },
      });
      return {
        ...baseOption(theme),
        legend: { top: 0, left: 0, textStyle: { color: theme.ink } },
        grid: { left: 48, right: 16, top: 36, bottom: 32 },
        tooltip: { ...tooltipStyle(theme), trigger: "axis" },
        xAxis: {
          type: "category",
          data: rows.map((r) => r.label),
          ...axisStyle(theme),
          splitLine: { show: false },
          axisPointer: {
            label: { formatter: ({ value }: { value: string }) => `${value} · ${rows.find((r) => r.label === value)?.race ?? ""}` },
          },
        },
        yAxis: { type: "value", ...axisStyle(theme) },
        series: [
          line(driverLabel, rows.map((r) => r.points), theme.series[5], "solid", "circle"),
          line(teammateLabel, rows.map((r) => r.teammatePoints), theme.series[0], "dashed", "rect"),
        ],
      };
    },
    [rows, driverLabel, teammateLabel],
  );
  return <EChart build={build} label={label} height={360} />;
}

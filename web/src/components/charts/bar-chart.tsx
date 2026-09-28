"use client";

import { useCallback } from "react";

import { axisStyle, baseOption, EChart, tooltipStyle, type ChartTheme } from "./echart";

export type BarItem = { label: string; value: number; highlight?: boolean };

/**
 * Gráfico de barras sencillo (horizontal o vertical) con el valor escrito en cada barra.
 * `highlight` marca en morado lo mejor (como en cronometraje); el resto va en el color principal.
 */
export function BarChart({
  items,
  label,
  valueLabel,
  unit = "",
  decimals = 0,
  horizontal = false,
  height,
}: {
  items: BarItem[];
  label: string;
  valueLabel: string;
  unit?: string;
  decimals?: number;
  horizontal?: boolean;
  height?: number;
}) {
  const build = useCallback(
    (theme: ChartTheme) => {
      const format = (v: number) => `${v.toLocaleString(document.documentElement.lang, { maximumFractionDigits: decimals, minimumFractionDigits: decimals })}${unit}`;
      const categories = {
        type: "category",
        data: items.map((i) => i.label),
        inverse: horizontal,
        axisLabel: horizontal
          ? { color: theme.ink, fontFamily: theme.sans }
          : { color: theme.ink, fontFamily: theme.sans, interval: 0, rotate: items.length > 12 ? 40 : 0 },
        axisLine: { lineStyle: { color: theme.line } },
        axisTick: { show: false },
      };
      const values = { type: "value", name: valueLabel, ...axisStyle(theme) };
      return {
        ...baseOption(theme),
        grid: horizontal
          ? { left: 150, right: 48, top: 8, bottom: 32 }
          : { left: 56, right: 16, top: 28, bottom: items.length > 12 ? 96 : 48 },
        tooltip: { ...tooltipStyle(theme), trigger: "item", valueFormatter: format },
        xAxis: horizontal ? values : categories,
        yAxis: horizontal ? categories : values,
        series: [
          {
            type: "bar",
            barMaxWidth: 40,
            data: items.map((item) => ({
              value: item.value,
              itemStyle: { color: item.highlight ? theme.purple : theme.series[0] },
            })),
            label: {
              show: true,
              position: horizontal ? "right" : "top",
              formatter: ({ value }: { value: number }) => format(value),
              color: theme.muted,
              fontFamily: theme.mono,
              fontSize: 11,
            },
          },
        ],
      };
    },
    [items, valueLabel, unit, decimals, horizontal],
  );
  return (
    <EChart
      build={build}
      label={label}
      height={height ?? (horizontal ? Math.max(220, items.length * 26 + 50) : 380)}
    />
  );
}

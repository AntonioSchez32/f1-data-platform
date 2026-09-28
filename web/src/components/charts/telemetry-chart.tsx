"use client";

import { useCallback } from "react";

import { axisStyle, baseOption, type ChartTheme, EChart, seriesStyle, tooltipStyle } from "./echart";

export type TelemetryTrace = {
  name: string;
  distance: number[];
  speed: (number | null)[];
  throttle: (number | null)[];
  brake: (boolean | null)[];
  x: (number | null)[];
  y: (number | null)[];
};

type Labels = { speed: string; throttle: string; brake: string; distance: string };

/** Velocidad, acelerador y freno frente a la distancia, en tres paneles con el eje X compartido. */
export function TelemetryChart({ traces, label, labels }: { traces: TelemetryTrace[]; label: string; labels: Labels }) {
  const build = useCallback(
    (theme: ChartTheme) => {
      const panels = [
        { top: 16, height: "44%", name: `${labels.speed} (km/h)` },
        { top: "58%", height: "17%", name: `${labels.throttle} (%)` },
        { top: "81%", height: "9%", name: labels.brake },
      ];
      const axis = axisStyle(theme);
      return {
        ...baseOption(theme),
        tooltip: { ...tooltipStyle(theme), trigger: "axis", axisPointer: { type: "line" } },
        axisPointer: { link: [{ xAxisIndex: "all" }] },
        legend: { top: 0, right: 0, textStyle: { color: theme.ink } },
        grid: panels.map((p) => ({ left: 64, right: 16, top: p.top, height: p.height })),
        xAxis: panels.map((_, i) => ({
          type: "value",
          gridIndex: i,
          min: 0,
          max: Math.max(...traces.map((t) => t.distance[t.distance.length - 1] ?? 0)),
          ...axis,
          axisLabel: { ...axis.axisLabel, show: i === panels.length - 1, formatter: "{value} m" },
          name: i === panels.length - 1 ? labels.distance : undefined,
          nameLocation: "middle",
          nameGap: 26,
        })),
        yAxis: panels.map((p, i) => ({
          type: "value",
          gridIndex: i,
          ...axis,
          name: p.name,
          nameTextStyle: { color: theme.muted, align: "left" },
          ...(i === 2 ? { min: 0, max: 1, axisLabel: { show: false }, splitLine: { show: false } } : {}),
          ...(i === 1 ? { min: 0, max: 100 } : {}),
        })),
        series: traces.flatMap((trace, i) => {
          const style = seriesStyle(theme, i);
          const common = { name: trace.name, color: style.color, showSymbol: false, lineStyle: { width: 1.6, type: style.lineType } };
          const pairs = <T,>(values: T[]) => trace.distance.map((d, j) => [d, values[j]]);
          return [
            { ...common, type: "line", xAxisIndex: 0, yAxisIndex: 0, data: pairs(trace.speed) },
            { ...common, type: "line", xAxisIndex: 1, yAxisIndex: 1, data: pairs(trace.throttle) },
            {
              ...common,
              type: "line",
              step: "end",
              xAxisIndex: 2,
              yAxisIndex: 2,
              data: pairs(trace.brake.map((b) => (b ? 1 : 0))),
            },
          ];
        }),
      };
    },
    [traces, labels],
  );
  return <EChart build={build} label={label} height={520} />;
}

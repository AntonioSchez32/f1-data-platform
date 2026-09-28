"use client";

import { BarChart, BoxplotChart, LineChart, ScatterChart } from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import * as echarts from "echarts/core";
import { SVGRenderer } from "echarts/renderers";
import { useEffect, useRef, useState } from "react";

echarts.use([
  BarChart,
  BoxplotChart,
  LineChart,
  ScatterChart,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
  VisualMapComponent,
  SVGRenderer,
]);

export type EChartsOption = echarts.EChartsCoreOption;

export type ChartTheme = {
  ink: string;
  muted: string;
  line: string;
  surface: string;
  purple: string;
  green: string;
  red: string;
  mono: string;
  sans: string;
  dark: boolean;
  /** Paleta Okabe-Ito (segura para daltonismo), ajustada a claro/oscuro. */
  series: string[];
};

export const LIGHT_SERIES = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#6B4C9A", "#8C6D31"];
export const DARK_SERIES = ["#56B4E9", "#FF8A3D", "#2ECC9A", "#E7A3CC", "#F5C04A", "#9ED8F5", "#B79CE0", "#D9B77A"];

function readTheme(): ChartTheme {
  const style = getComputedStyle(document.documentElement);
  const v = (name: string) => style.getPropertyValue(name).trim();
  const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  return {
    ink: v("--ink"),
    muted: v("--muted"),
    line: v("--line"),
    surface: v("--surface"),
    purple: v("--purple"),
    green: v("--green"),
    red: v("--red"),
    mono: `${v("--font-plex-mono")}, ui-monospace, monospace`,
    sans: `${v("--font-plex-sans")}, system-ui, sans-serif`,
    dark,
    series: dark ? DARK_SERIES : LIGHT_SERIES,
  };
}

/** Estilo de la serie i: color, tipo de línea y marcador, para no depender solo del color. */
export function seriesStyle(theme: ChartTheme, i: number) {
  const symbols = ["circle", "rect", "triangle", "diamond", "roundRect", "pin", "arrow"];
  const lineTypes = ["solid", "dashed", "dotted"] as const;
  return {
    color: theme.series[i % theme.series.length],
    lineType: lineTypes[Math.floor(i / theme.series.length) % lineTypes.length],
    symbol: symbols[i % symbols.length],
  };
}

/** Estilo del tooltip coherente con el tema. */
export function tooltipStyle(theme: ChartTheme) {
  return {
    backgroundColor: theme.surface,
    borderColor: theme.line,
    textStyle: { color: theme.ink, fontFamily: theme.sans },
    confine: true,
  };
}

/** Opciones comunes: tipografía y tooltip coherentes con el tema. */
export function baseOption(theme: ChartTheme) {
  return {
    textStyle: { fontFamily: theme.sans, color: theme.ink },
    tooltip: tooltipStyle(theme),
    aria: { enabled: false },
  };
}

export function axisStyle(theme: ChartTheme) {
  return {
    axisLine: { lineStyle: { color: theme.line } },
    axisTick: { lineStyle: { color: theme.line } },
    axisLabel: { color: theme.muted, fontFamily: theme.mono },
    splitLine: { lineStyle: { color: theme.line, opacity: 0.6 } },
    nameTextStyle: { color: theme.muted },
  };
}

/**
 * Contenedor de ECharts. `build` recibe el tema y devuelve las opciones; el gráfico se redibuja al
 * cambiar el tema del sistema. El contenedor es una imagen con descripción: los datos completos
 * están siempre en la tabla alternativa de ChartFigure.
 */
export function EChart({
  build,
  height = 420,
  label,
}: {
  build: (theme: ChartTheme) => EChartsOption;
  height?: number;
  label: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [themeVersion, setThemeVersion] = useState(0);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setThemeVersion((v) => v + 1);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, undefined, { renderer: "svg" });
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    chart.setOption({ ...build(readTheme()), animation: !reduceMotion });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [build, themeVersion]);

  return <div ref={ref} role="img" aria-label={label} style={{ height, width: "100%" }} />;
}

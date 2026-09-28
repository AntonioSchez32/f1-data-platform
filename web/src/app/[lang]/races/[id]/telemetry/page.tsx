import { ChartFigure } from "@/components/charts/chart-figure";
import { TelemetryChart, type TelemetryTrace } from "@/components/charts/telemetry-chart";
import { TrackMap } from "@/components/track-map";
import { DataTable, EmptyState, Section } from "@/components/ui";
import { apiGet, type Schemas } from "@/lib/api/client";
import { lapTime, number } from "@/lib/format";
import { getDictionary } from "@/lib/i18n";
import { getDriverNames, getRace } from "@/lib/race";
import { fill } from "@/lib/text";

export default async function TelemetryPage({
  params,
  searchParams,
}: PageProps<"/[lang]/races/[id]/telemetry">) {
  const { lang, id } = await params;
  const { locale, t } = await getDictionary(lang);
  const race = await getRace(id);
  if (race.season < 2024) {
    return (
      <Section title={t.race.telemetryTitle} id="telemetria">
        <EmptyState>{t.race.telemetryUnavailable}</EmptyState>
      </Section>
    );
  }

  const { results, names } = await getDriverNames(id);
  const query = await searchParams;
  const valid = (value: unknown) => (typeof value === "string" && names.has(value) ? value : undefined);
  const a = valid(query.a) ?? results[0]?.driver_id;
  const b = valid(query.b) ?? results.find((r) => r.driver_id !== a)?.driver_id;
  const laps = a && b ? await apiGet<Schemas["TelemetryLap"][]>(`/races/${id}/telemetry`, { drivers: `${a},${b}` }) : null;

  const traces: TelemetryTrace[] = (laps ?? []).map((lap) => ({
    name: names.get(lap.driver_id) ?? lap.driver_id,
    distance: lap.distance_m,
    speed: lap.speed_kmh,
    throttle: lap.throttle_pct,
    brake: lap.is_braking,
    x: lap.x,
    y: lap.y,
  }));
  const summary = (laps ?? []).map((lap) => {
    const speeds = lap.speed_kmh.filter((s): s is number => s !== null);
    const throttle = lap.throttle_pct.filter((v): v is number => v !== null);
    return {
      driverId: lap.driver_id,
      name: names.get(lap.driver_id) ?? lap.driver_id,
      time: lapTime(lap.lap_time_ms),
      top: Math.max(...speeds),
      min: Math.min(...speeds),
      fullThrottle: (100 * throttle.filter((v) => v >= 98).length) / Math.max(throttle.length, 1),
      compound: lap.tyre_compound,
    };
  });

  return (
    <Section title={t.race.telemetryTitle} id="telemetria" lede={t.race.telemetryLede}>
      <form className="flex flex-wrap items-end gap-3" aria-label={t.race.telemetryCompare}>
        {[
          { name: "a", label: t.race.telemetryDriverA, value: a },
          { name: "b", label: t.race.telemetryDriverB, value: b },
        ].map((field) => (
          <label key={field.name} className="grid gap-1 text-sm font-medium">
            {field.label}
            <select
              name={field.name}
              defaultValue={field.value}
              className="rounded-md border border-line bg-surface px-3 py-2"
            >
              {results.map((r) => (
                <option key={r.driver_id} value={r.driver_id}>
                  {r.driver_name}
                </option>
              ))}
            </select>
          </label>
        ))}
        <button type="submit" className="rounded-md bg-ink px-4 py-2 font-semibold text-surface">
          {t.race.telemetryCompare}
        </button>
      </form>

      {summary.length < 2 ? (
        <EmptyState>{t.common.noData}</EmptyState>
      ) : (
        <>
          <ChartFigure
            title={`${summary[0].name} · ${summary[1].name}`}
            summary={fill(t.race.telemetrySummary, {
              a: summary[0].name,
              timeA: summary[0].time,
              b: summary[1].name,
              timeB: summary[1].time,
              topA: number(summary[0].top, locale, 1),
              topB: number(summary[1].top, locale, 1),
            })}
            tableLabel={t.common.viewTable}
            table={
              <DataTable
                caption={t.race.telemetryTitle}
                rows={summary}
                rowKey={(s) => s.driverId}
                compact
                columns={[
                  { header: t.common.driver, rowHeader: true, cell: (s) => s.name },
                  { header: t.common.time, align: "right", className: "tabular", cell: (s) => s.time },
                  {
                    header: t.race.topSpeed,
                    align: "right",
                    className: "tabular",
                    cell: (s) => `${number(s.top, locale, 1)} km/h`,
                  },
                  {
                    header: t.race.minSpeed,
                    align: "right",
                    className: "tabular",
                    cell: (s) => `${number(s.min, locale, 1)} km/h`,
                  },
                  {
                    header: t.race.fullThrottle,
                    align: "right",
                    className: "tabular",
                    cell: (s) => `${number(s.fullThrottle, locale, 1)} %`,
                  },
                ]}
              />
            }
          >
            <TelemetryChart
              traces={traces}
              label={t.race.telemetryTitle}
              labels={{
                speed: t.race.speed,
                throttle: t.race.throttle,
                brake: t.race.brake,
                distance: t.race.distanceAxis,
              }}
            />
          </ChartFigure>
          <figure className="grid gap-3 rounded-lg border border-line bg-surface p-4">
            <figcaption className="font-display text-lg font-bold">
              {t.race.trackMap} · {summary[0].name}
            </figcaption>
            <TrackMap
              x={traces[0].x}
              y={traces[0].y}
              speed={traces[0].speed}
              title={`${t.race.trackMap} · ${summary[0].name}`}
              description={`${t.race.minSpeed}: ${number(summary[0].min, locale, 0)} km/h. ${t.race.topSpeed}: ${number(summary[0].top, locale, 0)} km/h.`}
              slowLabel={`${number(summary[0].min, locale, 0)} km/h`}
              fastLabel={`${number(summary[0].top, locale, 0)} km/h`}
            />
          </figure>
        </>
      )}
    </Section>
  );
}

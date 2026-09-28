/** Selector de temporada: formulario GET que redirige a /seasons/{año} (funciona sin JavaScript). */
export function SeasonPicker({
  action,
  seasons,
  current,
  label,
  buttonLabel,
}: {
  action: string;
  seasons: number[];
  current?: number;
  label: string;
  buttonLabel: string;
}) {
  return (
    <form action={action} className="flex items-end gap-2">
      <label className="grid gap-1 text-sm font-medium">
        {label}
        <select
          name="year"
          defaultValue={current}
          className="rounded-md border border-line bg-surface px-3 py-2 tabular"
        >
          {seasons.map((season) => (
            <option key={season} value={season}>
              {season}
            </option>
          ))}
        </select>
      </label>
      <button type="submit" className="rounded-md border border-line bg-surface px-4 py-2 font-semibold">
        {buttonLabel}
      </button>
    </form>
  );
}

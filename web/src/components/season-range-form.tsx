/** Rango de temporadas (desde/hasta) como formulario GET: funciona sin JavaScript. */
export function SeasonRangeForm({
  label,
  fromLabel,
  toLabel,
  applyLabel,
  min,
  max,
  from,
  to,
  hidden = {},
}: {
  label: string;
  fromLabel: string;
  toLabel: string;
  applyLabel: string;
  min: number;
  max: number;
  from: number;
  to: number;
  /** Parámetros que se conservan al aplicar (p. ej. la vista seleccionada). */
  hidden?: Record<string, string>;
}) {
  const input = "w-28 rounded-md border border-line bg-surface px-3 py-2 tabular";
  return (
    <form className="flex flex-wrap items-end gap-3" aria-label={label}>
      {Object.entries(hidden).map(([name, value]) => (
        <input key={name} type="hidden" name={name} value={value} />
      ))}
      <label className="grid gap-1 text-sm font-medium">
        {fromLabel}
        <input name="from" type="number" min={min} max={max} defaultValue={from} className={input} />
      </label>
      <label className="grid gap-1 text-sm font-medium">
        {toLabel}
        <input name="to" type="number" min={min} max={max} defaultValue={to} className={input} />
      </label>
      <button type="submit" className="rounded-md border border-line bg-surface px-4 py-2 font-semibold">
        {applyLabel}
      </button>
    </form>
  );
}

/** Lee un año de los parámetros de búsqueda dentro de [min, max]. */
export function parseYear(value: string | string[] | undefined, fallback: number, min: number, max: number) {
  const year = Number(Array.isArray(value) ? value[0] : value);
  return Number.isInteger(year) && year >= min && year <= max ? year : fallback;
}

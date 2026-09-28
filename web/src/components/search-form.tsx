/** Buscador por nombre: formulario GET normal, funciona sin JavaScript. */
export function SearchForm({
  action,
  label,
  placeholder,
  buttonLabel,
  defaultValue,
}: {
  action: string;
  label: string;
  placeholder?: string;
  buttonLabel: string;
  defaultValue?: string;
}) {
  return (
    <form action={action} role="search" className="flex max-w-md gap-2">
      <label htmlFor="q" className="sr-only">
        {label}
      </label>
      <input
        id="q"
        name="q"
        type="search"
        minLength={2}
        defaultValue={defaultValue}
        placeholder={placeholder}
        className="min-w-0 flex-1 rounded-md border border-line bg-surface px-3 py-2"
      />
      <button type="submit" className="rounded-md bg-ink px-4 py-2 font-semibold text-surface">
        {buttonLabel}
      </button>
    </form>
  );
}

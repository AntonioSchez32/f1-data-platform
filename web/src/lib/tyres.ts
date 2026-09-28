/** Colores oficiales de Pirelli y letra de cada compuesto (la letra evita depender solo del color). */
export const COMPOUNDS: Record<string, { color: string; text: string; letter: string }> = {
  SOFT: { color: "#DA291C", text: "#ffffff", letter: "S" },
  MEDIUM: { color: "#FFD12E", text: "#14161b", letter: "M" },
  HARD: { color: "#F0F0EC", text: "#14161b", letter: "H" },
  INTERMEDIATE: { color: "#43B02A", text: "#14161b", letter: "I" },
  WET: { color: "#0067AD", text: "#ffffff", letter: "W" },
  HYPERSOFT: { color: "#FFB3C3", text: "#14161b", letter: "HS" },
  ULTRASOFT: { color: "#8E44AD", text: "#ffffff", letter: "US" },
  SUPERSOFT: { color: "#E53935", text: "#ffffff", letter: "SS" },
  SUPERHARD: { color: "#F39C12", text: "#14161b", letter: "SH" },
};

export const UNKNOWN_COMPOUND = { color: "#9AA0AE", text: "#14161b", letter: "?" };

export function compoundStyle(compound: string | null | undefined) {
  return (compound && COMPOUNDS[compound]) || UNKNOWN_COMPOUND;
}

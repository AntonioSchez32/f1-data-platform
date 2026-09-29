"""Convierte las notas Markdown de los agentes en capítulos LaTeX para el informe.

Uso: python md2tex.py notas/01_inventario_huecos.md capitulos/01_inventario_huecos.tex
Soporta lo que usan las notas: títulos, párrafos, listas anidadas, tablas GFM, bloques de
código, citas, reglas horizontales y el marcado en línea habitual (negrita, cursiva, código,
enlaces y URL sueltas).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SIMBOLOS = {
    "✅": r"\si{}",
    "✓": r"\si{}",
    "❌": r"\no{}",
    "✗": r"\no{}",
    "✕": r"\no{}",
    "🟡": r"\parcial{}",
    "⚪": r"\nada{}",
    "⟕": " LEFT JOIN ",
    "⋈": " JOIN ",
    "‑": "-",
    "−": "\u2212",
}

ESPECIALES = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "$": r"\$",
    "&": r"\&",
    "%": r"\%",
    "#": r"\#",
    "_": r"\_",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def escapar(texto: str) -> str:
    salida = "".join(ESPECIALES.get(c, c) for c in texto)
    for simbolo, latex in SIMBOLOS.items():
        salida = salida.replace(simbolo, latex)
    return salida


def escapar_codigo(texto: str) -> str:
    """Escapa texto monoespaciado permitiendo cortes de línea tras separadores."""
    partes = []
    anterior = ""
    for c in texto:
        if c.isupper() and anterior.islower():
            partes.append(r"\allowbreak{}")
        anterior = c
        partes.append(ESPECIALES.get(c, c))
        if c in "/_.,-=:(":
            partes.append(r"\allowbreak{}")
    salida = "".join(partes)
    for simbolo, latex in SIMBOLOS.items():
        salida = salida.replace(simbolo, latex)
    return salida


def escapar_url(url: str) -> str:
    return (
        url.replace("\\", "/")
        .replace("%", r"\%")
        .replace("#", r"\#")
        .replace("{", "")
        .replace("}", "")
    )


TOKEN = re.compile(
    r"(?P<code>`+)(?P<codetxt>.+?)(?P=code)"
    r"|\[(?P<ltxt>[^\]]+)\]\((?P<lurl>[^)\s]+)\)"
    r"|(?P<url>https?://[^\s)<>|]+[^\s)<>|.,;:»\"'])"
    r"|\*\*(?P<bold>.+?)\*\*"
    r"|(?<![\w*])\*(?!\s)(?P<ital>[^*\n]+?)(?<!\s)\*(?![\w*])"
)


def en_linea(texto: str) -> str:
    salida = []
    pos = 0
    for m in TOKEN.finditer(texto):
        salida.append(escapar(texto[pos : m.start()]))
        if m.group("code"):
            salida.append(r"\code{" + escapar_codigo(m.group("codetxt").strip()) + "}")
        elif m.group("ltxt"):
            salida.append(
                r"\href{" + escapar_url(m.group("lurl")) + "}{" + en_linea(m.group("ltxt")) + "}"
            )
        elif m.group("url"):
            url = m.group("url")
            salida.append(
                r"\href{" + escapar_url(url) + r"}{\urltexto{" + escapar_codigo(url) + "}}"
            )
        elif m.group("bold"):
            salida.append(r"\textbf{" + en_linea(m.group("bold")) + "}")
        elif m.group("ital"):
            salida.append(r"\emph{" + en_linea(m.group("ital")) + "}")
        pos = m.end()
    salida.append(escapar(texto[pos:]))
    return "".join(salida)


NUM_TITULO = re.compile(r"^(\d+(\.\d+)*\.?|[A-Z]\d*\.)(\s*·)?\s+")


def titulo(nivel: int, texto: str, primer_nivel: int) -> str:
    texto = NUM_TITULO.sub("", texto.strip())
    comandos = ["chapter", "section", "subsection", "subsubsection", "paragraph", "subparagraph"]
    indice = min(max(nivel - primer_nivel, 0), len(comandos) - 1)
    comando = comandos[indice]
    cuerpo = en_linea(texto)
    corto = re.sub(r"\\(href|urltexto)\{[^}]*\}", "", cuerpo)
    if comando in ("chapter", "section", "subsection") and corto != cuerpo:
        return f"\\{comando}[{escapar(texto)}]{{{cuerpo}}}\n"
    return f"\\{comando}{{{cuerpo}}}\n"


FILA_TABLA = re.compile(r"^\s*\|")
SEPARADOR = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
ITEM = re.compile(r"^(?P<ind>\s*)(?P<marca>[-*+]|\d+[.)])\s+(?P<txt>.*)$")
TITULO = re.compile(r"^(?P<h>#{1,6})\s+(?P<txt>.+?)\s*#*\s*$")


def celdas(linea: str) -> list[str]:
    linea = linea.strip()
    if linea.startswith("|"):
        linea = linea[1:]
    if linea.endswith("|") and not linea.endswith("\\|"):
        linea = linea[:-1]
    partes, actual, en_codigo = [], [], False
    for c in linea:
        if c == "`":
            en_codigo = not en_codigo
        if c == "|" and not en_codigo:
            partes.append("".join(actual))
            actual = []
        else:
            actual.append(c)
    partes.append("".join(actual))
    return [p.strip().replace("\\|", "|") for p in partes]


def texto_plano(celda: str) -> str:
    celda = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", celda)
    return re.sub(r"[*`]", "", celda)


def tabla(lineas: list[str]) -> str:
    cabecera = celdas(lineas[0])
    filas = [celdas(fila) for fila in lineas[2:] if not SEPARADOR.match(fila)]
    n = len(cabecera)
    filas = [(f + [""] * n)[:n] for f in filas]
    largos = []
    for i in range(n):
        textos = [texto_plano(cabecera[i])] + [texto_plano(f[i]) for f in filas]
        largo_max = max(len(t) for t in textos)
        largo_palabra = max((len(w) for t in textos for w in t.split()), default=1)
        largos.append(max(min(largo_max, 60), largo_palabra * 0.9, 4) ** 0.85)
    total = sum(largos)
    tam = r"\small" if n <= 3 else r"\footnotesize" if n <= 5 else r"\scriptsize"
    sep = 4 if n > 5 else 5
    disponible = f"(\\linewidth-{2 * sep * n}pt)"
    alineacion = r">{\raggedright\arraybackslash}"
    columnas = "".join(
        f"{alineacion}p{{{largos[i] / total:.3f}\\dimexpr{disponible}\\relax}}" for i in range(n)
    )
    salida = [
        "{"
        + tam
        + r"\sloppy"
        + f"\\setlength{{\\tabcolsep}}{{{sep}pt}}\\renewcommand{{\\arraystretch}}{{1.15}}",
        f"\\begin{{longtable}}{{@{{}}{columnas}@{{}}}}",
        r"\toprule",
        " & ".join(r"\textbf{" + en_linea(c) + "}" for c in cabecera) + r" \\",
        r"\midrule\endhead",
        r"\bottomrule\endlastfoot",
    ]
    for f in filas:
        salida.append(" & ".join(en_linea(c) for c in f) + r" \\")
    salida.append(r"\end{longtable}}")
    return "\n".join(salida) + "\n"


def bloque_codigo(lenguaje: str, lineas: list[str]) -> str:
    cuerpo = "\n".join(linea.replace("\t", "    ") for linea in lineas)
    if lenguaje == "diagrama":
        return "\\begin{diagramatexto}\n" + cuerpo + "\n\\end{diagramatexto}\n"
    return "\\begin{codigo}\n" + cuerpo + "\n\\end{codigo}\n"


def lista(lineas: list[str]) -> str:
    """Convierte un bloque de líneas de lista (con continuaciones) en itemize/enumerate anidados."""
    items: list[tuple[int, bool, str]] = []
    for linea in lineas:
        m = ITEM.match(linea)
        if m:
            items.append(
                (len(m.group("ind").expandtabs(4)), m.group("marca")[0].isdigit(), m.group("txt"))
            )
        elif linea.strip() and items:
            ind, num, txt = items[-1]
            items[-1] = (ind, num, txt + " " + linea.strip())
    salida: list[str] = []
    pila: list[tuple[int, str]] = []
    for ind, num, txt in items:
        entorno = "enumerate" if num else "itemize"
        while pila and ind < pila[-1][0]:
            salida.append(f"\\end{{{pila.pop()[1]}}}")
        if not pila or ind > pila[-1][0]:
            if len(pila) >= 4:
                ind = pila[-1][0]
            else:
                salida.append(f"\\begin{{{entorno}}}")
                pila.append((ind, entorno))
        salida.append(r"\item " + en_linea(txt))
    while pila:
        salida.append(f"\\end{{{pila.pop()[1]}}}")
    return "\n".join(salida) + "\n"


def convertir(md: str, primer_nivel: int = 1, omitir_titulo: bool = False) -> str:
    lineas = md.replace("\r\n", "\n").split("\n")
    salida: list[str] = []
    i = 0
    visto_titulo = False
    while i < len(lineas):
        linea = lineas[i]
        if not linea.strip():
            i += 1
            continue
        fence = re.match(r"^\s*(```+|~~~+)\s*([\w-]*)", linea)
        if fence:
            marca, lenguaje = fence.group(1), fence.group(2).lower()
            j = i + 1
            cuerpo = []
            while j < len(lineas) and not lineas[j].strip().startswith(marca[:3]):
                cuerpo.append(lineas[j])
                j += 1
            salida.append(bloque_codigo(lenguaje, cuerpo))
            i = j + 1
            continue
        m = TITULO.match(linea)
        if m:
            nivel = len(m.group("h"))
            if nivel == primer_nivel and omitir_titulo and not visto_titulo:
                visto_titulo = True
            else:
                salida.append(titulo(nivel, m.group("txt"), primer_nivel))
            i += 1
            continue
        if FILA_TABLA.match(linea) and i + 1 < len(lineas) and SEPARADOR.match(lineas[i + 1]):
            j = i
            while j < len(lineas) and FILA_TABLA.match(lineas[j]):
                j += 1
            salida.append(tabla(lineas[i:j]))
            i = j
            continue
        if re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", linea):
            salida.append(
                "\\medskip\\noindent\\textcolor{muted!40}{\\rule{\\linewidth}{0.3pt}}\\medskip\n"
            )
            i += 1
            continue
        if linea.lstrip().startswith(">"):
            j = i
            cuerpo = []
            while j < len(lineas) and lineas[j].lstrip().startswith(">"):
                cuerpo.append(lineas[j].lstrip()[1:].lstrip())
                j += 1
            interior = convertir("\n".join(cuerpo), primer_nivel + 6)
            salida.append("\\begin{nota}\n" + interior + "\\end{nota}\n")
            i = j
            continue
        if ITEM.match(linea):
            j = i
            bloque = []
            while j < len(lineas):
                actual = lineas[j]
                if not actual.strip():
                    k = j + 1
                    while k < len(lineas) and not lineas[k].strip():
                        k += 1
                    if (
                        k < len(lineas)
                        and (ITEM.match(lineas[k]) or lineas[k].startswith("  "))
                        and not TITULO.match(lineas[k])
                    ):
                        j = k
                        continue
                    break
                if (
                    TITULO.match(actual)
                    or re.match(r"^\s*```", actual)
                    or (FILA_TABLA.match(actual) and not actual.startswith("  "))
                ):
                    break
                if (
                    not ITEM.match(actual)
                    and not actual.startswith((" ", "\t"))
                    and bloque
                    and not bloque[-1].strip()
                ):
                    break
                bloque.append(actual)
                j += 1
            salida.append(lista(bloque))
            i = j
            continue
        j = i
        parrafo = []
        while j < len(lineas) and lineas[j].strip():
            if j > i and (
                TITULO.match(lineas[j])
                or ITEM.match(lineas[j])
                or re.match(r"^\s*```", lineas[j])
                or FILA_TABLA.match(lineas[j])
                or lineas[j].lstrip().startswith(">")
            ):
                break
            parrafo.append(lineas[j].strip())
            j += 1
        texto = " ".join(parrafo)
        salida.append(en_linea(texto) + "\n")
        i = j
    return "\n".join(salida)


def main() -> None:
    origen, destino = Path(sys.argv[1]), Path(sys.argv[2])
    omitir = "--sin-titulo" in sys.argv
    tex = convertir(origen.read_text(encoding="utf-8"), primer_nivel=1, omitir_titulo=omitir)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        f"% Generado automáticamente desde {origen.as_posix()} con md2tex.py; no editar a mano.\n"
        + tex,
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

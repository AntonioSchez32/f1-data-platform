# Instrucciones comunes de la auditoría (02/10/2026)

AUDITORÍA del proyecto f1-data-platform (TFG). Eres un AUDITOR: solo lees, ejecutas pruebas y consultas. NO modifiques ficheros del proyecto; la ÚNICA escritura permitida es tu nota de auditoría en `docs/auditoria/notas/` (ruta indicada abajo). Sigue las normas de tu definición de agente (higiene de contexto incluida: salidas resumidas, nada de volcar ficheros enteros).

## Qué se audita
Lo hecho hasta hoy (02/10/2026) del PLAN ORIGINAL (fases 0-6, fichero `C:/Users/Antonio/.claude/plans/esta-carpeta-tiene-mi-kind-owl.md`, fuera del repo) y del PLAN DE ACCIÓN (`docs/informe_situacion/plan_accion.tex`, decisiones en `docs/informe_situacion/DECISIONES.md`, estado en `docs/informe_situacion/SIGUIENTES_PASOS.md`): tronco T1-T3, C1, C2 y D1. Lo pendiente (D2, D3, S1, C3, W1, W2, A1, F0) NO cuenta como fallo, salvo que algo hecho lo bloquee o lo complique.
- Las decisiones registradas no se reabren; pero sí puedes señalar si están MAL IMPLEMENTADAS, o como «observación» si ves un riesgo serio en una decisión.
- Datos: la base local construida por dbt es `data/gold/f1.duckdb` (ábrela en solo lectura con `.venv/Scripts/python.exe` + duckdb). La publicada (`data-latest`, release `data-2026-10-01-6.1`) puedes descargarla con `gh release download data-latest -p f1.duckdb -D <tu carpeta temporal>` desde PowerShell con el repo como directorio (si `gh` no está en el PATH de bash). No la guardes dentro del repo.
- Producción: API en la URL de Render del README (solo GET, sin carga: pocas peticiones) y web en Vercel.
- Restricciones: sin scraping de formula1db.com ni statsf1; sin sortear bloqueos; sin crear releases, commits ni lanzar workflows.

## Qué entregar
Escribe tu nota en Markdown, en español, con esta estructura (sé conciso; calidad antes que cantidad, máximo ~25 hallazgos):
1. **Alcance y método**: qué revisaste y qué comandos/consultas ejecutaste (con resultados resumidos).
2. **Bien hecho**: puntos fuertes concretos, con evidencia (fichero:línea o resultado).
3. **Hallazgos**: tabla con ID (prefijo de tu área), gravedad (crítica / alta / media / baja), título, evidencia reproducible (fichero:línea, comando o consulta y su resultado), impacto, propuesta de arreglo y bloque sugerido (uno existente del plan —D2, D3, S1, C3, W1, W2, A1, F0— o «nuevo bloque»). Marca con «(verificado)» los que hayas reproducido ejecutando algo y con «(lectura)» los deducidos solo leyendo código.
4. **Promesas del plan no cumplidas o desviadas** en tu área (qué decía el plan, qué hay).
5. **Dudas**: lo que no pudiste comprobar.
No inventes: si no tienes evidencia, va a «Dudas». Tu respuesta final para la sesión principal: 10 líneas como máximo con los hallazgos críticos/altos y la ruta de tu nota.

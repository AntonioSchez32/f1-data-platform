# Catálogo del informe de Power BI del TFG

Fecha: 09/10/2026. Decisión 38. Fuente: `Report/Layout` del `.pbix` final, «Trabajo de fin de grado -
Only F1 DB - Modificado.pbix» (08/12/2024), y las figuras 5.23–5.33 de la memoria. La paridad de
las cifras está en [`paridad_tfg.md`](paridad_tfg.md).

## Estructura

- **8 páginas y 80 objetos visuales.** Unos 35 son decoración repetida en cada página: logotipo,
  título «FORMULA 1 DASHBOARD», grupo de cabecera, botón de inicio y navegador de marcadores.
- **Marcadores:** cinco páginas tienen dos vistas que se alternan con un navegador de marcadores
  (Pilotos / Constructores, o dos gráficos). Por eso la memoria muestra 11 figuras y el plan
  original hablaba de «11 páginas».
- **Segmentaciones:** rango de temporadas (control deslizante, 1950–2024) en «El gran circo» y
  «Récords»; temporada (desplegable, 2024 por defecto) en «Temporadas»; año + Gran Premio
  (desplegable, Abu Dabi 2024 por defecto) en las cuatro páginas de carrera; piloto en «Ritmo en
  carrera».
- **Obtener detalle:** desde «Récords», clic derecho sobre un piloto abre «Detalle de rendimiento
  piloto» filtrado por él. Sin selección, la página muestra a Lewis Hamilton (filtro de página).
- **Objetos personalizados:** diagrama de violín (`violinPlot`) y dos de líneas (`linechart`,
  `multiLineChart`) que no se usan en ninguna página.
- Rutas de la web: https://f1-data-platform.vercel.app/es/… (también en `/en/`).

## Catálogo por página

### 1. El gran circo (Fig. 5.23), página de inicio

| Visual | Tipo | Qué muestra | Equivalente en la web |
|---|---|---|---|
| El gran circo por el mundo: eventos disputados por país | Mapa de burbujas (Bing) | Burbuja por país del circuito (latitud y longitud del circuito), tamaño = nº de carreras (`Eventos`) | `/` · mapa mundial (d3-geo) por país o por circuito, con rango de temporadas y tabla accesible |
| Filtro de temporadas | Segmentación de rango | 1950–2024 | `/` · selector «desde / hasta» |
| Navegador de páginas | `pageNavigator` | Menú lateral con las 8 páginas | Navegación general de la web |

### 2. Récords (Fig. 5.24 y 5.25), vistas PILOTOS y CONSTRUCTORES

| Visual | Tipo | Qué muestra | Equivalente en la web |
|---|---|---|---|
| Campeonatos mundiales por piloto | Barras horizontales agrupadas | Títulos por piloto (solo los que tienen ≥ 1) | `/records` (vista pilotos) · gráfico de títulos por piloto |
| Pilotos más laureados | Tabla | Nombre, país, carreras, victorias, podios, puntos; las 150 primeras filas | `/records` (vista pilotos) · tabla ordenable que añade poles, vueltas rápidas y títulos |
| Campeonatos mundiales por constructor | Barras horizontales | Títulos de constructores | `/records` (vista constructores) · títulos por constructor |
| Constructores más laureados | Tabla | Nombre, país, carreras, victorias, podios, vueltas rápidas. Agrupa por **nombre** (une los dos «Lotus» y los dos «ATS») | `/records` (vista constructores) · tabla por identificador (los dos Lotus por separado) |
| Filtro de temporadas | Segmentación de rango | Recalcula todo para el periodo elegido | `/records` · selector de rango |
| Navegador PILOTOS / CONSTRUCTORES | Marcadores | Cambia de vista | `/records` · conmutador de vista |

### 3. Temporadas (Fig. 5.26), vistas PILOTOS y CONSTRUCTORES

| Visual | Tipo | Qué muestra | Equivalente en la web |
|---|---|---|---|
| Campeonato de pilotos | Tarjeta de varias filas | Los 3 primeros: nombre, posición y puntos | `/seasons/[year]` · tabla completa de la clasificación de pilotos |
| Piloto campeón | Tarjeta | Nombre del campeón | `/seasons/[year]` · tarjeta «Piloto campeón del mundo» |
| Equipo piloto | Tarjeta | Equipo del campeón en la última carrera (vacío en 1961, 1970 y 1977) | Parcial: `/seasons/[year]` muestra el equipo campeón; los equipos del campeón salen en `/drivers/[id]` |
| Victorias piloto | Tarjeta | Victorias del campeón en el año | `/seasons/[year]` · tarjeta de victorias del campeón |
| Campeonato de constructores | Tarjeta de varias filas | Los 3 primeros constructores con posición y puntos | `/seasons/[year]` · tabla de constructores (con motor y victorias) |
| Equipo campeón | Tarjeta | Campeón de constructores | `/seasons/[year]` · tarjeta «Equipo campeón del mundo» |
| Motorista campeón | Tarjeta | Motor del campeón de constructores | Parcial: columna de motor en la tabla de constructores, sin tarjeta propia |
| Victorias equipo | Tarjeta | Victorias del campeón de constructores | Parcial: columna de victorias en la tabla de constructores |
| Pilotos equipo campeón | Tarjeta (texto concatenado) | Pilotos del campeón de constructores ese año | No existe en `/seasons/[year]`; sí en `/constructors/[id]` (pilotos por temporada) |
| Filtro temporada | Desplegable | Año | `/seasons` (índice por décadas) y selector en `/seasons/[year]` |

### 4. Rendimiento en clasificación (Fig. 5.27), vistas PILOTOS y CONSTRUCTORES

Filtros de página: solo `QUALIFYING_RESULT` y pilotos con tiempo.

| Visual | Tipo | Qué muestra | Equivalente en la web |
|---|---|---|---|
| Distancia media en % respecto al mejor tiempo, por piloto | Columnas | % del mejor tiempo de cada piloto frente al mejor de la sesión | `/races/[id]/qualifying` · barras por piloto |
| Distancia media en %, por constructor | Columnas | Media del % de sus pilotos | `/races/[id]/qualifying` · barras por constructor |
| Gran Premio | Desplegable año + GP | Carrera | Navegación por carrera (`/seasons/[year]` → `/races/[id]`); la web añade la clasificación sprint |

### 5. Situación de carrera (Fig. 5.28 y 5.29), vistas «Vuelta a vuelta» y «Neumáticos usados en carrera»

| Visual | Tipo | Qué muestra | Equivalente en la web |
|---|---|---|---|
| Vuelta a vuelta | Líneas | Posición de cada piloto en cada vuelta (`Sum(Rank)`, aunque la referencia diga «CountNonNull») | `/races/[id]/lap-chart` · gráfico de posiciones con resaltado por piloto y tabla |
| Neumáticos usados en carrera | Matriz | Piloto × vuelta con el compuesto; al desplegarla, el estado de la vuelta (boxes, vuelta de salida, SC, VSC, amarilla) | `/races/[id]/tyres` · gráfico de stints y matriz de compuestos por vuelta con las vueltas de entrada a boxes recuadradas. No muestra SC, VSC ni banderas amarillas por vuelta |

### 6. Ritmo en carrera (Fig. 5.30 y 5.31), vistas «Tiempos de carrera» y «Ritmo de carrera»

Filtro de página: vueltas sin estado o con «Lap Time Deleted» (quita boxes, SC, VSC y amarillas).

| Visual | Tipo | Qué muestra | Equivalente en la web |
|---|---|---|---|
| Tiempos en carrera por piloto | Líneas | Tiempo de cada vuelta por piloto | `/races/[id]/pace` · gráfico de tiempos por vuelta |
| Ritmos de carrera por piloto | Violín (personalizado) | Distribución de tiempos por vuelta | `/races/[id]/pace` · violín con mediana y dispersión |
| Piloto | Segmentación (lista) | Elegir pilotos | `/races/[id]/pace` · selección de pilotos («todos / ninguno») y opción de ocultar vueltas neutralizadas |

### 7. Paradas en boxes (Fig. 5.32)

| Visual | Tipo | Qué muestra | Equivalente en la web |
|---|---|---|---|
| Tiempo medio de parada (s) por constructor | Columnas | Media por equipo de las paradas de menos de 70 s | `/races/[id]/pitstops` · media por equipo (umbral de 60 s, ver `paridad_tfg.md`), más la lista de paradas y los pasos por el pit lane |

### 8. Detalle de rendimiento piloto (Fig. 5.33)

| Visual | Tipo | Qué muestra | Equivalente en la web |
|---|---|---|---|
| Piloto | Tarjeta | Nombre (Hamilton por defecto) | `/drivers/[id]` · cabecera |
| Campeonatos, Carreras, Victorias, Podios, Vueltas rápidas, Pole position | 6 tarjetas | KPIs de toda la carrera deportiva (pole = salida desde la posición 1) | `/drivers/[id]` · KPIs (pole oficial; añade salidas y puntos) |
| Rendimiento en clasificación contra compañeros | Columnas apiladas al 100 % por año | % por delante / por detrás del compañero en clasificación | `/drivers/[id]` · gráfico de reparto frente al compañero (clasificación) |
| Rendimiento en carrera contra compañeros | Columnas apiladas al 100 % por año | Lo mismo en carrera (solo carreras con los dos clasificados) | `/drivers/[id]` · lo mismo en carrera (todas las carreras compartidas) |
| Puntos piloto contra compañeros | Columnas agrupadas por año | Puntos del piloto y de sus compañeros | `/drivers/[id]` · «Puntos frente al compañero» (ojo al error de duplicados anterior a 1982, `paridad_tfg.md` §5) |

## Lo que el TFG tenía y la web no (ideas para W2/W3)

1. **Estado de cada vuelta en la matriz de neumáticos** (SC, VSC, amarilla, boxes). La web solo
   marca la entrada a boxes. Los datos existen en `fact_laptimes` (`is_safety_car`,
   `is_virtual_safety_car`, `is_yellow_flag`, `is_red_flag`). Encaja en W2, con la dirección de
   carrera (decisión 29).
2. **Tarjetas de temporada:** pilotos del equipo campeón, motorista campeón y victorias del equipo
   campeón como tarjetas, y el equipo del piloto campeón (que puede no ser el campeón de
   constructores, como en 2021 o 2008). Hoy están repartidos en tablas o en otras páginas. Es poco
   trabajo (W2).
3. **Detalle filtrado por periodo:** en Power BI, las segmentaciones y la obtención de detalle
   permitían ver los récords de una época y saltar al piloto con ese contexto. La web tiene el rango
   en `/records`, pero `/drivers/[id]` siempre muestra la carrera completa. Opcional (W3).

Todo lo demás del informe tiene equivalente en la web (el ajuste de ejes de los tiempos por vuelta
que cita la memoria también: `lap-times-chart.tsx` usa `dataZoom`).

## Lo que añade la web

- **Datos nuevos:** telemetría de clasificación (`/races/[id]/telemetry`: velocidad, acelerador y
  freno de dos pilotos), pasos por el pit lane, resultados de la carrera y el sprint con
  correcciones marcadas, mensajes de dirección de carrera y meteorología (en la API; web en W2).
- **Páginas nuevas:** índices de pilotos y constructores con buscador (`/drivers`, `/constructors`),
  ficha de constructor con puntos por temporada (`/constructors/[id]`), evolución del campeonato
  como gráfico acumulado (`/seasons/[year]`), calendario de la temporada, ficha de carrera
  (`/races/[id]`) y la página de calidad de datos (`/quality`), con el contraste entre fuentes.
- **Métricas extra:** poles oficiales en récords y fichas y dobletes en la ficha de constructor.
  La API (`/drivers`, `agg_driver_career`) ofrece además grand slams, piloto del día, victorias al
  sprint, mejor resultado, vueltas completadas y porcentajes de victorias y podios, que la web aún
  no muestra (posible idea para W2).
- **Actualización automática** tras cada GP (pipeline con OpenF1 y Jolpica) frente al informe
  estático de 2024. Bilingüe español/inglés, accesible (tabla alternativa en cada gráfico, teclado,
  modo oscuro) y sin licencia de Power BI.

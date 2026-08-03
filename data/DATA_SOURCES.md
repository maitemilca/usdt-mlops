# Fuentes de datos

## 1. Tipo de cambio paralelo USDT/BOB — la variable que modela el proyecto

- **Fuente:** [usdtbol.com](https://usdtbol.com/), que agrega cotizaciones de
  compra/venta de USDT contra bolivianos en el mercado P2P de Binance.
- **Archivo:** `usdtbol_full.csv` — dos columnas (fecha/hora, precio en Bs).
- **Cobertura:** 2.937 observaciones entre el 2024-08-31 y el 2026-07-31.
- **Densidad:** muy desigual, y esto condiciona todo el diseño del modelo.

| Año | Días | Días con cotización | Cobertura |
|---|---|---|---|
| 2024 | 123 | 24 | 20% |
| 2025 | 365 | 264 | 72% |
| 2026 | 212 | 209 | 99% |

**Por qué el proyecto trabaja a frecuencia diaria.** Sobre 700 días hay 2.937
cotizaciones, o sea unas 4 por día en promedio, pero repartidas de forma muy
irregular. Al remuestrear a frecuencia horaria, el 87% de las casillas hay que
rellenarlas hacia adelante, y un modelo entrenado sobre eso solo aprende que
el precio de la próxima hora es igual al de esta. Agregando por día, el 71% de
los días tiene cotización real y el horizonte de predicción pasa a ser el que
económicamente importa.

**Un solo archivo, no dos.** El corte entre entrenamiento y holdout no está
materializado en archivos separados: lo define `FECHA_CORTE_V1` en
`src/config.py` y el código parte la serie al vuelo. Así hay una única fuente
de verdad, y cambiar la fecha de corte o incorporar datos nuevos no obliga a
regenerar archivos derivados que podrían quedar desincronizados.

### Cómo actualizar con datos más recientes

1. Exportar el histórico nuevo desde usdtbol.com.
2. Reemplazar `data/usdtbol_full.csv` (mismo formato: fecha, precio).
3. Correr `./scripts/02_entrenar.sh`.

El pipeline vuelve a partir la serie, reentrena, registra una versión nueva y
los monitores de deriva recalculan sus lotes. No hay que tocar código.

---

## 2. Tipo de cambio oficial (TCO) — segunda fuente, de contexto

- **Fuente:** [Banco Central de Bolivia, reporte histórico del TCO](https://www.bcb.gob.bo/tco_reporte_detalle_historico.php)
- **Archivo crudo:** `TCO_bcb_crudo.csv`, tal como lo exporta el sitio del BCB
  (detalle de operaciones por banco, separado por punto y coma, con números en
  formato boliviano: punto de miles y coma decimal).
- **Archivo procesado:** `tco_oficial_diario.csv`, generado por
  `src/parse_tco.py`. Es el promedio ponderado diario por monto operado,
  replicando la definición oficial del TCO.

### Por qué esta fuente importa, y por qué NO es una variable del modelo

El 29 de junio de 2026 Bolivia abandonó el tipo de cambio fijo de 6,96 Bs,
vigente desde 2011, y pasó a un régimen flexible calculado a diario
(Resolución de Directorio BCB N.º 88/2026). El TCO pasó de 9,73 Bs el primer
día del nuevo régimen a 12,15 Bs el 31 de julio: una devaluación oficial de
~25% en un mes.

Ese cambio de régimen ocurrió **completamente fuera de la ventana de
entrenamiento** del modelo, que termina el 2025-12-11. Es un escenario de
deriva real, fechado y documentado por el banco central — no hay que inventar
nada.

Pero como **variable de entrada del modelo no sirve**, y conviene tenerlo
claro para la defensa: antes del 29-jun-2026 el TCO fue una constante (6,96)
durante toda la ventana de entrenamiento, y después existen apenas 24 días de
serie variable. Una constante no aporta información al entrenamiento, y 24
observaciones no alcanzan para nada. Su papel en el proyecto es documental:
fecha y cuantifica el cambio de régimen que sostiene el análisis de la Fase 6.

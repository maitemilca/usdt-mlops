# Fuentes de datos

## 1. Tipo de cambio P2P (variable de entrenamiento del modelo)

- **Fuente:** [usdtbol.com](https://usdtbol.com/), que agrega cotizaciones de
  compra/venta de USDT en el mercado P2P de Binance (par BOB).
- **Archivo:** `usdt_bs.csv` (2 columnas: fecha/hora, tipo de cambio en Bs.)
- **Ventana usada para entrenar (Fase 1):** hasta el 2025-12-11, que documentamos
    en un modelo precendente.

## 2. Tipo de cambio oficial (dato de contexto / segunda fuente)

- **Fuente:** [Banco Central de Bolivia — reporte histórico del TCO]
  (https://www.bcb.gob.bo/tco_reporte_detalle_historico.php)
- **Archivo crudo:** `TCO_fecha_corte_2026-06-26_al_2026-07-30.csv` (reporte
  detallado por banco, tal como lo exporta el sitio del BCB)
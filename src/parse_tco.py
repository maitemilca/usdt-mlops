"""
Convierte el reporte crudo del BCB (tal como lo exporta
https://www.bcb.gob.bo/tco_reporte_detalle_historico.php, con el detalle
de operaciones por banco) en una serie diaria simple: fecha -> TCO.

El TCO oficial se define como el promedio ponderado (por monto operado)
de las operaciones de compra de dólares de todos los bancos en el día.
Esta función replica esa definición usando la columna TOTAL BANCOS del
reporte crudo.

Este dato NO entra al modelo: el TCO solo existe como serie variable desde el
29-jun-2026 (antes estuvo fijo en 6,96 Bs desde 2011), asi que como variable de
entrada seria una constante durante toda la ventana de entrenamiento. Se usa
como segunda fuente documental: es lo que fecha y cuantifica el cambio de
regimen que sostiene el escenario de deriva de la Fase 6.

Uso:
    python parse_tco.py --input ../data/TCO_bcb_crudo.csv \
                        --output ../data/tco_oficial_diario.csv
"""
from __future__ import annotations

import argparse
import csv

import numpy as np
import pandas as pd


def _parse_numero_es(valor: str):
    """Convierte '11.890,00' (formato boliviano: punto=miles, coma=decimal) a float."""
    if valor is None or valor.strip() in ("", "-"):
        return None
    limpio = valor.strip().replace(".", "").replace(",", ".")
    try:
        return float(limpio)
    except ValueError:
        return None


def parse_tco_csv(path: str) -> pd.DataFrame:
    with open(path, encoding="utf-8-sig") as f:
        filas = list(csv.reader(f, delimiter=";"))

    # Las primeras filas son metadatos/encabezados de dos niveles; los
    # datos de precio por bracket empiezan en la fila 9 (índice 9).
    filas_datos = filas[9:]

    registros = []
    for fila in filas_datos:
        if len(fila) < 3 or not fila[0].strip():
            continue
        precio = _parse_numero_es(fila[2].strip())
        if precio is None:
            # Salta las filas resumen "TOTAL" / "TCO" por banco, que no
            # son brackets de precio.
            continue
        monto_total_bancos = _parse_numero_es(fila[-1]) or 0.0
        registros.append((fila[0].strip(), fila[1].strip(), precio, monto_total_bancos))

    df = pd.DataFrame(registros, columns=["fecha_corte", "fecha_vigencia", "precio", "monto"])

    diario = (
        df.groupby("fecha_vigencia")
        .apply(
            lambda g: np.average(g["precio"], weights=g["monto"]) if g["monto"].sum() > 0 else np.nan,
            include_groups=False,
        )
        .reset_index()
    )
    diario.columns = ["fecha_vigencia", "tco_oficial_bob_usd"]
    diario["fecha_vigencia"] = pd.to_datetime(diario["fecha_vigencia"])
    return diario.sort_values("fecha_vigencia").reset_index(drop=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    # Los valores por defecto salen de config.py y no de rutas relativas
    # escritas a mano: asi el script funciona desde cualquier directorio y en
    # cualquier sistema operativo.
    import config as cfg

    parser.add_argument("--input", default=str(cfg.DIR_DATOS / "TCO_bcb_crudo.csv"))
    parser.add_argument("--output", default=str(cfg.CSV_TCO_DIARIO))
    args = parser.parse_args()

    diario = parse_tco_csv(args.input)
    diario.to_csv(args.output, index=False)
    print(diario.to_string(index=False))
    print(f"\nGuardado en {args.output}")


if __name__ == "__main__":
    main()

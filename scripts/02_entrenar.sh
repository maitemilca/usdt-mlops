#!/usr/bin/env bash
# Paso 2 -- Fase 1: entrena, registra los experimentos en MLflow y publica la
# version 1 del modelo con el alias 'champion'.
set -euo pipefail
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ/src"
exec ../.venv/bin/python train.py "$@"

# Reparto de trabajo

**Integrantes**

| Integrante | GitHub | Rol en el equipo |
|---|---|---|
| Elmar Rodas Banegas | `@Elmarcinho` | Ejecución e infraestructura |
| Milca | `@maitemilca` | Análisis y documentación |

**Criterio del reparto.** No se repartió por cantidad de archivos sino por
subsistema, agrupando lo que se defiende junto. Milca se ocupa de los datos,
el monitoreo de deriva y la documentación analítica; Elmar, del entrenamiento
y de llevar el modelo a producción (servicio, contenedor, clúster). Cada mitad
tiene una narrativa propia y completa.

---

## 1. Componentes de código

| # | Componente | Archivos | Responsable |
|---|---|---|---|
| 1 | Datos, fuentes y procesamiento del TCO | `src/parse_tco.py`, `data/DATA_SOURCES.md` | Milca |
| 2 | Entrenamiento y experimentación en MLflow | `src/train.py`, `src/config.py` | Elmar |
| 3 | Registro, versionado y alias de despliegue | `src/train.py`, `MODELO_DESPLEGADO.md` | Elmar |
| 4 | Servicio de inferencia | `src/app.py` | Elmar |
| 5 | Contenerización y portabilidad del store | `Dockerfile`, `.dockerignore`, `src/portar_store.py` | Elmar |
| 6 | Despliegue en Kubernetes | `k8s/deployment.yaml`, `k8s/service.yaml` | Elmar |
| 7 | Evidencia de las cuatro demostraciones | `scripts/05_pruebas_kubernetes.sh` | Elmar |
| 8 | Data drift: pruebas estadísticas y umbrales | `src/drift_common.py`, `src/monitor_data_drift.py` | Milca |
| 9 | Concept drift y criterio de reentrenamiento | `src/monitor_concept_drift.py` | Milca |
| 10 | Pruebas automatizadas | `tests/test_deteccion_deriva.py` | Elmar |
| 11 | Interfaz web (puntos extra) | `ui/app_streamlit.py` | Elmar |
| 12 | Construcción de variables | `src/features.py` | Elmar |

## 2. Documentación

Estas filas no son un anexo: la consigna evalúa explícitamente documentar y
defender las decisiones de arquitectura, y la entrega incluye un comprimido
con documentación y evidencia.

| Entregable | Archivo | Responsable |
|---|---|---|
| Documento de arquitectura | `ARQUITECTURA.md` | Milca |
| Diagrama de la solución | `docs/arquitectura.png` | Milca |
| Análisis de la Fase 6 | `FASE6_DRIFT.md` | Milca |
| **Informe final con las capturas** | documento Word de la entrega | Milca |
| Guía de ejecución | `GUIA_PASO_A_PASO.md` | Elmar |
| Índice del repositorio | `README.md` | Elmar |
| Comparación entre versiones | `COMPARACION_VERSIONES.md` | Elmar |

## 3. Ejecución y captura de evidencia

Cada integrante ejecuta sus fases en su propia máquina y deja las capturas en
`evidencia/capturas/`, numeradas según `GUIA_PASO_A_PASO.md`. Así nadie queda
esperando material del otro: el texto explicativo de cada captura ya está
escrito en la guía, listo para pegar en el informe.

| Fase | Capturas | Responsable |
|---|---|---|
| Paso 0-1: entorno y clúster | 1, 2 | Elmar |
| Paso 2: entrenamiento y ficha del modelo | 3, 4 | Elmar |
| Paso 3: interfaz de MLflow (runs, comparación, registry) | 5, 6, 7, 8 | Milca |
| Paso 4: pruebas automatizadas | 9 | Elmar |
| Paso 4: monitores de deriva y gráficos | 10, 11, 12, 13, 14 | Milca |
| Paso 5: contenerización | 15, 16 | Elmar |
| Paso 6: Kubernetes, cuatro demostraciones | 17, 18, 19, 20, 21 | Elmar |
| Paso 7: interfaz web | 22, 23 | Elmar |
| Paso 8: versión 2 y promoción del alias | 24, 25 | Elmar |
| Paso 9: historial de Git | 26 | Elmar |

---

## Cómo se respalda este reparto en el historial de commits

La consigna avisa que **el historial de commits se revisa como evidencia del
reparto declarado**. Para que lo respalde de verdad y no de forma cosmética:

**Cada quien commitea lo que efectivamente produjo.** Nadie sube archivos que
no puede explicar línea por línea.

**La versión inicial del proyecto y la versión actual conviven en el mismo
repositorio** (`usdt-mlops`), no en repositorios separados. El historial
muestra la evolución: versión inicial → revisión → versión corregida. Esa
evolución es parte de lo que se está evaluando.

**La versión corregida entra por Pull Request, no por push directo.** La
revisión y aprobación quedan registradas en GitHub con usuario y fecha, y son
evidencia de colaboración que un push directo no genera. La descripción del
Pull Request es el contenido de `COMPARACION_VERSIONES.md`.

**Trabajo real pendiente sobre los componentes asignados.** El código está
escrito, pero cada integrante debe apropiarse de su parte antes de
commitearla: revisarla, ajustarla y mejorarla. Concretamente hay trabajo
genuino en cada lado —reescribir `FASE6_DRIFT.md` con los números nuevos,
rehacer el diagrama, agregar pruebas, generar toda la evidencia de ejecución—
y esos commits sí reflejan autoría real.

Si trabajan sobre la misma máquina, configurar el autor antes de cada tanda:

```bash
git config user.name "Nombre que corresponda"
git config user.email "correo@que-corresponda"
```

---

## Preparación para la defensa

La consigna es explícita: **cada integrante responde por separado sobre
cualquier parte del proyecto, no solo sobre la que construyó.** Ese es el
riesgo más grande del equipo, mayor que el reparto en el papel.

Tres compromisos:

1. **Los dos corren `GUIA_PASO_A_PASO.md` completa al menos una vez**, como
   aprendizaje y sin generar entregables. Recién después cada uno ejecuta en
   serio las fases que le tocan.

2. **Las preguntas de defensa se practican cruzadas.** La guía termina con 30
   preguntas y sus respuestas. Cada integrante practica las de la mitad del
   otro: quien hizo el monitoreo practica Docker y Kubernetes; quien hizo la
   infraestructura practica deriva, umbrales y retraso de etiqueta.

3. **Intercambio final antes de entregar.** Cada uno le explica su mitad al
   otro en voz alta, que es distinto de haberla leído.

---

## Orden de trabajo sugerido

1. Los dos recorren la guía completa por separado (aprendizaje).
2. Se integra la versión corregida al repositorio mediante Pull Request.
3. Cada uno ejecuta sus fases y deja sus capturas numeradas.
4. Se reescribe `FASE6_DRIFT.md` y se rehace el diagrama de arquitectura.
5. Se arma el informe final alrededor de las capturas.
6. Intercambio de preguntas de defensa.
7. Se verifica que este reparto coincida con `git log --oneline --format='%an %s'`
   antes de entregar.

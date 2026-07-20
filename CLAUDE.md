# Instrucciones para Claude Code en este repo

## Verificar cambios de backend/pipeline vía Docker, no solo el venv local

Antes de dar por verificado un cambio en `backend/pipeline/` o
`backend/apps/surveys/` (ingesta, orquestación, productores), correr la
suite completa contra el stack real de `docker compose`, no solo el venv
local (`backend/.venv`):

```bash
cd infra && docker compose up -d --build
docker compose exec backend pytest -q
```

**Por qué:** el venv local (macOS/homebrew) suele tener `pdal`/`gdal` pero
no `untwine`, así que la generación de COPC cae silenciosamente al fallback
`pdal writers.copc`, que **no es reproducible** de una corrida a otra en ese
camino. Esto puede parecer un bug real cuando en realidad es solo una brecha
de entorno. La imagen `backend`/`worker` (`infra/backend.Dockerfile`, conda-forge
con `pdal`+`untwine`+`gdal`) es el entorno real, con Postgres/PostGIS, MinIO
(S3) y Redis reales — coincide con el principio "infraestructura demo-first"
de la constitución y con la regla de validación obligatoria contra una
muestra LAZ real para cualquier PR que toque la ingesta.

Para cambios en productores/pipeline, además correr el test marcado
`real_laz` con una muestra generada dentro del contenedor:

```bash
docker compose exec backend python3 -c "
from tests.fixtures import make_fixtures
from pathlib import Path
make_fixtures.make_ramp_laz(Path('/tmp/fixture'))
"
docker compose exec backend pytest tests/integration/test_real_laz_ingest.py \
  -m real_laz --laz-sample /tmp/fixture/ramp.laz -v
```

El venv local sigue siendo válido para iteración rápida durante el
desarrollo, pero la corrida dentro del contenedor es la que debe citarse
como evidencia de verificación al cerrar una fase o tarea.

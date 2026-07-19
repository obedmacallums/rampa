# Multi-arch (linux/arm64 + linux/amd64) backend/worker image.
# conda-forge provides PDAL, untwine and GDAL binaries for both architectures.
FROM condaforge/miniforge3:24.9.2-0

RUN conda install -y -c conda-forge \
        python=3.12 pdal untwine gdal \
    && conda clean -afy

WORKDIR /app

COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir \
        "django>=5.0,<6" "djangorestframework>=3.15" "celery[redis]>=5.3" \
        "boto3>=1.34" "laspy[lazrs]>=2.5" "pyproj>=3.6" "gunicorn>=22" "psycopg[binary]>=3.1" \
        "pytest>=8" "pytest-django>=4.8"

COPY backend/ ./
RUN pip install --no-cache-dir --no-deps -e .

ENV DJANGO_SETTINGS_MODULE=config.settings PYTHONUNBUFFERED=1

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]

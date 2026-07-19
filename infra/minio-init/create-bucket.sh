#!/bin/sh
# Bootstrap the object-storage bucket and a 7-day expiry rule for abandoned
# tus uploads (FR-004); the Celery beat purge task reaps the UploadSession rows.
set -e
mc alias set local http://minio:9000 rampa rampasecret
mc mb --ignore-existing local/rampa
mc ilm rule add local/rampa --prefix "tus-staging/" --expire-days 7 || true
echo "minio bucket ready"

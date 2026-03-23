#!/bin/bash
set -euo pipefail
BACKUP_TYPE=${1:-full}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/tmp/financeops_backup_${TIMESTAMP}"
: "${POSTGRES_URL:?POSTGRES_URL must be set}"
: "${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET must be set}"
mkdir -p "${BACKUP_DIR}"
if [ "${BACKUP_TYPE}" = "full" ]; then
  pg_dump "${POSTGRES_URL}" \
    --format=custom --compress=9 \
    --file="${BACKUP_DIR}/financeops_${TIMESTAMP}.dump"
  aws s3 cp \
    "${BACKUP_DIR}/financeops_${TIMESTAMP}.dump" \
    "s3://${BACKUP_S3_BUCKET}/postgres/full/financeops_${TIMESTAMP}.dump" \
    --storage-class STANDARD_IA
  echo "Full backup complete: financeops_${TIMESTAMP}.dump"
elif [ "${BACKUP_TYPE}" = "incremental" ]; then
  pg_basebackup -D "${BACKUP_DIR}/base" -Ft -z -Xs -P \
    -d "${POSTGRES_URL}"
  aws s3 sync "${BACKUP_DIR}/base" \
    "s3://${BACKUP_S3_BUCKET}/postgres/wal/${TIMESTAMP}/"
  echo "Incremental backup complete"
fi
rm -rf "${BACKUP_DIR}"

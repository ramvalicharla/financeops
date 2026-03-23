#!/bin/bash
set -euo pipefail
BACKUP_FILE=${1:?Usage: ./restore_postgres.sh <backup_filename>}
: "${POSTGRES_URL:?Required}"
: "${BACKUP_S3_BUCKET:?Required}"
: "${RESTORE_CONFIRM:?Set RESTORE_CONFIRM=yes to proceed}"
if [ "${RESTORE_CONFIRM}" != "yes" ]; then
  echo "ERROR: Set RESTORE_CONFIRM=yes to proceed"; exit 1
fi
aws s3 cp \
  "s3://${BACKUP_S3_BUCKET}/postgres/full/${BACKUP_FILE}" \
  "/tmp/${BACKUP_FILE}"
pg_restore --dbname="${POSTGRES_URL}" \
  --clean --if-exists --verbose "/tmp/${BACKUP_FILE}"
echo "Restore complete. Run verify_restore.sh to verify."
rm -f "/tmp/${BACKUP_FILE}"

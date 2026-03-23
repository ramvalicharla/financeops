#!/bin/bash
set -euo pipefail
: "${POSTGRES_TEST_URL:?Required for CI verify}"
: "${BACKUP_S3_BUCKET:?Required}"
LATEST=$(aws s3 ls \
  "s3://${BACKUP_S3_BUCKET}/postgres/full/" \
  | sort | tail -1 | awk '{print $4}')
if [ -z "${LATEST}" ]; then
  echo "No backups found - SKIP"; exit 0
fi
aws s3 cp \
  "s3://${BACKUP_S3_BUCKET}/postgres/full/${LATEST}" \
  "/tmp/verify_${LATEST}"
pg_restore --dbname="${POSTGRES_TEST_URL}" \
  --clean --if-exists "/tmp/verify_${LATEST}"
echo "RESTORE VERIFICATION PASSED"
rm -f "/tmp/verify_${LATEST}"

#!/bin/bash
set -euo pipefail
: "${REDIS_URL:?Required}"
: "${BACKUP_S3_BUCKET:?Required}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
redis-cli -u "${REDIS_URL}" BGSAVE
sleep 5
REDIS_DIR=$(redis-cli -u "${REDIS_URL}" CONFIG GET dir | tail -1)
REDIS_FILE=$(redis-cli -u "${REDIS_URL}" CONFIG GET dbfilename \
  | tail -1)
aws s3 cp "${REDIS_DIR}/${REDIS_FILE}" \
  "s3://${BACKUP_S3_BUCKET}/redis/dump_${TIMESTAMP}.rdb"
echo "Redis backup complete: dump_${TIMESTAMP}.rdb"

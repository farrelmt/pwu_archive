#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

readonly DATE="$(date +"%Y-%m-%d_%H-%M-%S")"
readonly BACKUP_BASE="/home/itpwu/pwu_archive/backups"
readonly RUN_DIR="$BACKUP_BASE/$DATE"
readonly KEY_DIR="/home/itpwu/.config/pwu-archive"
readonly KEY_FILE="$KEY_DIR/backup.key"
readonly DB_CONTAINER="archiveproject-db-1"
readonly DB_USER="farrel"
readonly DB_NAME="pwu_archive_db"
readonly MEDIA_VOLUME="archiveproject_media_volume"

command -v docker >/dev/null
command -v openssl >/dev/null

install -d -m 700 "$BACKUP_BASE" "$RUN_DIR" "$KEY_DIR"
if [[ ! -s "$KEY_FILE" ]]; then
    install -m 600 /dev/null "$KEY_FILE"
    openssl rand -hex 32 > "$KEY_FILE"
fi
chmod 600 "$KEY_FILE"

cleanup_partial() {
    find "$RUN_DIR" -maxdepth 1 -type f -name '*.partial' -delete
}
trap cleanup_partial EXIT

echo "Starting encrypted backup for $DATE..."

docker exec "$DB_CONTAINER" pg_dump -Fc -U "$DB_USER" "$DB_NAME" \
    | openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
        -pass "file:$KEY_FILE" \
        -out "$RUN_DIR/db.dump.enc.partial"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
    -pass "file:$KEY_FILE" \
    -in "$RUN_DIR/db.dump.enc.partial" \
    | docker exec -i "$DB_CONTAINER" pg_restore --list >/dev/null
mv "$RUN_DIR/db.dump.enc.partial" "$RUN_DIR/db.dump.enc"

docker run --rm \
    -v "$MEDIA_VOLUME:/media_data:ro" \
    alpine:3.22 tar -czf - -C /media_data . \
    | openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
        -pass "file:$KEY_FILE" \
        -out "$RUN_DIR/media.tar.gz.enc.partial"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
    -pass "file:$KEY_FILE" \
    -in "$RUN_DIR/media.tar.gz.enc.partial" \
    | docker run --rm -i alpine:3.22 tar -tzf - >/dev/null
mv "$RUN_DIR/media.tar.gz.enc.partial" "$RUN_DIR/media.tar.gz.enc"

chmod 600 "$RUN_DIR"/*
find "$BACKUP_BASE" -mindepth 1 -maxdepth 1 -type d -mtime +7 \
    -exec rm -rf -- {} +

echo "Encrypted backup completed: $RUN_DIR"

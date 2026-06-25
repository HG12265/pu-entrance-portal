#!/bin/bash
set -e

if [ -z "$1" ]; then
  echo "Usage: $0 <backup-file.sql.gz>"
  exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "Error: File $BACKUP_FILE does not exist."
  exit 1
fi

echo "Restoring database from $BACKUP_FILE..."

TEMP_SQL="/tmp/restore_temp.sql"

echo "Decompressing backup..."
gunzip -c "$BACKUP_FILE" > "$TEMP_SQL"

echo "Re-creating database: $MYSQL_DATABASE..."
mysql -h "$MYSQL_HOST" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" -e "DROP DATABASE IF EXISTS $MYSQL_DATABASE; CREATE DATABASE $MYSQL_DATABASE CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

echo "Importing SQL structure and data..."
mysql -h "$MYSQL_HOST" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" < "$TEMP_SQL"

rm -f "$TEMP_SQL"
echo "Database restoration completed successfully!"

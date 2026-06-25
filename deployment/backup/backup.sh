#!/bin/bash
set -e

BACKUP_DIR="/backups"
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
FILENAME="$BACKUP_DIR/backup_$TIMESTAMP.sql"
GZ_FILENAME="$FILENAME.gz"

echo "Starting backup to $GZ_FILENAME..."
mysqldump -h "$MYSQL_HOST" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" \
  --single-transaction --routines --triggers "$MYSQL_DATABASE" > "$FILENAME"

gzip -f "$FILENAME"
echo "Backup completed successfully."

# Retention Cleanup
echo "Running retention cleanup..."
NOW_EPOCH=$(date +%s)

files=($(ls -1 "$BACKUP_DIR"/backup_*.sql.gz 2>/dev/null | sort))
declare -A daily_kept

for file in "${files[@]}"; do
  [ -e "$file" ] || continue
  basename_file=$(basename "$file")
  ts_str=${basename_file#backup_}
  ts_str=${ts_str%.sql.gz}
  file_date="${ts_str:0:8}"
  
  # Parse date to epoch
  formatted_ts="${ts_str:0:4}-${ts_str:4:2}-${ts_str:6:2} ${ts_str:9:2}:${ts_str:11:2}:${ts_str:13:2}"
  file_epoch=$(date -d "$formatted_ts" +%s 2>/dev/null || stat -c %Y "$file")
  age_seconds=$((NOW_EPOCH - file_epoch))
  age_hours=$((age_seconds / 3600))
  
  if [ "$age_hours" -le 24 ]; then
    echo "Keeping hourly backup: $basename_file (Age: ${age_hours}h)"
  elif [ "$age_hours" -le 168 ]; then
    if [ -z "${daily_kept[$file_date]}" ]; then
      echo "Keeping daily backup (first of the day): $basename_file (Age: ${age_hours}h)"
      daily_kept[$file_date]="$file"
    else
      echo "Deleting redundant backup for day $file_date: $basename_file (Age: ${age_hours}h)"
      rm -f "$file"
    fi
  else
    echo "Deleting expired backup (>7 days): $basename_file (Age: ${age_hours}h)"
    rm -f "$file"
  fi
done

#!/bin/bash
set -e

# Configuration
BACKUP_DIR="./backups"
DB_FILE="./database.db"
XML_DATA="./data"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_PATH="$BACKUP_DIR/$TIMESTAMP"

echo "🔄 Starting local backup for $TIMESTAMP..."

# Create backup directory
mkdir -p "$BACKUP_PATH"

# Backup database
if [ -f "$DB_FILE" ]; then
    echo "📦 Backing up database..."
    cp "$DB_FILE" "$BACKUP_PATH/database.db"
else
    echo "⚠️  Database file not found, skipping"
fi

# Backup XML data (only if directory exists and has files)
if [ -d "$XML_DATA" ] && [ "$(ls -A $XML_DATA)" ]; then
    echo "📦 Backing up XML files..."
    mkdir -p "$BACKUP_PATH/data"
    cp -r "$XML_DATA"/* "$BACKUP_PATH/data/" 2>/dev/null || true
    FILE_COUNT=$(ls -1 "$BACKUP_PATH/data" | wc -l)
    echo "   Backed up $FILE_COUNT files"
else
    echo "⚠️  No XML files to backup"
fi

# Create compressed archive
echo "🗜️  Creating compressed archive..."
tar -czf "$BACKUP_DIR/anidb-backup-$TIMESTAMP.tar.gz" -C "$BACKUP_PATH" .
rm -rf "$BACKUP_PATH"

# Calculate size
BACKUP_SIZE=$(du -h "$BACKUP_DIR/anidb-backup-$TIMESTAMP.tar.gz" | cut -f1)

echo "✅ Backup complete!"
echo "   Location: $BACKUP_DIR/anidb-backup-$TIMESTAMP.tar.gz"
echo "   Size: $BACKUP_SIZE"

# Optional: Keep only last 7 backups
echo "🧹 Cleaning old backups (keeping last 7)..."
ls -t "$BACKUP_DIR"/anidb-backup-*.tar.gz | tail -n +8 | xargs -r rm
echo "✅ Backup process finished"

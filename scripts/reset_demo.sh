#!/bin/bash
# Reset Pincer demo state by deleting and reinitializing the database

set -e

echo "🔄 Resetting Pincer demo state..."

# Remove existing database
if [ -f "pincer.db" ]; then
    echo "  📁 Removing existing database..."
    rm pincer.db
fi

# Reinitialize database
echo "  🗄️  Reinitializing database..."
python scripts/init_ledger.py

echo "✅ Demo state reset complete!"
echo ""
echo "You can now run the demo from a clean state."

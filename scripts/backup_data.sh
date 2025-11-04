#!/bin/bash

# 🌙 Moon Dev's Revival Scanner - Data Backup Script
# Backs up paper trading and scanner data from Railway to local machine

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   🌙 Moon Dev's Revival Scanner - Data Backup Utility${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Check if Railway URL is provided
if [ -z "$1" ]; then
    echo -e "${YELLOW}Usage: ./scripts/backup_data.sh <RAILWAY_APP_URL>${NC}"
    echo -e "${YELLOW}Example: ./scripts/backup_data.sh https://revival-scanner-production.up.railway.app${NC}"
    echo ""
    exit 1
fi

RAILWAY_URL=$1
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo -e "${GREEN}📦 Creating backup in: $BACKUP_DIR${NC}"
echo ""

# Function to download CSV files via Railway API
download_csv() {
    local endpoint=$1
    local filename=$2

    echo -e "${BLUE}⬇️  Downloading $filename...${NC}"

    curl -s "${RAILWAY_URL}/api/paper/${endpoint}" -o "${BACKUP_DIR}/${filename}"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Downloaded $filename${NC}"
    else
        echo -e "${RED}❌ Failed to download $filename${NC}"
    fi
}

# Backup paper trading data
echo -e "${YELLOW}📊 Backing up paper trading data...${NC}"
download_csv "positions" "positions.json"
download_csv "trades" "trades.json"
download_csv "portfolio" "portfolio.json"
download_csv "metrics" "metrics.json"
echo ""

# Backup scan results
echo -e "${YELLOW}🔍 Backing up scan results...${NC}"
curl -s "${RAILWAY_URL}/api/results" -o "${BACKUP_DIR}/scan_results.json"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Downloaded scan_results.json${NC}"
else
    echo -e "${RED}❌ Failed to download scan_results.json${NC}"
fi
echo ""

# Create backup summary
echo -e "${YELLOW}📝 Creating backup summary...${NC}"
cat > "${BACKUP_DIR}/backup_info.txt" <<EOF
Revival Scanner Data Backup
═══════════════════════════════════════════════════════════
Backup Date: $(date)
Railway URL: ${RAILWAY_URL}
Files Backed Up:
  - positions.json
  - trades.json
  - portfolio.json
  - metrics.json
  - scan_results.json

To restore data:
1. Copy CSV files to /app/src/data/paper_trading/ on Railway
2. Use Railway CLI: railway volumes cp <local-file> <volume-path>

For help: https://docs.railway.app/guides/volumes
EOF

echo -e "${GREEN}✅ Backup summary created${NC}"
echo ""

# Display summary
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✨ Backup Complete!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Backup Location:${NC} $BACKUP_DIR"
echo -e "${YELLOW}Files Backed Up:${NC}"
ls -lh "$BACKUP_DIR" | tail -n +2
echo ""
echo -e "${GREEN}💾 Keep this backup safe!${NC}"
echo ""

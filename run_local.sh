#!/bin/bash
# run_local.sh - One-click local job scraper
# 
# Usage:
#   ./run_local.sh          # Run and show results
#   ./run_local.sh --open   # Run and open in browser
#   ./run_local.sh --all    # Show all matching jobs (not just new)

set -e

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "🚀 Job Monitor - Local Run"
echo "=========================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3."
    exit 1
fi

# Install dependencies if needed
if ! python3 -c "import yaml" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip3 install pyyaml requests --quiet
fi

# Run scraper
echo "🔍 Starting job scan..."
echo ""

python3 scraper.py "$@"

# Show output location
echo ""
echo "📄 Results saved to: $SCRIPT_DIR/output/new_jobs.md"
echo ""

# Open results if on Mac
if [[ "$OSTYPE" == "darwin"* ]] && [[ "$*" == *"--open"* ]]; then
    open "$SCRIPT_DIR/output/new_jobs.md"
fi

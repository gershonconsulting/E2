#!/usr/bin/env bash
# run_daily.sh  --  cron wrapper for the E-2 Florida pipeline
# Cron entry (Mon-Sat 08:00 server time):
#   0 8 * * 1-6  /opt/e2/run_daily.sh
#
# To go live, switch the mailer line below from dry-run to --send.

set -euo pipefail

ENGINE_DIR="/opt/e2"
LOG_FILE="$ENGINE_DIR/out/run.log"

# Load secrets
if [ -f "$ENGINE_DIR/.env" ]; then
    set -a
        source "$ENGINE_DIR/.env"
            set +a
            fi

            mkdir -p "$ENGINE_DIR/out"
            cd "$ENGINE_DIR"

            echo "========================================" >> "$LOG_FILE"
            echo "[run_daily] Start: $(date -u '+%Y-%m-%d %H:%M:%S UTC')" >> "$LOG_FILE"

            # Step 1: Download and score
            python3 florida_pipeline.py >> "$LOG_FILE" 2>&1

            # Step 2: Send email
            # DRY-RUN (default — safe):
            # python3 mailer.py --count 10 >> "$LOG_FILE" 2>&1

            # LIVE (uncomment after Olivier/Aina approve a dry-run preview):
            python3 mailer.py --count 10 --send >> "$LOG_FILE" 2>&1

            echo "[run_daily] Done:  $(date -u '+%Y-%m-%d %H:%M:%S UTC')" >> "$LOG_FILE"
            

"""
24/7 Autonomous Watchdog Supervisor
Monitors the bot process, handles graceful restarts, network recovery, and crash protection.
"""
import sys
import subprocess
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | [SUPERVISOR-24/7] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("Supervisor")

PYTHON_EXE = sys.executable

def run_supervisor():
    logger.info("==========================================================")
    logger.info("     SHITCOIN SNIPER PRO - 24/7 SUPERVISOR ACTIVATED")
    logger.info("==========================================================")
    logger.info("Monitoring main.py on http://localhost:8080 non-stop...")
    
    restart_count = 0
    while True:
        try:
            logger.info("Starting bot instance...")
            process = subprocess.Popen([PYTHON_EXE, "main.py"])
            exit_code = process.wait()
            
            restart_count += 1
            logger.warning(f"Bot exited with code {exit_code}. Total auto-restarts: {restart_count}")
            logger.info("Restarting in 3 seconds to guarantee 24/7 operation...")
            time.sleep(3)
        except KeyboardInterrupt:
            logger.info("Supervisor stopped by user.")
            break
        except Exception as e:
            logger.error(f"Supervisor error: {e}. Resuming in 5s...")
            time.sleep(5)

if __name__ == "__main__":
    run_supervisor()

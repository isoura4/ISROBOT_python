"""
Dashboard Manager for ISROBOT V2.

This module handles automatic installation and startup of the Next.js dashboard.
It runs npm install (if needed) and npm run dev in the background when the bot starts.
"""

import os
import subprocess
import threading
import time
from pathlib import Path

from utils.logging_config import get_logger

logger = get_logger(__name__)

# Dashboard directory
DASHBOARD_DIR = Path(__file__).parent / "dashboard"


def is_node_installed() -> bool:
    """Check if Node.js and npm are installed."""
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        node_ok = result.returncode == 0

        result = subprocess.run(
            ["npm", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        npm_ok = result.returncode == 0

        return node_ok and npm_ok
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def is_npm_installed() -> bool:
    """Check if npm dependencies are already installed."""
    node_modules = DASHBOARD_DIR / "node_modules"

    # Check if node_modules exists and has content
    if not node_modules.exists():
        return False

    # Check for at least some dependencies
    next_dir = node_modules / "next"
    react_dir = node_modules / "react"

    return next_dir.exists() and react_dir.exists()


def install_npm_dependencies() -> bool:
    """Install npm dependencies for the dashboard."""
    if not DASHBOARD_DIR.exists():
        logger.error(f"Dashboard directory not found: {DASHBOARD_DIR}")
        return False

    print("📦 Installation des dépendances du dashboard...")
    logger.info("Installing npm dependencies for dashboard...")

    try:
        # Use --legacy-peer-deps to avoid peer dependency conflicts
        result = subprocess.run(
            ["npm", "install", "--legacy-peer-deps"],
            cwd=DASHBOARD_DIR,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )

        if result.returncode != 0:
            logger.error(f"npm install failed: {result.stderr}")
            print(f"❌ Erreur lors de l'installation: {result.stderr[:200]}")
            return False

        print("✅ Dépendances installées avec succès!")
        logger.info("npm dependencies installed successfully")
        return True

    except subprocess.TimeoutExpired:
        logger.error("npm install timed out after 5 minutes")
        print("❌ L'installation a pris trop de temps")
        return False
    except FileNotFoundError:
        logger.error("npm not found - Node.js may not be installed")
        print("❌ npm non trouvé - installez Node.js")
        return False
    except Exception as e:
        logger.error(f"Error installing npm dependencies: {e}")
        print(f"❌ Erreur: {e}")
        return False


def start_dashboard(port: int = 3000) -> subprocess.Popen | None:
    """
    Start the Next.js dashboard in development mode.

    Args:
        port: Port to run the dashboard on (default: 3000)

    Returns:
        The subprocess.Popen object if successful, None otherwise
    """
    if not DASHBOARD_DIR.exists():
        logger.error(f"Dashboard directory not found: {DASHBOARD_DIR}")
        return None

    # Check if node_modules exists, install if not
    if not is_npm_installed():
        if not install_npm_dependencies():
            return None

    print(f"🌐 Démarrage du dashboard sur le port {port}...")
    logger.info(f"Starting dashboard on port {port}")

    try:
        # Set environment variables for the dashboard
        env = os.environ.copy()
        env["PORT"] = str(port)

        # Start npm run dev in the background
        # Use shell=False for security and proper process management
        process = subprocess.Popen(
            ["npm", "run", "dev", "--", "-p", str(port)],
            cwd=DASHBOARD_DIR,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1  # Line buffered
        )

        # Create a thread to read and log output
        def log_output():
            try:
                while process.poll() is None:
                    line = process.stdout.readline()
                    if line:
                        # Filter out noisy lines
                        line = line.strip()
                        if line and not line.startswith("▲"):
                            logger.debug(f"[Dashboard] {line}")
            except Exception as e:
                logger.debug(f"Dashboard output reader stopped: {e}")

        output_thread = threading.Thread(target=log_output, daemon=True)
        output_thread.start()

        # Wait a bit to see if the process starts successfully
        time.sleep(2)

        if process.poll() is not None:
            # Process already exited
            logger.error("Dashboard process exited immediately")
            print("❌ Le dashboard s'est arrêté immédiatement")
            return None

        print(f"✅ Dashboard démarré sur http://localhost:{port}")
        logger.info(f"Dashboard started successfully on port {port}")

        return process

    except FileNotFoundError:
        logger.error("npm not found - Node.js may not be installed")
        print("❌ npm non trouvé - installez Node.js pour utiliser le dashboard")
        return None
    except Exception as e:
        logger.error(f"Error starting dashboard: {e}")
        print(f"❌ Erreur lors du démarrage du dashboard: {e}")
        return None


def stop_dashboard(process: subprocess.Popen) -> None:
    """
    Stop the dashboard process gracefully.

    Args:
        process: The subprocess.Popen object to stop
    """
    if process is None:
        return

    try:
        logger.info("Stopping dashboard...")
        process.terminate()

        # Wait up to 5 seconds for graceful shutdown
        try:
            process.wait(timeout=5)
            logger.info("Dashboard stopped gracefully")
        except subprocess.TimeoutExpired:
            logger.warning("Dashboard did not stop gracefully, killing...")
            process.kill()
            process.wait()
            logger.info("Dashboard killed")

    except Exception as e:
        logger.error(f"Error stopping dashboard: {e}")


def run_dashboard_in_background(port: int = 3000) -> subprocess.Popen | None:
    """
    Run the dashboard setup and start in the background.

    This is the main entry point for starting the dashboard from main.py.
    It handles checking Node.js, installing dependencies, and starting the server.

    Args:
        port: Port to run the dashboard on

    Returns:
        The subprocess.Popen object if successful, None otherwise
    """
    print("\n" + "=" * 50)
    print("🖥️  ISROBOT Dashboard")
    print("=" * 50)

    # Check if Node.js is installed
    if not is_node_installed():
        print("⚠️  Node.js n'est pas installé.")
        print("   Le dashboard ne sera pas disponible.")
        print("   Pour l'installer: https://nodejs.org/")
        print("=" * 50 + "\n")
        logger.warning("Node.js not installed - dashboard disabled")
        return None

    # Start the dashboard
    process = start_dashboard(port)

    if process:
        print(f"   URL: http://localhost:{port}")
        print("=" * 50 + "\n")
    else:
        print("=" * 50 + "\n")

    return process


if __name__ == "__main__":
    # Test the dashboard manager
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3000

    print("Testing dashboard manager...")
    print(f"Node.js installed: {is_node_installed()}")
    print(f"npm dependencies installed: {is_npm_installed()}")

    process = run_dashboard_in_background(port)

    if process:
        print(f"\nDashboard running on http://localhost:{port}")
        print("Press Ctrl+C to stop...")
        try:
            process.wait()
        except KeyboardInterrupt:
            stop_dashboard(process)
            print("\nStopped.")

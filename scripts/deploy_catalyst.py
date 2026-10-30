# ChainC2 Sentinel — Zoho Catalyst CloudScale Automated Deployment & Validation Script
"""Automated deployment, configuration verification, and operational readiness checker for Zoho Catalyst CloudScale.

Usage:
    python scripts/deploy_catalyst.py [--dry-run] [--skip-tests] [--deploy]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chainc2_sentinel.deploy_catalyst")


def check_prerequisites(repo_root: Path) -> bool:
    """Verify Catalyst CLI, configuration files, and dependencies."""
    logger.info("Step 1: Checking Zoho Catalyst CloudScale prerequisites...")

    catalyst_bin = shutil.which("catalyst") or shutil.which("catalyst.cmd")
    if not catalyst_bin:
        logger.error("Catalyst CLI ('catalyst') not found on system PATH.")
        logger.info("Install with: npm install -g zcatalyst-cli")
        return False
    logger.info("✓ Catalyst CLI found at: %s", catalyst_bin)

    required_files = [
        repo_root / "catalyst.json",
        repo_root / "client" / "client-package.json",
        repo_root / "client" / "index.html",
        repo_root / "appsail" / "app-config.json",
        repo_root / "appsail" / "run_appsail.py",
        repo_root / "functions" / "sepolia_cron" / "catalyst-config.json",
        repo_root / "functions" / "sepolia_cron" / "main.py",
    ]

    for rf in required_files:
        if not rf.exists():
            logger.error("Missing required Catalyst configuration: %s", rf)
            return False
        logger.info("✓ Verified configuration file: %s", rf.relative_to(repo_root))

    return True


def check_auth_status() -> tuple[bool, str]:
    """Check CLI login state."""
    logger.info("Step 2: Checking Zoho Catalyst authentication status...")
    try:
        proc = subprocess.run(
            ["catalyst", "whoami"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            shell=True,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        output = (stdout + stderr).strip()
        if "Not logged in" in output or proc.returncode != 0:
            return False, "Not authenticated in Catalyst CLI."
        return True, output
    except Exception as e:
        return False, str(e)


def run_pre_deployment_tests(repo_root: Path) -> bool:
    """Run regression test suites prior to deployment."""
    logger.info("Step 3: Running pre-deployment validation test suites...")
    try:
        res = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_sepolia_monitor.py", "tests/test_catalyst_cloudscale.py", "-v"],
            cwd=str(repo_root),
            timeout=60,
        )
        return res.returncode == 0
    except Exception as e:
        logger.error("Test execution failed: %s", e)
        return False


def execute_deployment(repo_root: Path, dry_run: bool = False) -> bool:
    """Execute Catalyst deployment via CLI."""
    logger.info("Step 4: Executing Zoho Catalyst CloudScale deployment...")
    if dry_run:
        logger.info("[DRY RUN] Would execute: catalyst deploy --only client,appsail,functions:sepolia_cron")
        return True

    cmd = ["catalyst", "deploy"]
    logger.info("Running: %s", " ".join(cmd))
    try:
        proc = subprocess.run(cmd, cwd=str(repo_root), shell=True)
        return proc.returncode == 0
    except Exception as e:
        logger.error("Deployment failed: %s", e)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="ChainC2 Sentinel Zoho Catalyst CloudScale Deployer")
    parser.add_argument("--dry-run", action="store_true", help="Validate configuration without deploying")
    parser.add_argument("--skip-tests", action="store_true", help="Skip pre-deployment tests")
    parser.add_argument("--deploy", action="store_true", help="Execute actual cloud deployment")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent

    print("=" * 70)
    print("  ChainC2 Sentinel — Zoho Catalyst CloudScale Deployment Pipeline")
    print("  Ethereum Sepolia Testnet (11155111) • $250.00 Credit Budget Cap")
    print("=" * 70)

    if not check_prerequisites(repo_root):
        sys.exit(1)

    is_logged_in, auth_msg = check_auth_status()
    if not is_logged_in:
        logger.warning("Authentication Status: %s", auth_msg)
        logger.info("To login, run:")
        logger.info("   catalyst login")
        logger.info("Or without local browser:")
        logger.info("   catalyst login --no-localhost")
        if args.deploy and not args.dry_run:
            logger.error("Cannot proceed with remote deployment without active Catalyst authentication.")
            sys.exit(1)
    else:
        logger.info("✓ Authenticated as: %s", auth_msg)

    if not args.skip_tests:
        if not run_pre_deployment_tests(repo_root):
            logger.error("Pre-deployment tests failed. Aborting deployment.")
            sys.exit(1)
        logger.info("✓ Pre-deployment test suites PASSED.")

    if args.deploy or args.dry_run:
        if not execute_deployment(repo_root, dry_run=args.dry_run):
            logger.error("Deployment step failed.")
            sys.exit(1)
        logger.info("✓ Deployment pipeline completed.")


if __name__ == "__main__":
    main()


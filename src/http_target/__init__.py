# ChainC2 Sentinel — HTTP Target Package
"""Controlled HTTP server that receives synthetic network requests
as the destination endpoint in test scenarios."""

from src.http_target.server import LocalHttpTargetServer

__all__ = ["LocalHttpTargetServer"]

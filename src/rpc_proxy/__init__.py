# ChainC2 Sentinel — RPC Proxy Package
"""JSON-RPC monitoring proxy that records request/response pairs
between the simulated Web3.py client and the local Hardhat node."""

from src.rpc_proxy.proxy import RpcProxy

__all__ = [
    "RpcProxy",
]

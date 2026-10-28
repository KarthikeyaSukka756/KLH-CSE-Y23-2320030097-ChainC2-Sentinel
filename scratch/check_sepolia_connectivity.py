# Stage B: Read-Only Public Sepolia RPC Connectivity Check
"""Executes strictly two read-only JSON-RPC queries (eth_chainId, eth_blockNumber)

against the approved public Sepolia endpoint.
Zero credentials, zero state changes, zero contracts queried.
"""

import json
import sys
import time
import requests

ENDPOINT = "https://ethereum-sepolia-rpc.publicnode.com"
EXPECTED_CHAIN_ID_DEC = 11155111
EXPECTED_CHAIN_ID_HEX = "0xaa36a7"

def run_check():
    headers = {"Content-Type": "application/json"}
    
    print(f"Target Endpoint: {ENDPOINT}")
    print(f"Expected Chain ID: {EXPECTED_CHAIN_ID_DEC} ({EXPECTED_CHAIN_ID_HEX})")
    print("-" * 60)

    # 1. eth_chainId
    req_chain_id = {
        "jsonrpc": "2.0",
        "method": "eth_chainId",
        "params": [],
        "id": 1
    }
    
    t0 = time.perf_counter()
    try:
        resp1 = requests.post(ENDPOINT, json=req_chain_id, headers=headers, timeout=10.0)
        dur1_ms = (time.perf_counter() - t0) * 1000.0
        resp1.raise_for_status()
        data1 = resp1.json()
    except Exception as e:
        print(f"FAILED: eth_chainId request failed: {e}")
        sys.exit(1)

    if "error" in data1:
        print(f"RPC ERROR on eth_chainId: {data1['error']}")
        sys.exit(1)

    raw_chain_id = data1.get("result")
    if not raw_chain_id:
        print(f"ERROR: Empty result for eth_chainId: {data1}")
        sys.exit(1)

    dec_chain_id = int(raw_chain_id, 16)
    hex_chain_id = hex(dec_chain_id).lower()
    chain_id_match = (dec_chain_id == EXPECTED_CHAIN_ID_DEC)

    print(f"1. eth_chainId:")
    print(f"   Status: SUCCESS ({resp1.status_code} OK in {dur1_ms:.2f} ms)")
    print(f"   Raw Returned Value: {raw_chain_id}")
    print(f"   Hex Value: {hex_chain_id}")
    print(f"   Decimal Value: {dec_chain_id}")
    print(f"   Matches Sepolia ({EXPECTED_CHAIN_ID_DEC} / {EXPECTED_CHAIN_ID_HEX}): {chain_id_match}")

    if not chain_id_match:
        print(f"ABORT: Chain ID mismatch! Expected {EXPECTED_CHAIN_ID_DEC}, got {dec_chain_id}. Stopping immediately.")
        sys.exit(1)

    print("-" * 60)

    # 2. eth_blockNumber
    req_block_num = {
        "jsonrpc": "2.0",
        "method": "eth_blockNumber",
        "params": [],
        "id": 2
    }
    
    t0 = time.perf_counter()
    try:
        resp2 = requests.post(ENDPOINT, json=req_block_num, headers=headers, timeout=10.0)
        dur2_ms = (time.perf_counter() - t0) * 1000.0
        resp2.raise_for_status()
        data2 = resp2.json()
    except Exception as e:
        print(f"FAILED: eth_blockNumber request failed: {e}")
        sys.exit(1)

    if "error" in data2:
        print(f"RPC ERROR on eth_blockNumber: {data2['error']}")
        sys.exit(1)

    raw_block_num = data2.get("result")
    if not raw_block_num:
        print(f"ERROR: Empty result for eth_blockNumber: {data2}")
        sys.exit(1)

    dec_block_num = int(raw_block_num, 16)
    hex_block_num = hex(dec_block_num).lower()
    valid_block = dec_block_num >= 0

    print(f"2. eth_blockNumber:")
    print(f"   Status: SUCCESS ({resp2.status_code} OK in {dur2_ms:.2f} ms)")
    print(f"   Raw Returned Value: {raw_block_num}")
    print(f"   Hex Value: {hex_block_num}")
    print(f"   Decimal Value: {dec_block_num}")
    print(f"   Valid Non-Negative Block Number: {valid_block}")

    print("-" * 60)
    print("STAGE B VERIFICATION SUMMARY: ALL READ-ONLY CHECKS PASSED.")

if __name__ == "__main__":
    run_check()

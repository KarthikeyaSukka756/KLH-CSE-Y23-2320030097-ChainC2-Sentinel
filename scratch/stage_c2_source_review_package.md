# ChainC2 Sentinel — Stage C2 Source Review Package
Generated: 2026-10-28
Repository: KarthikeyaSukka756/KLH-CSE-Y23-2320030097-ChainC2-Sentinel
Branch: main
HEAD Commit: 24db27085a3f107858d90e3304d82710e65f541a

This review package provides the complete source code, diffs, and audit artifacts required for independent verification.

---

## 1. Complete Source: src/blockchain/scripts/deploy.js (195 lines)
```javascript
/**
 * ChainC2 Sentinel — Network-Aware Contract Deployment Script
 *
 * Deploys research contracts with strict network-registry isolation:
 *   1. C2DataStore — synthetic research data store
 *   2. BenignDAppContract — legitimate DApp baseline
 *   3. LegitimateDAppContract — decentralized task registry baseline
 *
 * Strict Isolation Guarantees:
 *   - Local deployments (localhost, hardhat, hardhat_docker) write to src/blockchain/deployed-addresses.json
 *   - Sepolia deployments write ONLY to src/blockchain/deployed-addresses.sepolia.json
 *   - Unknown networks or Chain ID mismatches fail safely before deployment
 *   - Addresses and receipts are validated before writing metadata
 *
 * Usage:
 *   npm run deploy          (localhost network, chain 31337)
 *   npm run deploy:local    (hardhat_docker network, chain 31337)
 */

const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

const NETWORK_REGISTRY_MAP = {
  localhost: {
    expectedChainId: 31337n,
    registryFile: "deployed-addresses.json",
    isLocal: true,
  },
  hardhat: {
    expectedChainId: 31337n,
    registryFile: "deployed-addresses.json",
    isLocal: true,
  },
  hardhat_docker: {
    expectedChainId: 31337n,
    registryFile: "deployed-addresses.json",
    isLocal: true,
  },
  sepolia: {
    expectedChainId: 11155111n,
    registryFile: "deployed-addresses.sepolia.json",
    isLocal: false,
  },
};

/**
 * Resolve the authoritative registry file path for a network and assert chain ID alignment.
 *
 * @param {string} networkName - Name of the selected Hardhat network.
 * @param {bigint|number|string} chainId - Chain ID returned by provider.
 * @returns {string} Absolute path to the destination registry JSON.
 */
function resolveRegistryPath(networkName, chainId) {
  const normNetwork = (networkName || "").trim().toLowerCase();
  const config = NETWORK_REGISTRY_MAP[normNetwork];

  if (!config) {
    throw new Error(
      `Deployment aborted: Unsupported network '${networkName}'. ` +
      `Allowed networks: ${Object.keys(NETWORK_REGISTRY_MAP).join(", ")}. ` +
      `Refusing to write deployment addresses to prevent silent local registry corruption.`
    );
  }

  const currentChainId = BigInt(chainId);
  if (currentChainId !== config.expectedChainId) {
    throw new Error(
      `Deployment aborted: Chain ID mismatch for network '${networkName}'. ` +
      `Expected chain ID ${config.expectedChainId}, but connected provider returned ${currentChainId}. ` +
      `Refusing to proceed to prevent cross-network state corruption.`
    );
  }

  return path.join(__dirname, "..", config.registryFile);
}

/**
 * Validate that deployed contracts have valid Ethereum addresses before persisting.
 *
 * @param {Record<string, { address: string }>} contracts - Mapping of contract names to deployment data.
 */
function validateDeployedAddresses(contracts) {
  const addressRegex = /^0x[0-9a-fA-F]{40}$/;
  const required = ["C2DataStore", "BenignDAppContract", "LegitimateDAppContract"];

  for (const name of required) {
    const entry = contracts[name];
    if (!entry || !entry.address || !addressRegex.test(entry.address)) {
      throw new Error(
        `Deployment validation failed: Contract '${name}' missing valid Ethereum address.`
      );
    }
  }
}

async function main() {
  console.log("=".repeat(60));
  console.log("ChainC2 Sentinel — Network-Aware Contract Deployment");
  console.log("Network:", hre.network.name);
  console.log("=".repeat(60));

  // 1. Validate network and chain ID prior to deployment
  const network = await hre.ethers.provider.getNetwork();
  const chainId = network.chainId;
  const targetRegistryPath = resolveRegistryPath(hre.network.name, chainId);

  console.log("Target Network:        ", hre.network.name);
  console.log("Validated Chain ID:    ", chainId.toString());
  console.log("Target Registry Path:  ", targetRegistryPath);

  const [deployer] = await hre.ethers.getSigners();
  if (!deployer) {
    throw new Error("Deployment aborted: No signer/deployer account configured.");
  }
  console.log("\nDeployer address:      ", deployer.address);

  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("Deployer balance:      ", hre.ethers.formatEther(balance), "ETH\n");

  if (balance === 0n && !NETWORK_REGISTRY_MAP[hre.network.name]?.isLocal) {
    throw new Error(
      `Deployment aborted: Deployer ${deployer.address} has 0 ETH on public network '${hre.network.name}'.`
    );
  }

  // 2. Deploy C2DataStore
  console.log("Deploying C2DataStore...");
  const C2DataStore = await hre.ethers.getContractFactory("C2DataStore");
  const c2DataStore = await C2DataStore.deploy();
  await c2DataStore.waitForDeployment();
  const c2Address = await c2DataStore.getAddress();
  console.log("  C2DataStore deployed at:", c2Address);

  // 3. Deploy BenignDAppContract
  const initialMessage = "ChainC2 Sentinel — Benign DApp Active";
  console.log("\nDeploying BenignDAppContract...");
  const BenignDAppContract = await hre.ethers.getContractFactory("BenignDAppContract");
  const benignDApp = await BenignDAppContract.deploy(initialMessage);
  await benignDApp.waitForDeployment();
  const benignAddress = await benignDApp.getAddress();
  console.log("  BenignDAppContract deployed at:", benignAddress);

  // 4. Deploy LegitimateDAppContract (Scenario C)
  console.log("\nDeploying LegitimateDAppContract (Scenario C)...");
  const LegitimateDAppContract = await hre.ethers.getContractFactory("LegitimateDAppContract");
  const legitimateDApp = await LegitimateDAppContract.deploy();
  await legitimateDApp.waitForDeployment();
  const legitimateAddress = await legitimateDApp.getAddress();
  console.log("  LegitimateDAppContract deployed at:", legitimateAddress);

  // 5. Validate deployment output
  const deployedContracts = {
    C2DataStore: {
      address: c2Address,
      name: "C2DataStore",
    },
    BenignDAppContract: {
      address: benignAddress,
      name: "BenignDAppContract",
      constructorArgs: {
        initialMessage: initialMessage,
      },
    },
    LegitimateDAppContract: {
      address: legitimateAddress,
      name: "LegitimateDAppContract",
    },
  };

  validateDeployedAddresses(deployedContracts);

  const addresses = {
    network: hre.network.name,
    chainId: chainId.toString(),
    status: "DEPLOYED",
    deployedAt: new Date().toISOString(),
    deployer: deployer.address,
    contracts: deployedContracts,
  };

  fs.writeFileSync(targetRegistryPath, JSON.stringify(addresses, null, 2));
  console.log("\n[SUCCESS] Deployed addresses written to:", targetRegistryPath);

  console.log("\n" + "=".repeat(60));
  console.log("Deployment complete.");
  console.log("=".repeat(60));
}

if (require.main === module) {
  main()
    .then(() => process.exit(0))
    .catch((error) => {
      console.error("Deployment failed:", error.message || error);
      process.exit(1);
    });
}

module.exports = {
  NETWORK_REGISTRY_MAP,
  resolveRegistryPath,
  validateDeployedAddresses,
  main,
};
```

---

## 2. Complete Source: src/blockchain/test/deployment_safeguards.test.js (84 lines)
```javascript
const { expect } = require("chai");
const path = require("path");
const {
  NETWORK_REGISTRY_MAP,
  resolveRegistryPath,
  validateDeployedAddresses,
} = require("../scripts/deploy");

describe("Stage C1: Deployment Safeguards and Registry Routing", function () {
  const localRegistry = path.join(__dirname, "..", "deployed-addresses.json");
  const sepoliaRegistry = path.join(__dirname, "..", "deployed-addresses.sepolia.json");

  describe("resolveRegistryPath", function () {
    it("routes 'localhost' with chainId 31337 to local deployed-addresses.json", function () {
      const resolved = resolveRegistryPath("localhost", 31337);
      expect(resolved).to.equal(localRegistry);
    });

    it("routes 'hardhat' with chainId 31337 to local deployed-addresses.json", function () {
      const resolved = resolveRegistryPath("hardhat", "31337");
      expect(resolved).to.equal(localRegistry);
    });

    it("routes 'hardhat_docker' with chainId 31337 to local deployed-addresses.json", function () {
      const resolved = resolveRegistryPath("hardhat_docker", 31337n);
      expect(resolved).to.equal(localRegistry);
    });

    it("routes 'sepolia' with chainId 11155111 strictly to deployed-addresses.sepolia.json", function () {
      const resolved = resolveRegistryPath("sepolia", 11155111);
      expect(resolved).to.equal(sepoliaRegistry);
      expect(resolved).to.not.equal(localRegistry);
    });

    it("rejects unknown network and prevents silent local registry fallback", function () {
      expect(() => resolveRegistryPath("mainnet", 1)).to.throw(
        /Unsupported network 'mainnet'/
      );
      expect(() => resolveRegistryPath("goerli", 5)).to.throw(
        /Unsupported network 'goerli'/
      );
    });

    it("aborts when chain ID does not match network expectations (Sepolia with local chainId)", function () {
      expect(() => resolveRegistryPath("sepolia", 31337)).to.throw(
        /Chain ID mismatch for network 'sepolia'/
      );
    });

    it("aborts when chain ID does not match network expectations (Localhost with Sepolia chainId)", function () {
      expect(() => resolveRegistryPath("localhost", 11155111)).to.throw(
        /Chain ID mismatch for network 'localhost'/
      );
    });
  });

  describe("validateDeployedAddresses", function () {
    it("passes when all three contracts have valid Ethereum addresses", function () {
      const validContracts = {
        C2DataStore: { address: "0x5FbDB2315678afecb367f032d93F642f64180aa3" },
        BenignDAppContract: { address: "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512" },
        LegitimateDAppContract: { address: "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0" },
      };
      expect(() => validateDeployedAddresses(validContracts)).to.not.throw();
    });

    it("rejects when any required contract is missing", function () {
      const missingOne = {
        C2DataStore: { address: "0x5FbDB2315678afecb367f032d93F642f64180aa3" },
        BenignDAppContract: { address: "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512" },
      };
      expect(() => validateDeployedAddresses(missingOne)).to.throw(
        /Contract 'LegitimateDAppContract' missing/
      );
    });

    it("rejects invalid Ethereum address format", function () {
      const invalidAddr = {
        C2DataStore: { address: "0x5FbDB2315678afecb367f032d93F642f64180aa3" },
        BenignDAppContract: { address: "not-an-address" },
        LegitimateDAppContract: { address: "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0" },
      };
      expect(() => validateDeployedAddresses(invalidAddr)).to.throw(
        /Contract 'BenignDAppContract' missing valid Ethereum address/
      );
    });
  });
});
```

---

## 3. Complete Source: src/blockchain/hardhat.config.js (43 lines)
```javascript
require("@nomicfoundation/hardhat-toolbox");

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.24",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
    },
  },
  networks: {
    // Default Hardhat network (in-process, used by `hardhat test`)
    hardhat: {
      chainId: 31337,
    },
    // For connecting to the Hardhat node running inside Docker
    hardhat_docker: {
      url: "http://hardhat-node:8545",
      chainId: 31337,
    },
    // For connecting to a locally-running Hardhat node (outside Docker)
    localhost: {
      url: "http://127.0.0.1:8545",
      chainId: 31337,
    },
    // Isolated Sepolia public-testnet configuration (requires explicit --network sepolia)
    sepolia: {
      url: process.env.SEPOLIA_RPC_URL || "https://ethereum-sepolia-rpc.publicnode.com",
      chainId: 11155111,
      accounts: process.env.SEPOLIA_PRIVATE_KEY ? [process.env.SEPOLIA_PRIVATE_KEY] : [],
    },
  },
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts",
  },
};
```

---

## 4. Complete Source: src/blockchain/deployment.py (109 lines)
```python
# ChainC2 Sentinel — Contract Deployment Resolution
"""Authoritative resolution and validation of locally deployed smart contracts.

Strictly validates contract addresses from deployed-addresses.json
to prevent silent configuration inversions or hardcoded address drift.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger("chainc2_sentinel.blockchain.deployment")

ETH_ADDRESS_REGEX = re.compile(r"^0x[0-9a-fA-F]{40}$")
DEFAULT_DEPLOYMENT_PATH = Path(__file__).resolve().parent / "deployed-addresses.json"
SEPOLIA_DEPLOYMENT_PATH = Path(__file__).resolve().parent / "deployed-addresses.sepolia.json"

NETWORK_DEPLOYMENT_PATHS: dict[str, Path] = {
    "localhost": DEFAULT_DEPLOYMENT_PATH,
    "hardhat": DEFAULT_DEPLOYMENT_PATH,
    "sepolia": SEPOLIA_DEPLOYMENT_PATH,
}


class DeploymentResolutionError(RuntimeError):
    """Raised when contract deployment data is missing, malformed, or invalid."""
    pass


def get_deployment_path_for_network(network: str = "localhost") -> Path:
    """Resolve the authoritative deployment address registry path for a specified network.

    Args:
        network: Network identifier (e.g., 'localhost', 'hardhat', 'sepolia'). Defaults to 'localhost'.

    Returns:
        Path to the network's deployment JSON file.

    Raises:
        DeploymentResolutionError: If the network is unknown, preventing silent fallback.
    """
    norm = network.strip().lower()
    if norm not in NETWORK_DEPLOYMENT_PATHS:
        raise DeploymentResolutionError(
            f"Unknown network '{network}'. Known networks: {list(NETWORK_DEPLOYMENT_PATHS.keys())}"
        )
    return NETWORK_DEPLOYMENT_PATHS[norm]


def load_deployed_addresses(path: Optional[Path | str] = None) -> dict[str, str]:
    """Load and strictly validate contract addresses from authoritative deployment JSON.

    Args:
        path: Optional path to deployed-addresses JSON. Defaults to src/blockchain/deployed-addresses.json.

    Returns:
        Mapping of contract name to validated Ethereum address string.

    Raises:
        DeploymentResolutionError: If file is missing, JSON is invalid, unconfigured, or required contracts/addresses are missing.
    """
    file_path = Path(path) if path is not None else DEFAULT_DEPLOYMENT_PATH
    if not file_path.is_file():
        raise DeploymentResolutionError(
            f"Deployment address file not found: {file_path}. Ensure 'npm run deploy' was executed."
        )

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise DeploymentResolutionError(
            f"Failed to parse deployment JSON at {file_path}: {e}"
        ) from e

    status = data.get("status")
    if status == "UNCONFIGURED":
        notice = data.get("notice", "Deployment not yet performed.")
        net = data.get("network", "unknown")
        raise DeploymentResolutionError(
            f"Deployment registry for network '{net}' at {file_path} is UNCONFIGURED. {notice}"
        )

    contracts = data.get("contracts")
    if not isinstance(contracts, dict):
        raise DeploymentResolutionError(
            f"Missing or invalid 'contracts' dictionary in {file_path}"
        )

    required_contracts = ["C2DataStore", "BenignDAppContract", "LegitimateDAppContract"]
    resolved: dict[str, str] = {}

    for name in required_contracts:
        if name not in contracts:
            raise DeploymentResolutionError(
                f"Required contract '{name}' missing from deployment artifact: {file_path}"
            )
        entry = contracts[name]
        if not isinstance(entry, dict) or "address" not in entry:
            raise DeploymentResolutionError(
                f"Contract '{name}' entry missing 'address' field in {file_path}"
            )
        addr = entry["address"]
        if not isinstance(addr, str) or not ETH_ADDRESS_REGEX.match(addr):
            raise DeploymentResolutionError(
                f"Invalid Ethereum address format for '{name}' in {file_path}: '{addr}'"
            )
        resolved[name] = addr

    logger.debug("Successfully resolved deployed contract addresses: %s", resolved)
    return resolved
```

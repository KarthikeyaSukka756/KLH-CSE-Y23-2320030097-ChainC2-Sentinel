/**
 * ChainC2 Sentinel — Network-Aware Contract Deployment Script
 *
 * Deploys research contracts with strict network-registry isolation,
 * verified on-chain bytecode assertions, and atomic filesystem persistence.
 *
 * Deployed Contracts:
 *   1. C2DataStore — synthetic research data store
 *   2. BenignDAppContract — legitimate DApp baseline
 *   3. LegitimateDAppContract — decentralized task registry baseline
 *
 * Strict Isolation & Safety Guarantees:
 *   - Local deployments (localhost, hardhat, hardhat_docker) write to src/blockchain/deployed-addresses.json
 *   - Sepolia deployments write ONLY to src/blockchain/deployed-addresses.sepolia.json
 *   - Unknown networks or Chain ID mismatches fail safely BEFORE deployment
 *   - Deployments verify mined transaction receipts (status === 1) and non-empty bytecode (eth_getCode)
 *   - Registry writes use temporary files and atomic rename to prevent partial/corrupted registries
 *   - Any failure during deployment or verification aborts immediately without touching existing registries
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

/**
 * Rigorously verify contract deployment receipt and on-chain bytecode.
 *
 * @param {import("ethers").Contract} contract - Deployed contract instance.
 * @param {string} contractName - Name of contract for reporting.
 * @param {import("ethers").Provider} provider - Ethers provider.
 * @param {bigint|string|number} expectedChainId - Expected network chain ID.
 * @returns {Promise<{ address: string, txHash: string, blockNumber: number, gasUsed: string }>}
 */
async function verifyContractDeployment(contract, contractName, provider, expectedChainId) {
  const address = await contract.getAddress();
  const addressRegex = /^0x[0-9a-fA-F]{40}$/;
  if (!address || !addressRegex.test(address)) {
    throw new Error(`Verification failed: ${contractName} returned invalid address '${address}'`);
  }

  // 1. Verify deployment transaction receipt
  const deploymentTx = contract.deploymentTransaction();
  if (!deploymentTx) {
    throw new Error(`Verification failed: ${contractName} has no associated deployment transaction.`);
  }

  const receipt = await deploymentTx.wait(1);
  if (!receipt) {
    throw new Error(`Verification failed: No deployment receipt received for ${contractName}.`);
  }

  const statusNum = Number(receipt.status);
  if (statusNum !== 1) {
    throw new Error(
      `Verification failed: Deployment transaction for ${contractName} reverted or failed on-chain (status ${receipt.status}, hash: ${receipt.hash}).`
    );
  }

  // 2. Verify chain ID alignment
  const network = await provider.getNetwork();
  if (BigInt(network.chainId) !== BigInt(expectedChainId)) {
    throw new Error(
      `Verification failed: Provider chain ID ${network.chainId} does not match expected chain ID ${expectedChainId}.`
    );
  }

  // 3. Verify on-chain bytecode exists and is non-empty
  const code = await provider.getCode(address);
  if (!code || code === "0x" || code === "0x0") {
    throw new Error(
      `Verification failed: No deployed bytecode found at ${address} for ${contractName} on chain ${expectedChainId}.`
    );
  }

  return {
    address,
    txHash: receipt.hash,
    blockNumber: receipt.blockNumber,
    gasUsed: receipt.gasUsed ? receipt.gasUsed.toString() : "0",
  };
}

/**
 * Safely persist registry JSON using a temporary file in the destination directory and atomic rename.
 *
 * NOTE ON ATOMICITY:
 * Atomic replacement over an existing file via fs.renameSync is guaranteed on POSIX filesystems
 * within the same directory/mount. On platforms where the runtime/OS cannot guarantee atomic
 * replacement over an existing file (such as Windows returning EPERM when the destination file exists),
 * this function deliberately DOES NOT fall back to a non-atomic copy-and-delete approach.
 * Instead, it safely aborts and guarantees that any pre-existing valid registry file remains completely intact.
 *
 * @param {string} targetPath - Absolute path to final registry file.
 * @param {object} data - JavaScript object to serialize.
 */
function saveRegistryAtomic(targetPath, data) {
  const targetDir = path.dirname(targetPath);
  const targetFilename = path.basename(targetPath);
  const randomSuffix = `${Date.now()}_${process.pid}_${Math.random().toString(36).slice(2, 8)}`;
  const tempPath = path.join(targetDir, `.${targetFilename}.tmp.${randomSuffix}`);

  try {
    const serialized = JSON.stringify(data, null, 2) + "\n";
    // 1. Write completely to temp file in destination directory
    fs.writeFileSync(tempPath, serialized, { encoding: "utf8", mode: 0o644 });

    // 2. Verify temp file exists and has non-zero size
    const stat = fs.statSync(tempPath);
    if (stat.size === 0) {
      throw new Error(`Atomic write aborted: Temp file ${tempPath} is empty.`);
    }

    // 3. Atomically replace target path via renameSync.
    // Genuinely atomic on POSIX filesystems within the same directory.
    // On platforms where atomic replacement over an existing file is unsupported (e.g. Windows EPERM),
    // we fail safely rather than using a non-atomic copy-and-truncate fallback.
    fs.renameSync(tempPath, targetPath);
  } catch (err) {
    // Clean up temporary file without modifying or corrupting the existing targetPath
    try {
      if (fs.existsSync(tempPath)) {
        fs.unlinkSync(tempPath);
      }
    } catch (_) {}
    throw new Error(`Failed to atomically save registry to ${targetPath}: ${err.message}`);
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
  const expectedChainId = NETWORK_REGISTRY_MAP[hre.network.name.trim().toLowerCase()].expectedChainId;

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

  // 2. Deploy and verify C2DataStore
  console.log("Deploying C2DataStore...");
  const C2DataStoreFactory = await hre.ethers.getContractFactory("C2DataStore");
  const c2Contract = await C2DataStoreFactory.deploy();
  await c2Contract.waitForDeployment();
  const c2Verified = await verifyContractDeployment(c2Contract, "C2DataStore", hre.ethers.provider, expectedChainId);
  console.log("  C2DataStore deployed & verified at:", c2Verified.address, `(tx: ${c2Verified.txHash}, block: ${c2Verified.blockNumber})`);

  // 3. Deploy and verify BenignDAppContract
  const initialMessage = "ChainC2 Sentinel — Benign DApp Active";
  console.log("\nDeploying BenignDAppContract...");
  const BenignFactory = await hre.ethers.getContractFactory("BenignDAppContract");
  const benignContract = await BenignFactory.deploy(initialMessage);
  await benignContract.waitForDeployment();
  const benignVerified = await verifyContractDeployment(benignContract, "BenignDAppContract", hre.ethers.provider, expectedChainId);
  console.log("  BenignDAppContract deployed & verified at:", benignVerified.address, `(tx: ${benignVerified.txHash}, block: ${benignVerified.blockNumber})`);

  // 4. Deploy and verify LegitimateDAppContract (Scenario C)
  console.log("\nDeploying LegitimateDAppContract (Scenario C)...");
  const LegitFactory = await hre.ethers.getContractFactory("LegitimateDAppContract");
  const legitContract = await LegitFactory.deploy();
  await legitContract.waitForDeployment();
  const legitVerified = await verifyContractDeployment(legitContract, "LegitimateDAppContract", hre.ethers.provider, expectedChainId);
  console.log("  LegitimateDAppContract deployed & verified at:", legitVerified.address, `(tx: ${legitVerified.txHash}, block: ${legitVerified.blockNumber})`);

  // 5. Structure and validate deployment metadata
  const deployedContracts = {
    C2DataStore: {
      address: c2Verified.address,
      name: "C2DataStore",
      txHash: c2Verified.txHash,
      blockNumber: c2Verified.blockNumber,
      gasUsed: c2Verified.gasUsed,
    },
    BenignDAppContract: {
      address: benignVerified.address,
      name: "BenignDAppContract",
      txHash: benignVerified.txHash,
      blockNumber: benignVerified.blockNumber,
      gasUsed: benignVerified.gasUsed,
      constructorArgs: {
        initialMessage: initialMessage,
      },
    },
    LegitimateDAppContract: {
      address: legitVerified.address,
      name: "LegitimateDAppContract",
      txHash: legitVerified.txHash,
      blockNumber: legitVerified.blockNumber,
      gasUsed: legitVerified.gasUsed,
    },
  };

  validateDeployedAddresses(deployedContracts);

  const registryPayload = {
    network: hre.network.name,
    chainId: chainId.toString(),
    status: "DEPLOYED",
    deployedAt: new Date().toISOString(),
    deployer: deployer.address,
    contracts: deployedContracts,
  };

  // 6. Atomically persist verified metadata
  try {
    saveRegistryAtomic(targetRegistryPath, registryPayload);
    console.log("\n[SUCCESS] Deployed addresses atomically written to:", targetRegistryPath);
  } catch (saveError) {
    throw new Error(
      `Deployment partially failed: Contracts mined on-chain, but registry save failed: ${saveError.message}. ` +
      `Contracts may be active on-chain while registry was NOT updated. Do not assume registry reflects on-chain state.`
    );
  }

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
  verifyContractDeployment,
  saveRegistryAtomic,
  main,
};

/**
 * ChainC2 Sentinel — Contract Deployment Script
 *
 * Deploys both test contracts to the local Hardhat network:
 *   1. C2DataStore — synthetic research data store
 *   2. BenignDAppContract — legitimate DApp baseline
 *
 * Outputs deployed addresses to stdout and writes them to a JSON file
 * for consumption by the Python telemetry collectors.
 *
 * Usage:
 *   npm run deploy          (localhost network)
 *   npm run deploy:local    (hardhat_docker network)
 */

const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("=".repeat(60));
  console.log("ChainC2 Sentinel — Contract Deployment");
  console.log("Network:", hre.network.name);
  console.log("=".repeat(60));

  const [deployer] = await hre.ethers.getSigners();
  console.log("\nDeployer address:", deployer.address);

  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("Deployer balance:", hre.ethers.formatEther(balance), "ETH\n");

  // --- Deploy C2DataStore ---
  console.log("Deploying C2DataStore...");
  const C2DataStore = await hre.ethers.getContractFactory("C2DataStore");
  const c2DataStore = await C2DataStore.deploy();
  await c2DataStore.waitForDeployment();
  const c2Address = await c2DataStore.getAddress();
  console.log("  C2DataStore deployed at:", c2Address);

  // --- Deploy BenignDAppContract ---
  const initialMessage = "ChainC2 Sentinel — Benign DApp Active";
  console.log("\nDeploying BenignDAppContract...");
  const BenignDAppContract = await hre.ethers.getContractFactory(
    "BenignDAppContract"
  );
  const benignDApp = await BenignDAppContract.deploy(initialMessage);
  await benignDApp.waitForDeployment();
  const benignAddress = await benignDApp.getAddress();
  console.log("  BenignDAppContract deployed at:", benignAddress);

  // --- Deploy LegitimateDAppContract (Scenario C) ---
  console.log("\nDeploying LegitimateDAppContract (Scenario C)...");
  const LegitimateDAppContract = await hre.ethers.getContractFactory(
    "LegitimateDAppContract"
  );
  const legitimateDApp = await LegitimateDAppContract.deploy();
  await legitimateDApp.waitForDeployment();
  const legitimateAddress = await legitimateDApp.getAddress();
  console.log("  LegitimateDAppContract deployed at:", legitimateAddress);

  // --- Write deployed addresses to JSON ---
  const addresses = {
    network: hre.network.name,
    chainId: (await hre.ethers.provider.getNetwork()).chainId.toString(),
    deployedAt: new Date().toISOString(),
    deployer: deployer.address,
    contracts: {
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
    },
  };

  const outputPath = path.join(__dirname, "..", "deployed-addresses.json");
  fs.writeFileSync(outputPath, JSON.stringify(addresses, null, 2));
  console.log("\nDeployed addresses written to:", outputPath);

  console.log("\n" + "=".repeat(60));
  console.log("Deployment complete.");
  console.log("=".repeat(60));
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("Deployment failed:", error);
    process.exit(1);
  });

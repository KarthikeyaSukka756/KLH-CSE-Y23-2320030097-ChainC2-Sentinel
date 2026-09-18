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
  },
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts",
  },
};

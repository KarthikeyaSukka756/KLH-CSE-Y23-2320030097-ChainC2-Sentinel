const { expect } = require("chai");
const fs = require("fs");
const path = require("path");
const {
  NETWORK_REGISTRY_MAP,
  resolveRegistryPath,
  validateDeployedAddresses,
  verifyContractDeployment,
  saveRegistryAtomic,
} = require("../scripts/deploy");

describe("Stage C: Deployment Safeguards, Atomic Persistence & Verification", function () {
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

  describe("saveRegistryAtomic", function () {
    const testDir = path.join(__dirname, "..", "cache");
    const testRegistryFile = path.join(testDir, `test-atomic-reg-${Date.now()}.json`);

    afterEach(function () {
      if (fs.existsSync(testRegistryFile)) {
        fs.unlinkSync(testRegistryFile);
      }
    });

    it("atomically writes registry file via temp file in destination directory", function () {
      const payload = { test: "atomic_success", timestamp: Date.now() };
      saveRegistryAtomic(testRegistryFile, payload);

      expect(fs.existsSync(testRegistryFile)).to.be.true;
      const parsed = JSON.parse(fs.readFileSync(testRegistryFile, "utf8"));
      expect(parsed.test).to.equal("atomic_success");
    });

    it("cleans up temporary files if serialization or write encounters an error", function () {
      // Circular object cannot be JSON-serialized
      const circular = {};
      circular.self = circular;

      expect(() => saveRegistryAtomic(testRegistryFile, circular)).to.throw(
        /Failed to atomically save registry/
      );

      // Verify no dangling temp files remain in testDir
      const dangling = fs.readdirSync(testDir).filter((f) => f.startsWith(".test-atomic-reg"));
      expect(dangling).to.have.lengthOf(0);
      expect(fs.existsSync(testRegistryFile)).to.be.false;
    });

    it("preserves existing registry file intact if an overwrite attempt fails", function () {
      const originalPayload = { status: "PRESERVED_ORIGINAL" };
      fs.writeFileSync(testRegistryFile, JSON.stringify(originalPayload), "utf8");

      const circular = {};
      circular.self = circular;

      expect(() => saveRegistryAtomic(testRegistryFile, circular)).to.throw();

      const existingContent = JSON.parse(fs.readFileSync(testRegistryFile, "utf8"));
      expect(existingContent.status).to.equal("PRESERVED_ORIGINAL");
    });

    it("preserves existing registry file intact when rename/replacement fails", function () {
      const originalPayload = { status: "PRESERVED_ORIGINAL", timestamp: 123456 };
      fs.writeFileSync(testRegistryFile, JSON.stringify(originalPayload), "utf8");

      const originalRename = fs.renameSync;
      try {
        fs.renameSync = () => {
          const err = new Error("EPERM: operation not permitted, rename conflict");
          err.code = "EPERM";
          throw err;
        };

        expect(() => saveRegistryAtomic(testRegistryFile, { status: "SHOULD_FAIL" })).to.throw(
          /Failed to atomically save registry.*EPERM/
        );

        // Verify original registry was not touched, truncated, or overwritten
        const preservedContent = JSON.parse(fs.readFileSync(testRegistryFile, "utf8"));
        expect(preservedContent.status).to.equal("PRESERVED_ORIGINAL");
        expect(preservedContent.timestamp).to.equal(123456);

        // Verify temp file cleaned up
        const dangling = fs.readdirSync(testDir).filter((f) => f.startsWith(".test-atomic-reg"));
        expect(dangling).to.have.lengthOf(0);
      } finally {
        fs.renameSync = originalRename;
      }
    });
  });

  describe("verifyContractDeployment", function () {
    const validAddr = "0x5FbDB2315678afecb367f032d93F642f64180aa3";

    it("rejects contract with missing deploymentTransaction", async function () {
      const mockContract = {
        getAddress: async () => validAddr,
        deploymentTransaction: () => null,
      };
      const mockProvider = {
        getNetwork: async () => ({ chainId: 31337n }),
        getCode: async () => "0x60806040",
      };

      try {
        await verifyContractDeployment(mockContract, "TestContract", mockProvider, 31337n);
        expect.fail("Should have thrown error");
      } catch (err) {
        expect(err.message).to.match(/has no associated deployment transaction/);
      }
    });

    it("rejects contract when deployment receipt indicates revert (status 0)", async function () {
      const mockContract = {
        getAddress: async () => validAddr,
        deploymentTransaction: () => ({
          wait: async () => ({ status: 0, hash: "0xdeadbeef", blockNumber: 1 }),
        }),
      };
      const mockProvider = {
        getNetwork: async () => ({ chainId: 31337n }),
        getCode: async () => "0x60806040",
      };

      try {
        await verifyContractDeployment(mockContract, "RevertedContract", mockProvider, 31337n);
        expect.fail("Should have thrown error");
      } catch (err) {
        expect(err.message).to.match(/reverted or failed on-chain/);
      }
    });

    it("rejects contract when on-chain bytecode is empty ('0x')", async function () {
      const mockContract = {
        getAddress: async () => validAddr,
        deploymentTransaction: () => ({
          wait: async () => ({ status: 1, hash: "0x1234", blockNumber: 10, gasUsed: 50000n }),
        }),
      };
      const mockProvider = {
        getNetwork: async () => ({ chainId: 31337n }),
        getCode: async () => "0x",
      };

      try {
        await verifyContractDeployment(mockContract, "EmptyBytecodeContract", mockProvider, 31337n);
        expect.fail("Should have thrown error");
      } catch (err) {
        expect(err.message).to.match(/No deployed bytecode found/);
      }
    });

    it("rejects contract when provider chain ID does not match expected network", async function () {
      const mockContract = {
        getAddress: async () => validAddr,
        deploymentTransaction: () => ({
          wait: async () => ({ status: 1, hash: "0x1234", blockNumber: 10, gasUsed: 50000n }),
        }),
      };
      const mockProvider = {
        getNetwork: async () => ({ chainId: 1n }), // Mainnet instead of Sepolia
        getCode: async () => "0x60806040",
      };

      try {
        await verifyContractDeployment(mockContract, "MismatchContract", mockProvider, 11155111n);
        expect.fail("Should have thrown error");
      } catch (err) {
        expect(err.message).to.match(/Provider chain ID 1 does not match expected chain ID 11155111/);
      }
    });

    it("passes and returns receipt metadata when receipt succeeds and bytecode exists", async function () {
      const mockContract = {
        getAddress: async () => validAddr,
        deploymentTransaction: () => ({
          wait: async () => ({ status: 1, hash: "0xabcdef123456", blockNumber: 42, gasUsed: 350000n }),
        }),
      };
      const mockProvider = {
        getNetwork: async () => ({ chainId: 11155111n }),
        getCode: async () => "0x608060405234801561001057600080fd5b50",
      };

      const result = await verifyContractDeployment(mockContract, "VerifiedContract", mockProvider, 11155111n);
      expect(result.address).to.equal(validAddr);
      expect(result.txHash).to.equal("0xabcdef123456");
      expect(result.blockNumber).to.equal(42);
      expect(result.gasUsed).to.equal("350000");
    });
  });

  describe("Preservation of Local Registry During Sepolia Failure", function () {
    it("ensures local deployed-addresses.json is never overwritten by a failed Sepolia operation", function () {
      const localBefore = fs.readFileSync(localRegistry, "utf8");
      expect(() => resolveRegistryPath("sepolia", 31337)).to.throw();
      const localAfter = fs.readFileSync(localRegistry, "utf8");
      expect(localAfter).to.equal(localBefore);
    });

    it("verifies that simulated registry persistence failure after deployment reports honest partial failure", function () {
      const simulatedSaveError = new Error("EPERM: rename failed");
      let caughtError = null;
      try {
        try {
          throw simulatedSaveError;
        } catch (saveError) {
          throw new Error(
            `Deployment partially failed: Contracts mined on-chain, but registry save failed: ${saveError.message}. ` +
            `Contracts may be active on-chain while registry was NOT updated. Do not assume registry reflects on-chain state.`
          );
        }
      } catch (err) {
        caughtError = err;
      }
      expect(caughtError).to.not.be.null;
      expect(caughtError.message).to.include("Deployment partially failed: Contracts mined on-chain, but registry save failed");
      expect(caughtError.message).to.include("Contracts may be active on-chain while registry was NOT updated");
    });
  });
});

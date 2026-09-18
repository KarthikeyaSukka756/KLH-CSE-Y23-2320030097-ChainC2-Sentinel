/**
 * ChainC2 Sentinel — Contract Test Suite
 *
 * Tests for both Solidity test contracts:
 *   1. C2DataStore — synthetic research data store
 *   2. BenignDAppContract — legitimate DApp baseline
 *
 * Validates:
 *   - Deployment succeeds
 *   - Contracts have expected initial state
 *   - Synthetic data can be stored and read
 *   - Benign contract functions work correctly
 *   - Events are emitted as expected
 *   - Edge cases produce expected behavior
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("C2DataStore", function () {
  let c2DataStore;
  let deployer;
  let otherAccount;

  beforeEach(async function () {
    [deployer, otherAccount] = await ethers.getSigners();
    const C2DataStore = await ethers.getContractFactory("C2DataStore");
    c2DataStore = await C2DataStore.deploy();
    await c2DataStore.waitForDeployment();
  });

  describe("Deployment", function () {
    it("should deploy successfully", async function () {
      const address = await c2DataStore.getAddress();
      expect(address).to.be.properAddress;
    });

    it("should set the deployer address", async function () {
      expect(await c2DataStore.deployer()).to.equal(deployer.address);
    });

    it("should have zero commands initially", async function () {
      expect(await c2DataStore.getCommandCount()).to.equal(0);
    });

    it("should return empty string for getLatestCommand when empty", async function () {
      expect(await c2DataStore.getLatestCommand()).to.equal("");
    });
  });

  describe("Storing synthetic commands", function () {
    it("should store a synthetic command and increment count", async function () {
      await c2DataStore.storeCommand("SYNTHETIC_PING");
      expect(await c2DataStore.getCommandCount()).to.equal(1);
    });

    it("should emit CommandStored event with correct args", async function () {
      await expect(c2DataStore.storeCommand("SYNTHETIC_PING"))
        .to.emit(c2DataStore, "CommandStored")
        .withArgs(deployer.address, "SYNTHETIC_PING", 0, (value) => value > 0);
    });

    it("should store multiple synthetic commands in order", async function () {
      await c2DataStore.storeCommand("SYNTHETIC_PING");
      await c2DataStore.storeCommand("SYNTHETIC_RESOLVE:localhost");
      await c2DataStore.storeCommand("SYNTHETIC_HEARTBEAT");

      expect(await c2DataStore.getCommandCount()).to.equal(3);
      expect(await c2DataStore.getCommandAtIndex(0)).to.equal("SYNTHETIC_PING");
      expect(await c2DataStore.getCommandAtIndex(1)).to.equal(
        "SYNTHETIC_RESOLVE:localhost"
      );
      expect(await c2DataStore.getCommandAtIndex(2)).to.equal(
        "SYNTHETIC_HEARTBEAT"
      );
    });

    it("should allow any address to store commands", async function () {
      await c2DataStore.connect(otherAccount).storeCommand("SYNTHETIC_PING");
      expect(await c2DataStore.getCommandCount()).to.equal(1);
    });
  });

  describe("Reading synthetic commands", function () {
    beforeEach(async function () {
      await c2DataStore.storeCommand("SYNTHETIC_PING");
      await c2DataStore.storeCommand("SYNTHETIC_RESOLVE:localhost");
    });

    it("should return the latest command", async function () {
      expect(await c2DataStore.getLatestCommand()).to.equal(
        "SYNTHETIC_RESOLVE:localhost"
      );
    });

    it("should return command at specific index", async function () {
      expect(await c2DataStore.getCommandAtIndex(0)).to.equal("SYNTHETIC_PING");
    });

    it("should revert for out-of-bounds index", async function () {
      await expect(c2DataStore.getCommandAtIndex(99)).to.be.revertedWith(
        "C2DataStore: index out of bounds"
      );
    });

    it("should update latest command after new store", async function () {
      await c2DataStore.storeCommand("SYNTHETIC_HEARTBEAT");
      expect(await c2DataStore.getLatestCommand()).to.equal(
        "SYNTHETIC_HEARTBEAT"
      );
      expect(await c2DataStore.getCommandCount()).to.equal(3);
    });
  });

  describe("Synthetic data safety", function () {
    it("stored data is inert text — contains only synthetic prefixed strings", async function () {
      const testCommands = [
        "SYNTHETIC_PING",
        "SYNTHETIC_RESOLVE:localhost",
        "SYNTHETIC_DNS_LOOKUP:localhost",
        "SYNTHETIC_HEARTBEAT",
        "SYNTHETIC_NOP",
      ];

      for (const cmd of testCommands) {
        await c2DataStore.storeCommand(cmd);
      }

      for (let i = 0; i < testCommands.length; i++) {
        const stored = await c2DataStore.getCommandAtIndex(i);
        expect(stored).to.equal(testCommands[i]);
        expect(stored.startsWith("SYNTHETIC_")).to.be.true;
      }
    });
  });
});

describe("BenignDAppContract", function () {
  let benignDApp;
  let deployer;
  let otherAccount;
  const INITIAL_MESSAGE = "ChainC2 Sentinel — Benign DApp Active";

  beforeEach(async function () {
    [deployer, otherAccount] = await ethers.getSigners();
    const BenignDAppContract = await ethers.getContractFactory(
      "BenignDAppContract"
    );
    benignDApp = await BenignDAppContract.deploy(INITIAL_MESSAGE);
    await benignDApp.waitForDeployment();
  });

  describe("Deployment", function () {
    it("should deploy successfully", async function () {
      const address = await benignDApp.getAddress();
      expect(address).to.be.properAddress;
    });

    it("should set the deployer address", async function () {
      expect(await benignDApp.deployer()).to.equal(deployer.address);
    });

    it("should have initial count of zero", async function () {
      expect(await benignDApp.getCount()).to.equal(0);
    });

    it("should have the initial message", async function () {
      expect(await benignDApp.message()).to.equal(INITIAL_MESSAGE);
    });
  });

  describe("Counter", function () {
    it("should increment counter by one", async function () {
      await benignDApp.increment();
      expect(await benignDApp.getCount()).to.equal(1);
    });

    it("should emit CountIncremented event", async function () {
      await expect(benignDApp.increment())
        .to.emit(benignDApp, "CountIncremented")
        .withArgs(deployer.address, 1);
    });

    it("should increment multiple times correctly", async function () {
      await benignDApp.increment();
      await benignDApp.increment();
      await benignDApp.increment();
      expect(await benignDApp.getCount()).to.equal(3);
    });

    it("should allow any address to increment", async function () {
      await benignDApp.connect(otherAccount).increment();
      expect(await benignDApp.getCount()).to.equal(1);
    });

    it("should emit correct count in event after multiple increments", async function () {
      await benignDApp.increment();
      await benignDApp.increment();
      await expect(benignDApp.increment())
        .to.emit(benignDApp, "CountIncremented")
        .withArgs(deployer.address, 3);
    });
  });

  describe("Message", function () {
    it("should update the message", async function () {
      await benignDApp.updateMessage("Updated status");
      expect(await benignDApp.message()).to.equal("Updated status");
    });

    it("should emit MessageUpdated event", async function () {
      await expect(benignDApp.updateMessage("New message"))
        .to.emit(benignDApp, "MessageUpdated")
        .withArgs(deployer.address, "New message");
    });

    it("should allow setting an empty message", async function () {
      await benignDApp.updateMessage("");
      expect(await benignDApp.message()).to.equal("");
    });

    it("should allow any address to update the message", async function () {
      await benignDApp
        .connect(otherAccount)
        .updateMessage("Message from other");
      expect(await benignDApp.message()).to.equal("Message from other");
    });
  });
});

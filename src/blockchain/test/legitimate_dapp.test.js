const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("LegitimateDAppContract", function () {
  let legitimateDApp;
  let deployer;
  let user1;

  beforeEach(async function () {
    [deployer, user1] = await ethers.getSigners();
    const LegitimateDAppFactory = await ethers.getContractFactory("LegitimateDAppContract");
    legitimateDApp = await LegitimateDAppFactory.deploy();
    await legitimateDApp.waitForDeployment();
  });

  describe("Deployment", function () {
    it("should deploy successfully with valid address", async function () {
      const address = await legitimateDApp.getAddress();
      expect(address).to.be.properAddress;
    });

    it("should set deployer address correctly", async function () {
      expect(await legitimateDApp.deployer()).to.equal(deployer.address);
    });

    it("should initialize with zero tasks", async function () {
      expect(await legitimateDApp.getTaskCount()).to.equal(0);
    });
  });

  describe("Task Lifecycle (Scenario C Workload)", function () {
    it("should create a new task and emit TaskCreated event", async function () {
      const tx = await legitimateDApp.createTask("Telemetry Task", "Process telemetry events");
      await expect(tx)
        .to.emit(legitimateDApp, "TaskCreated")
        .withArgs(1, deployer.address, "Telemetry Task", (ts) => ts > 0);

      expect(await legitimateDApp.getTaskCount()).to.equal(1);

      const task = await legitimateDApp.getTask(1);
      expect(task.id).to.equal(1);
      expect(task.creator).to.equal(deployer.address);
      expect(task.title).to.equal("Telemetry Task");
      expect(task.description).to.equal("Process telemetry events");
      expect(task.status).to.equal(0); // TaskStatus.Pending
    });

    it("should update task status and emit TaskStatusUpdated event", async function () {
      await legitimateDApp.createTask("Audit Record", "Verify logs");
      
      const tx = await legitimateDApp.updateTaskStatus(1, 2); // Status: Completed
      await expect(tx)
        .to.emit(legitimateDApp, "TaskStatusUpdated")
        .withArgs(1, 0, 2, (ts) => ts > 0);

      const task = await legitimateDApp.getTask(1);
      expect(task.status).to.equal(2);
    });

    it("should reject empty task titles", async function () {
      await expect(
        legitimateDApp.createTask("", "Invalid description")
      ).to.be.revertedWith("Title cannot be empty");
    });

    it("should revert when querying non-existent task", async function () {
      await expect(legitimateDApp.getTask(999)).to.be.revertedWith("Task does not exist");
    });

    it("should revert when updating non-existent task", async function () {
      await expect(legitimateDApp.updateTaskStatus(999, 1)).to.be.revertedWith("Task does not exist");
    });

    it("should allow multi-user interactions", async function () {
      await legitimateDApp.connect(user1).createTask("User Task", "User description");
      expect(await legitimateDApp.getTaskCount()).to.equal(1);

      const task = await legitimateDApp.getTask(1);
      expect(task.creator).to.equal(user1.address);
    });
  });
});

// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title LegitimateDAppContract
 * @notice ChainC2 Sentinel — Legitimate DApp Baseline Contract (Scenario C)
 *
 * This contract simulates realistic, multi-step decentralized application activity
 * in a decentralized task/record registry. Unlike simple counters, it exercises
 * multi-step state operations: record creation, deterministic state reads via eth_call,
 * state updates via transactions, and structured event emission.
 *
 * SAFETY DECLARATION:
 * - Harmless, standard Solidity smart contract.
 * - Deployed ONLY to local Hardhat node for laboratory evaluation.
 * - No external network calls, no C2 data, no arbitrary code execution.
 */
contract LegitimateDAppContract {
    enum TaskStatus { Pending, InProgress, Completed, Cancelled }

    struct Task {
        uint256 id;
        address creator;
        string title;
        string description;
        TaskStatus status;
        uint256 createdAt;
        uint256 updatedAt;
    }

    // --- State Variables ---
    uint256 private nextTaskId = 1;
    mapping(uint256 => Task) private tasks;
    uint256 public totalTasks;
    address public immutable deployer;

    // --- Events ---
    event TaskCreated(
        uint256 indexed taskId,
        address indexed creator,
        string title,
        uint256 timestamp
    );

    event TaskStatusUpdated(
        uint256 indexed taskId,
        TaskStatus oldStatus,
        TaskStatus newStatus,
        uint256 timestamp
    );

    constructor() {
        deployer = msg.sender;
    }

    /**
     * @notice Creates a new task in the registry.
     * @param title Title of the task.
     * @param description Description of the task.
     * @return taskId Unique identifier of the created task.
     */
    function createTask(
        string calldata title,
        string calldata description
    ) external returns (uint256 taskId) {
        require(bytes(title).length > 0, "Title cannot be empty");

        taskId = nextTaskId++;
        tasks[taskId] = Task({
            id: taskId,
            creator: msg.sender,
            title: title,
            description: description,
            status: TaskStatus.Pending,
            createdAt: block.timestamp,
            updatedAt: block.timestamp
        });

        totalTasks++;

        emit TaskCreated(taskId, msg.sender, title, block.timestamp);
    }

    /**
     * @notice Updates the status of an existing task.
     * @param taskId ID of the task to update.
     * @param newStatus New status to set.
     */
    function updateTaskStatus(uint256 taskId, TaskStatus newStatus) external {
        require(tasks[taskId].id != 0, "Task does not exist");
        Task storage task = tasks[taskId];
        TaskStatus oldStatus = task.status;
        task.status = newStatus;
        task.updatedAt = block.timestamp;

        emit TaskStatusUpdated(taskId, oldStatus, newStatus, block.timestamp);
    }

    /**
     * @notice Retrieves task details by task ID.
     * @param taskId ID of the task.
     * @return Task struct.
     */
    function getTask(uint256 taskId) external view returns (Task memory) {
        require(tasks[taskId].id != 0, "Task does not exist");
        return tasks[taskId];
    }

    /**
     * @notice Returns the total count of created tasks.
     */
    function getTaskCount() external view returns (uint256) {
        return totalTasks;
    }
}

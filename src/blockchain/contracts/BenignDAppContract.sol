// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title BenignDAppContract
 * @notice ChainC2 Sentinel — Legitimate Web3 Baseline Contract
 *
 * This contract simulates ordinary, legitimate decentralized application
 * activity. It provides a simple counter and a message board to generate
 * benign blockchain telemetry that Phase 2 must distinguish from the
 * simulated C2 pattern produced by C2DataStore interactions.
 *
 * SAFETY DECLARATION:
 * - This is a standard, harmless smart contract.
 * - It performs no privileged, destructive, or malicious operations.
 * - Deployed ONLY on a local Hardhat EVM for research telemetry.
 */
contract BenignDAppContract {
    // --- State ---

    /// @notice A simple incrementing counter.
    uint256 private counter;

    /// @notice A public message string (simulates a DApp status/message).
    string public message;

    /// @notice Address of the contract deployer.
    address public immutable deployer;

    // --- Events ---

    /// @notice Emitted when the counter is incremented.
    /// @param sender The address that incremented the counter.
    /// @param newCount The counter value after incrementing.
    event CountIncremented(address indexed sender, uint256 newCount);

    /// @notice Emitted when the message is updated.
    /// @param sender The address that updated the message.
    /// @param newMessage The new message string.
    event MessageUpdated(address indexed sender, string newMessage);

    // --- Constructor ---

    /**
     * @param initialMessage The initial message for the DApp.
     */
    constructor(string memory initialMessage) {
        deployer = msg.sender;
        counter = 0;
        message = initialMessage;
    }

    // --- Write Functions ---

    /**
     * @notice Increment the counter by one.
     */
    function increment() external {
        counter += 1;
        emit CountIncremented(msg.sender, counter);
    }

    /**
     * @notice Update the DApp message.
     * @param newMessage The new message string.
     */
    function updateMessage(string calldata newMessage) external {
        message = newMessage;
        emit MessageUpdated(msg.sender, newMessage);
    }

    // --- Read Functions ---

    /**
     * @notice Get the current counter value.
     * @return The current count.
     */
    function getCount() external view returns (uint256) {
        return counter;
    }
}

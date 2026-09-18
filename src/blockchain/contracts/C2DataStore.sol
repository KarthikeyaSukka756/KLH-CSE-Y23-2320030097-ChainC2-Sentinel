// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title C2DataStore
 * @notice ChainC2 Sentinel — Synthetic Research Data Store
 *
 * This contract is part of a DEFENSIVE academic cybersecurity research project.
 * It stores and exposes predetermined synthetic text data representing
 * configuration/command-like strings for a controlled laboratory experiment.
 *
 * SAFETY DECLARATION:
 * - This contract does NOT execute any commands.
 * - This contract does NOT perform any malicious action.
 * - This contract does NOT interact with external systems.
 * - All stored data consists of inert synthetic strings (e.g., "SYNTHETIC_PING").
 * - This contract is deployed ONLY on a local Hardhat EVM for research telemetry.
 */
contract C2DataStore {
    // --- State ---

    /// @notice Array of stored synthetic command strings.
    string[] private commands;

    /// @notice Address of the contract deployer.
    address public immutable deployer;

    // --- Events ---

    /// @notice Emitted when a synthetic command string is stored.
    /// @param sender The address that stored the command.
    /// @param command The synthetic command string.
    /// @param index The index of the stored command.
    /// @param timestamp The block timestamp at storage time.
    event CommandStored(
        address indexed sender,
        string command,
        uint256 index,
        uint256 timestamp
    );

    // --- Constructor ---

    constructor() {
        deployer = msg.sender;
    }

    // --- Write Functions ---

    /**
     * @notice Store a synthetic command string.
     * @dev Any address can store data. The command is an inert string —
     *      nothing is executed or interpreted by this contract.
     * @param cmd The synthetic command string to store.
     */
    function storeCommand(string calldata cmd) external {
        commands.push(cmd);
        emit CommandStored(
            msg.sender,
            cmd,
            commands.length - 1,
            block.timestamp
        );
    }

    // --- Read Functions ---

    /**
     * @notice Retrieve the most recently stored synthetic command.
     * @return The latest command string, or an empty string if none stored.
     */
    function getLatestCommand() external view returns (string memory) {
        if (commands.length == 0) {
            return "";
        }
        return commands[commands.length - 1];
    }

    /**
     * @notice Retrieve a synthetic command by its index.
     * @param index The zero-based index of the command.
     * @return The command string at the given index.
     */
    function getCommandAtIndex(uint256 index) external view returns (string memory) {
        require(index < commands.length, "C2DataStore: index out of bounds");
        return commands[index];
    }

    /**
     * @notice Get the total number of stored synthetic commands.
     * @return The count of stored commands.
     */
    function getCommandCount() external view returns (uint256) {
        return commands.length;
    }
}

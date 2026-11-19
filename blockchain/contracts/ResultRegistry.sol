// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title ResultRegistry
 * @notice Immutable on-chain registry storing SHA-256 hashes of published student results.
 *         Only the contract owner (Controller of Examinations backend signer) can write hashes;
 *         anyone can publicly verify a result hash without authentication.
 */
contract ResultRegistry {
    struct ResultRecord {
        bytes32 resultHash;
        uint256 timestamp;
        uint256 blockNumber;
        address publishedBy;
        bool exists;
    }

    address public owner;
    mapping(bytes32 => ResultRecord) private _records;

    error Unauthorized(address caller);
    error ZeroAddress();
    error EmptyResultId();
    error ZeroHash();
    error ResultAlreadyStored(string resultId);

    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event ResultHashStored(
        bytes32 indexed resultKey,
        string resultId,
        bytes32 indexed resultHash,
        uint256 timestamp,
        uint256 blockNumber,
        address indexed publishedBy
    );

    modifier onlyOwner() {
        if (msg.sender != owner) {
            revert Unauthorized(msg.sender);
        }
        _;
    }

    constructor() {
        owner = msg.sender;
        emit OwnershipTransferred(address(0), msg.sender);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) {
            revert ZeroAddress();
        }
        address previousOwner = owner;
        owner = newOwner;
        emit OwnershipTransferred(previousOwner, newOwner);
    }

    /**
     * @notice Stores a SHA-256 result hash for a unique resultId. Immutable once stored.
     */
    function storeResultHash(string calldata resultId, bytes32 resultHash) external onlyOwner {
        if (bytes(resultId).length == 0) {
            revert EmptyResultId();
        }
        if (resultHash == bytes32(0)) {
            revert ZeroHash();
        }

        bytes32 key = keccak256(abi.encodePacked(resultId));
        if (_records[key].exists) {
            revert ResultAlreadyStored(resultId);
        }

        _records[key] = ResultRecord({
            resultHash: resultHash,
            timestamp: block.timestamp,
            blockNumber: block.number,
            publishedBy: msg.sender,
            exists: true
        });

        emit ResultHashStored(
            key,
            resultId,
            resultHash,
            block.timestamp,
            block.number,
            msg.sender
        );
    }

    /**
     * @notice Publicly verifies whether expectedHash matches the stored on-chain hash for resultId.
     */
    function verifyResultHash(
        string calldata resultId,
        bytes32 expectedHash
    )
        external
        view
        returns (
            bool isValid,
            bytes32 storedHash,
            uint256 timestamp,
            uint256 blockNumber,
            address publishedBy
        )
    {
        bytes32 key = keccak256(abi.encodePacked(resultId));
        ResultRecord memory rec = _records[key];
        bool valid = rec.exists && (rec.resultHash == expectedHash);
        return (valid, rec.resultHash, rec.timestamp, rec.blockNumber, rec.publishedBy);
    }

    /**
     * @notice Returns full stored metadata for a resultId.
     */
    function getResultRecord(
        string calldata resultId
    )
        external
        view
        returns (
            bool exists,
            bytes32 resultHash,
            uint256 timestamp,
            uint256 blockNumber,
            address publishedBy
        )
    {
        bytes32 key = keccak256(abi.encodePacked(resultId));
        ResultRecord memory rec = _records[key];
        return (rec.exists, rec.resultHash, rec.timestamp, rec.blockNumber, rec.publishedBy);
    }
}

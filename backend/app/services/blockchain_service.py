import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from web3 import Web3
from web3.contract import Contract

from app.core.config import settings

DEFAULT_ABI_PATH = Path(__file__).resolve().parents[1] / "blockchain" / "result_registry_abi.json"


@dataclass(frozen=True)
class OnChainReceipt:
    result_id: str
    result_hash_sha256: str
    tx_hash: str
    block_number: int
    timestamp: int
    contract_address: str


@dataclass(frozen=True)
class OnChainVerificationResult:
    result_id: str
    is_valid: bool
    exists: bool
    stored_hash_sha256: str
    expected_hash_sha256: str
    timestamp: int
    block_number: int
    published_by: str


def compute_result_hash(payload: dict[str, Any]) -> str:
    """Computes a deterministic 64-char lowercase SHA-256 hex digest for a canonical result payload."""
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def hex_hash_to_bytes32(hash_hex: str) -> bytes:
    cleaned = hash_hex.lower().removeprefix("0x").strip()
    if len(cleaned) != 64:
        raise ValueError(f"Expected 64-character SHA-256 hex digest, got length {len(cleaned)}")
    return bytes.fromhex(cleaned)


class BlockchainService:
    """Production web3.py client for ResultRegistry.sol (Hardhat local node or Sepolia testnet)."""

    def __init__(
        self,
        *,
        w3: Optional[Web3] = None,
        rpc_url: Optional[str] = None,
        contract_address: Optional[str] = None,
        deployer_key: Optional[str] = None,
        sender_address: Optional[str] = None,
        abi: Optional[list[dict[str, Any]]] = None,
        abi_path: Optional[Path] = None,
    ) -> None:
        if w3 is not None:
            self.w3 = w3
        else:
            resolved_rpc = (rpc_url or settings.BLOCKCHAIN_RPC_URL).strip()
            if not resolved_rpc:
                raise RuntimeError("BLOCKCHAIN_RPC_URL is not configured.")
            self.w3 = Web3(Web3.HTTPProvider(resolved_rpc))

        resolved_addr = (contract_address or settings.RESULT_REGISTRY_CONTRACT_ADDRESS).strip()
        if not resolved_addr:
            raise RuntimeError("RESULT_REGISTRY_CONTRACT_ADDRESS is not configured.")

        self.contract_address = Web3.to_checksum_address(resolved_addr)
        raw_key = (
            deployer_key if deployer_key is not None else os.getenv("BLOCKCHAIN_DEPLOYER_KEY", "")
        )
        self.deployer_key = raw_key.strip()
        self.sender_address = (
            Web3.to_checksum_address(sender_address) if sender_address else None
        )

        if abi is not None:
            resolved_abi = abi
        else:
            path = abi_path or DEFAULT_ABI_PATH
            if not path.exists():
                raise FileNotFoundError(f"Contract ABI not found at {path}")
            resolved_abi = json.loads(path.read_text(encoding="utf-8"))

        self.contract: Contract = self.w3.eth.contract(
            address=self.contract_address,
            abi=resolved_abi,
        )

    def is_connected(self) -> bool:
        return bool(self.w3.is_connected())

    def store_result_hash(self, result_id: str, result_hash_hex: str) -> OnChainReceipt:
        if not result_id.strip():
            raise ValueError("result_id cannot be empty")
        hash_bytes = hex_hash_to_bytes32(result_hash_hex)
        normalized_hex = hash_bytes.hex()

        fn_call = self.contract.functions.storeResultHash(result_id, hash_bytes)

        if self.deployer_key:
            account = self.w3.eth.account.from_key(self.deployer_key)
            nonce = self.w3.eth.get_transaction_count(account.address, "pending")
            tx = fn_call.build_transaction(
                {
                    "from": account.address,
                    "nonce": nonce,
                    "chainId": self.w3.eth.chain_id,
                }
            )
            signed = self.w3.eth.account.sign_transaction(tx, private_key=self.deployer_key)
            raw_tx = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
            tx_hash_bytes = self.w3.eth.send_raw_transaction(raw_tx)
        else:
            from_addr = self.sender_address or self.w3.eth.accounts[0]
            tx_hash_bytes = fn_call.transact({"from": from_addr})

        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash_bytes, timeout=120)
        if receipt["status"] != 1:
            raise RuntimeError(f"On-chain transaction reverted: {tx_hash_bytes.hex()}")

        block = self.w3.eth.get_block(receipt["blockNumber"])
        tx_hash_str = tx_hash_bytes.hex()
        if not tx_hash_str.startswith("0x"):
            tx_hash_str = f"0x{tx_hash_str}"

        return OnChainReceipt(
            result_id=result_id,
            result_hash_sha256=normalized_hex,
            tx_hash=tx_hash_str,
            block_number=int(receipt["blockNumber"]),
            timestamp=int(block["timestamp"]),
            contract_address=self.contract_address,
        )

    def verify_result_hash(
        self, result_id: str, expected_hash_hex: str
    ) -> OnChainVerificationResult:
        expected_bytes = hex_hash_to_bytes32(expected_hash_hex)
        is_valid, stored_bytes, timestamp, block_number, published_by = (
            self.contract.functions.verifyResultHash(result_id, expected_bytes).call()
        )
        stored_hex = bytes(stored_bytes).hex()
        exists = any(b != 0 for b in stored_bytes)
        return OnChainVerificationResult(
            result_id=result_id,
            is_valid=bool(is_valid),
            exists=exists,
            stored_hash_sha256=stored_hex,
            expected_hash_sha256=expected_bytes.hex(),
            timestamp=int(timestamp),
            block_number=int(block_number),
            published_by=Web3.to_checksum_address(published_by),
        )

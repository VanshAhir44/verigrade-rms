"""Compiles ResultRegistry.sol via py-solc-x and exports ABI/bytecode artifacts."""

import json
from pathlib import Path
from typing import Any

import solcx

SOLC_VERSION = "0.8.24"
REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = REPO_ROOT / "blockchain" / "contracts" / "ResultRegistry.sol"
ABI_OUTPUT_PATH = Path(__file__).resolve().parent / "result_registry_abi.json"


def ensure_solc_installed() -> None:
    installed = [str(v) for v in solcx.get_installed_solc_versions()]
    if SOLC_VERSION not in installed:
        solcx.install_solc(SOLC_VERSION)


def compile_result_registry(export_abi: bool = True) -> dict[str, Any]:
    ensure_solc_installed()
    source = CONTRACT_PATH.read_text(encoding="utf-8")
    compiled = solcx.compile_standard(
        {
            "language": "Solidity",
            "sources": {"ResultRegistry.sol": {"content": source}},
            "settings": {
                "optimizer": {"enabled": True, "runs": 200},
                "outputSelection": {
                    "*": {
                        "*": ["abi", "evm.bytecode.object"],
                    }
                },
            },
        },
        solc_version=SOLC_VERSION,
    )
    contract_data = compiled["contracts"]["ResultRegistry.sol"]["ResultRegistry"]
    abi = contract_data["abi"]
    bytecode = contract_data["evm"]["bytecode"]["object"]

    if export_abi:
        ABI_OUTPUT_PATH.write_text(json.dumps(abi, indent=2), encoding="utf-8")

    return {"abi": abi, "bytecode": bytecode}


if __name__ == "__main__":
    result = compile_result_registry(export_abi=True)
    print(f"Compiled ResultRegistry.sol (ABI entries: {len(result['abi'])}, bytecode bytes: {len(result['bytecode']) // 2})")

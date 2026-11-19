require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config({ path: "../.env" });

const SEPOLIA_RPC_URL = process.env.BLOCKCHAIN_RPC_URL || "";
const DEPLOYER_KEY = process.env.BLOCKCHAIN_DEPLOYER_KEY || "";

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
    hardhat: {
      chainId: 31337,
    },
    localhost: {
      url: process.env.BLOCKCHAIN_RPC_URL || "http://localhost:8545",
      chainId: Number(process.env.BLOCKCHAIN_CHAIN_ID || 31337),
    },
    ...(SEPOLIA_RPC_URL && DEPLOYER_KEY
      ? {
          sepolia: {
            url: SEPOLIA_RPC_URL,
            accounts: [DEPLOYER_KEY],
            chainId: 11155111,
          },
        }
      : {}),
  },
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts",
  },
};

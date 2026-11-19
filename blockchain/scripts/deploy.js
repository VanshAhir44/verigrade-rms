const fs = require("fs");
const path = require("path");
const hre = require("hardhat");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  console.log(`Deploying ResultRegistry with account: ${deployer.address}`);

  const ResultRegistry = await hre.ethers.getContractFactory("ResultRegistry");
  const registry = await ResultRegistry.deploy();
  await registry.waitForDeployment();

  const contractAddress = await registry.getAddress();
  const network = await hre.ethers.provider.getNetwork();
  console.log(`ResultRegistry deployed to: ${contractAddress} (chainId: ${network.chainId})`);

  // Export deployment metadata & ABI for backend consumption
  const artifact = await hre.artifacts.readArtifact("ResultRegistry");
  const deploymentInfo = {
    contractName: "ResultRegistry",
    address: contractAddress,
    chainId: Number(network.chainId),
    deployer: deployer.address,
    deployedAt: new Date().toISOString(),
  };

  const outDir = path.join(__dirname, "..", "deployments");
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(
    path.join(outDir, `${network.chainId}.json`),
    JSON.stringify(deploymentInfo, null, 2)
  );

  const backendAbiDir = path.join(__dirname, "..", "..", "backend", "app", "blockchain");
  fs.mkdirSync(backendAbiDir, { recursive: true });
  fs.writeFileSync(
    path.join(backendAbiDir, "result_registry_abi.json"),
    JSON.stringify(artifact.abi, null, 2)
  );
  console.log(`Exported ABI to ${path.join(backendAbiDir, "result_registry_abi.json")}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

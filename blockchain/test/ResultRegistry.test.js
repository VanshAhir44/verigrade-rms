const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("ResultRegistry", function () {
  async function deployFixture() {
    const [owner, nonOwner, newOwner] = await ethers.getSigners();
    const ResultRegistry = await ethers.getContractFactory("ResultRegistry");
    const registry = await ResultRegistry.deploy();
    await registry.waitForDeployment();
    return { registry, owner, nonOwner, newOwner };
  }

  it("sets deployer as owner", async function () {
    const { registry, owner } = await deployFixture();
    expect(await registry.owner()).to.equal(owner.address);
  });

  it("allows owner to store and anyone to verify a result hash", async function () {
    const { registry, owner, nonOwner } = await deployFixture();
    const resultId = "res-2026-sem1-enr001";
    const resultHash = ethers.sha256(ethers.toUtf8Bytes('{"sgpa":"9.25","student":"ENR2026CS001"}'));

    await expect(registry.storeResultHash(resultId, resultHash))
      .to.emit(registry, "ResultHashStored");

    // Public verification from non-owner account succeeds
    const [isValid, storedHash, timestamp, blockNumber, publishedBy] =
      await registry.connect(nonOwner).verifyResultHash(resultId, resultHash);

    expect(isValid).to.equal(true);
    expect(storedHash).to.equal(resultHash);
    expect(timestamp).to.be.greaterThan(0n);
    expect(blockNumber).to.be.greaterThan(0n);
    expect(publishedBy).to.equal(owner.address);

    // Tampered hash fails verification
    const tamperedHash = ethers.sha256(ethers.toUtf8Bytes('{"sgpa":"9.99","student":"ENR2026CS001"}'));
    const [tamperedValid] = await registry.connect(nonOwner).verifyResultHash(resultId, tamperedHash);
    expect(tamperedValid).to.equal(false);
  });

  it("reverts when non-owner tries to store a result hash", async function () {
    const { registry, nonOwner } = await deployFixture();
    const resultHash = ethers.sha256(ethers.toUtf8Bytes("payload"));

    await expect(
      registry.connect(nonOwner).storeResultHash("res-unauth", resultHash)
    )
      .to.be.revertedWithCustomError(registry, "Unauthorized")
      .withArgs(nonOwner.address);
  });

  it("enforces immutability and rejects empty id or zero hash", async function () {
    const { registry } = await deployFixture();
    const resultHash = ethers.sha256(ethers.toUtf8Bytes("payload-1"));

    await expect(registry.storeResultHash("", resultHash))
      .to.be.revertedWithCustomError(registry, "EmptyResultId");

    await expect(registry.storeResultHash("res-zero", ethers.ZeroHash))
      .to.be.revertedWithCustomError(registry, "ZeroHash");

    await registry.storeResultHash("res-immutable", resultHash);
    await expect(registry.storeResultHash("res-immutable", resultHash))
      .to.be.revertedWithCustomError(registry, "ResultAlreadyStored")
      .withArgs("res-immutable");
  });

  it("allows owner to transfer ownership", async function () {
    const { registry, owner, newOwner } = await deployFixture();

    await expect(registry.transferOwnership(newOwner.address))
      .to.emit(registry, "OwnershipTransferred")
      .withArgs(owner.address, newOwner.address);

    expect(await registry.owner()).to.equal(newOwner.address);
  });
});

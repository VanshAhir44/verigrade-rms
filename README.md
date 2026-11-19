
# Real-Time Verified Student Result Management System (VeriGrade RMS)

Production-grade academic result management platform built with **FastAPI**, **PostgreSQL (SQLAlchemy 2.0 async + Alembic)**, **Solidity / Hardhat (`ResultRegistry.sol`) + `web3.py`**, **ReportLab + QR Code**, and **Next.js (App Router + Tailwind CSS + Framer Motion + Recharts)**.

---
## System Walkthrough & Screenshots

### 1. Authentication & Public Verifier Portal
<img width="2816" height="1100" alt="Login Page" src="https://github.com/user-attachments/assets/f152c109-3b1b-41ef-85d9-a003f3be5215" />

### 2. Faculty Marks Workbench
<img width="2816" height="990" alt="Faculty Workbench" src="https://github.com/user-attachments/assets/60519176-1a63-40a5-99db-7b744076d432" />

### 3. Admin Controller — One-Click On-Chain Publish
<img width="2816" height="1302" alt="Admin Live Publish" src="https://github.com/user-attachments/assets/9a3e1361-980e-4fae-9f90-4038cef58b6c" />

### 4. Student Live Result Dashboard (Dark & Light Themes)
<img width="2816" height="2158" alt="Student Dashboard Dark" src="https://github.com/user-attachments/assets/b5094f21-1df0-4ada-b93a-6e92cb0ecc3d" />
<img width="2816" height="2158" alt="Student Dashboard Light" src="https://github.com/user-attachments/assets/d67424f1-a8a4-4ebc-aa8a-9ad7853d8d2e" />

### 5. Public Cryptographic Verification Proof
<img width="2816" height="1960" alt="Public Verify Result" src="https://github.com/user-attachments/assets/122347a8-6303-44b3-a8ab-a4c324bfc137" />

---



## Repository Structure

```text
result-management-system/
├── .env.example              # Environment template (zero hardcoded secrets)
├── docker-compose.yml        # Orchestrates PostgreSQL 16, Hardhat node, FastAPI backend, Next.js frontend
├── render.yaml               # Render Blueprint (FastAPI Web Service + Managed PostgreSQL)
├── backend/                  # FastAPI, SQLAlchemy 2.0 async, Alembic, JWT RBAC, Grading Engine, WebSockets, PDF+QR, Pytest
├── blockchain/               # Hardhat, contracts/ResultRegistry.sol, deploy.js, Mocha/Chai tests, Dockerfile
└── frontend/                 # Next.js App Router, TypeScript, Tailwind CSS, Framer Motion, Recharts, vercel.json
```

---

## 1. Local End-to-End Setup (Docker Compose)

1. **Create `.env` from template:**
   ```bash
   cp .env.example .env
   ```
   Fill in `POSTGRES_PASSWORD`, `DATABASE_URL`, `JWT_SIGNING_KEY` (32+ random chars), and `SEED_*_PASSWORD` values.

2. **Start PostgreSQL and local Hardhat Ethereum node:**
   ```bash
   docker compose up -d --build postgres hardhat
   ```

3. **Deploy `ResultRegistry.sol` to the local Hardhat node:**
   ```bash
   docker compose exec hardhat npm run deploy:local
   ```
   Copy the deployed contract address into `RESULT_REGISTRY_CONTRACT_ADDRESS` in `.env`.

4. **Start Backend & Frontend (backend automatically runs `alembic upgrade head` on startup):**
   ```bash
   docker compose up -d --build backend frontend
   ```

5. **Seed initial Admin, Faculty, 2 Students, and 4 Sample Subjects (idempotent):**
   ```bash
   docker compose exec backend python -m app.db.seed
   ```

6. **Verify the complete live flow:**
   - Open `http://localhost:3000`
   - Sign in as **Student** (`student1@university.edu`) in Window A — confirm the pulsing **Live Connected** WebSocket badge.
   - Sign in as **Faculty** (`faculty@university.edu`) in Window B — enter marks for all 4 subjects (`CS101`–`CS104`) and click **Submit & Lock**.
   - Sign in as **Admin** (`admin@university.edu`) in Window C — click **One-Click Live Publish**.
   - Watch Window A receive the live **RESULT_PUBLISHED** celebratory reveal automatically (zero page reload), download the **QR-Verified PDF Marksheet**, and click **Verify On-Chain** (`/verify/[result_id]`) to confirm `VERIFIED ON-CHAIN`.

---

## 2. Running Automated Tests Locally

### Backend + Live EVM Integration Suite (Python 3.11+)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.blockchain.compiler
pytest -v
```

### Smart Contract Suite (Node.js 20+)
```bash
cd blockchain
npm install
npm test
```

### Frontend Type-Check & Production Build (Node.js 20+)
```bash
cd frontend
npm install
npm run typecheck
npm run build
```

---

## 3. Cloud Deployment Guides

### A. Smart Contract on Sepolia Testnet
1. Provision a Sepolia RPC endpoint (Alchemy / Infura) and fund a deployer wallet with Sepolia ETH.
2. Set `BLOCKCHAIN_RPC_URL`, `BLOCKCHAIN_CHAIN_ID=11155111`, and `BLOCKCHAIN_DEPLOYER_KEY` in `.env`.
3. Run:
   ```bash
   cd blockchain && npm run deploy:sepolia
   ```
4. Save the printed `ResultRegistry` contract address for your backend environment (`RESULT_REGISTRY_CONTRACT_ADDRESS`).

### B. Backend + Managed PostgreSQL on Render (`render.yaml`)
1. Push the repository to GitHub.
2. In the Render Dashboard, choose **New -> Blueprint** and select this repository. Render reads `render.yaml` to provision `rms-postgres` and `rms-backend-api`.
3. Note: Convert Render's `postgres://` connection string to `postgresql+asyncpg://` if needed in `DATABASE_URL`.
4. Set secret environment variables in Render (`CORS_ORIGINS`, `PUBLIC_VERIFY_BASE_URL`, `BLOCKCHAIN_RPC_URL`, `BLOCKCHAIN_DEPLOYER_KEY`, `RESULT_REGISTRY_CONTRACT_ADDRESS`).
5. Run `python -m app.db.seed` once via Render Shell to bootstrap initial accounts.

### C. Frontend on Vercel (`frontend/vercel.json`)
1. Import the GitHub repository in Vercel and set **Root Directory** to `frontend`.
2. Add Environment Variables:
   - `NEXT_PUBLIC_API_URL=https://<your-backend-domain>/api/v1`
   - `NEXT_PUBLIC_WS_URL=wss://<your-backend-domain>/ws`
3. Deploy — Vercel automatically applies the security headers in `frontend/vercel.json`.

### D. Alternative: Azure Container Apps + Azure Database for PostgreSQL
1. Create an **Azure Database for PostgreSQL Flexible Server** and an **Azure Container Registry (ACR)**.
2. Build and push the backend image:
   ```bash
   az acr build --registry <acr-name> --image rms-backend:latest ./backend
   ```
3. Deploy to **Azure Container Apps** with ingress on port `8000` (WebSockets are supported natively on ACA), injecting `DATABASE_URL` (`postgresql+asyncpg://...?ssl=require`), `JWT_SIGNING_KEY`, `CORS_ORIGINS`, `PUBLIC_VERIFY_BASE_URL`, `BLOCKCHAIN_RPC_URL`, `BLOCKCHAIN_DEPLOYER_KEY`, and `RESULT_REGISTRY_CONTRACT_ADDRESS` via Azure Container App Secrets.
4. Point Vercel's `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` (`wss://`) to your Azure Container App FQDN.

# PrioMon: Distributed Priority-Based Monitoring System

PrioMon is a high-performance, decentralized monitoring system built for edge environments. It utilizes a custom **Gossip Protocol** to propagate system metrics (CPU, Memory, Network, Storage) across a cluster of nodes without a single point of failure.

To optimize network bandwidth, PrioMon implements a unique **Value-of-Information (VoI) filtering mechanism** that drastically reduces redundant data transmission while ensuring critical status updates propagate instantly.

## 🚀 Key Engineering Features

- **Decentralized Gossip Protocol**: Efficient data dissemination avoiding bottlenecks of centralized masters.
- **Bandwidth Optimization (VoI)**: Reduces network payload by up to 100x by prioritizing significant metric changes and critical state transitions.
- **High-Performance Storage**: Utilizes SQLite with WAL (Write-Ahead Logging) to sustain high-frequency simulation writes without hardware degradation.
- **Containerized Architecture**: Fully Dockerized node clusters for scalable deployment and testing.
- **Full-Stack Dashboard**: Integrated React/Node.js web dashboard for real-time monitoring and analytics visualization.
- **Fault Tolerance**: Automatic detection and handling of dead nodes via Leaderless Quorum Consensus (LQC).

## 🛠️ Tech Stack

- **Core Engine**: Python 3.9+
- **Backend API**: Node.js, Express
- **Frontend**: React, Tailwind CSS, Vite
- **Database**: SQLite (WAL optimized)
- **Deployment & Orchestration**: Docker, Docker Compose

## 📂 Project Structure

```text
PrioMon/
├── src/               # Core Gossip Engine & Node implementation (Python)
├── dashboard/         # Full-stack monitoring dashboard
│   ├── api/           # Node.js backend server
│   └── client/        # React frontend application
├── experiments/       # Simulation orchestrator, database schemas, and analytics
├── docker-compose.yml # Container orchestration for the node cluster
└── README.md
```

## 🏁 Quick Start

### 1. Prerequisites
- Docker & Docker Compose
- Python 3.9+
- Node.js & npm (for dashboard)

### 2. Build and Run the Gossip Cluster
Spin up the decentralized nodes using Docker Compose:
```bash
docker-compose up --build -d
```

### 3. Start the Simulation Orchestrator
In a virtual environment, install the requirements and run the monitoring server:
```bash
pip install -r requirements.txt
python experiments/monitoring.py
```

### 4. Launch the Dashboard
Start the API and Client to visualize the cluster in real-time:
```bash
# Terminal 1: Start API
cd dashboard/api
npm install
npm start

# Terminal 2: Start Client
cd dashboard/client
npm install
npm run dev
```

Navigate to the provided localhost URL (usually `http://localhost:5173`) to view the dashboard. To trigger the simulated workloads, visit `http://localhost:4000/start`.

## 📊 Analytics & Visualization

PrioMon includes built-in tools to measure convergence time, success rates, and bandwidth savings. After running a simulation, generate the performance charts:
```bash
python experiments/plot.py
```
This will output PNG charts in the `experiments/` directory demonstrating the efficiency of the VoI filtering algorithm.
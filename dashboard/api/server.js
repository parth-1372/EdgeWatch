const express = require("express");
const cors = require("cors");
const fs = require("fs");
const path = require("path");
const ini = require("ini");
const http = require("http");
const { Server } = require("socket.io");

const app = express();
const PORT = 5000;

// Create HTTP server and attach Socket.io
const server = http.createServer(app);
const io = new Server(server, {
  cors: {
    origin: "*",
    methods: ["GET", "POST"],
  },
});

// Path to config.ini relative to this file (dashboard/api/ -> experiments/)
const CONFIG_PATH = path.resolve(__dirname, "../../experiments/config.ini");

app.use(cors());
app.use(express.json());

// ---------------------------------------------------------------------------
// Socket.io connection handling
// ---------------------------------------------------------------------------
io.on("connection", (socket) => {
  console.log(`[Socket.io] Client connected: ${socket.id}`);
  socket.on("disconnect", () => {
    console.log(`[Socket.io] Client disconnected: ${socket.id}`);
  });
});

// ---------------------------------------------------------------------------
// GET /api/config
// Read config.ini and return as a nested JSON object
// ---------------------------------------------------------------------------
app.get("/api/config", (req, res) => {
  try {
    const raw = fs.readFileSync(CONFIG_PATH, "utf-8");
    const parsed = ini.parse(raw);
    res.json(parsed);
  } catch (err) {
    console.error("[GET /api/config] Error reading config:", err.message);
    res.status(500).json({ error: "Failed to read config.ini", details: err.message });
  }
});

// ---------------------------------------------------------------------------
// POST /api/config
// Accept updated config JSON, serialise back to INI, overwrite config.ini
// ---------------------------------------------------------------------------
app.post("/api/config", (req, res) => {
  try {
    const updated = req.body;
    if (!updated || typeof updated !== "object") {
      return res.status(400).json({ error: "Invalid payload: expected a JSON object" });
    }
    const iniString = ini.stringify(updated);
    fs.writeFileSync(CONFIG_PATH, iniString, "utf-8");
    res.json({ success: true, message: "Configuration saved successfully." });
  } catch (err) {
    console.error("[POST /api/config] Error writing config:", err.message);
    res.status(500).json({ error: "Failed to write config.ini", details: err.message });
  }
});

// ---------------------------------------------------------------------------
// POST /api/start
// Forward a trigger to the Python orchestrator running on localhost:4000
// ---------------------------------------------------------------------------
app.post("/api/start", async (req, res) => {
  try {
    const orchestratorUrl = "http://localhost:4000/start";
    const response = await fetch(orchestratorUrl);

    // Surface the orchestrator's own status code if it signals an error
    if (!response.ok) {
      const text = await response.text();
      return res.status(response.status).json({
        error: "Orchestrator returned an error",
        details: text,
      });
    }

    // Try to parse JSON; fall back to raw text
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json")
      ? await response.json()
      : await response.text();

    res.json({ success: true, orchestratorResponse: data });
  } catch (err) {
    console.error("[POST /api/start] Error contacting orchestrator:", err.message);
    res.status(503).json({
      error: "Could not reach the orchestrator at localhost:4000",
      details: err.message,
    });
  }
});

// ---------------------------------------------------------------------------
// POST /api/live-metrics
// Receives metric payloads from the Python orchestrator and broadcasts them
// to all connected frontend clients via Socket.io
// ---------------------------------------------------------------------------
app.post("/api/live-metrics", (req, res) => {
  const payload = req.body;
  io.emit("new_metric", payload);
  res.json({ received: true });
});

// ---------------------------------------------------------------------------
// POST /api/live-run-start
// Receives the initial node list from the orchestrator and broadcasts it
// to the frontend to pre-initialize the graph.
// ---------------------------------------------------------------------------
app.post("/api/live-run-start", (req, res) => {
  const payload = req.body;
  io.emit("run_started", payload);
  res.json({ success: true });
});

// ---------------------------------------------------------------------------
// Start server (use server.listen, NOT app.listen, so socket.io binds too)
// ---------------------------------------------------------------------------
server.listen(PORT, () => {
  console.log(`PrioMon Control Center API running on http://localhost:${PORT}`);
  console.log(`Socket.io attached and listening for connections`);
  console.log(`Config path: ${CONFIG_PATH}`);
});

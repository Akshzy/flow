#!/usr/bin/env node
/**
 * Manages a local embedded PostgreSQL server for development and tests.
 *
 * The PostgreSQL binaries are provided by the `embedded-postgres` npm package
 * (installed via `npm install` at the repository root); this script drives the
 * server lifecycle directly with `initdb` / `pg_ctl` so the server runs
 * detached from this process (no auto-shutdown when the script exits).
 * The `pg` client performs readiness checks and database creation.
 *
 * Usage:
 *   node scripts/pg.mjs up [--fresh] [--json]
 *   node scripts/pg.mjs down [--json]
 *   node scripts/pg.mjs status [--json]
 *
 * Configuration (environment variables, see .env.example):
 *   PG_DATA_DIR  data directory          (default: <repo>/.pgdata/dev)
 *   PG_PORT      server port             (default: 55432)
 *   PG_USER      superuser name          (default: postgres)
 *   PG_PASSWORD  superuser password      (default: postgres; local only)
 *   PG_DATABASE  application database    (default: floww)
 *
 * With --json, a single machine-readable line prefixed with FLOWW_PG_JSON: is
 * printed last (the local dev/test password is included; it is a throwaway
 * local credential, never committed).
 */

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import net from "node:net";
import { fileURLToPath } from "node:url";
import pg from "pg";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.dirname(scriptDir);

const PLATFORM_DIR = {
  "win32-x64": "windows-x64",
  "linux-x64": "linux-x64",
  "linux-arm64": "linux-arm64",
  "darwin-x64": "darwin-x64",
  "darwin-arm64": "darwin-arm64",
}[`${process.platform}-${process.arch}`];

if (!PLATFORM_DIR) {
  console.error(`Unsupported platform: ${process.platform}-${process.arch}`);
  process.exit(1);
}

const binDir = path.join(
  repoRoot,
  "node_modules",
  "@embedded-postgres",
  PLATFORM_DIR,
  "native",
  "bin"
);

const exe = (name) =>
  path.join(binDir, process.platform === "win32" ? `${name}.exe` : name);

const args = process.argv.slice(2);
const command = args[0];
const fresh = args.includes("--fresh");
const json = args.includes("--json");

const config = {
  data_dir: process.env.PG_DATA_DIR || path.join(repoRoot, ".pgdata", "dev"),
  port: parseInt(process.env.PG_PORT || "55432", 10),
  user: process.env.PG_USER || "postgres",
  password: process.env.PG_PASSWORD || "postgres",
  database: process.env.PG_DATABASE || "floww",
};

/** Run a binary synchronously with inherited stdio (no server children). */
function run(name, binArgs, opts = {}) {
  return spawnSync(exe(name), binArgs, { encoding: "utf8", ...opts });
}

/**
 * Run a server-management binary with stdio ignored. pg_ctl/postgres must not
 * inherit stdio pipes: the detached server keeps the pipe handles open, which
 * makes spawnSync hang until the server exits (classic Windows EOF hang).
 */
function runDetached(name, binArgs) {
  return spawnSync(exe(name), binArgs, { encoding: "utf8", stdio: "ignore" });
}

/** Wait until the server accepts TCP connections (or timeout). */
function waitUntilListening(timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve) => {
    const attempt = () => {
      const socket = net.connect({ host: "127.0.0.1", port: config.port });
      socket.setTimeout(1000);
      socket.on("connect", () => {
        socket.destroy();
        resolve(true);
      });
      const retry = () => {
        socket.destroy();
        if (Date.now() < deadline) setTimeout(attempt, 250);
        else resolve(false);
      };
      socket.on("error", retry);
      socket.on("timeout", retry);
    };
    attempt();
  });
}

/** Verify the server answers a real SQL query. */
async function sqlReady() {
  const client = new pg.Client({
    host: "127.0.0.1",
    port: config.port,
    user: config.user,
    password: config.password,
    database: "postgres",
    connectionTimeoutMillis: 3000,
  });
  try {
    await client.connect();
    await client.query("SELECT 1");
    return true;
  } catch {
    return false;
  } finally {
    await client.end().catch(() => {});
  }
}

function stopServer() {
  if (!fs.existsSync(config.data_dir)) return;
  // Best-effort stop; -m immediate for tests that want a hard stop.
  const mode = args.includes("--immediate") ? "-m immediate" : "-m fast";
  runDetached("pg_ctl", ["-D", config.data_dir, ...mode.split(" "), "-w", "stop"]);
}

function initCluster() {
  fs.mkdirSync(config.data_dir, { recursive: true });
  const pwfile = path.join(config.data_dir, "..", "pwfile.txt");
  fs.writeFileSync(pwfile, `${config.password}\n`);
  const result = run("initdb", [
    "--pgdata",
    config.data_dir,
    "--username",
    config.user,
    "--auth",
    "scram-sha-256",
    "--pwfile",
    pwfile,
    "--encoding=UTF8",
    "--no-instructions",
  ]);
  fs.rmSync(pwfile, { force: true });
  if (result.status !== 0) {
    console.error(result.stderr || result.stdout || "initdb failed");
    process.exit(1);
  }
}

function startServer() {
  const logFile = path.join(config.data_dir, "..", `pg-${config.port}.log`);
  // pg_ctl -w start waits until the server is ready; the detached server must
  // not inherit stdio pipes (see runDetached). The log file captures errors.
  runDetached("pg_ctl", [
    "-D",
    config.data_dir,
    "-w",
    "-t",
    "60",
    "-l",
    logFile,
    "-o",
    `-p ${config.port}`,
    "start",
  ]);
}

async function ensureDatabase() {
  const client = new pg.Client({
    host: "127.0.0.1",
    port: config.port,
    user: config.user,
    password: config.password,
    database: "postgres",
    connectionTimeoutMillis: 3000,
  });
  await client.connect();
  try {
    const exists = await client.query(
      "SELECT 1 FROM pg_database WHERE datname = $1",
      [config.database]
    );
    if (exists.rowCount === 0) {
      // Identifier cannot be parameterized; the name is local configuration.
      await client.query(`CREATE DATABASE "${config.database.replace(/"/g, "")}"`);
    }
  } finally {
    await client.end().catch(() => {});
  }
}

function emit(extra = {}) {
  if (json) {
    console.log(
      `FLOWW_PG_JSON: ${JSON.stringify({ ...config, host: "127.0.0.1", ...extra })}`
    );
  } else {
    console.log(
      `PostgreSQL ${command}: port ${config.port}, data ${config.data_dir}${extra.status ? `, ${extra.status}` : ""}`
    );
  }
}

async function main() {
  if (command === "up") {
    if (fresh) {
      stopServer();
      fs.rmSync(config.data_dir, { recursive: true, force: true });
    }
    if (!fs.existsSync(config.data_dir)) {
      initCluster();
    }
    if (!(await sqlReady())) {
      startServer();
      const listening = await waitUntilListening();
      if (!listening || !(await sqlReady())) {
        console.error(
          `PostgreSQL failed to start on port ${config.port}; see log: ${path.join(config.data_dir, "..", `pg-${config.port}.log`)}`
        );
        process.exit(1);
      }
    }
    await ensureDatabase();
    emit({ status: "running" });
  } else if (command === "down") {
    stopServer();
    emit({ status: "stopped" });
  } else if (command === "status") {
    const running = await sqlReady();
    emit({ status: running ? "running" : "stopped" });
    process.exit(running ? 0 : 1);
  } else {
    console.error(
      "Usage: node scripts/pg.mjs <up|down|status> [--fresh] [--json]"
    );
    process.exit(2);
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});

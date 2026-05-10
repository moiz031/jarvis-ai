const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..");
const requestedArgs = process.argv.slice(2);

if (requestedArgs.length === 0) {
  console.error("Usage: node scripts/python-runner.cjs <python args>");
  process.exit(1);
}

function fileCandidate(relativePath) {
  const absPath = path.join(repoRoot, relativePath);
  return fs.existsSync(absPath) ? { command: absPath, args: [] } : null;
}

const candidates = [
  process.env.JARVIS_PYTHON ? { command: process.env.JARVIS_PYTHON, args: [] } : null,
  fileCandidate(path.join(".venv", "Scripts", "python.exe")),
  fileCandidate(path.join("jarvis_backend_env", "Scripts", "python.exe")),
  fileCandidate(path.join(".venv", "bin", "python")),
  fileCandidate(path.join("jarvis_backend_env", "bin", "python")),
  { command: "py", args: ["-3"] },
  { command: "python", args: [] },
  { command: "python3", args: [] },
].filter(Boolean);

for (const candidate of candidates) {
  const result = spawnSync(candidate.command, [...candidate.args, ...requestedArgs], {
    cwd: repoRoot,
    stdio: "inherit",
    shell: false,
  });

  if (result.error) {
    if (result.error.code === "ENOENT") {
      continue;
    }
    console.error(`Python launcher error (${candidate.command}): ${result.error.message}`);
    process.exit(1);
  }

  process.exit(result.status ?? 0);
}

console.error(
  "No working Python interpreter found. Set JARVIS_PYTHON or create jarvis_backend_env/.venv."
);
process.exit(1);

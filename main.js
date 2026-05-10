const { app, BrowserWindow, crashReporter } = require("electron");
const fs = require("fs");
const path = require("path");

crashReporter.start({
  productName: "Jarvis AI",
  companyName: "Michael Carter",
  submitURL: "https://api.jarvis-ai.com/crash-reports", // Placeholder for actual endpoint
  uploadToServer: false // Set to true if endpoint is real
});

const { spawn } = require("child_process");
const http = require("http");

let mainWindow;
let backendProcess;
let backendStartError = "";
const BACKEND_URL = "http://127.0.0.1:8080";

function pythonCandidates() {
  const localCandidates = process.platform === "win32"
    ? [
        path.join(__dirname, ".venv", "Scripts", "python.exe"),
        path.join(__dirname, "jarvis_backend_env", "Scripts", "python.exe"),
      ]
    : [
        path.join(__dirname, ".venv", "bin", "python"),
        path.join(__dirname, "jarvis_backend_env", "bin", "python"),
      ];

  const resolved = [];
  for (const candidate of localCandidates) {
    if (fs.existsSync(candidate)) {
      resolved.push([candidate, []]);
    }
  }

  if (process.platform === "win32") {
    resolved.push(["py", ["-3"]], ["python", []]);
  } else {
    resolved.push(["python3", []], ["python", []]);
  }
  return resolved;
}

function backendExecutablePath() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "backend", "JarvisBackend.exe");
  }
  return path.join(__dirname, "backend", "JarvisBackend.exe");
}

function startBackend() {
  const backendExe = backendExecutablePath();
  const attachProcessHandlers = (proc, label) => {
    proc.on("error", (err) => {
      backendStartError = `${label} launch failed: ${err.message}. Ensure ${label.includes("JarvisBackend") ? "backend is built" : "Python 3.8+ is installed"}.`;
    });
    proc.on("exit", (code, signal) => {
      if (code && code !== 0) {
        backendStartError = `${label} exited with code ${code}${signal ? ` (signal: ${signal})` : ""}. Check system logs for details.`;
      }
    });
  };

  if (fs.existsSync(backendExe)) {
    backendProcess = spawn(backendExe, [], {
      windowsHide: true,
      stdio: "ignore",
    });
    attachProcessHandlers(backendProcess, "JarvisBackend.exe");
    return;
  }
  for (const [cmd, args] of pythonCandidates()) {
    try {
      backendProcess = spawn(cmd, [...args, "jarvis/main.py"], {
        windowsHide: true,
        stdio: "ignore",
      });
      attachProcessHandlers(backendProcess, cmd);
      return;
    } catch {
      // Try next candidate.
    }
  }
  backendStartError = "Unable to find a working Python runtime to start jarvis/main.py. Set up jarvis_backend_env or install Python 3.10+.";
}

function waitForBackend(timeoutMs = 30000) {
  const start = Date.now();

  return new Promise((resolve) => {
    const check = () => {
      if (backendStartError) {
        resolve(false);
        return;
      }
      const req = http.get(`${BACKEND_URL}/health`, (res) => {
        if (res.statusCode === 200) {
          resolve(true);
          return;
        }
        retry();
      });

      req.on("error", retry);
      req.setTimeout(1000, () => {
        req.destroy();
        retry();
      });
    };

    const retry = () => {
      if (Date.now() - start > timeoutMs) {
        resolve(false);
        return;
      }
      setTimeout(check, 500);
    };

    check();
  });
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    show: false,
    webPreferences: {
      nodeIntegration: false,
    },
  });

  const ready = await waitForBackend();
  if (!ready) {
    const msg = backendStartError || "Jarvis backend start nahi hua. Ollama chalu hai aur logs check karein.";
    const errorHTML = `
      <html>
        <head>
          <style>
            body { font-family: Arial; padding: 40px; color: #333; background: #f5f5f5; }
            h2 { color: #d32f2f; }
            p { line-height: 1.6; }
            code { background: #fff; padding: 2px 6px; border-radius: 3px; }
          </style>
        </head>
        <body>
          <h2>Jarvis Backend Start Failed</h2>
          <p>${msg}</p>
          <p><strong>Troubleshooting:</strong></p>
          <ul>
            <li>Ensure Python 3.8+ is installed and in PATH</li>
            <li>Check if "pip install -r jarvis/requirements.txt" completed successfully</li>
            <li>Verify Ollama is running on http://localhost:11434</li>
            <li>Check system logs in %APPDATA%/JarvisAI for details</li>
          </ul>
        </body>
      </html>
    `;
    mainWindow.loadURL(`data:text/html,${encodeURIComponent(errorHTML)}`);
  } else {
    mainWindow.loadURL(BACKEND_URL);
  }

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });
}

app.whenReady().then(async () => {
  startBackend();
  await createWindow();
});

app.on("window-all-closed", () => {
  if (backendProcess) backendProcess.kill();
  if (process.platform !== "darwin") app.quit();
});

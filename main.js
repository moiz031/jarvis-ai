const { app, BrowserWindow, crashReporter } = require("electron");

crashReporter.start({
  productName: "Jarvis AI",
  companyName: "Michael Carter",
  submitURL: "https://api.jarvis-ai.com/crash-reports", // Placeholder for actual endpoint
  uploadToServer: false // Set to true if endpoint is real
});

const { spawn } = require("child_process");
const http = require("http");

let mainWindow;
let pythonProcess;
const BACKEND_URL = "http://127.0.0.1:8080";

function startPython() {
  pythonProcess = spawn("python", ["jarvis/main.py"], {
    windowsHide: true,
    stdio: "ignore",
  });
}

function waitForBackend(timeoutMs = 30000) {
  const start = Date.now();

  return new Promise((resolve) => {
    const check = () => {
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
    mainWindow.loadURL(
      "data:text/html,<h2>Jarvis backend start nahi hua. Ollama aur logs check karein.</h2>",
    );
  } else {
    mainWindow.loadURL(BACKEND_URL);
  }

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });
}

app.whenReady().then(async () => {
  startPython();
  await createWindow();
});

app.on("window-all-closed", () => {
  if (pythonProcess) pythonProcess.kill();
  if (process.platform !== "darwin") app.quit();
});

require("dotenv").config();
const WebSocket = require("ws");
const fs = require("fs");
const path = require("path");

const API_KEY = process.env.HAMSA_API_KEY;
const WS_URL = `wss://api.tryhamsa.com/v1/realtime/ws?api_key=${API_KEY}`;

/**
 * Send audio for speech-to-text transcription via WebSocket.
 * @param {string} audioFilePath - Path to an audio file (WAV, MP3, etc.)
 * @param {object} options
 * @param {string}  [options.language="ar"]       - Language code
 * @param {boolean} [options.isEosEnabled=true]    - End-of-speech detection
 * @param {number}  [options.eosThreshold=0.3]     - EOS sensitivity 0.0–1.0
 */
function transcribeAudio(audioFilePath, options = {}) {
  const { language = "ar", isEosEnabled = true, eosThreshold = 0.3 } = options;

  const ws = new WebSocket(WS_URL);

  ws.on("open", () => {
    console.log("[STT] Connected to Hamsa WebSocket server");

    const audioBuffer = fs.readFileSync(audioFilePath);
    const audioBase64 = audioBuffer.toString("base64");

    const message = {
      type: "stt",
      payload: {
        audioBase64,
        language,
        isEosEnabled,
        eosThreshold,
      },
    };

    ws.send(JSON.stringify(message));
    console.log("[STT] Audio sent, waiting for transcription...");
  });

  ws.on("message", (data) => {
    const text = data.toString();

    // Responses can be plain text (transcription) or JSON (error / info)
    try {
      const json = JSON.parse(text);
      if (json.type === "error") {
        console.error("[STT] Error:", json.payload.message);
      } else if (json.type === "info") {
        console.log("[STT] Info:", json.payload.message);
      } else {
        console.log("[STT] Response:", json);
      }
    } catch {
      // Plain string = transcription result
      console.log("[STT] Transcription:", text);
    }
  });

  ws.on("error", (err) => {
    console.error("[STT] WebSocket error:", err.message);
  });

  ws.on("close", (code, reason) => {
    console.log(`[STT] Connection closed (code: ${code}, reason: ${reason})`);
  });

  return ws;
}

/**
 * Send raw Float32 PCM samples (16 kHz, mono) for transcription.
 * @param {Float32Array} samples - PCM audio samples
 * @param {object} options       - Same options as transcribeAudio
 */
function transcribePCM(samples, options = {}) {
  const { language = "ar", isEosEnabled = true, eosThreshold = 0.3 } = options;

  const ws = new WebSocket(WS_URL);

  ws.on("open", () => {
    console.log("[STT] Connected to Hamsa WebSocket server");

    const message = {
      type: "stt",
      payload: {
        audioList: Array.from(samples),
        language,
        isEosEnabled,
        eosThreshold,
      },
    };

    ws.send(JSON.stringify(message));
    console.log("[STT] PCM samples sent, waiting for transcription...");
  });

  ws.on("message", (data) => {
    const text = data.toString();
    try {
      const json = JSON.parse(text);
      if (json.type === "error") {
        console.error("[STT] Error:", json.payload.message);
      } else if (json.type === "info") {
        console.log("[STT] Info:", json.payload.message);
      } else {
        console.log("[STT] Response:", json);
      }
    } catch {
      console.log("[STT] Transcription:", text);
    }
  });

  ws.on("error", (err) => {
    console.error("[STT] WebSocket error:", err.message);
  });

  ws.on("close", (code, reason) => {
    console.log(`[STT] Connection closed (code: ${code}, reason: ${reason})`);
  });

  return ws;
}

// --- CLI usage: node websocket-stt.js <audio-file> [language] ---
if (require.main === module) {
  const audioFile = process.argv[2];
  const language = process.argv[3] || "ar";

  if (!audioFile) {
    console.log("Usage: node websocket-stt.js <audio-file> [language]");
    console.log("Example: node websocket-stt.js recording.wav ar");
    process.exit(1);
  }

  if (!API_KEY || API_KEY === "your_api_key_here") {
    console.error("Error: Set HAMSA_API_KEY in your .env file");
    process.exit(1);
  }

  const filePath = path.resolve(audioFile);
  if (!fs.existsSync(filePath)) {
    console.error(`Error: File not found: ${filePath}`);
    process.exit(1);
  }

  transcribeAudio(filePath, { language });
}

module.exports = { transcribeAudio, transcribePCM };

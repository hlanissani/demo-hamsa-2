require("dotenv").config();
const WebSocket = require("ws");
const fs = require("fs");
const path = require("path");

const API_KEY = process.env.HAMSA_API_KEY;
const WS_URL = `wss://api.tryhamsa.com/v1/realtime/ws?api_key=${API_KEY}`;

/**
 * Synthesize speech from text via WebSocket and save to a file.
 * @param {string} text     - Text to synthesize (max 2000 chars)
 * @param {string} outFile  - Output file path for the audio
 * @param {object} options
 * @param {string}  [options.speaker="default"]   - Speaker name or custom voice UUID
 * @param {string}  [options.dialect="modern"]     - Dialect variant
 * @param {string}  [options.languageId="ar"]      - Language code
 * @param {boolean} [options.mulaw=false]          - Use mu-law encoding
 */
function synthesizeSpeech(text, outFile, options = {}) {
  const {
    speaker = "default",
    dialect = "modern",
    languageId = "ar",
    mulaw = false,
  } = options;

  const ws = new WebSocket(WS_URL);
  const audioChunks = [];

  ws.on("open", () => {
    console.log("[TTS] Connected to Hamsa WebSocket server");

    const message = {
      type: "tts",
      payload: {
        text,
        speaker,
        dialect,
        languageId,
        mulaw,
      },
    };

    ws.send(JSON.stringify(message));
    console.log("[TTS] Request sent, streaming audio...");
  });

  ws.on("message", (data) => {
    // Binary data = audio chunk
    if (Buffer.isBuffer(data) || data instanceof ArrayBuffer) {
      const chunk = Buffer.from(data);
      audioChunks.push(chunk);
      return;
    }

    // Text data = JSON control message
    const text = data.toString();
    try {
      const json = JSON.parse(text);

      switch (json.type) {
        case "ack":
          console.log("[TTS] Acknowledged:", json.payload.message);
          break;
        case "end":
          console.log("[TTS] Stream complete:", json.payload.message);
          if (audioChunks.length > 0) {
            const output = path.resolve(outFile);
            fs.writeFileSync(output, Buffer.concat(audioChunks));
            console.log(`[TTS] Audio saved to: ${output} (${Buffer.concat(audioChunks).length} bytes)`);
          }
          ws.close();
          break;
        case "error":
          console.error("[TTS] Error:", json.payload.message);
          break;
        case "info":
          console.log("[TTS] Info:", json.payload.message);
          break;
        default:
          console.log("[TTS] Message:", json);
      }
    } catch {
      console.log("[TTS] Raw message:", text);
    }
  });

  ws.on("error", (err) => {
    console.error("[TTS] WebSocket error:", err.message);
  });

  ws.on("close", (code, reason) => {
    console.log(`[TTS] Connection closed (code: ${code}, reason: ${reason})`);
  });

  return ws;
}

/**
 * Preload a custom cloned voice before using it in TTS.
 * Must be called before synthesizeSpeech with a custom voice UUID.
 * @param {string} voiceId - Custom voice UUID
 */
async function preloadCustomVoice(voiceId) {
  const res = await fetch("https://api.tryhamsa.com/v2/tts/voices/custom/preload", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Api-Key": API_KEY,
    },
    body: JSON.stringify({ voice_id: voiceId }),
  });

  if (!res.ok) {
    throw new Error(`Preload failed: ${res.status} ${res.statusText}`);
  }

  console.log(`[TTS] Custom voice ${voiceId} preloaded`);
  return res.json();
}

// --- CLI usage: node websocket-tts.js "<text>" [output.wav] [language] ---
if (require.main === module) {
  const text = process.argv[2];
  const outFile = process.argv[3] || "output.wav";
  const languageId = process.argv[4] || "ar";

  if (!text) {
    console.log('Usage: node websocket-tts.js "<text>" [output-file] [language]');
    console.log('Example: node websocket-tts.js "مرحبا بالعالم" output.wav ar');
    process.exit(1);
  }

  if (!API_KEY || API_KEY === "your_api_key_here") {
    console.error("Error: Set HAMSA_API_KEY in your .env file");
    process.exit(1);
  }

  synthesizeSpeech(text, outFile, { languageId });
}

module.exports = { synthesizeSpeech, preloadCustomVoice };

# Hamsa TTS WebSocket API - FAQ & Troubleshooting

**Last Updated**: February 15, 2026
**For**: Developers using Hamsa TTS WebSocket API with Python `websockets` library

---

## 🔥 Common Issues

### Q1: Why am I getting 640-byte incomplete audio responses?

**Symptom:**
```
[TTS] <<< COMPLETE: 1 chunks, 640 bytes  ❌
Expected: 80,000 - 400,000 bytes
```

**Root Cause:**
You're creating **too many new WebSocket connections** instead of reusing them. Hamsa's API has rate limiting on connection creation, and when you exceed the limit, it returns incomplete audio (exactly 640 bytes - just the WAV header).

**Solution:**
Implement **persistent WebSocket connections** that are reused across multiple TTS requests.

---

### Q2: How do I properly reuse WebSocket connections?

**✅ CORRECT Implementation:**

```python
class VoiceAgent:
    def __init__(self):
        self.tts_ws = None  # Persistent connection

    async def get_tts_connection(self):
        """Get or create persistent TTS WebSocket connection."""
        if self.tts_ws is None:
            print("Creating new persistent connection")
            self.tts_ws = await websockets.connect(
                f"wss://api.tryhamsa.com/v1/realtime/ws?api_key={API_KEY}",
                ping_interval=20,
                ping_timeout=10
            )
        else:
            # Check if connection is still open
            from websockets.protocol import State
            if self.tts_ws.state != State.OPEN:
                print("Connection closed, reconnecting")
                self.tts_ws = await websockets.connect(...)
            else:
                print("Reusing existing connection ✓")

        return self.tts_ws

    async def text_to_speech(self, text):
        """Generate TTS audio using persistent connection."""
        ws = await self.get_tts_connection()

        # Send TTS request
        await ws.send(json.dumps({
            "type": "tts",
            "payload": {
                "text": text,
                "speaker": "Majd",
                "dialect": "ksa",
                "languageId": "ar",
                "mulaw": False
            }
        }))

        # Collect audio chunks
        audio_chunks = []
        async for message in ws:
            if isinstance(message, bytes):
                audio_chunks.append(message)
            else:
                data = json.loads(message)
                if data.get("type") == "end":
                    break

        # ✅ Connection stays OPEN for next request
        return b"".join(audio_chunks)

    async def close(self):
        """Close connection when session ends."""
        if self.tts_ws:
            await self.tts_ws.close()
```

**❌ WRONG Implementation (causes 640-byte failures):**

```python
async def text_to_speech(text):
    # ❌ Creates fresh connection EVERY time
    ws = await websockets.connect(
        f"wss://api.tryhamsa.com/v1/realtime/ws?api_key={API_KEY}"
    )

    await ws.send(json.dumps({"type": "tts", ...}))

    audio_chunks = []
    async for message in ws:
        # ... collect audio
        if data.get("type") == "end":
            break

    await ws.close()  # ❌ Closes immediately
    return b"".join(audio_chunks)

# Calling multiple times triggers rate limiting
audio1 = await text_to_speech("text 1")  # May work
audio2 = await text_to_speech("text 2")  # 640 bytes ❌
audio3 = await text_to_speech("text 3")  # 640 bytes ❌
```

---

### Q3: I'm checking `ws.closed` but getting AttributeError. Why?

**Error:**
```python
AttributeError: 'ClientConnection' object has no attribute 'closed'
```

**Problem:**
The Python `websockets` library's connection object **doesn't have a `.closed` attribute**.

**Wrong:**
```python
if self.tts_ws.closed:  # ❌ AttributeError!
    # reconnect
```

**Correct:**
```python
from websockets.protocol import State

if self.tts_ws.state != State.OPEN:  # ✅ Correct!
    # reconnect
```

**Alternative (simpler but less precise):**
```python
try:
    await self.tts_ws.ping()  # Test if connection is alive
    # Connection is alive
except:
    # Connection is dead, reconnect
    self.tts_ws = await websockets.connect(...)
```

---

### Q4: How long does a WebSocket connection stay alive?

**Hamsa's Connection Lifetime:**
- Server sends **ping frames every 30 seconds**
- Connection **auto-closes after 60 minutes** of inactivity
- You can keep a connection alive indefinitely by using it

**Best Practice:**
```python
ws = await websockets.connect(
    url,
    ping_interval=20,  # Send ping every 20 seconds
    ping_timeout=10    # Wait 10 seconds for pong response
)
```

This ensures the connection stays alive even during idle periods.

---

### Q5: Can the first TTS request also get 640 bytes?

**Yes!** If you've hit account-level or IP-level rate limits from previous sessions/tests.

**Solution:**
- Wait 30-60 seconds between testing sessions
- Implement exponential backoff retry logic:

```python
async def tts_with_retry(text, max_retries=2):
    for attempt in range(max_retries + 1):
        audio = await text_to_speech(text)

        # Check if audio is complete (>10KB typically means success)
        if len(audio) > 10000:
            return audio

        # Incomplete audio, retry with delay
        if attempt < max_retries:
            delay = 2 ** attempt  # 1s, 2s, 4s
            print(f"Incomplete audio ({len(audio)} bytes), retrying in {delay}s...")
            await asyncio.sleep(delay)

    raise Exception(f"Failed after {max_retries + 1} attempts")
```

---

## 📊 Performance Tips

### Latency Breakdown

With persistent connections:

| Phase | Time | Optimization |
|-------|------|--------------|
| **First Request (per session)** | | |
| Connection establishment | ~1,200ms | One-time cost ✓ |
| TTS processing | ~3,000-5,000ms | Depends on text length |
| **Subsequent Requests** | | |
| Connection reuse | ~0ms | Free! ✓ |
| TTS processing | ~3,000-5,000ms | Same as above |

**Savings:** ~1,200ms per request (except first one)

### Multi-sentence Responses

For voice agents with multi-sentence responses:

```python
# Stream sentences to TTS in real-time
async def handle_conversation(user_input):
    # 1. Get LLM response (streaming)
    async for sentence in llm_stream(user_input):
        # 2. Immediately send to TTS (parallel with LLM)
        asyncio.create_task(text_to_speech(sentence))

    # User hears first sentence while LLM is still generating!
```

**Result:** 40-60% faster perceived response time

---

## 🛠️ Debugging

### Enable Detailed Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('websockets').setLevel(logging.DEBUG)
```

### Check Connection State

```python
from websockets.protocol import State

print(f"Connection state: {ws.state}")
# State.CONNECTING (0)
# State.OPEN (1)       ← Should be this during operation
# State.CLOSING (2)
# State.CLOSED (3)
```

### Monitor Audio Size

```python
audio = await text_to_speech(text)
print(f"Audio size: {len(audio)} bytes")

if len(audio) < 10000:
    print("⚠️  Suspiciously small - likely incomplete!")
else:
    print("✓ Normal size")
```

### Common Log Patterns

**✅ Good (connection reuse working):**
```
[TTS] Creating new persistent connection
[TTS] <<< COMPLETE: 7 chunks, 217,116 bytes, 4709ms
[TTS] Reusing existing connection ✓
[TTS] <<< COMPLETE: 5 chunks, 115,184 bytes, 4110ms
[TTS] Reusing existing connection ✓
[TTS] <<< COMPLETE: 6 chunks, 145,498 bytes, 4032ms
```

**❌ Bad (creating new connections every time):**
```
[TTS] Creating new persistent connection
[TTS] <<< COMPLETE: 1 chunks, 640 bytes, 2993ms  ❌
[TTS] Creating new persistent connection
[TTS] <<< COMPLETE: 1 chunks, 640 bytes, 3384ms  ❌
[TTS] Creating new persistent connection
[TTS] <<< COMPLETE: 5 chunks, 115,184 bytes, 4110ms
```

---

## 🎯 Quick Checklist

Before deploying to production, verify:

- [ ] Using persistent WebSocket connection (not creating new one per request)
- [ ] Checking connection state with `.state != State.OPEN` (not `.closed`)
- [ ] Setting `ping_interval=20, ping_timeout=10` in `websockets.connect()`
- [ ] Handling connection failures gracefully (auto-reconnect)
- [ ] Cleaning up connection on session end
- [ ] Logging audio sizes to detect 640-byte failures
- [ ] Implementing retry logic for incomplete audio
- [ ] Testing with multiple consecutive requests (3-5 in a row)

---

## 📚 Additional Resources

- [Hamsa API Documentation](https://api.tryhamsa.com/docs)
- [Python websockets Library Docs](https://websockets.readthedocs.io/)
- [WebSocket State Reference](https://websockets.readthedocs.io/en/stable/reference/protocol.html#websockets.protocol.State)

---

## 💡 Still Having Issues?

**Checklist:**
1. ✅ Are you using persistent connections? (not creating new ones each time)
2. ✅ Are you checking `ws.state` instead of `ws.closed`?
3. ✅ Are all TTS responses at least 10KB? (640 bytes = failure)
4. ✅ Are you seeing "Reusing existing connection" in logs?

**If still stuck:**
- Check your Hamsa API account limits
- Verify your API key is valid
- Test with longer text (50+ characters)
- Add delays between requests (rule out rate limiting)

---

**Document Version:** 1.0
**Compatible with:** `websockets` 12.0+, Python 3.11+
**Hamsa API Version:** v1

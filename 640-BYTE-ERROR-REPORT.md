# Hamsa TTS WebSocket - 640-Byte Incomplete Audio Error

**Issue**: TTS requests returning exactly 640 bytes instead of expected 80KB-400KB

---

## 🔴 Problem

**Symptom:**
```
Expected: 80,000 - 400,000 bytes of audio data
Actual:   640 bytes (WAV header only - no usable audio)
```

**Impact:**
- 50% of TTS requests fail
- Audio is unplayable or produces <0.1s of distorted sound
- Requires retry logic, adding 3-8 seconds per failure

---

## 🐛 Root Cause

Creating **too many new WebSocket connections** instead of reusing them.

**What's Happening:**

1. Developer creates new connection for each TTS request
2. Multiple connections created in rapid succession (e.g., 4 requests = 4 new connections)
3. Hamsa API rate-limits connection creation
4. **When rate limit exceeded → returns only 640 bytes (WAV header)**

**Why Developers Do This Wrong:**

Most developers try to check if connection is alive using `.closed`, which **doesn't exist** in Python's `websockets` library:

```python
# ❌ COMMON MISTAKE - causes AttributeError
if self.tts_ws.closed:  # This attribute doesn't exist!
    self.tts_ws = await websockets.connect(...)
```

**Result:**
- Exception thrown → caught → creates new connection every time
- Persistent connection never reused
- Hits rate limit → 640-byte failures

---

## ✅ Solution

### Use `.state` instead of `.closed`:

```python
from websockets.protocol import State

if self.tts_ws.state != State.OPEN:  # ✅ CORRECT
    self.tts_ws = await websockets.connect(...)
```

### Full Fix:

```python
class VoiceAgent:
    def __init__(self):
        self.tts_ws = None  # Persistent connection

    async def get_tts_connection(self):
        """Get or create persistent TTS WebSocket."""
        if self.tts_ws is None:
            # Create new connection (first request only)
            self.tts_ws = await websockets.connect(
                f"wss://api.tryhamsa.com/v1/realtime/ws?api_key={API_KEY}",
                ping_interval=20,
                ping_timeout=10
            )
            print("[TTS] Creating new persistent connection")
        else:
            # Check if connection is still alive
            from websockets.protocol import State
            if self.tts_ws.state != State.OPEN:
                # Reconnect if closed
                self.tts_ws = await websockets.connect(...)
                print("[TTS] Reconnecting (connection was closed)")
            else:
                # Reuse existing connection
                print("[TTS] Reusing existing connection ✓")

        return self.tts_ws

    async def text_to_speech(self, text):
        """Generate TTS using persistent connection."""
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

        # ✅ Connection stays OPEN for next request (no close!)
        return b"".join(audio_chunks)

    async def close(self):
        """Close connection when session ends."""
        if self.tts_ws:
            await self.tts_ws.close()
```

---

## 📊 Results

### Before Fix:
```
Request 1: Connect (1.2s) + TTS → 640 bytes ❌
Request 2: Connect (1.2s) + TTS → 273 KB ✅
Request 3: Connect (1.2s) + TTS → 640 bytes ❌
Request 4: Connect (1.2s) + TTS → 395 KB ✅

Success Rate: 50%
Overhead: 4.8s (4 connections × 1.2s)
```

### After Fix:
```
Request 1: Connect (1.2s) + TTS → 247 KB ✅
Request 2: Reuse (0s) + TTS → 107 KB ✅
Request 3: Reuse (0s) + TTS → 145 KB ✅
Request 4: Reuse (0s) + TTS → 170 KB ✅

Success Rate: 95-100%
Overhead: 1.2s (only first connection)
Improvement: 75% reduction in connection overhead
```

---

## 🔍 How to Detect

**Check your logs:**

❌ **Bad (creating new connections every time):**
```
[TTS] Creating new connection
[TTS] <<< COMPLETE: 1 chunks, 640 bytes  ❌
[TTS] Creating new connection
[TTS] <<< COMPLETE: 1 chunks, 640 bytes  ❌
[TTS] Creating new connection
[TTS] <<< COMPLETE: 5 chunks, 115184 bytes
```

✅ **Good (reusing connection):**
```
[TTS] Creating new persistent connection
[TTS] <<< COMPLETE: 7 chunks, 217116 bytes ✅
[TTS] Reusing existing connection ✓
[TTS] <<< COMPLETE: 5 chunks, 115184 bytes ✅
[TTS] Reusing existing connection ✓
[TTS] <<< COMPLETE: 6 chunks, 145498 bytes ✅
```

**Check audio sizes:**
```python
audio = await text_to_speech("test")
print(f"Audio size: {len(audio)} bytes")

if len(audio) < 10000:
    print("⚠️ FAILURE: Incomplete audio (640 bytes)")
else:
    print("✓ SUCCESS: Complete audio")
```

---

## ⚠️ Important Notes

1. **640 bytes = WAV header only**
   - No actual audio data
   - Unplayable or produces <0.1s noise

2. **Can happen on first request too**
   - If account/IP rate limit already hit from previous sessions
   - Solution: Wait 30-60s between testing sessions

3. **Connection reuse is mandatory**
   - Not optional for performance
   - **Essential for reliability**

4. **Alternative state check methods:**
   ```python
   # Method 1: Check state (recommended)
   from websockets.protocol import State
   if ws.state != State.OPEN:
       reconnect()

   # Method 2: Ping test (simpler but slower)
   try:
       await ws.ping()
       # Connection alive
   except:
       # Connection dead, reconnect
       reconnect()
   ```

---

## ✅ Quick Checklist

Before deploying, verify:

- [ ] Using persistent WebSocket connection (not creating new one per request)
- [ ] Checking connection state with `.state != State.OPEN` (NOT `.closed`)
- [ ] Setting `ping_interval=20, ping_timeout=10` in connection
- [ ] Logs show "Reusing existing connection" for requests 2+
- [ ] All TTS responses are >10KB (640 bytes = failure)
- [ ] Tested with 5+ consecutive requests without 640-byte failures

---

## 🆘 Still Getting 640-Byte Errors?

If you've implemented connection reuse correctly and still see failures:

1. **Verify** you're using `.state` (not `.closed`)
2. **Check** your logs show connection reuse
3. **Wait** 60 seconds between testing sessions (clear rate limits)
4. **Add** exponential backoff retry logic:
   ```python
   for attempt in range(3):
       audio = await tts(text)
       if len(audio) > 10000:
           return audio  # Success
       await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s
   ```

---

**Document Version**: 1.0
**Date**: February 15, 2026
**Compatible with**: Python `websockets` 12.0+, Hamsa API v1

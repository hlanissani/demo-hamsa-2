# TTS Audio Issue - Only 3 Chunks Received

## Problem
- Frontend receives only 3 audio chunks (640 bytes each = 1920 bytes total)
- This is only 60ms of audio (way too short!)
- Expected: 50-100+ chunks for a full TTS response

## What to Check in Railway Logs

Look for these log messages:

### 1. TTS Sentence Processing
```
[TTS-STREAM] sentence 1: '...'  ← How many sentences?
[TTS-STREAM] sentence 2: '...'
```

### 2. TTS WebSocket Response
```
[TTS-WS] sent request: '...'
[TTS-WS] ack: ...
[TTS-WS] done: X chunks, Y bytes  ← How many chunks?
```

### 3. Sentence Detection
```
[WEBHOOK] sentence ready (X chars): '...'  ← Are sentences detected?
[WEBHOOK] ✓ STREAMING MODE - Sentences streamed to TTS in real-time
```
OR
```
[WEBHOOK] ⚠️ NO STREAMING - Falling back to batch mode split
```

## Possible Causes

### A) Hamsa TTS Only Sent 3 Chunks
- Hamsa API issue
- Text too short
- Connection dropped

### B) TTS Loop Stopped Early
- Error in _call_tts_ws()
- Timeout (30s)
- WebSocket closed prematurely

### C) Sentence Not Sent to TTS
- Sentence detection failed
- Sentence queue empty
- TTS consumer not processing

## Quick Test

Add this log to see what's being sent to TTS:

In consumers.py line 106-107, the log should show:
```python
log(f"[TTS-STREAM] sentence {idx}: '{sentence[:80]}'")
```

Check Railway logs to see:
1. How many sentences were queued
2. What text was sent to Hamsa TTS
3. How many chunks Hamsa returned

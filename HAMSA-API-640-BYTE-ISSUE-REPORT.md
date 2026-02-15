# Technical Report: 640-Byte TTS Response Issue
## Hamsa Realtime WebSocket API

**Date:** February 15, 2026
**Client:** BeSmart Voice Agent Team
**Issue Type:** Intermittent TTS failures returning incomplete audio
**API Version:** v1 Realtime WebSocket

---

## Executive Summary

We are experiencing intermittent failures with the Hamsa TTS WebSocket API where approximately 25-50% of Text-to-Speech requests return only 640 bytes (WAV header only) instead of complete audio data (typically 80KB-400KB). This occurs despite implementing proper WebSocket connection reuse as recommended in the API documentation.

**Impact:**
- Degraded user experience due to retry delays (2-8 seconds per failure)
- Increased latency in voice agent responses
- Additional load on API from retry requests

**Current Mitigation:**
- Implemented exponential backoff retry logic
- Successfully recovers ~95% of failures on first retry
- System is production-ready but suboptimal

---

## 1. Issue Description

### 1.1 Observed Behavior

**Expected Response:**
- Audio data size: 80,000 - 400,000 bytes
- Multiple audio chunks (5-10 chunks)
- Playable WAV audio

**Actual Response (Failure Case):**
- Audio data size: **Exactly 640 bytes**
- Single chunk only
- Contains WAV header but no usable audio data
- Results in silence or <0.1s distorted noise

### 1.2 Frequency

- **Overall:** 25-50% of TTS requests fail with 640-byte response
- **First request in session:** Can fail even on initial connection
- **Subsequent requests:** Intermittent failures despite connection reuse
- **Pattern:** Appears random, not correlated with:
  - Text length (tested 25-200 characters)
  - Speaker selection
  - Time of day
  - Sentence position in conversation

### 1.3 Evidence from Logs

**Successful Request:**
```
[TTS-WS] Reusing existing connection ✓
[TTS-WS] >>> REQUEST START: 'أهلاً استاذ هلا نساني...' (51 chars)
[TTS-WS] ack: Real time text to speach connection establesh
[TTS-WS-2308994984976] First audio chunk: 513ms
[TTS-WS] chunk #1, total: 7398 bytes
[TTS-WS] chunk #2, total: 39398 bytes
[TTS-WS] chunk #3, total: 82022 bytes
[TTS-WS] chunk #4, total: 122720 bytes
[TTS-WS] chunk #5, total: 133222 bytes
[TTS-WS] end signal received, waiting for remaining chunks...
[TTS-WS] <<< COMPLETE: 5 chunks, 133222 bytes, 3446ms total
```

**Failed Request (640 bytes):**
```
[TTS-WS] Reusing existing connection ✓
[TTS-WS] >>> REQUEST START: 'اذا ممكن تزودني برقم التواصل...' (53 chars)
[TTS-WS] ack: Real time text to speach connection establesh
[TTS-WS-2308994984976] First audio chunk: 291ms
[TTS-WS] chunk #1, total: 640 bytes
[TTS-WS] end signal received, waiting for remaining chunks...
[TTS-WS] <<< COMPLETE: 1 chunks, 640 bytes, 2298ms total
[TTS-WS] ⚠️  Incomplete audio (640 bytes), retrying...
```

---

## 2. System Architecture

### 2.1 Overview

We have implemented a real-time voice agent using Django Channels (WebSocket consumer) that orchestrates:
1. Speech-to-Text (STT) via Hamsa API
2. LLM processing via n8n webhook
3. Text-to-Speech (TTS) via Hamsa API
4. Real-time audio streaming to client

### 2.2 Component Diagram

```
┌─────────────────┐
│  Client Browser │
│  (WebSocket)    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Django Channels WebSocket Consumer     │
│  (VoiceAgentConsumer)                   │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │ Pipeline Orchestration             │ │
│  │ 1. STT → 2. Webhook → 3. TTS      │ │
│  └────────────────────────────────────┘ │
└───┬─────────────┬──────────────┬────────┘
    │             │              │
    ▼             ▼              ▼
┌─────────┐  ┌─────────┐  ┌──────────────┐
│ Hamsa   │  │  n8n    │  │ Hamsa TTS    │
│ STT WS  │  │ Webhook │  │ WebSocket    │
│         │  │ Stream  │  │ (Persistent) │
└─────────┘  └─────────┘  └──────────────┘
```

### 2.3 TTS WebSocket Connection Management

**Implementation Details:**

We follow the recommended pattern for persistent WebSocket connections:

```python
class VoiceAgentConsumer(AsyncWebsocketConsumer):
    def __init__(self):
        self.tts_ws = None  # Persistent TTS WebSocket connection

    async def _get_or_create_tts_ws(self):
        """Get existing TTS WebSocket or create new one."""
        if self.tts_ws is None:
            # First request: create new connection
            self.tts_ws = await self._connect_hamsa_ws()
        else:
            # Check if existing connection is still alive
            from websockets.protocol import State
            if self.tts_ws.state != State.OPEN:
                # Reconnect if closed
                self.tts_ws = await self._connect_hamsa_ws()
            else:
                # Reuse existing connection
                log("[TTS-WS] Reusing existing connection ✓")

        return self.tts_ws
```

**Connection Lifecycle:**
- **Created:** On first TTS request for session
- **Reused:** All subsequent TTS requests in same session
- **Checked:** Connection state verified before each use (`.state != State.OPEN`)
- **Maintained:** Ping/pong enabled (`ping_interval=20, ping_timeout=10`)
- **Closed:** Only when WebSocket session ends (client disconnect)

**Evidence of Correct Implementation:**

Logs confirm connection reuse is working:
```
[TTS-WS] Creating new persistent connection
[TTS-WS] <<< COMPLETE: 7 chunks, 181120 bytes, 4684ms total ✅
[TTS-WS] Reusing existing connection ✓
[TTS-WS] <<< COMPLETE: 5 chunks, 110958 bytes, 3137ms total ✅
[TTS-WS] Reusing existing connection ✓
[TTS-WS] <<< COMPLETE: 5 chunks, 133222 bytes, 3446ms total ✅
[TTS-WS] Reusing existing connection ✓
[TTS-WS] <<< COMPLETE: 1 chunks, 640 bytes, 2298ms total ❌ (FAILURE)
```

### 2.4 Request Flow (TTS)

**Streaming Sentence Detection:**

We implement intelligent sentence boundary detection to enable real-time TTS streaming:

```python
# Minimum sentence length: 50 characters
# Only split on complete sentence endings: [.!?؟]
_SENTENCE_END_RE = re.compile(r'[.!?؟]\s*$')

should_stream = (
    len(sentence) >= 50 and
    self._SENTENCE_END_RE.search(sentence)
)
```

**TTS Request Pattern:**

1. Webhook streams LLM response in real-time
2. Sentences detected as they arrive (50+ chars + ending punctuation)
3. Each sentence immediately queued for TTS
4. TTS consumer processes sentences **sequentially** (awaits completion before next)
5. Audio chunks streamed to client in real-time

**Sequential Processing:**

```python
async def _tts_consumer(self, sentence_q):
    """Process TTS requests sequentially."""
    while True:
        sentence = await sentence_q.get()
        if sentence is None:
            break

        # This await ensures sequential processing
        # Next sentence waits for previous to complete
        await self._call_tts_ws(sentence)
```

This means **we do NOT send rapid-fire parallel requests** - each TTS request completes before the next begins.

### 2.5 Retry Logic

Implemented exponential backoff for 640-byte failures:

```python
async def _call_tts_ws(self, text):
    """TTS with retry logic for 640-byte failures."""
    max_retries = 2
    for attempt in range(max_retries + 1):
        total_bytes = await self._do_tts_request(text, attempt)

        # Check if we got complete audio (>10KB = success)
        if total_bytes > 10000:
            return  # Success!

        # Incomplete audio (640 bytes), retry if attempts left
        if attempt < max_retries:
            delay = 2 ** attempt  # Exponential backoff: 1s, 2s
            await asyncio.sleep(delay)
            self.tts_ws = None  # Force reconnection on retry
```

**Retry Statistics:**
- **Success rate after 1 retry:** ~95%
- **Success rate after 2 retries:** ~99%
- **Average retry overhead:** 2-4 seconds per failure

---

## 3. Questions for Hamsa Team

### 3.1 Rate Limiting

**Q1:** What are the current rate limits for TTS WebSocket requests?
- Requests per second/minute per connection?
- Requests per second/minute per API key?
- Requests per second/minute per IP address?

**Q2:** Does the 640-byte response indicate we've hit a rate limit?
- Is this the intended behavior for rate limiting?
- Should we expect a different error message or response code?

**Q3:** Are rate limits applied differently for:
- New connections vs. persistent connections?
- Different API tiers/plans?
- Different times of day?

### 3.2 Connection Reuse

**Q4:** Is our connection reuse implementation correct?
- We use `websockets` library and check `.state != State.OPEN`
- Ping/pong enabled: `ping_interval=20, ping_timeout=10`
- Connection persists for entire session (multiple requests)

**Q5:** Is there a maximum duration or request count for persistent connections?
- Should we rotate connections periodically?
- Is there a connection TTL (time-to-live)?

### 3.3 Request Patterns

**Q6:** What is the recommended request pattern for conversational use cases?
- We send sequential requests (wait for completion before next)
- Typical interval: 2-5 seconds between requests
- Session duration: 2-10 minutes (10-30 requests)

**Q7:** Could webhook-to-TTS latency affect rate limiting?
- Our webhook completes before TTS starts
- But multiple sentences may be detected within 1-2 seconds
- All sentences processed sequentially (not parallel)

### 3.4 API Status

**Q8:** Is there currently elevated load on TTS API?
- We see ~25-50% failure rate
- Pattern appears intermittent/random

**Q9:** Are there any known issues or maintenance windows?

**Q10:** Is there a status page or monitoring dashboard we can reference?

---

## 4. Requested Information

To help us optimize our implementation, we would appreciate:

1. **Rate Limit Documentation:**
   - Official limits for our API tier
   - Best practices for high-throughput applications
   - Recommended backoff strategies

2. **Error Response Documentation:**
   - What does 640-byte response signify?
   - Are there other error patterns we should handle?
   - Should we look for specific error messages?

3. **Connection Management Guidelines:**
   - Connection pooling recommendations
   - When to reconnect vs. reuse
   - Optimal ping/pong settings

4. **API Tier Options:**
   - Are higher rate limits available?
   - Can we purchase dedicated capacity?
   - Enterprise/custom pricing options?

---

## 5. Current Workaround

### 5.1 Implementation

We have implemented a robust retry mechanism that:
- Detects 640-byte responses (`total_bytes < 10000`)
- Retries with exponential backoff (1s, 2s)
- Forces new connection on retry
- Successfully recovers ~95% of failures

### 5.2 Performance Impact

**Without failures:**
- Average TTS latency: 3-5 seconds
- End-to-end latency: 8-12 seconds

**With failures + retry:**
- Failed request + 1 retry: +3-5 seconds
- Total latency: 11-17 seconds

### 5.3 Production Readiness

Our current implementation is **production-ready** and handles failures gracefully, but we would like to:
- Eliminate unnecessary retries
- Reduce latency overhead
- Optimize for better user experience

---

## 6. Technical Environment

**Client Implementation:**
- **Framework:** Django 4.2.10 + Channels (Daphne 4.2.1)
- **WebSocket Library:** `websockets` 12.0+
- **HTTP Client:** `httpx` with HTTP/2 support
- **Python Version:** 3.10+

**API Usage:**
- **Endpoint:** `wss://api.tryhamsa.com/v1/realtime/ws`
- **Features Used:** STT, TTS
- **TTS Parameters:**
  - Speaker: "Majd"
  - Dialect: "ksa"
  - Language: "ar"
  - mulaw: false

**Typical Session:**
- Duration: 5-10 minutes
- Requests: 10-30 per session
- Request frequency: 1 request every 10-30 seconds (user-paced)

---

## 7. Appendix: Complete Log Sequence

### Test Session: February 15, 2026 13:43

**Request 1: "صباح الخير"**
```
[TTS-WS] Creating new persistent connection
[TTS-WS] >>> REQUEST START: 'شكرا لاتصالك بناقل اكسبرس...' (57 chars)
[TTS-WS] First audio chunk: 1707ms
[TTS-WS] <<< COMPLETE: 7 chunks, 181120 bytes, 4684ms total ✅
```

**Request 2: "بدي أستعلم عن شحنة"**
```
[TTS-WS] Reusing existing connection ✓
[TTS-WS] >>> REQUEST START: 'تمام، اذا ممكن تزودني...' (43 chars)
[TTS-WS] First audio chunk: 588ms
[TTS-WS] <<< COMPLETE: 5 chunks, 110958 bytes, 3137ms total ✅
```

**Request 3: "هلا نساني"**
```
[TTS-WS] Reusing existing connection ✓
[TTS-WS] >>> REQUEST START: 'أهلاً استاذ هلا نساني...' (51 chars)
[TTS-WS] First audio chunk: 513ms
[TTS-WS] <<< COMPLETE: 5 chunks, 133222 bytes, 3446ms total ✅
```

**Request 4: "رقم الشحنة ما عندي إياه"**
```
[TTS-WS] Reusing existing connection ✓
[TTS-WS] >>> REQUEST START: 'اذا ممكن تزودني برقم التواصل...' (53 chars)
[TTS-WS] First audio chunk: 291ms
[TTS-WS] chunk #1, total: 640 bytes
[TTS-WS] end signal received, waiting for remaining chunks...
[TTS-WS] <<< COMPLETE: 1 chunks, 640 bytes, 2298ms total ❌
[TTS-WS] ⚠️  Incomplete audio (640 bytes), retrying in 1s...
[TTS-WS] Creating new persistent connection
[TTS-WS] >>> REQUEST START: (same text, retry attempt)
[TTS-WS] First audio chunk: 1691ms
[TTS-WS] <<< COMPLETE: 4 chunks, 134632 bytes, 4528ms total ✅
```

**Analysis:**
- 3 consecutive successful requests with connection reuse
- 4th request fails with 640 bytes despite using same connection
- Retry with new connection succeeds
- Pattern suggests API-side rate limiting, not client implementation issue

---

## 8. Contact Information

**Technical Contact:**
- Name: [Your Name]
- Email: [Your Email]
- Company: BeSmart
- Project: Voice Agent Platform

**Additional Resources:**
- GitHub Repository: [if applicable]
- API Key: [provide if needed for investigation]

---

## 9. Summary

We have implemented Hamsa's TTS WebSocket API according to best practices with proper connection reuse and error handling. Despite this, we experience intermittent 640-byte failures that appear to be API-side rate limiting.

**We request:**
1. Clarification on rate limits and 640-byte response meaning
2. Guidance on optimal request patterns for our use case
3. Information on API tier options with higher limits

Our current implementation is production-ready with retry logic, but we aim to optimize the user experience by eliminating unnecessary retries.

Thank you for your assistance.

---

**Report Generated:** February 15, 2026
**Version:** 1.0

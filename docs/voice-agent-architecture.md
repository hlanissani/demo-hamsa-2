# Voice Agent Architecture Guide

## Overview
Voice agents convert spoken language into actions and responses. They're used in customer service, virtual assistants, and automated phone systems.

---

## Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    VOICE AGENT PIPELINE                      │
└─────────────────────────────────────────────────────────────┘

[User Speaks]
     │
     ▼
┌─────────────────┐
│  1. ASR         │  Speech → Text
│  (Whisper, etc) │  "مرحبا" (audio) → "مرحبا" (text)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  2. NLU/Intent  │  Text → Structured Data
│  Classification │  "مرحبا" → {intent: "greeting", lang: "ar"}
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  3. Dialog      │  Context + Intent → Action
│  Management     │  Check session, determine next step
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  4. Business    │  Execute Actions
│  Logic / Tools  │  Query DB, call APIs, lookup data
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  5. NLG         │  Data → Natural Response
│  Response Gen   │  Format message using templates/AI
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  6. TTS         │  Text → Speech
│  (ElevenLabs)   │  "شكرا لاتصالك" (text) → audio
└────────┬────────┘
         │
         ▼
   [User Hears]
```

---

## 1. ASR (Automatic Speech Recognition)

**Purpose:** Convert audio to text

**Popular Services:**
- **OpenAI Whisper** - Best multilingual support (Arabic + English)
- **Google Speech-to-Text** - Fast, good for real-time
- **Azure Speech** - Enterprise-grade
- **Deepgram** - Ultra-low latency (< 300ms)

**Implementation:**
```python
# Example: Whisper API
import openai

audio_file = open("customer_voice.wav", "rb")
transcript = openai.Audio.transcribe(
    model="whisper-1",
    file=audio_file,
    language="ar"  # Arabic
)
# Result: "اسمي احمد محمد"
```

**Key Metrics:**
- Latency: 500ms - 2s
- Accuracy: 90-95% (depends on audio quality)
- Cost: ~$0.006/minute (Whisper)

---

## 2. Intent Classification (NLU)

**Purpose:** Understand what user wants

**Approaches:**

### A. Rule-Based (Fastest)
```javascript
// Regex patterns
if (text.match(/NQL\d+/)) {
  intent = "provide_waybill";
  waybill = text.match(/NQL\d+/)[0];
}
```
- **Pros:** < 50ms, zero cost, deterministic
- **Cons:** Brittle, needs maintenance
- **Use when:** Structured data (phone, waybill, yes/no)

### B. AI-Based (Flexible)
```javascript
// LLM classification
const prompt = `
Extract intent from: "${text}"
Options: greeting, provide_name, provide_waybill
Return JSON only.
`;
```
- **Pros:** Handles edge cases, multilingual
- **Cons:** 300-1000ms latency, costs money
- **Use when:** Complex intents, ambiguous input

### C. Hybrid (Best of Both)
```javascript
// Try regex first, fallback to AI
const waybill = text.match(/NQL\d+/);
if (waybill) {
  return {intent: "waybill", data: waybill[0]};
}
// If no pattern match, call AI
return await classifyWithAI(text);
```

---

## 3. Dialog Management

**Purpose:** Track conversation state and decide next step

**State Management:**

```javascript
// Session state
{
  session_id: "abc123",
  stage: "awaiting_waybill",
  customer_name: "احمد محمد",
  language: "ar",
  history: [
    {role: "assistant", text: "كيف اقدر اساعدك؟"},
    {role: "user", text: "اسمي احمد محمد"}
  ]
}
```

**Storage Options:**
- **Redis** - Fast (< 10ms), good for real-time
- **PostgreSQL** - Persistent, good for analytics
- **In-Memory** - Ultra-fast but lost on restart

**Flow Logic:**
```javascript
// State machine
const nextStage = {
  greeting: "awaiting_name",
  awaiting_name: "awaiting_waybill",
  awaiting_waybill: "deliver_status",
  deliver_status: "awaiting_additional_service"
};

currentStage = nextStage[currentStage];
```

---

## 4. Business Logic / Tools

**Purpose:** Execute actions (database queries, API calls)

**Examples:**
- Lookup shipment by waybill
- Search by phone number
- Update order status
- Create support ticket

**Implementation Patterns:**

### A. Direct Database
```python
result = db.query(
    "SELECT * FROM shipments WHERE waybill = ?",
    [waybill]
)
```

### B. API Call
```python
response = requests.post(
    "https://api.naqel.com/tracking",
    json={"waybill": waybill}
)
```

### C. MCP Tool (Model Context Protocol)
```json
{
  "tool": "NaqelTrackingDB",
  "parameters": {
    "waybill_number": "NQL123456"
  }
}
```

---

## 5. Response Generation (NLG)

**Purpose:** Create natural language responses

**Approaches:**

### A. Templates (Fastest)
```javascript
const templates = {
  greeting: {
    ar: "شكرا لاتصالك بناقل اكسبرس",
    en: "Thank you for calling Naqel Express"
  }
};
response = templates[intent][language];
```
- **Speed:** < 1ms
- **Use when:** Fixed scripts, compliance required

### B. Template + Variables
```javascript
const script = "أهلاً استاذ {name}، شحنتك رقم {waybill} تم التسليم بتاريخ {date}";
response = script
  .replace("{name}", customerName)
  .replace("{waybill}", waybill)
  .replace("{date}", deliveryDate);
```
- **Speed:** < 10ms
- **Use when:** Structured responses with dynamic data

### C. RAG (Retrieval-Augmented Generation)
```javascript
// 1. Search knowledge base
const script = await vectorDB.search({
  query: "Shipment Delivered",
  topK: 1
});

// 2. Fill with data
response = fillTemplate(script, trackingData);
```
- **Speed:** 200-500ms
- **Use when:** Complex scripts, compliance docs

### D. Full AI Generation
```javascript
const prompt = `
Generate Arabic response for delivered shipment.
Data: ${JSON.stringify(trackingData)}
Style: Formal, Saudi dialect
`;
response = await llm.generate(prompt);
```
- **Speed:** 1-3 seconds
- **Use when:** Personalized, conversational

---

## 6. TTS (Text-to-Speech)

**Purpose:** Convert text response to audio

**Popular Services:**
- **ElevenLabs** - Most natural (Arabic support)
- **Azure TTS** - Good Arabic voices
- **Google TTS** - Fast, affordable
- **AWS Polly** - Wide language support

**Implementation:**
```python
import elevenlabs

audio = elevenlabs.generate(
    text="شكرا لاتصالك بناقل اكسبرس",
    voice="Hamza",  # Arabic voice
    model="eleven_multilingual_v2"
)
```

**Optimization:**
- **Streaming:** Start playing while generating (reduces perceived latency)
- **Chunking:** Split long responses into sentences
- **Caching:** Pre-generate common phrases

---

## Performance Targets

| Component | Target | Typical | Fast |
|-----------|--------|---------|------|
| ASR | < 1s | 1-2s | 300ms (Deepgram) |
| Intent | < 500ms | 500ms-1s | 50ms (regex) |
| Dialog | < 100ms | 50-100ms | 10ms (Redis) |
| Tools | < 500ms | 300-500ms | 100ms (cached) |
| NLG | < 500ms | 500ms-2s | 1ms (template) |
| TTS | < 1s | 1-2s | 500ms (streaming) |
| **Total** | **< 3s** | **3-6s** | **< 2s** |

---

## Architecture Patterns

### Pattern 1: Monolithic (Simple)
```
ASR → Single Agent (handles everything) → TTS
```
- **Pros:** Easy to build
- **Cons:** Slow (3-6s), hard to debug
- **Use when:** Prototype, low volume

### Pattern 2: Pipeline (Optimized)
```
ASR → Intent → Dialog → Tools → NLG → TTS
```
- **Pros:** Fast (< 2s), reusable components
- **Cons:** More complex setup
- **Use when:** Production, high volume

### Pattern 3: Hybrid (Your Approach)
```
ASR → [Intent Classifier (regex)]
          ↓
     [Route by Action]
          ↓
     ┌────┴─────┬──────────┐
     ▼          ▼          ▼
  [Template] [Tools+RAG] [AI Gen]
     └────┬─────┴──────────┘
          ▼
        TTS
```
- **Pros:** Fast templates (70%), accurate RAG (30%)
- **Cons:** More logic to maintain
- **Use when:** Performance + accuracy required

---

## Your Naqel Voice Agent Architecture

Based on your n8n workflows:

```
┌─────────────────────────────────────────────────────────┐
│              EXTERNAL VOICE PLATFORM                    │
│          (Twilio / Vapi / Custom WebRTC)                │
└─────────────────────┬───────────────────────────────────┘
                      │
                      │ 1. Audio Stream
                      ▼
              ┌───────────────┐
              │  ASR Service  │ (Whisper/Deepgram)
              │  Audio → Text │
              └───────┬───────┘
                      │
                      │ 2. POST /webhook/besmart/voice/agent/
                      │    {text: "...", session_id: "..."}
                      ▼
         ┌────────────────────────────────────┐
         │  N8N WORKFLOW 1: Orchestrator      │
         │  ┌──────────┐  ┌──────────────┐   │
         │  │ Webhook  ├─→│ Prepare      │   │
         │  │ Receiver │  │ Context      │   │
         │  └──────────┘  └──────┬───────┘   │
         └────────────────────────┼───────────┘
                                  │
                                  │ 3. HTTP Call
                                  ▼
         ┌────────────────────────────────────┐
         │  N8N WORKFLOW 2: Intent Classifier │
         │  ┌──────────────────────────────┐  │
         │  │  Function Node (Pure JS)     │  │
         │  │  - Regex: NQL\d+             │  │
         │  │  - Regex: 05\d{8}            │  │
         │  │  - Detect: نعم/لا             │  │
         │  │  Returns: {next_action, ...} │  │
         │  └──────────────┬───────────────┘  │
         └─────────────────┼───────────────────┘
                           │
                           │ 4. Returns intent
                           ▼
         ┌────────────────────────────────────┐
         │  N8N WORKFLOW 1: Route by Action   │
         │         ┌─────────────┐            │
         │         │   Switch    │            │
         │         └──┬──┬───┬──┘            │
         │            │  │   │                │
         └────────────┼──┼───┼────────────────┘
                      │  │   │
        ┌─────────────┘  │   └─────────────┐
        │                │                 │
        │ lookup_waybill │ ask_name        │
        ▼                ▼                 ▼
 ┌─────────────┐  ┌──────────────┐  ┌──────────────┐
 │ WORKFLOW 3: │  │ WORKFLOW 4:  │  │ WORKFLOW 4:  │
 │ Data Lookup │  │ Response Gen │  │ Response Gen │
 │             │  │              │  │              │
 │ Query DB by │  │ RAG: Search  │  │ Template:    │
 │ waybill/    │  │ Qdrant for   │  │ "اذا ممكن   │
 │ phone       │  │ script       │  │  تزودني..."  │
 └──────┬──────┘  └──────┬───────┘  └──────┬───────┘
        │                │                 │
        └────────────────┴─────────────────┘
                         │
                         │ 5. Final response
                         ▼
         ┌────────────────────────────────────┐
         │  N8N WORKFLOW 1: Respond           │
         │  Returns: {text: "...", ...}       │
         └───────────────┬────────────────────┘
                         │
                         │ 6. HTTP Response
                         ▼
              ┌───────────────┐
              │  TTS Service  │ (ElevenLabs)
              │  Text → Audio │
              └───────┬───────┘
                      │
                      │ 7. Audio Stream
                      ▼
┌─────────────────────────────────────────────────────────┐
│              EXTERNAL VOICE PLATFORM                    │
│          User hears response                            │
└─────────────────────────────────────────────────────────┘
```

---

## Integration with Voice Platforms

Your n8n workflow needs to integrate with a voice platform:

### Option 1: Twilio (Popular)
```python
from twilio.twiml.voice_response import VoiceResponse

@app.route('/voice', methods=['POST'])
def voice():
    response = VoiceResponse()

    # 1. Gather speech input
    gather = response.gather(
        input='speech',
        language='ar-SA',  # Saudi Arabic
        action='/process'
    )

    return str(response)

@app.route('/process', methods=['POST'])
def process():
    # 2. Get transcribed text
    text = request.form['SpeechResult']
    session_id = request.form['CallSid']

    # 3. Call your n8n workflow
    result = requests.post(
        'https://n8n-service.onrender.com/webhook/besmart/voice/agent/',
        json={'text': text, 'session_id': session_id}
    )

    # 4. Convert response to speech
    response = VoiceResponse()
    response.say(
        result.json()['text'],
        voice='Polly.Zeina',  # Arabic voice
        language='ar-SA'
    )

    return str(response)
```

### Option 2: Vapi.ai (AI-First)
```javascript
// Vapi configuration
{
  "assistant": {
    "name": "Majed - Naqel Support",
    "voice": "ar-SA-HamedNeural",  // Azure voice
    "model": {
      "provider": "custom",
      "url": "https://n8n-service.onrender.com/webhook/besmart/voice/agent/"
    },
    "firstMessage": "شكرا لاتصالك بناقل اكسبرس"
  }
}
```

### Option 3: Custom WebRTC
```javascript
// Real-time voice pipeline
const stream = await getUserMedia();

// Send audio chunks
stream.getTracks()[0].addEventListener('data', async (chunk) => {
  // 1. Send to ASR
  const text = await whisper.transcribe(chunk);

  // 2. Call n8n
  const response = await fetch('/webhook/besmart/voice/agent/', {
    method: 'POST',
    body: JSON.stringify({text, session_id})
  });

  // 3. Convert to speech
  const audio = await elevenLabs.generate(response.text);

  // 4. Play to user
  audioElement.src = audio;
  audioElement.play();
});
```

---

## Best Practices

### 1. Latency Optimization
```javascript
// ✅ GOOD: Parallel execution
const [intent, sessionData] = await Promise.all([
  classifyIntent(text),
  loadSession(sessionId)
]);

// ❌ BAD: Sequential
const intent = await classifyIntent(text);
const sessionData = await loadSession(sessionId);
```

### 2. Error Handling
```javascript
try {
  const data = await lookupWaybill(waybill);
} catch (error) {
  // Fallback response
  return {
    text: "للاسف، النظام مشغول حالياً. الرجاء المحاولة لاحقاً",
    retry: true
  };
}
```

### 3. Streaming TTS
```javascript
// Start playing audio BEFORE full generation
const stream = elevenLabs.generateStream(longText);

stream.on('data', (chunk) => {
  audioQueue.push(chunk);
  if (!isPlaying) {
    playAudio(); // Start immediately
  }
});
```

### 4. Session Management
```javascript
// Keep only last N turns (not full history)
const recentHistory = history.slice(-4); // Last 2 exchanges

// Set expiry
redis.setex(`session:${id}`, 300, JSON.stringify(data)); // 5 min
```

### 5. Monitoring
```javascript
// Track key metrics
metrics.timing('asr_latency', asrTime);
metrics.timing('intent_latency', intentTime);
metrics.timing('total_latency', totalTime);
metrics.increment('errors.asr_failed');
```

---

## Common Pitfalls

1. **Full conversation history** → Slow, expensive
   - Solution: Keep last 2-4 turns only

2. **AI for everything** → High latency
   - Solution: Use templates for 70% of responses

3. **No streaming** → User waits for full response
   - Solution: Stream TTS output

4. **Synchronous tools** → Blocking
   - Solution: Use async/await, parallel calls

5. **No timeout handling** → Calls hang
   - Solution: Set 3-5 second timeouts

---

## Testing Voice Agents

### Unit Testing
```javascript
// Test intent classifier
assert.equal(
  classifyIntent("NQL123456").intent,
  "provide_waybill"
);
```

### Integration Testing
```bash
# Test full n8n workflow
curl -X POST https://n8n.../webhook/besmart/voice/agent/ \
  -d '{"text": "اسمي احمد", "session_id": "test"}'
```

### Load Testing
```javascript
// Simulate 100 concurrent calls
await Promise.all(
  Array(100).fill().map(() =>
    callVoiceAgent({text: "مرحبا", session_id: uuid()})
  )
);
```

### Voice Quality Testing
- Record real calls
- Measure transcription accuracy (ASR)
- Check TTS naturalness (human evaluation)
- Verify response relevance

---

## Cost Estimation

For 1000 calls/day, 3 min average:

| Component | Provider | Cost/min | Monthly |
|-----------|----------|----------|---------|
| ASR | Whisper | $0.006 | $540 |
| Intent | GPT-4o-mini | $0.0001 | $9 |
| TTS | ElevenLabs | $0.18 | $16,200 |
| Hosting | Render | - | $25 |
| **Total** | | | **~$16,774** |

**Optimization:**
- Use Haiku instead of GPT → Save 50%
- Use templates instead of AI → Save 70%
- Cache common responses → Save 30%

**Optimized monthly:** ~$5,000

---

## Resources

- **Twilio Voice Docs:** https://www.twilio.com/docs/voice
- **OpenAI Whisper:** https://platform.openai.com/docs/guides/speech-to-text
- **ElevenLabs TTS:** https://elevenlabs.io/docs
- **Vapi.ai:** https://docs.vapi.ai
- **n8n Voice Templates:** https://n8n.io/workflows/voice-assistant

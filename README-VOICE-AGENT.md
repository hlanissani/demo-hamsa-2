# N8N Voice Agent - Implementation Summary

## 🎯 What You're Building

A complete voice agent for Naqel Express customer support that:
- Handles phone calls in Arabic & English
- Tracks shipments by waybill or phone number
- Uses templates for fast responses (< 300ms)
- Uses RAG for accurate status messages
- Manages conversation state across turns
- **Target: < 2 seconds total response time**

---

## 📋 Architecture Overview

```
Phone Call
    ↓
Voice Platform (Twilio/Vapi)
    ├─ ASR: Speech → Text
    └─ TTS: Text → Speech
    ↓
N8N Workflows (Your Backend)
    ├─ Main Orchestrator
    ├─ Intent Classifier (< 50ms)
    ├─ Data Lookup (DB query)
    └─ Response Generator (Templates/RAG)
    ↓
Response back to user
```

---

## 📂 Files You Have

### Documentation
1. **[docs/voice-agent-architecture.md](docs/voice-agent-architecture.md)**
   - Complete architecture explanation
   - How ASR, NLU, Dialog, Tools, NLG, TTS work
   - Performance targets and optimization

2. **[docs/quick-setup-guide.md](docs/quick-setup-guide.md)**
   - Step-by-step setup for Vapi (15 min) or Twilio (30 min)
   - Bridge server code
   - Testing procedures

3. **[docs/n8n-voice-agent-implementation.md](docs/n8n-voice-agent-implementation.md)**
   - N8N-specific implementation
   - 4 complete workflows with JSON
   - Testing commands

### N8N Workflows

#### Your Original Workflows
Located in `n8n-workflows/`:
1. `1-orchestrator-main.json` - Main routing logic
2. `2-intent-classifier.json` - Fast regex classifier
3. `3-data-lookup.json` - Database queries
4. `4-response-generator.json` - Templates + RAG

#### Production-Ready Version
Located in `n8n-workflows/production-ready/`:
1. `1-main-orchestrator.json` - Enhanced with Redis session management

---

## 🚀 Quick Start (3 Steps)

### Step 1: Import N8N Workflows

```bash
# In n8n:
1. Go to Workflows
2. Click "Import from JSON"
3. Import these 4 files in order:
   - n8n-workflows/2-intent-classifier.json
   - n8n-workflows/3-data-lookup.json
   - n8n-workflows/4-response-generator.json
   - n8n-workflows/production-ready/1-main-orchestrator.json
4. Activate all workflows
```

### Step 2: Set Environment Variables

Add to your n8n instance (Render dashboard → Environment):

```bash
N8N_WEBHOOK_BASE_URL=https://n8n-service-z1ur.onrender.com
WEBHOOK_URL=https://n8n-service-z1ur.onrender.com
```

### Step 3: Choose Voice Platform

**Option A: Vapi.ai (Easiest - 15 minutes)**

1. Sign up at https://vapi.ai
2. Create assistant with this config:

```json
{
  "name": "Majed - Naqel Support",
  "voice": {
    "provider": "11labs",
    "voiceId": "pNInz6obpgDQGcFmaJgB"
  },
  "model": {
    "provider": "custom-llm",
    "url": "https://n8n-service-z1ur.onrender.com/webhook/voice/agent"
  },
  "firstMessage": "شكرا لاتصالك بناقل اكسبرس – معك ماجد – كيف اقدر اساعدك؟",
  "language": "ar"
}
```

3. Get phone number from Vapi
4. Call and test!

**Option B: Twilio (More Control - 30 minutes)**

See [docs/quick-setup-guide.md](docs/quick-setup-guide.md) for full Twilio setup with bridge server.

---

## 🧪 Testing

### Test 1: Intent Classifier Only
```bash
curl -X POST https://n8n-service-z1ur.onrender.com/webhook/voice/intent-classifier \
  -H "Content-Type: application/json" \
  -d '{
    "text": "اسمي احمد محمد",
    "session_id": "test-1",
    "previous_stage": "greeting"
  }'
```

**Expected:**
```json
{
  "current_stage": "awaiting_name",
  "extracted_data": {
    "customer_name": "احمد محمد",
    "waybill": null,
    "phone": null,
    "has_waybill": false
  },
  "next_action": "ask_waybill",
  "language": "ar"
}
```

### Test 2: Full Voice Agent
```bash
curl -X POST https://n8n-service-z1ur.onrender.com/webhook/voice/agent \
  -H "Content-Type: application/json" \
  -d '{
    "text": "مرحبا",
    "session_id": "session-123"
  }'
```

**Expected:**
```json
{
  "text": "شكرا لاتصالك بناقل اكسبرس – معك \"ماجد\" – كيف اقدر اساعدك؟",
  "session_id": "session-123",
  "stage": "greeting",
  "is_closing": false
}
```

### Test 3: Full Conversation Flow
```bash
# Turn 1: Greeting
curl -X POST .../webhook/voice/agent \
  -d '{"text": "مرحبا", "session_id": "test-conv"}'
# Response: "شكرا لاتصالك..."

# Turn 2: Name
curl -X POST .../webhook/voice/agent \
  -d '{"text": "اسمي احمد محمد", "session_id": "test-conv"}'
# Response: "أهلاً استاذ احمد محمد اذا ممكن تزودني برقم الشحنة"

# Turn 3: Waybill
curl -X POST .../webhook/voice/agent \
  -d '{"text": "NQL123456", "session_id": "test-conv"}'
# Response: [Status from database + KB script]
```

---

## ⚡ Performance Breakdown

| Component | Method | Time |
|-----------|--------|------|
| **Intent Classification** | Regex (JS) | < 50ms |
| **Simple Responses** | Templates | < 10ms |
| **Database Lookup** | PostgreSQL | 100-200ms |
| **RAG Response** | Qdrant + Fill | 200-400ms |
| **Session Load/Save** | Redis | < 10ms |
| **TOTAL (Simple)** | Template | **< 300ms** ✅ |
| **TOTAL (With DB)** | Template + DB | **< 500ms** ✅ |
| **TOTAL (With RAG)** | RAG + DB | **< 800ms** ✅ |

**Voice Platform adds:**
- ASR (Speech → Text): 500ms - 1s
- TTS (Text → Speech): 500ms - 1s
- **Grand Total: 1.5s - 3s** ✅ (Well under 5s target)

---

## 🎨 How It Works

### Example Conversation

**User:** "مرحبا" (Hello)
```
1. Voice Platform: ASR converts speech → "مرحبا"
2. Calls: /webhook/voice/agent
3. N8N Main Orchestrator:
   - Loads session (none exists)
   - Calls Intent Classifier
4. Intent Classifier (Regex):
   - Detects: is_greeting=true, language=ar
   - Returns: next_action="ask_name"
5. Response Generator:
   - Looks up template: templates.greeting.ar
   - Returns: "شكرا لاتصالك بناقل اكسبرس..."
6. Main Orchestrator:
   - Saves session to Redis
   - Returns response
7. Voice Platform: TTS converts → speech
8. User hears greeting
```

**User:** "اسمي احمد محمد" (My name is Ahmed Mohammed)
```
1. ASR → "اسمي احمد محمد"
2. N8N Intent Classifier:
   - Regex finds: "احمد محمد" (2 Arabic words)
   - Extracts: customer_name="احمد محمد"
   - Returns: next_action="ask_waybill"
3. Response Generator:
   - Template: "أهلاً استاذ {name} اذا ممكن تزودني برقم الشحنة"
   - Fills: {name} → "احمد محمد"
4. Returns: "أهلاً استاذ احمد محمد اذا ممكن تزودني برقم الشحنة"
```

**User:** "NQL123456"
```
1. ASR → "NQL123456"
2. Intent Classifier:
   - Regex: /NQL\\d+/ matches
   - Extracts: waybill="NQL123456"
   - Returns: next_action="lookup_waybill"
3. Main Orchestrator routes to Data Lookup
4. Data Lookup:
   - Queries: SELECT * FROM shipments WHERE waybill_number = 'NQL123456'
   - Returns: {status: 'delivered', delivery_date: '2025-01-15', ...}
5. Response Generator:
   - Maps status='delivered' → keyword='Shipment Delivered'
   - Searches Qdrant for 'Shipment Delivered' script
   - Gets: "شحنتك رقم {Waybill} تم تسليمها بتاريخ {Delivery Date}..."
   - Fills placeholders with tracking data
6. Returns: "شحنتك رقم NQL123456 تم تسليمها بتاريخ 15 يناير..."
```

---

## 🔧 Components Explained

### 1. Main Orchestrator
**What:** Entry point, routes to sub-workflows
**Speed:** < 50ms (just routing)
**Key Features:**
- Normalizes input from any voice platform
- Loads session from Redis
- Routes based on intent
- Saves session state

### 2. Intent Classifier
**What:** Extracts data using regex (NO AI)
**Speed:** < 50ms
**Extracts:**
- Customer name (Arabic/English)
- Waybill (NQL...)
- Phone (05... or +966...)
- Yes/No
- Language

### 3. Data Lookup
**What:** Queries database for tracking info
**Speed:** 100-200ms
**Queries:**
- By waybill number
- By phone number
**Returns:** Tracking data or NOT_FOUND

### 4. Response Generator
**What:** Creates response text
**Speed:** 10ms (template) or 300ms (RAG)
**Two modes:**
- **Template:** Instant, pre-written scripts
- **RAG:** Search knowledge base, fill placeholders

---

## 📊 Cost Estimation

### N8N Backend (Free Tier)
- Render: $0/month (or $25/month for always-on)
- Redis: Free tier sufficient
- PostgreSQL: Already have
- Qdrant: Already have

### Voice Platform

**Option 1: Vapi.ai**
- $0.05/min platform fee
- TTS (ElevenLabs): $0.18/min
- ASR (Deepgram): $0.0043/min
- **Total: ~$0.23/min**
- **1000 calls × 3 min = $690/month**

**Option 2: Twilio**
- Phone number: $1/month
- Incoming call: $0.0085/min
- Speech recognition: $0.02/min
- TTS: $4/1M characters (≈$0.02/min)
- **Total: ~$0.05/min**
- **1000 calls × 3 min = $150/month**

---

## 🚨 Troubleshooting

### Issue: "Cannot read properties of undefined"
**Fix:** Check webhook receives correct format:
```json
{
  "body": {
    "text": "message here",
    "session_id": "123"
  }
}
```

### Issue: Slow responses (> 5s)
**Fix:**
1. Check n8n execution logs
2. Look for timeouts in HTTP Request nodes
3. Verify Redis is responding (< 10ms)
4. Check if database queries are indexed

### Issue: Intent classifier not detecting Arabic
**Fix:**
- Verify UTF-8 encoding in all workflows
- Test regex pattern: `/[\u0600-\u06FF]/`
- Check voice platform is sending Arabic text correctly

### Issue: Voice platform can't reach n8n
**Fix:**
1. Verify webhook URL is public (not localhost)
2. Check Render logs for incoming requests
3. Test with curl first
4. Verify n8n webhook is activated

---

## 📈 Next Steps

1. ✅ **Import workflows** to n8n
2. ✅ **Test each component** individually
3. ✅ **Test full flow** with curl
4. ⬜ **Connect voice platform** (Vapi or Twilio)
5. ⬜ **Test real phone call**
6. ⬜ **Monitor performance**
7. ⬜ **Optimize based on metrics**

---

## 📚 Resources

- [Voice Agent Architecture](docs/voice-agent-architecture.md) - Deep dive into components
- [Quick Setup Guide](docs/quick-setup-guide.md) - Vapi & Twilio setup
- [N8N Implementation](docs/n8n-voice-agent-implementation.md) - N8N-specific details
- [Original Prompts](prompts/) - Your orchestrator and classifier prompts

---

## 🎉 You're Ready!

You have everything needed to build a production voice agent:

✅ **Fast intent classification** (< 50ms with regex)
✅ **Efficient data lookup** (< 200ms with indexed DB)
✅ **Smart response generation** (templates + RAG)
✅ **Session management** (Redis for speed)
✅ **Modular architecture** (reusable workflows)

**Total implementation time: 1-2 hours**

Need help with a specific part? Check the relevant doc file or ask!

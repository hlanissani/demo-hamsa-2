# RAG Voice Agent - Quick Setup

## What You Need

1. **Qdrant collection** with all voice scripts
2. **N8N workflow** that searches Qdrant for every response
3. **Voice platform** (Twilio/Vapi) connected to n8n

---

## Step 1: Populate Qdrant (5 minutes)

```bash
# Set credentials
export QDRANT_URL="your-qdrant-url"
export QDRANT_API_KEY="your-key"
export OPENAI_API_KEY="your-key"

# Run script
cd "c:\Users\Windows.10\Desktop\hamsa ws\scripts"
python populate_rag_knowledge_base.py
```

**Result:** 26 scripts uploaded to Qdrant
- Greetings (AR/EN)
- Questions (ask name, waybill, phone)
- Status messages (delivered, in_transit, etc.)
- Closing & error handling

---

## Step 2: Import RAG Workflow (2 minutes)

1. Open n8n
2. Import: `n8n-workflows/production-ready/5-rag-response-generator.json`
3. Activate workflow

**Test it:**
```bash
curl -X POST https://n8n-service-z1ur.onrender.com/webhook/voice/rag-response \
  -H "Content-Type: application/json" \
  -d '{
    "current_stage": "greeting",
    "next_action": "ask_name",
    "language": "ar"
  }'

# Expected: "تمام، اذا ممكن تزودني باسمك الكامل من فضلك؟"
```

---

## Step 3: Update Main Orchestrator (1 minute)

Change the Response Generator call in workflow 1:

**OLD:**
```
URL: /webhook/voice/response-generator
```

**NEW:**
```
URL: /webhook/voice/rag-response
```

Done. Now ALL responses come from Qdrant.

---

## How It Works

```
User: "مرحبا"
  ↓
Intent Classifier: action="ask_name", language="ar"
  ↓
RAG Search: Filter by action + language
  ↓
Qdrant Returns: "تمام، اذا ممكن تزودني..."
  ↓
Response to user
```

**Performance:** 60-150ms (fast enough for voice)

---

## Update Scripts Later

### Option 1: Re-run Python script
```bash
python populate_rag_knowledge_base.py
# Choose "yes" to recreate collection
```

### Option 2: Update single script via Qdrant API
```python
from qdrant_client import QdrantClient

qdrant = QdrantClient(url="...", api_key="...")
qdrant.set_payload(
    collection_name="nagel-demo-rag",
    payload={"text": "NEW SCRIPT TEXT"},
    points=[0]  # ID of script to update
)
```

### Option 3: Qdrant Dashboard
- Go to Qdrant UI
- Edit payload directly

---

## Key Files

| File | Purpose |
|------|---------|
| `scripts/populate_rag_knowledge_base.py` | Upload scripts to Qdrant |
| `n8n-workflows/production-ready/5-rag-response-generator.json` | RAG workflow |
| `docs/rag-voice-agent-architecture.md` | Full explanation (if needed) |

---

## Benefits vs Templates

| | Templates | RAG |
|---|---|---|
| **Speed** | 1ms | 100ms |
| **Update** | Edit code | Edit Qdrant |
| **Consistency** | Manual | Automatic |
| **A/B testing** | Hard | Easy |
| **Compliance** | Scattered | Single source |

**Verdict:** RAG is better for production (easier to manage)

---

## That's It

3 steps total:
1. ✅ Run Python script (populate Qdrant)
2. ✅ Import RAG workflow
3. ✅ Update orchestrator URL

**Total time: 10 minutes**

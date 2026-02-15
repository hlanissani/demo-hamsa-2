# RAG-Based Voice Agent Architecture

## Overview

**Fully RAG-powered voice agent** - ALL responses come from knowledge base retrieval.

```
User Speech → ASR → Intent Classifier → RAG Search → Response → TTS
                    (What to search)    (Knowledge Base)
```

---

## Why Full RAG?

### Advantages ✅
1. **Easy Updates** - Change scripts in KB, not code
2. **Consistency** - All responses follow same style/tone
3. **Compliance** - Single source of truth for approved scripts
4. **A/B Testing** - Test different scripts easily
5. **Multilingual** - Store AR/EN versions in KB
6. **Audit Trail** - Track which script was used

### Tradeoffs ⚠️
1. **Slower** - 300-500ms vs 10ms templates
2. **More Expensive** - Embedding search costs
3. **Needs Comprehensive KB** - Must cover ALL scenarios

**Decision:** For voice agent, consistency > speed
- Still fast enough (< 500ms target)
- Worth it for easier management

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  VOICE PLATFORM                                     │
└──────────────┬──────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────┐
│  1. INTENT CLASSIFIER (Fast Regex)                  │
│  - Extract: waybill, phone, name, yes/no            │
│  - Determine: current_stage, next_action            │
│  - Output: search_query for RAG                     │
└──────────────┬──────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────┐
│  2. DATA LOOKUP (if needed)                         │
│  - Query database by waybill/phone                  │
│  - Get tracking data                                │
└──────────────┬──────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────┐
│  3. RAG RESPONSE GENERATOR                          │
│  A. Search Knowledge Base                           │
│     - Query: "{stage}_{action}_{language}"          │
│     - Example: "greeting_ask_name_ar"               │
│  B. Fill Placeholders                               │
│     - {Customer Name}, {Waybill}, {Date}, etc.      │
│  C. Return Final Script                             │
└──────────────┬──────────────────────────────────────┘
               │
               ▼
           Response
```

---

## Knowledge Base Structure

### Document Schema

Each document in Qdrant should have:

```json
{
  "id": "greeting-ask-name-ar",
  "text": "تمام، اذا ممكن تزودني باسمك الكامل من فضلك؟",
  "metadata": {
    "stage": "greeting",
    "action": "ask_name",
    "language": "ar",
    "category": "question",
    "placeholders": [],
    "requires_data": false
  }
}
```

### Required Documents

#### 1. Greetings
```json
{
  "id": "greeting-initial-ar",
  "text": "شكرا لاتصالك بناقل اكسبرس – معك \"ماجد\" – كيف اقدر اساعدك؟",
  "metadata": {
    "stage": "greeting",
    "action": "ask_name",
    "language": "ar",
    "search_keywords": ["greeting", "initial", "first message"]
  }
}
```

```json
{
  "id": "greeting-initial-en",
  "text": "Thank you for calling Naqel Express. This is Majed, How may I help you?",
  "metadata": {
    "stage": "greeting",
    "action": "ask_name",
    "language": "en",
    "search_keywords": ["greeting", "initial", "first message"]
  }
}
```

#### 2. Ask for Name
```json
{
  "id": "awaiting-name-ar",
  "text": "تمام، اذا ممكن تزودني باسمك الكامل من فضلك؟",
  "metadata": {
    "stage": "awaiting_name",
    "action": "ask_name",
    "language": "ar",
    "search_keywords": ["ask name", "request name"]
  }
}
```

#### 3. Ask for Waybill
```json
{
  "id": "ask-waybill-ar",
  "text": "أهلاً استاذ {Customer Name} اذا ممكن تزودني برقم الشحنة",
  "metadata": {
    "stage": "awaiting_waybill",
    "action": "ask_waybill",
    "language": "ar",
    "placeholders": ["Customer Name"],
    "search_keywords": ["ask waybill", "request tracking number"]
  }
}
```

#### 4. Ask for Phone
```json
{
  "id": "ask-phone-ar",
  "text": "اذا ممكن تزودني برقم التواصل المسجل في بيانات الشحنه",
  "metadata": {
    "stage": "awaiting_phone",
    "action": "ask_phone",
    "language": "ar",
    "search_keywords": ["ask phone", "request contact number"]
  }
}
```

#### 5. Delivery Status (requires tracking data)
```json
{
  "id": "delivered-status-ar",
  "text": "شحنتك رقم {Waybill Number} تم تسليمها بتاريخ {Delivery Date} الساعة {Delivery Time} والمستلم {Signed By}",
  "metadata": {
    "stage": "delivered_status",
    "action": "deliver_status",
    "language": "ar",
    "placeholders": ["Waybill Number", "Delivery Date", "Delivery Time", "Signed By"],
    "requires_data": true,
    "status": "delivered",
    "search_keywords": ["delivered", "shipment delivered", "تم التسليم"]
  }
}
```

#### 6. In Transit Status
```json
{
  "id": "in-transit-status-ar",
  "text": "شحنتك رقم {Waybill Number} حالياً في الطريق للتسليم. راح توصلك خلال 24 ساعة ان شاء الله",
  "metadata": {
    "stage": "delivered_status",
    "action": "deliver_status",
    "language": "ar",
    "placeholders": ["Waybill Number"],
    "requires_data": true,
    "status": "in_transit",
    "search_keywords": ["in transit", "under delivery", "في الطريق"]
  }
}
```

#### 7. Ask for More Service
```json
{
  "id": "ask-more-service-ar",
  "text": "أي خدمه ثانية استاذ {Customer Name}؟",
  "metadata": {
    "stage": "awaiting_additional_service",
    "action": "ask_more_service",
    "language": "ar",
    "placeholders": ["Customer Name"],
    "search_keywords": ["additional service", "more help", "خدمة ثانية"]
  }
}
```

#### 8. Closing
```json
{
  "id": "closing-ar",
  "text": "شكرا لاتصالك بناقل اكسبرس, راح يتم تحويلك للتقييم",
  "metadata": {
    "stage": "closing",
    "action": "close",
    "language": "ar",
    "search_keywords": ["closing", "goodbye", "end call", "وداعاً"]
  }
}
```

#### 9. Out of Scope
```json
{
  "id": "out-of-scope-ar",
  "text": "للاسف استاذ {Customer Name} هذا خارج نطاق خدمتنا. اقدر اساعدك في تتبع الشحنات. عندك شحنة تبي تستفسر عنها؟",
  "metadata": {
    "stage": "out_of_scope",
    "action": "handle_out_of_scope",
    "language": "ar",
    "placeholders": ["Customer Name"],
    "search_keywords": ["out of scope", "خارج النطاق"]
  }
}
```

#### 10. Clarification
```json
{
  "id": "ask-clarification-ar",
  "text": "عفواً، مافهمت طلبك. ممكن تعيد مرة ثانية؟",
  "metadata": {
    "stage": "any",
    "action": "ask_clarification",
    "language": "ar",
    "search_keywords": ["clarification", "repeat", "didn't understand"]
  }
}
```

---

## RAG Search Strategy

### Option 1: Metadata Filtering (Recommended)
```javascript
// Search with exact filters
const query = {
  filter: {
    must: [
      { key: "stage", match: { value: current_stage }},
      { key: "action", match: { value: next_action }},
      { key: "language", match: { value: language }}
    ]
  },
  limit: 1
}
```

**Pros:** Fast, deterministic, exact match
**Cons:** Requires structured metadata

### Option 2: Semantic Search
```javascript
// Search by text similarity
const query = {
  query_text: `${stage} ${action} ${language}`,
  limit: 1,
  score_threshold: 0.8
}
```

**Pros:** Flexible, handles edge cases
**Cons:** Slower, might return wrong script

### Option 3: Hybrid (Best)
```javascript
// Combine both
const query = {
  query_text: search_keywords.join(' '),
  filter: {
    must: [
      { key: "language", match: { value: language }}
    ]
  },
  limit: 1,
  score_threshold: 0.7
}
```

**Pros:** Fast + flexible
**Cons:** More complex

---

## N8N RAG Implementation

### Updated Response Generator Workflow

```json
{
  "name": "RAG Response Generator - Full",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "voice/rag-response",
        "responseMode": "responseNode"
      },
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2.1,
      "position": [240, 300],
      "name": "Webhook"
    },
    {
      "parameters": {
        "functionCode": "// Build RAG search query\nconst body = $input.item.json.body;\nconst stage = body.current_stage;\nconst action = body.next_action;\nconst lang = body.language || 'ar';\nconst trackingData = body.tracking_data;\n\n// Determine search strategy\nlet searchQuery = '';\nlet useMetadataFilter = true;\n\nif (trackingData) {\n  // For status delivery, search by status\n  const status = trackingData.status;\n  searchQuery = `${status} status delivery ${lang}`;\n} else {\n  // For questions/prompts, search by action\n  searchQuery = `${action} ${lang}`;\n}\n\nreturn {\n  json: {\n    search_query: searchQuery,\n    metadata_filter: {\n      stage: stage,\n      action: action,\n      language: lang,\n      status: trackingData?.status\n    },\n    tracking_data: trackingData,\n    customer_name: body.customer_name\n  }\n};"
      },
      "type": "n8n-nodes-base.function",
      "typeVersion": 1,
      "position": [460, 300],
      "name": "Build Search Query"
    },
    {
      "parameters": {
        "operation": "search",
        "qdrantCollection": {
          "__rl": true,
          "value": "naqel-voice-scripts",
          "mode": "list"
        },
        "queryText": "={{ $json.search_query }}",
        "limit": 1,
        "options": {
          "filter": "={{ JSON.stringify({\n  must: [\n    { key: 'language', match: { value: $json.metadata_filter.language }},\n    { key: 'action', match: { value: $json.metadata_filter.action }}\n  ]\n}) }}"
        }
      },
      "type": "n8n-nodes-base.qdrant",
      "typeVersion": 1,
      "position": [680, 300],
      "name": "Search Knowledge Base",
      "credentials": {
        "qdrantApi": {
          "id": "eHKzmykBYzgeewCh",
          "name": "QdrantApi account"
        }
      }
    },
    {
      "parameters": {
        "functionCode": "// Extract script and fill placeholders\nconst results = $input.item.json;\nconst searchData = $('Build Search Query').item.json;\n\n// Get script text\nlet script = '';\nif (Array.isArray(results) && results.length > 0) {\n  script = results[0].payload?.text || results[0].text || '';\n} else if (results.payload?.text) {\n  script = results.payload.text;\n} else if (results.text) {\n  script = results.text;\n} else {\n  // Fallback\n  script = 'عفواً، حدث خطأ. الرجاء المحاولة لاحقاً';\n}\n\n// Fill placeholders\nconst trackingData = searchData.tracking_data;\nconst customerName = searchData.customer_name;\n\nif (customerName) {\n  script = script.replace(/\\{Customer Name\\}/g, customerName);\n  script = script.replace(/\\{اسم العميل\\}/g, customerName);\n}\n\nif (trackingData) {\n  if (trackingData.waybill_number) {\n    script = script.replace(/\\{Waybill Number\\}/g, trackingData.waybill_number);\n    script = script.replace(/\\{رقم الشحنة\\}/g, trackingData.waybill_number);\n  }\n  if (trackingData.delivery_date) {\n    script = script.replace(/\\{Delivery Date\\}/g, trackingData.delivery_date);\n    script = script.replace(/\\{تاريخ التسليم\\}/g, trackingData.delivery_date);\n  }\n  if (trackingData.delivery_time) {\n    script = script.replace(/\\{Delivery Time\\}/g, trackingData.delivery_time);\n    script = script.replace(/\\{وقت التسليم\\}/g, trackingData.delivery_time);\n  }\n  if (trackingData.signed_by) {\n    script = script.replace(/\\{Signed By\\}/g, trackingData.signed_by);\n    script = script.replace(/\\{المستلم\\}/g, trackingData.signed_by);\n  }\n}\n\nreturn {\n  json: {\n    text: script,\n    source: 'rag',\n    search_score: results[0]?.score || 0\n  }\n};"
      },
      "type": "n8n-nodes-base.function",
      "typeVersion": 1,
      "position": [900, 300],
      "name": "Fill Placeholders"
    },
    {
      "parameters": {
        "respondWith": "json",
        "responseBody": "={{ $json }}"
      },
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1.1,
      "position": [1120, 300],
      "name": "Respond"
    }
  ],
  "connections": {
    "Webhook": {
      "main": [[{"node": "Build Search Query", "type": "main", "index": 0}]]
    },
    "Build Search Query": {
      "main": [[{"node": "Search Knowledge Base", "type": "main", "index": 0}]]
    },
    "Search Knowledge Base": {
      "main": [[{"node": "Fill Placeholders", "type": "main", "index": 0}]]
    },
    "Fill Placeholders": {
      "main": [[{"node": "Respond", "type": "main", "index": 0}]]
    }
  },
  "settings": {
    "executionOrder": "v1"
  }
}
```

---

## Populating Knowledge Base

### Python Script to Upload Scripts

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from openai import OpenAI

# Initialize clients
qdrant = QdrantClient(url="YOUR_QDRANT_URL", api_key="YOUR_API_KEY")
openai_client = OpenAI(api_key="YOUR_OPENAI_KEY")

# Create collection
collection_name = "naqel-voice-scripts"

qdrant.recreate_collection(
    collection_name=collection_name,
    vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
)

# Define all scripts
scripts = [
    {
        "id": "greeting-initial-ar",
        "text": "شكرا لاتصالك بناقل اكسبرس – معك \"ماجد\" – كيف اقدر اساعدك؟",
        "metadata": {
            "stage": "greeting",
            "action": "ask_name",
            "language": "ar",
            "category": "greeting"
        }
    },
    {
        "id": "ask-name-ar",
        "text": "تمام، اذا ممكن تزودني باسمك الكامل من فضلك؟",
        "metadata": {
            "stage": "awaiting_name",
            "action": "ask_name",
            "language": "ar",
            "category": "question"
        }
    },
    {
        "id": "ask-waybill-ar",
        "text": "أهلاً استاذ {Customer Name} اذا ممكن تزودني برقم الشحنة",
        "metadata": {
            "stage": "awaiting_waybill",
            "action": "ask_waybill",
            "language": "ar",
            "category": "question"
        }
    },
    {
        "id": "ask-phone-ar",
        "text": "اذا ممكن تزودني برقم التواصل المسجل في بيانات الشحنه",
        "metadata": {
            "stage": "awaiting_phone",
            "action": "ask_phone",
            "language": "ar",
            "category": "question"
        }
    },
    {
        "id": "delivered-status-ar",
        "text": "شحنتك رقم {Waybill Number} تم تسليمها بتاريخ {Delivery Date} الساعة {Delivery Time} والمستلم {Signed By}",
        "metadata": {
            "stage": "delivered_status",
            "action": "deliver_status",
            "language": "ar",
            "category": "status",
            "status": "delivered"
        }
    },
    {
        "id": "in-transit-status-ar",
        "text": "شحنتك رقم {Waybill Number} حالياً في الطريق للتسليم. راح توصلك خلال 24 ساعة ان شاء الله",
        "metadata": {
            "stage": "delivered_status",
            "action": "deliver_status",
            "language": "ar",
            "category": "status",
            "status": "in_transit"
        }
    },
    {
        "id": "ask-more-service-ar",
        "text": "أي خدمه ثانية استاذ {Customer Name}؟",
        "metadata": {
            "stage": "awaiting_additional_service",
            "action": "ask_more_service",
            "language": "ar",
            "category": "question"
        }
    },
    {
        "id": "closing-ar",
        "text": "شكرا لاتصالك بناقل اكسبرس, راح يتم تحويلك للتقييم",
        "metadata": {
            "stage": "closing",
            "action": "close",
            "language": "ar",
            "category": "closing"
        }
    },
    {
        "id": "out-of-scope-ar",
        "text": "للاسف استاذ {Customer Name} هذا خارج نطاق خدمتنا. اقدر اساعدك في تتبع الشحنات. عندك شحنة تبي تستفسر عنها؟",
        "metadata": {
            "stage": "out_of_scope",
            "action": "handle_out_of_scope",
            "language": "ar",
            "category": "error_handling"
        }
    }
]

# Upload to Qdrant
points = []
for idx, script in enumerate(scripts):
    # Generate embedding
    embedding_response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=script["text"]
    )
    vector = embedding_response.data[0].embedding

    # Create point
    point = PointStruct(
        id=idx,
        vector=vector,
        payload={
            "text": script["text"],
            "script_id": script["id"],
            **script["metadata"]
        }
    )
    points.append(point)

# Batch upload
qdrant.upsert(
    collection_name=collection_name,
    points=points
)

print(f"✅ Uploaded {len(points)} scripts to Qdrant")
```

---

## Performance Considerations

### RAG Response Times

| Component | Time |
|-----------|------|
| Build query | 5ms |
| Qdrant search (metadata filter) | 50-100ms |
| Fill placeholders | 5ms |
| **Total** | **60-110ms** ✅

### Optimization Tips

1. **Use Metadata Filters**
   - Filter by `language`, `action`, `stage`
   - Reduces search space dramatically
   - Fast: 50-100ms vs 300-500ms semantic search

2. **Pre-generate Embeddings**
   - Done during upload
   - No embedding generation at runtime

3. **Cache Frequent Queries**
   ```javascript
   // Cache in Redis
   const cacheKey = `script:${action}:${lang}`;
   const cached = await redis.get(cacheKey);
   if (cached) return cached;
   ```

4. **Fallback to Templates**
   ```javascript
   if (searchScore < 0.7) {
     // Use hardcoded template as fallback
     return templates[action][lang];
   }
   ```

---

## Testing RAG Responses

### Test 1: Simple Query
```bash
curl -X POST https://n8n.../webhook/voice/rag-response \
  -H "Content-Type: application/json" \
  -d '{
    "current_stage": "greeting",
    "next_action": "ask_name",
    "language": "ar"
  }'

# Expected: "تمام، اذا ممكن تزودني باسمك الكامل من فضلك؟"
```

### Test 2: With Placeholders
```bash
curl -X POST https://n8n.../webhook/voice/rag-response \
  -d '{
    "current_stage": "awaiting_waybill",
    "next_action": "ask_waybill",
    "language": "ar",
    "customer_name": "احمد محمد"
  }'

# Expected: "أهلاً استاذ احمد محمد اذا ممكن تزودني برقم الشحنة"
```

### Test 3: With Tracking Data
```bash
curl -X POST https://n8n.../webhook/voice/rag-response \
  -d '{
    "current_stage": "delivered_status",
    "next_action": "deliver_status",
    "language": "ar",
    "tracking_data": {
      "waybill_number": "NQL123456",
      "status": "delivered",
      "delivery_date": "2025-01-15",
      "delivery_time": "14:30",
      "signed_by": "محمد"
    }
  }'

# Expected: "شحنتك رقم NQL123456 تم تسليمها بتاريخ 2025-01-15..."
```

---

## Updating Scripts

### Option 1: Via Python Script
```python
# Update single script
qdrant.upsert(
    collection_name="naqel-voice-scripts",
    points=[
        PointStruct(
            id=1,
            vector=new_embedding,
            payload={
                "text": "NEW SCRIPT TEXT",
                "action": "ask_name",
                "language": "ar"
            }
        )
    ]
)
```

### Option 2: Via N8N Workflow
Create an admin workflow to update scripts:
```
[HTTP Trigger] → [Generate Embedding] → [Update Qdrant]
```

### Option 3: Via UI (Qdrant Dashboard)
- Go to Qdrant dashboard
- Select collection
- Edit payload directly

---

## Summary

**Full RAG Architecture:**
- ✅ All responses from knowledge base
- ✅ Easy to update (just change KB)
- ✅ Consistent tone and compliance
- ✅ Fast with metadata filtering (60-110ms)
- ✅ Scales to thousands of scripts

**Next Steps:**
1. Create Qdrant collection
2. Upload scripts using Python
3. Update Response Generator workflow
4. Test with curl
5. Monitor search scores

Need help setting up the knowledge base?

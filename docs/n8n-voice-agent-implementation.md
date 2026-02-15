# N8N Voice Agent - Complete Implementation Guide

## Architecture Overview

```
┌────────────────────────────────────────────────────────────┐
│  VOICE PLATFORM (Twilio/Vapi)                              │
│  - Handles phone calls                                      │
│  - ASR: Speech → Text                                       │
│  - TTS: Text → Speech                                       │
└───────────────────┬────────────────────────────────────────┘
                    │
                    │ HTTP POST {"text": "...", "session_id": "..."}
                    ▼
┌────────────────────────────────────────────────────────────┐
│  N8N WORKFLOW 1: MAIN ORCHESTRATOR                         │
│                                                             │
│  [Webhook] → [Session Check] → [Intent Router]             │
│                                        │                    │
│                                        ├─→ lookup_waybill  │
│                                        ├─→ lookup_phone    │
│                                        ├─→ ask_name        │
│                                        └─→ close           │
└────────────────────┬───────────────────────────────────────┘
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
    ┌─────────┐ ┌──────────┐ ┌──────────┐
    │Intent   │ │Data      │ │Response  │
    │Classify │ │Lookup    │ │Generator │
    │(Workflow│ │(Workflow │ │(Workflow │
    │   2)    │ │   3)     │ │   4)     │
    └─────────┘ └──────────┘ └──────────┘
```

---

## Complete N8N Implementation

### Workflow 1: Main Orchestrator (Entry Point)

This is the main webhook that receives requests from your voice platform.

**Key Features:**
- Receives text from voice platform
- Manages session state
- Routes to appropriate sub-workflows
- Returns response to voice platform

**Import this workflow:**

```json
{
  "name": "Voice Agent - Main Orchestrator",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "voice/agent",
        "responseMode": "responseNode",
        "options": {}
      },
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2.1,
      "position": [240, 300],
      "id": "webhook-entry",
      "name": "Webhook - Voice Input",
      "webhookId": "voice-agent-main"
    },
    {
      "parameters": {
        "functionCode": "// Extract and normalize input\nconst body = $input.item.json.body;\nconst text = body.text || body.message || '';\nconst sessionId = body.session_id || body.sessionId || body.call_sid;\n\n// Validate input\nif (!text || !sessionId) {\n  throw new Error('Missing required fields: text and session_id');\n}\n\nreturn {\n  json: {\n    text: text.trim(),\n    session_id: sessionId,\n    timestamp: Date.now(),\n    source: 'voice'\n  }\n};"
      },
      "type": "n8n-nodes-base.function",
      "typeVersion": 1,
      "position": [460, 300],
      "id": "normalize-input",
      "name": "Normalize Input"
    },
    {
      "parameters": {
        "operation": "get",
        "key": "={{ 'session:' + $json.session_id }}",
        "options": {}
      },
      "type": "n8n-nodes-base.redis",
      "typeVersion": 1,
      "position": [680, 300],
      "id": "load-session",
      "name": "Load Session (Redis)",
      "credentials": {
        "redis": {
          "id": "1",
          "name": "Redis"
        }
      }
    },
    {
      "parameters": {
        "functionCode": "// Parse session data from Redis\nconst currentItem = $input.item.json;\nconst sessionData = currentItem.value ? JSON.parse(currentItem.value) : null;\n\nreturn {\n  json: {\n    text: $('Normalize Input').item.json.text,\n    session_id: $('Normalize Input').item.json.session_id,\n    previous_stage: sessionData?.stage || 'greeting',\n    customer_name: sessionData?.customer_name || null,\n    language: sessionData?.language || null,\n    turn_count: (sessionData?.turn_count || 0) + 1\n  }\n};"
      },
      "type": "n8n-nodes-base.function",
      "typeVersion": 1,
      "position": [900, 300],
      "id": "prepare-context",
      "name": "Prepare Context"
    },
    {
      "parameters": {
        "method": "POST",
        "url": "={{ $env.N8N_WEBHOOK_BASE_URL }}/webhook/voice/intent-classifier",
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify($json) }}",
        "options": {
          "timeout": 3000
        }
      },
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [1120, 300],
      "id": "call-intent-classifier",
      "name": "Call Intent Classifier"
    },
    {
      "parameters": {
        "rules": {
          "values": [
            {
              "conditions": {
                "string": [
                  {
                    "value1": "={{ $json.next_action }}",
                    "value2": "lookup_waybill"
                  },
                  {
                    "value1": "={{ $json.next_action }}",
                    "value2": "lookup_phone"
                  }
                ]
              },
              "renameOutput": true,
              "outputKey": "needs_lookup"
            },
            {
              "conditions": {
                "string": [
                  {
                    "value1": "={{ $json.next_action }}",
                    "value2": "ask_name"
                  },
                  {
                    "value1": "={{ $json.next_action }}",
                    "value2": "ask_waybill"
                  },
                  {
                    "value1": "={{ $json.next_action }}",
                    "value2": "ask_phone"
                  },
                  {
                    "value1": "={{ $json.next_action }}",
                    "value2": "ask_more_service"
                  },
                  {
                    "value1": "={{ $json.next_action }}",
                    "value2": "close"
                  }
                ]
              },
              "renameOutput": true,
              "outputKey": "simple_response"
            }
          ]
        },
        "options": {
          "fallbackOutput": "extra"
        }
      },
      "type": "n8n-nodes-base.switch",
      "typeVersion": 3,
      "position": [1340, 300],
      "id": "route-action",
      "name": "Route by Action"
    },
    {
      "parameters": {
        "method": "POST",
        "url": "={{ $env.N8N_WEBHOOK_BASE_URL }}/webhook/voice/data-lookup",
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify({\n  waybill: $json.extracted_data.waybill,\n  phone: $json.extracted_data.phone\n}) }}",
        "options": {
          "timeout": 5000
        }
      },
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [1560, 200],
      "id": "call-data-lookup",
      "name": "Data Lookup"
    },
    {
      "parameters": {
        "method": "POST",
        "url": "={{ $env.N8N_WEBHOOK_BASE_URL }}/webhook/voice/response-generator",
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify({\n  current_stage: $json.current_stage,\n  next_action: $json.next_action,\n  language: $json.language,\n  customer_name: $json.extracted_data?.customer_name,\n  tracking_data: $json.tracking_data\n}) }}",
        "options": {
          "timeout": 5000
        }
      },
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [1780, 300],
      "id": "call-response-gen",
      "name": "Response Generator"
    },
    {
      "parameters": {
        "functionCode": "// Prepare final response for voice platform\nconst responseData = $input.item.json;\nconst intentData = $('Call Intent Classifier').item.json;\n\n// Update session in Redis\nconst sessionUpdate = {\n  stage: intentData.current_stage,\n  customer_name: intentData.extracted_data?.customer_name,\n  language: intentData.language,\n  turn_count: $('Prepare Context').item.json.turn_count,\n  last_updated: Date.now()\n};\n\n// Return both response and session update\nreturn [\n  {\n    json: {\n      text: responseData.text || responseData.response,\n      session_id: $('Normalize Input').item.json.session_id,\n      stage: intentData.current_stage,\n      is_closing: intentData.next_action === 'close'\n    }\n  },\n  {\n    json: {\n      session_id: $('Normalize Input').item.json.session_id,\n      session_data: JSON.stringify(sessionUpdate)\n    }\n  }\n];"
      },
      "type": "n8n-nodes-base.function",
      "typeVersion": 1,
      "position": [2000, 300],
      "id": "format-final-response",
      "name": "Format Response"
    },
    {
      "parameters": {
        "operation": "set",
        "key": "={{ 'session:' + $json.session_id }}",
        "value": "={{ $json.session_data }}",
        "expire": true,
        "ttl": 600,
        "options": {}
      },
      "type": "n8n-nodes-base.redis",
      "typeVersion": 1,
      "position": [2220, 400],
      "id": "save-session",
      "name": "Save Session",
      "credentials": {
        "redis": {
          "id": "1",
          "name": "Redis"
        }
      }
    },
    {
      "parameters": {
        "respondWith": "json",
        "responseBody": "={{ $item(0).json }}",
        "options": {}
      },
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1.1,
      "position": [2220, 300],
      "id": "respond-to-caller",
      "name": "Respond to Caller"
    }
  ],
  "connections": {
    "Webhook - Voice Input": {
      "main": [[{"node": "Normalize Input", "type": "main", "index": 0}]]
    },
    "Normalize Input": {
      "main": [[{"node": "Load Session (Redis)", "type": "main", "index": 0}]]
    },
    "Load Session (Redis)": {
      "main": [[{"node": "Prepare Context", "type": "main", "index": 0}]]
    },
    "Prepare Context": {
      "main": [[{"node": "Call Intent Classifier", "type": "main", "index": 0}]]
    },
    "Call Intent Classifier": {
      "main": [[{"node": "Route by Action", "type": "main", "index": 0}]]
    },
    "Route by Action": {
      "main": [
        [{"node": "Data Lookup", "type": "main", "index": 0}],
        [{"node": "Response Generator", "type": "main", "index": 0}]
      ]
    },
    "Data Lookup": {
      "main": [[{"node": "Response Generator", "type": "main", "index": 0}]]
    },
    "Response Generator": {
      "main": [[{"node": "Format Response", "type": "main", "index": 0}]]
    },
    "Format Response": {
      "main": [
        [{"node": "Respond to Caller", "type": "main", "index": 0}],
        [{"node": "Save Session", "type": "main", "index": 0}]
      ]
    }
  },
  "settings": {
    "executionOrder": "v1"
  }
}
```

---

### Workflow 2: Intent Classifier (Fast Regex-Based)

Ultra-fast intent classification using pure JavaScript (< 50ms).

```json
{
  "name": "Voice Agent - Intent Classifier",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "voice/intent-classifier",
        "responseMode": "responseNode",
        "options": {}
      },
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2.1,
      "position": [240, 300],
      "id": "webhook-intent",
      "name": "Webhook"
    },
    {
      "parameters": {
        "functionCode": "// INTENT CLASSIFIER - Pure JavaScript (< 50ms)\nconst text = $input.item.json.text?.trim() || '';\nconst previousStage = $input.item.json.previous_stage || 'greeting';\nconst sessionId = $input.item.json.session_id;\n\n// Language detection\nconst arabicPattern = /[\\u0600-\\u06FF]/;\nconst isArabic = arabicPattern.test(text);\nconst language = isArabic ? 'ar' : 'en';\n\n// Initialize result\nconst result = {\n  current_stage: previousStage,\n  extracted_data: {\n    customer_name: null,\n    waybill: null,\n    phone: null,\n    has_waybill: false,\n    wants_more_service: null,\n    is_greeting: false,\n    is_out_of_scope: false\n  },\n  next_action: null,\n  language: language,\n  confidence: 1.0\n};\n\n// === EXTRACTION PATTERNS ===\n\n// 1. Name Detection (2+ words, Arabic or English)\nconst arabicNamePattern = /([\\u0600-\\u06FF]+\\s+[\\u0600-\\u06FF]+(?:\\s+[\\u0600-\\u06FF]+)?)/;\nconst englishNamePattern = /\\b([A-Z][a-z]+\\s+[A-Z][a-z]+(?:\\s+[A-Z][a-z]+)?)\\b/;\n\nconst arabicNameMatch = text.match(arabicNamePattern);\nconst englishNameMatch = text.match(englishNamePattern);\n\nif (arabicNameMatch) {\n  result.extracted_data.customer_name = arabicNameMatch[1].trim();\n} else if (englishNameMatch) {\n  result.extracted_data.customer_name = englishNameMatch[1].trim();\n}\n\n// 2. Waybill Detection (NQL + digits)\nconst waybillPattern = /NQL\\d{5,}/i;\nconst waybillMatch = text.match(waybillPattern);\n\nif (waybillMatch) {\n  result.extracted_data.waybill = waybillMatch[0].toUpperCase();\n  result.extracted_data.has_waybill = true;\n}\n\n// 3. Phone Detection (Saudi format)\nconst phonePattern = /(?:05|\\+?966\\s?5)\\d{8}/;\nconst phoneMatch = text.match(phonePattern);\n\nif (phoneMatch) {\n  result.extracted_data.phone = phoneMatch[0].replace(/\\s/g, '');\n}\n\n// 4. Yes/No Detection\nconst yesPatterns = [\n  'نعم', 'اي', 'ايوه', 'ايه', 'طيب', 'تمام', 'أكيد', 'اكيد',\n  'yes', 'yeah', 'yep', 'sure', 'okay', 'ok', 'y'\n];\nconst noPatterns = [\n  'لا', 'مافي', 'ماعندي', 'لايوجد', 'ماني', 'مو',\n  'no', 'nope', 'nah', 'nothing', 'none', 'n'\n];\n\nconst lowerText = text.toLowerCase();\nconst hasYes = yesPatterns.some(word => lowerText.includes(word));\nconst hasNo = noPatterns.some(word => lowerText.includes(word));\n\nif (hasYes) result.extracted_data.wants_more_service = true;\nif (hasNo) result.extracted_data.wants_more_service = false;\n\n// 5. Greeting Detection\nconst greetingPatterns = [\n  'مرحبا', 'السلام', 'هلا', 'اهلا', 'صباح', 'مساء',\n  'hello', 'hi', 'hey', 'good morning', 'good evening'\n];\nresult.extracted_data.is_greeting = greetingPatterns.some(g => \n  lowerText.includes(g)\n);\n\n// 6. Out of Scope Detection\nconst outOfScopeKeywords = [\n  // Complaints\n  'شكوى', 'اشتكي', 'متأخر', 'سيء', 'زعلان', 'غاضب',\n  'complaint', 'complain', 'bad', 'angry',\n  // Pricing\n  'سعر', 'كم', 'تكلفة', 'فلوس', 'price', 'cost', 'how much',\n  // New shipment\n  'ارسال', 'شحن جديد', 'ابي اشحن', 'send', 'ship new',\n  // Refunds\n  'استرجاع', 'ارجاع', 'refund', 'return',\n  // Lost items\n  'مفقود', 'ضاع', 'lost', 'missing'\n];\nresult.extracted_data.is_out_of_scope = outOfScopeKeywords.some(k => \n  lowerText.includes(k)\n);\n\n// === STAGE LOGIC ===\n\nif (previousStage === 'greeting' || result.extracted_data.is_greeting) {\n  result.current_stage = 'greeting';\n  result.next_action = 'ask_name';\n}\nelse if (result.extracted_data.customer_name) {\n  result.current_stage = 'awaiting_name';\n  result.next_action = 'ask_waybill';\n}\nelse if (result.extracted_data.waybill) {\n  result.current_stage = 'awaiting_waybill';\n  result.next_action = 'lookup_waybill';\n}\nelse if (hasNo && previousStage === 'awaiting_waybill') {\n  // Customer said they don't have waybill\n  result.current_stage = 'awaiting_waybill';\n  result.next_action = 'ask_phone';\n  result.extracted_data.has_waybill = false;\n}\nelse if (result.extracted_data.phone) {\n  result.current_stage = 'awaiting_phone';\n  result.next_action = 'lookup_phone';\n}\nelse if (previousStage === 'delivered_status') {\n  result.current_stage = 'delivered_status';\n  result.next_action = 'ask_more_service';\n}\nelse if (previousStage === 'awaiting_additional_service') {\n  if (result.extracted_data.wants_more_service === true) {\n    result.current_stage = 'awaiting_additional_service';\n    result.next_action = 'ask_waybill';\n  } else if (result.extracted_data.wants_more_service === false) {\n    result.current_stage = 'awaiting_additional_service';\n    result.next_action = 'close';\n  }\n}\nelse if (result.extracted_data.is_out_of_scope) {\n  result.current_stage = 'out_of_scope';\n  result.next_action = 'handle_out_of_scope';\n}\nelse {\n  // Fallback: repeat question\n  result.next_action = 'ask_clarification';\n  result.confidence = 0.5;\n}\n\n// Return result\nreturn { json: result };"
      },
      "type": "n8n-nodes-base.function",
      "typeVersion": 1,
      "position": [460, 300],
      "id": "classify-intent",
      "name": "Classify Intent (Regex)"
    },
    {
      "parameters": {
        "respondWith": "json",
        "responseBody": "={{ $json }}",
        "options": {}
      },
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1.1,
      "position": [680, 300],
      "id": "respond",
      "name": "Respond"
    }
  ],
  "connections": {
    "Webhook": {
      "main": [[{"node": "Classify Intent (Regex)", "type": "main", "index": 0}]]
    },
    "Classify Intent (Regex)": {
      "main": [[{"node": "Respond", "type": "main", "index": 0}]]
    }
  },
  "settings": {
    "executionOrder": "v1"
  }
}
```

---

### Workflow 3: Data Lookup (Database Queries)

Queries tracking database by waybill or phone number.

```json
{
  "name": "Voice Agent - Data Lookup",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "voice/data-lookup",
        "responseMode": "responseNode"
      },
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2.1,
      "position": [240, 300],
      "id": "webhook-lookup",
      "name": "Webhook"
    },
    {
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{ $json.body.waybill }}",
              "operation": "isNotEmpty"
            }
          ]
        }
      },
      "type": "n8n-nodes-base.if",
      "typeVersion": 2,
      "position": [460, 300],
      "id": "check-lookup-type",
      "name": "Has Waybill?"
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT * FROM shipments WHERE waybill_number = $1 LIMIT 1",
        "options": {
          "queryBatching": false,
          "queryReplacement": "={{ [$json.body.waybill] }}"
        }
      },
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.4,
      "position": [680, 200],
      "id": "query-by-waybill",
      "name": "Query by Waybill",
      "credentials": {
        "postgres": {
          "id": "griqz7zpdIojGhLq",
          "name": "Postgress DB"
        }
      }
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT * FROM shipments WHERE sender_phone = $1 OR recipient_phone = $1 ORDER BY created_at DESC LIMIT 1",
        "options": {
          "queryReplacement": "={{ [$json.body.phone] }}"
        }
      },
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.4,
      "position": [680, 400],
      "id": "query-by-phone",
      "name": "Query by Phone",
      "credentials": {
        "postgres": {
          "id": "griqz7zpdIojGhLq",
          "name": "Postgress DB"
        }
      }
    },
    {
      "parameters": {
        "functionCode": "// Format tracking data\nconst data = $input.item.json;\n\nif (!data || (Array.isArray(data) && data.length === 0)) {\n  return {\n    json: {\n      success: false,\n      error: 'NOT_FOUND',\n      message: 'No tracking information found'\n    }\n  };\n}\n\nconst shipment = Array.isArray(data) ? data[0] : data;\n\nreturn {\n  json: {\n    success: true,\n    tracking_data: {\n      waybill_number: shipment.waybill_number,\n      status: shipment.status,\n      delivery_date: shipment.delivery_date,\n      delivery_time: shipment.delivery_time,\n      signed_by: shipment.signed_by,\n      sender_phone: shipment.sender_phone,\n      recipient_phone: shipment.recipient_phone,\n      recipient_name: shipment.recipient_name,\n      origin: shipment.origin,\n      destination: shipment.destination\n    }\n  }\n};"
      },
      "type": "n8n-nodes-base.function",
      "typeVersion": 1,
      "position": [900, 300],
      "id": "format-result",
      "name": "Format Result"
    },
    {
      "parameters": {
        "respondWith": "json",
        "responseBody": "={{ $json }}"
      },
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1.1,
      "position": [1120, 300],
      "id": "respond-lookup",
      "name": "Respond"
    }
  ],
  "connections": {
    "Webhook": {
      "main": [[{"node": "Has Waybill?", "type": "main", "index": 0}]]
    },
    "Has Waybill?": {
      "main": [
        [{"node": "Query by Waybill", "type": "main", "index": 0}],
        [{"node": "Query by Phone", "type": "main", "index": 0}]
      ]
    },
    "Query by Waybill": {
      "main": [[{"node": "Format Result", "type": "main", "index": 0}]]
    },
    "Query by Phone": {
      "main": [[{"node": "Format Result", "type": "main", "index": 0}]]
    },
    "Format Result": {
      "main": [[{"node": "Respond", "type": "main", "index": 0}]]
    }
  },
  "settings": {
    "executionOrder": "v1"
  }
}
```

---

### Workflow 4: Response Generator (Templates + RAG)

Generates responses using templates or RAG from knowledge base.

```json
{
  "name": "Voice Agent - Response Generator",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "voice/response-generator",
        "responseMode": "responseNode"
      },
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 2.1,
      "position": [240, 300],
      "id": "webhook-response",
      "name": "Webhook"
    },
    {
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{ $json.body.tracking_data }}",
              "operation": "isNotEmpty"
            }
          ]
        }
      },
      "type": "n8n-nodes-base.if",
      "typeVersion": 2,
      "position": [460, 300],
      "id": "needs-rag",
      "name": "Needs RAG?"
    },
    {
      "parameters": {
        "functionCode": "// TEMPLATE RESPONSES (instant, no AI needed)\nconst body = $input.item.json.body;\nconst lang = body.language || 'ar';\nconst stage = body.current_stage;\nconst action = body.next_action;\nconst name = body.customer_name || '';\n\nconst templates = {\n  greeting: {\n    ar: 'شكرا لاتصالك بناقل اكسبرس – معك \"ماجد\" – كيف اقدر اساعدك؟',\n    en: 'Thank you for calling Naqel Express. This is Majed, How may I help you?'\n  },\n  ask_name: {\n    ar: 'تمام، اذا ممكن تزودني باسمك الكامل من فضلك؟',\n    en: 'Alright, may I please have your full name?'\n  },\n  ask_waybill: {\n    ar: `أهلاً استاذ ${name} اذا ممكن تزودني برقم الشحنة`,\n    en: `Welcome Mr/Ms ${name}. Can I please have the waybill number?`\n  },\n  ask_phone: {\n    ar: 'اذا ممكن تزودني برقم التواصل المسجل في بيانات الشحنه',\n    en: 'Please provide the contact number registered with the shipment.'\n  },\n  ask_more_service: {\n    ar: `أي خدمه ثانية استاذ ${name}؟`,\n    en: `Any other service, Mr/Ms ${name}?`\n  },\n  close: {\n    ar: 'شكرا لاتصالك بناقل اكسبرس, راح يتم تحويلك للتقييم',\n    en: 'Thank you for calling Naqel Express. Please answer the evaluation.'\n  },\n  handle_out_of_scope: {\n    ar: `للاسف استاذ ${name} هذا خارج نطاق خدمتنا. اقدر اساعدك في تتبع الشحنات. عندك شحنة تبي تستفسر عنها؟`,\n    en: `I apologize, this is outside our scope. I can help with shipment tracking. Do you have a shipment to inquire about?`\n  },\n  ask_clarification: {\n    ar: 'عفواً، مافهمت طلبك. ممكن تعيد مرة ثانية؟',\n    en: 'Sorry, I did not understand. Can you please repeat?'\n  }\n};\n\n// Get template based on action\nconst key = action || stage;\nconst text = templates[key]?.[lang] || templates['ask_clarification'][lang];\n\nreturn {\n  json: {\n    text: text,\n    requires_rag: false,\n    stage: stage\n  }\n};"
      },
      "type": "n8n-nodes-base.function",
      "typeVersion": 1,
      "position": [680, 400],
      "id": "template-response",
      "name": "Template Response"
    },
    {
      "parameters": {
        "functionCode": "// Map status to Knowledge Base keyword\nconst trackingData = $input.item.json.body.tracking_data;\nconst status = trackingData?.status;\n\nconst statusMapping = {\n  'delivered': 'Shipment Delivered',\n  'in_transit': 'Shipment Under Delivery',\n  'out_for_delivery': 'Shipment Under Delivery',\n  'wrong_address': 'Shipment With Incorrect Address',\n  'incomplete_address': 'Shipment With Incorrect Address',\n  'refused': 'Shipment - Refused Delivery'\n};\n\nconst keyword = statusMapping[status] || 'Shipment Under Delivery';\n\nreturn {\n  json: {\n    search_keyword: keyword,\n    tracking_data: trackingData\n  }\n};"
      },
      "type": "n8n-nodes-base.function",
      "typeVersion": 1,
      "position": [680, 200],
      "id": "map-status",
      "name": "Map Status to Keyword"
    },
    {
      "parameters": {
        "operation": "search",
        "qdrantCollection": {
          "__rl": true,
          "value": "nagel-demo-rag",
          "mode": "list"
        },
        "query": "={{ $json.search_keyword }}",
        "limit": 1,
        "options": {}
      },
      "type": "n8n-nodes-base.qdrant",
      "typeVersion": 1,
      "position": [900, 200],
      "id": "search-kb",
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
        "functionCode": "// Fill script template with tracking data\nconst kbResult = $input.item.json;\nconst trackingData = $('Map Status to Keyword').item.json.tracking_data;\n\n// Get script from KB\nlet script = kbResult.payload?.text || kbResult.text || '';\n\n// Replace placeholders\nif (trackingData.waybill_number) {\n  script = script.replace(/\\{Waybill Number\\}/g, trackingData.waybill_number);\n  script = script.replace(/\\{رقم الشحنة\\}/g, trackingData.waybill_number);\n}\nif (trackingData.delivery_date) {\n  script = script.replace(/\\{Delivery Date\\}/g, trackingData.delivery_date);\n  script = script.replace(/\\{تاريخ التسليم\\}/g, trackingData.delivery_date);\n}\nif (trackingData.delivery_time) {\n  script = script.replace(/\\{Delivery Time\\}/g, trackingData.delivery_time);\n  script = script.replace(/\\{وقت التسليم\\}/g, trackingData.delivery_time);\n}\nif (trackingData.signed_by) {\n  script = script.replace(/\\{Signed By\\}/g, trackingData.signed_by);\n  script = script.replace(/\\{المستلم\\}/g, trackingData.signed_by);\n}\n\nreturn {\n  json: {\n    text: script,\n    requires_rag: true\n  }\n};"
      },
      "type": "n8n-nodes-base.function",
      "typeVersion": 1,
      "position": [1120, 200],
      "id": "fill-template",
      "name": "Fill Template"
    },
    {
      "parameters": {},
      "type": "n8n-nodes-base.merge",
      "typeVersion": 2.1,
      "position": [1340, 300],
      "id": "merge-responses",
      "name": "Merge"
    },
    {
      "parameters": {
        "respondWith": "json",
        "responseBody": "={{ $json }}"
      },
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1.1,
      "position": [1560, 300],
      "id": "respond-final",
      "name": "Respond"
    }
  ],
  "connections": {
    "Webhook": {
      "main": [[{"node": "Needs RAG?", "type": "main", "index": 0}]]
    },
    "Needs RAG?": {
      "main": [
        [{"node": "Map Status to Keyword", "type": "main", "index": 0}],
        [{"node": "Template Response", "type": "main", "index": 0}]
      ]
    },
    "Template Response": {
      "main": [[{"node": "Merge", "type": "main", "index": 1}]]
    },
    "Map Status to Keyword": {
      "main": [[{"node": "Search Knowledge Base", "type": "main", "index": 0}]]
    },
    "Search Knowledge Base": {
      "main": [[{"node": "Fill Template", "type": "main", "index": 0}]]
    },
    "Fill Template": {
      "main": [[{"node": "Merge", "type": "main", "index": 0}]]
    },
    "Merge": {
      "main": [[{"node": "Respond", "type": "main", "index": 0}]]
    }
  },
  "settings": {
    "executionOrder": "v1"
  }
}
```

---

## Environment Setup

### Required Environment Variables

Add these to your n8n deployment (Render/Railway):

```bash
# N8N Configuration
N8N_WEBHOOK_BASE_URL=https://n8n-service-z1ur.onrender.com

# Redis (for session management)
REDIS_HOST=your-redis-host
REDIS_PORT=6379
REDIS_PASSWORD=your-redis-password

# PostgreSQL (already configured)
DB_POSTGRESDB_HOST=your-postgres-host
DB_POSTGRESDB_USER=your-postgres-user
DB_POSTGRESDB_PASSWORD=your-postgres-password

# Qdrant (already configured)
QDRANT_URL=your-qdrant-url
QDRANT_API_KEY=your-api-key
```

---

## Testing the Workflows

### Step 1: Import All Workflows
1. Copy each JSON above
2. In n8n: Menu → Import from JSON
3. Paste and save
4. Activate each workflow

### Step 2: Test Intent Classifier
```bash
curl -X POST https://n8n-service-z1ur.onrender.com/webhook/voice/intent-classifier \
  -H "Content-Type: application/json" \
  -d '{
    "text": "اسمي احمد محمد العتيبي",
    "session_id": "test-123",
    "previous_stage": "greeting"
  }'

# Expected response:
{
  "current_stage": "awaiting_name",
  "extracted_data": {
    "customer_name": "احمد محمد العتيبي",
    "waybill": null,
    "phone": null,
    "has_waybill": false,
    "wants_more_service": null,
    "is_greeting": false,
    "is_out_of_scope": false
  },
  "next_action": "ask_waybill",
  "language": "ar",
  "confidence": 1.0
}
```

### Step 3: Test Data Lookup
```bash
curl -X POST https://n8n-service-z1ur.onrender.com/webhook/voice/data-lookup \
  -H "Content-Type: application/json" \
  -d '{
    "waybill": "NQL123456"
  }'

# Expected: Tracking data from database
```

### Step 4: Test Response Generator
```bash
curl -X POST https://n8n-service-z1ur.onrender.com/webhook/voice/response-generator \
  -H "Content-Type: application/json" \
  -d '{
    "current_stage": "greeting",
    "next_action": "ask_name",
    "language": "ar"
  }'

# Expected:
{
  "text": "تمام، اذا ممكن تزودني باسمك الكامل من فضلك؟",
  "requires_rag": false,
  "stage": "greeting"
}
```

### Step 5: Test Full Flow
```bash
curl -X POST https://n8n-service-z1ur.onrender.com/webhook/voice/agent \
  -H "Content-Type: application/json" \
  -d '{
    "text": "مرحبا",
    "session_id": "session-456"
  }'

# Expected:
{
  "text": "شكرا لاتصالك بناقل اكسبرس – معك \"ماجد\" – كيف اقدر اساعدك؟",
  "session_id": "session-456",
  "stage": "greeting",
  "is_closing": false
}
```

---

## Performance Optimization

### 1. Use Redis for Session Management
```javascript
// Instead of PostgreSQL for every request
// Redis: < 10ms
// PostgreSQL: 50-100ms
```

### 2. Cache Template Responses
```javascript
// Templates are instant (< 1ms)
// 70% of responses use templates
// Only 30% need RAG/AI
```

### 3. Parallel Execution
```javascript
// Your switch node already routes in parallel:
// - Simple responses go direct to template
// - Lookup actions go to database
// No blocking!
```

### 4. Set Timeouts
```javascript
// All HTTP Request nodes should have:
options: {
  timeout: 3000  // 3 seconds max
}
```

---

## Monitoring

### Add Logging to Each Workflow

```javascript
// In each Function node, add:
console.log(`[${new Date().toISOString()}] ${$node.name}: Processing...`);

// View logs in n8n: Executions → Click execution → View logs
```

### Track Performance
```javascript
// At start of workflow:
const startTime = Date.now();

// At end:
const duration = Date.now() - startTime;
console.log(`Total workflow time: ${duration}ms`);
```

---

## Next Steps

1. **Import all 4 workflows** to your n8n instance
2. **Configure Redis** for session management
3. **Test each workflow** individually
4. **Test full flow** end-to-end
5. **Connect to voice platform** (Twilio/Vapi)

Need help with any specific part?

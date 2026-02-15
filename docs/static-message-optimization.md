# Static Message Optimization (Advanced)

## Concept: Bypass LLM for Fixed Responses

**Problem:** Even simple greetings go through LLM (400-800ms latency)
**Solution:** Detect patterns and return static messages instantly (0ms)

---

## Implementation Options

### Option 1: n8n Pre-Processing Node

Add a **Switch** node before the agent:

```
Webhook → Switch (Pattern Detector) → [Static Response] or [Agent]
```

**Switch Logic:**
```javascript
// In Switch node
const text = $json.body.text.toLowerCase();
const sessionData = await getSessionData($json.body.session_id);

// Pattern 1: First message (greeting)
if (!sessionData.history || sessionData.history.length === 0) {
  const greetings = ['سلام', 'مرحبا', 'hello', 'hi'];
  if (greetings.some(g => text.includes(g))) {
    return {
      response: "شكرا لاتصالك بناقل اكسبرس – معك ماجد – كيف اقدر اساعدك؟",
      skipAgent: true,
      stage: 1
    };
  }
}

// Pattern 2: Name provided (after stage 1)
if (sessionData.lastStage === 1 && !text.match(/نقل|شحن|waybill/)) {
  return {
    customerName: extractName(text),
    response: `أهلاً استاذ ${extractName(text)} اذا ممكن تزودني برقم الشحنة`,
    skipAgent: true,
    stage: 3
  };
}

// Pattern 3: Waybill detected
if (text.match(/NQL\d+/i)) {
  // Let agent handle (needs tool call)
  return { skipAgent: false };
}

// Default: Use agent
return { skipAgent: false };
```

**n8n Workflow:**
```
Webhook
  ├─→ Switch (Pattern Detector)
      ├─→ [Route 0: Static Response] → Respond to Webhook (0ms)
      └─→ [Route 1: Dynamic] → Agent → Respond to Webhook (1200ms)
```

---

### Option 2: Django Smart Routing

```python
class SmartVoiceRouter:
    """Route to static responses or LLM based on pattern"""

    STATIC_RESPONSES = {
        "greeting": {
            "patterns": ["سلام", "مرحبا", "hello", "hi"],
            "response": "شكرا لاتصالك بناقل اكسبرس – معك ماجد – كيف اقدر اساعدك؟",
            "stage": 1
        },
        "name_capture": {
            # After greeting, assume next message is name if no keywords
            "anti_patterns": ["نقل", "شحن", "waybill", "nql"],
            "response_template": "أهلاً استاذ {name} اذا ممكن تزودني برقم الشحنة",
            "stage": 3
        },
        "additional_service_no": {
            "patterns": ["لا", "شكرا", "no", "thanks"],
            "after_stage": 5,
            "response": "شكرا لاتصالك بناقل اكسبرس, راح يتم تحويلك للتقييم",
            "stage": 6
        }
    }

    async def route(self, text: str, session_id: str):
        session = await self.get_session(session_id)

        # Check static patterns
        for pattern_name, config in self.STATIC_RESPONSES.items():
            if self._matches(text, session, config):
                # Return static response instantly
                response = self._build_response(config, text, session)
                await self.save_to_history(session_id, text, response)
                return {
                    "response": response,
                    "latency_ms": 5,  # Nearly instant
                    "source": "static"
                }

        # No match → Use LLM agent
        return await self.agent.get_response(text, session_id)

    def _matches(self, text: str, session: dict, config: dict) -> bool:
        text_lower = text.lower()

        # Check if stage requirement met
        if "after_stage" in config:
            if session.get("last_stage") != config["after_stage"]:
                return False

        # Check if text matches patterns
        if "patterns" in config:
            if any(p in text_lower for p in config["patterns"]):
                return True

        # Check if text doesn't match anti-patterns (for name capture)
        if "anti_patterns" in config:
            if not any(p in text_lower for p in config["anti_patterns"]):
                # Assume it's a name if no keywords found
                return True

        return False

    def _build_response(self, config: dict, text: str, session: dict) -> str:
        response = config.get("response", config.get("response_template", ""))

        # Fill placeholders
        if "{name}" in response:
            response = response.replace("{name}", text.strip())

        return response
```

**Usage:**
```python
router = SmartVoiceRouter()

# Example 1: Greeting
response = await router.route("السلام عليكم", session_id="123")
# → 5ms, static response

# Example 2: Name
response = await router.route("احمد محمد", session_id="123")
# → 5ms, static response with name

# Example 3: Waybill
response = await router.route("NQL123456", session_id="123")
# → 800ms, LLM + tools
```

---

## Performance Gains

| Stage | Current (LLM) | With Static | Savings |
|-------|---------------|-------------|---------|
| 1. Greeting | 800ms | **5ms** | **-795ms** |
| 2. Name request | 800ms | **5ms** | **-795ms** |
| 3. Waybill request | 800ms | **5ms** | **-795ms** |
| 4. Lookup + Script | 1200ms | 1200ms | 0ms (needs tools) |
| 5. Additional service? | 800ms | **5ms** | **-795ms** |
| 6. Closing | 800ms | **5ms** | **-795ms** |

**Total conversation latency:**
- **Current:** 800 + 800 + 800 + 1200 + 800 + 800 = **5,200ms** (5.2s)
- **Optimized LLM:** 500 + 500 + 500 + 800 + 500 + 500 = **3,300ms** (3.3s)
- **Static Messages:** 5 + 5 + 5 + 800 + 5 + 5 = **825ms** (0.8s!)

**Savings: 84%** for full conversation!

---

## Implementation Priority

### Phase 1: Easy Wins (n8n)
Add Switch node for:
- ✅ Greeting detection (stage 1)
- ✅ "No thanks" → Closing (stage 6)

**Effort:** 30 minutes
**Gain:** -1,600ms per conversation

### Phase 2: Smart Routing (Django)
Full pattern-based router:
- ✅ All fixed stages
- ✅ Fallback to LLM when needed

**Effort:** 2 hours
**Gain:** -4,000ms per conversation

---

## Considerations

### Pros
- **Massive latency reduction** (5-800ms → 5ms)
- **Lower costs** (fewer LLM calls)
- **More predictable** responses
- **Better user experience** for simple interactions

### Cons
- **More complex routing logic**
- **Maintenance overhead** (update static responses)
- **Less flexible** (can't adapt to variations)

### Hybrid Approach (Recommended)
- Use **static for 100% predictable stages** (greeting, closing)
- Use **LLM for dynamic stages** (waybill lookup, script delivery)
- Result: **Best of both worlds**

---

## Example: Hybrid n8n Workflow

```
Webhook
  │
  ├─→ Switch Node (Pattern Detector)
      │
      ├─→ [Greeting Detected] → Return Static → End (5ms)
      │
      ├─→ [Name Only] → Return Static → End (5ms)
      │
      ├─→ [Closing Keywords] → Return Static → End (5ms)
      │
      └─→ [Complex/Waybill] → Agent + Tools → End (800ms)
```

**Result:**
- 60% of messages → Static (5ms)
- 40% of messages → LLM (800ms)
- **Average latency: 320ms** (down from 1200ms)

---

## Testing

```bash
# Test static greeting
curl -X POST .../webhook/besmart/voice/agent/v2/ \
  -d '{"text": "السلام عليكم", "session_id": "test-static-1"}' \
  -w "\nTime: %{time_total}s\n"

# Expected: <50ms

# Test dynamic (waybill)
curl -X POST .../webhook/besmart/voice/agent/v2/ \
  -d '{"text": "رقم الشحنة NQL123456", "session_id": "test-static-2"}' \
  -w "\nTime: %{time_total}s\n"

# Expected: ~800ms (unchanged, needs LLM + tools)
```

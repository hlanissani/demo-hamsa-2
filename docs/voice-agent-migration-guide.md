# Voice Agent Migration Guide

## Quick Decision Matrix

| Scenario | Recommended Solution | Expected Latency |
|----------|---------------------|------------------|
| Quick win (today) | Optimized n8n workflow | 1.2-1.5s |
| High volume (>500 concurrent) | Django Direct | 0.6-0.8s |
| Need n8n features (UI, monitoring) | Optimized n8n | 1.2-1.5s |
| Maximum performance required | Django Direct | 0.6-0.8s |

---

## Migration Path Options

### Option 1: Optimized n8n (Recommended First Step)
**Effort:** 10 minutes
**Latency Improvement:** 60% (from 2.5s → 1.2s)

#### Steps:
1. **Import optimized workflow**
   ```bash
   # In n8n UI
   # Settings → Import → Select: docs/n8n-optimized-workflow.json
   ```

2. **Update webhook URL** (if needed)
   ```
   Old: /webhook/besmart/voice/agent/
   New: /webhook/besmart/voice/agent/v2/
   ```

3. **Test with curl**
   ```bash
   curl -X POST https://n8n-service-z1ur.onrender.com/webhook/besmart/voice/agent/v2/ \
     -H "Content-Type: application/json" \
     -d '{
       "text": "السلام عليكم",
       "session_id": "test-1"
     }' \
     -w "\nTime: %{time_total}s\n"
   ```

4. **Verify improvements**
   - First token: <600ms
   - Full response: <1.5s
   - Streaming chunks every 100ms

#### Key Changes:
- ✅ Removed MCP Server → MCP Client loop
- ✅ Direct tool connections to agent
- ✅ topK=1 for knowledge base
- ✅ Context window limited to 10 messages
- ✅ Model: gpt-4o-mini (faster inference)
- ✅ Max tokens: 150 (optimized for stage-based responses)

---

### Option 2: Django Direct Integration
**Effort:** 4-6 hours
**Latency Improvement:** 75% (from 2.5s → 0.6s)

#### Prerequisites:
```bash
pip install langchain-openai qdrant-client psycopg2-binary httpx
```

#### Steps:

1. **Set environment variables**
   ```bash
   export OPENAI_API_KEY="sk-..."
   export QDRANT_URL="https://..."
   export QDRANT_API_KEY="..."
   export DATABASE_URL="postgresql://..."
   ```

2. **Add to Django settings.py**
   ```python
   INSTALLED_APPS = [
       # ... existing apps
       'channels',  # For WebSocket support
   ]

   CHANNEL_LAYERS = {
       'default': {
           'BACKEND': 'channels_redis.core.RedisChannelLayer',
           'CONFIG': {
               "hosts": [('127.0.0.1', 6379)],
           },
       },
   }
   ```

3. **Create Django consumer** (copy from `scripts/voice_agent_direct.py`)
   ```python
   # voice_agent/consumers.py
   from scripts.voice_agent_direct import VoiceAgentConsumer
   ```

4. **Update routing.py**
   ```python
   from django.urls import path
   from voice_agent.consumers import VoiceAgentConsumer

   websocket_urlpatterns = [
       path('ws/voice/', VoiceAgentConsumer.as_asgi()),
   ]
   ```

5. **Test direct integration**
   ```bash
   python scripts/voice_agent_direct.py
   ```

6. **Gradual migration**
   ```
   Week 1: Run both (n8n + Django) in parallel
   Week 2: Route 10% traffic to Django
   Week 3: Route 50% traffic to Django
   Week 4: Full migration to Django
   ```

---

## Performance Comparison

### Current (Original n8n with MCP loop)
```
Timeline:
├─ Webhook receive: 0ms
├─ Agent start: +50ms
├─ MCP Client HTTP call: +100ms
├─ MCP Server receive: +150ms
├─ Tool execution: +200ms
├─ HTTP response back: +250ms
├─ Agent process: +300ms
├─ LLM first token: +800ms
└─ Stream complete: +2500ms

Total: ~2.5 seconds
```

### Optimized n8n (Direct tools)
```
Timeline:
├─ Webhook receive: 0ms
├─ Agent start: +50ms
├─ Tool execution (direct): +100ms ⚡ (-150ms)
├─ Agent process: +150ms
├─ LLM first token: +500ms ⚡ (-300ms)
└─ Stream complete: +1200ms

Total: ~1.2 seconds (-52%)
```

### Django Direct
```
Timeline:
├─ WebSocket receive: 0ms
├─ Agent start: +20ms ⚡ (in-process)
├─ Tool execution (direct DB): +50ms ⚡ (no HTTP)
├─ LLM first token: +350ms ⚡ (parallel prep)
└─ Stream complete: +600ms

Total: ~0.6 seconds (-76%)
```

---

## Cost Comparison

### Model Costs (per 1000 requests)

**Current (gpt-4.1-mini):**
```
Input: 1000 requests × 500 tokens × $0.150/1M = $0.075
Output: 1000 requests × 200 tokens × $0.600/1M = $0.120
Total: $0.195
```

**Optimized (gpt-4o-mini):**
```
Input: 1000 requests × 500 tokens × $0.150/1M = $0.075
Output: 1000 requests × 150 tokens × $0.600/1M = $0.090
Total: $0.165 (-15%)
```

**Alternative (gpt-3.5-turbo):**
```
Input: 1000 requests × 500 tokens × $0.500/1M = $0.025
Output: 1000 requests × 150 tokens × $1.500/1M = $0.045
Total: $0.070 (-64%)
```

### Infrastructure Costs

| Solution | Monthly Cost | Notes |
|----------|--------------|-------|
| Current n8n | $20 (Render) | Single instance |
| Optimized n8n | $20 (Render) | Same infrastructure |
| Django Direct | $40-60 | Django app + Redis + DB |

**Break-even point:** ~50,000 requests/month if using gpt-3.5-turbo

---

## Monitoring & Rollback

### Add Performance Metrics

**For n8n (add to Conversation Agent):**
```javascript
// In workflow, add Set node before agent
$json.request_start = Date.now();

// After agent, add another Set node
$json.metrics = {
  latency_ms: Date.now() - $json.request_start,
  first_token_ms: $json.ttft,
  model: "gpt-4o-mini"
};
```

**For Django:**
```python
import time
from prometheus_client import Histogram

LATENCY = Histogram('voice_agent_latency_seconds', 'Agent response latency')

@LATENCY.time()
async def stream_response(self, text, session_id):
    # ... existing code
```

### Rollback Plan

**If optimized n8n has issues:**
```bash
# In n8n UI, revert to original workflow
# Or manually reconnect MCP nodes
```

**If Django has issues:**
```python
# In Django settings.py
VOICE_AGENT_BACKEND = os.getenv('VOICE_BACKEND', 'n8n')  # Switch with env var

if VOICE_AGENT_BACKEND == 'n8n':
    # Route to n8n webhook
else:
    # Use direct agent
```

---

## Testing Checklist

### Before Migration
- [ ] Backup current n8n workflow
- [ ] Test current baseline latency
- [ ] Document expected response format
- [ ] Verify database indices exist

### During Migration
- [ ] Import optimized workflow
- [ ] Run parallel testing (both versions)
- [ ] Monitor error rates
- [ ] Check response quality (no hallucinations)

### After Migration
- [ ] Verify 50%+ latency improvement
- [ ] Monitor for 48 hours
- [ ] Collect user feedback
- [ ] Update documentation

---

## Troubleshooting

### Issue: Optimized n8n still slow

**Diagnosis:**
```bash
# Check which step is slow
curl -X POST ... -w "Time: %{time_total}s\nTTFB: %{time_starttransfer}s\n"
```

**Solutions:**
1. If TTFB > 1s → Database queries slow
   - Add indexes: `CREATE INDEX idx_waybillNumber ON shipments(waybillNumber);`

2. If streaming slow → Network buffering
   - Check Render.com buffering settings
   - Verify `X-Accel-Buffering: no` header

3. If tool calls slow → Qdrant latency
   - Reduce topK to 1
   - Add scoreThreshold filter

### Issue: Django direct integration errors

**Common errors:**

1. **Import error: No module named 'langchain_openai'**
   ```bash
   pip install langchain-openai langchain-community
   ```

2. **Database connection timeout**
   ```python
   # Increase connection pool
   DATABASES['default']['CONN_MAX_AGE'] = 60
   ```

3. **Qdrant timeout**
   ```python
   client = QdrantClient(url=..., timeout=10)  # Increase timeout
   ```

---

## Recommendations

### For Immediate Impact (Today)
1. ✅ **Deploy optimized n8n workflow** (10 min)
2. ✅ Monitor latency improvements
3. ✅ Collect metrics for 24 hours

### For Maximum Performance (Next Sprint)
1. ✅ **Implement Django direct** (1 day)
2. ✅ Run A/B test (n8n vs Django) (1 week)
3. ✅ Full migration if latency target met

### Long-term Architecture
```
┌─────────────┐
│ Voice Input │
└──────┬──────┘
       │
       v
┌─────────────┐     Fast Path (<800ms)
│   Django    ├───────────────────────┐
│  WebSocket  │                       │
└──────┬──────┘                       │
       │                              │
       ├─> Direct DB Lookup (20ms)   │
       ├─> Direct Qdrant RAG (50ms)  │
       └─> LLM Stream (400ms) ────────┘
                                      │
                                      v
                              ┌──────────────┐
                              │ Voice Output │
                              └──────────────┘
```

---

## Success Metrics

| Metric | Current | Target (n8n) | Target (Django) |
|--------|---------|--------------|-----------------|
| TTFT (Time to First Token) | 800ms | <500ms | <350ms |
| Total Latency (P50) | 2500ms | <1200ms | <600ms |
| Total Latency (P95) | 3500ms | <1800ms | <900ms |
| Error Rate | <1% | <1% | <1% |
| Tool Call Latency | 400ms | <100ms | <50ms |

Track these in production and adjust as needed.

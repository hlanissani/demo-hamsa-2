# Action Plan: Optimize Voice Agent to Hamsa-Level Performance

## Executive Summary

**Goal:** Reduce voice agent latency from 9.5s → <2s (matching Hamsa Voice Agent standards)

**Timeline:** 3 weeks
**Budget:** $0 (using existing infrastructure)
**Expected Results:**
- 82% latency reduction
- 30% cost savings
- Better user experience

---

## Phase 1: Quick Win (TODAY - 1 hour)

### 🚨 CRITICAL INSIGHT: System Prompt is the Biggest Bottleneck
Your current prompt is **~1,200 characters (250-300 words)** adding **500-1000ms latency**.

**Solution:** Use ultra-compact prompt (150 words) + move KB mappings to Qdrant

### Objective: Deploy ultra-optimized n8n workflow
**Target:** 9.5s → 3.5s (-63%)

### Steps:

#### 1.1 Import Ultra-Optimized Workflow ⭐ RECOMMENDED
```bash
# In n8n UI
1. Click "Workflows" → "Import"
2. Select: docs/n8n-ultra-optimized-workflow.json
3. Verify credentials auto-mapped:
   - QdrantApi account ✓
   - OpenAi account ✓
   - Postgres DB ✓
```

**Key changes vs original:**
- System prompt: 1,200 → 750 chars (-500 to -1000ms)
- maxIterations: 3 → 2 (-200 to -500ms)
- contextWindow: 10 → 6 (-50 to -100ms)
- maxTokens: 150 → 120 (-30 to -50ms)
- Removed MCP loop (-300ms)

**Alternative (if cautious):**
Use `n8n-optimized-workflow.json` (longer prompt but still optimized)

#### 1.2 Update Webhook Path (Optional)
```
Old: /webhook/besmart/voice/agent/
New: /webhook/besmart/voice/agent/v2/

Update in your Django voice_agent/consumers.py:
N8N_WEBHOOK_URL = "https://n8n-service-z1ur.onrender.com/webhook/besmart/voice/agent/v2/"
```

#### 1.3 Test Performance
```bash
# Terminal test
curl -X POST https://n8n-service-z1ur.onrender.com/webhook/besmart/voice/agent/v2/ \
  -H "Content-Type: application/json" \
  -d '{
    "text": "السلام عليكم",
    "session_id": "perf-test-1"
  }' \
  -w "\nTime: %{time_total}s\n"

# Expected: <1.5s (down from 2.5s)
```

#### 1.4 Activate and Monitor
```
1. Activate new workflow
2. Deactivate old workflow
3. Monitor for errors (check n8n executions tab)
```

### Success Criteria ✅
- [ ] First token: <600ms
- [ ] Total response: <1.5s
- [ ] No errors in 10 test calls
- [ ] Streaming works correctly

**Time investment:** 1 hour
**Impact:** -49% latency

---

## Phase 2: Static Messages (WEEK 1 - 1 day)

### Objective: Add instant responses for predictable stages
**Target:** 4.8s → 2.5s (-48% additional)

### Steps:

#### 2.1 Add Code Node: Static_Message_Handler

**In n8n:**
1. Add "Code" node before `Voice_Agent`
2. Name it: `Static_Message_Handler`
3. Paste this code:

```javascript
// Static message patterns
const text = $input.item.json.body.text.toLowerCase();
const sessionId = $input.item.json.body.session_id;

// Get session data (simplified - use your actual DB)
const session = await getSessionData(sessionId);

// Pattern 1: Greeting (first message)
if (!session?.history || session.history.length === 0) {
  if (/سلام|مرحبا|hello|hi/.test(text)) {
    return {
      json: {
        response: "شكرا لاتصالك بناقل اكسبرس – معك ماجد – كيف اقدر اساعدك؟",
        static: true,
        stage: 1
      }
    };
  }
}

// Pattern 2: Closing
if (session?.stage === 5 && /لا|شكرا|no|thanks/.test(text)) {
  return {
    json: {
      response: "شكرا لاتصالك بناقل اكسبرس, راح يتم تحويلك للتقييم",
      static: true,
      stage: 6
    }
  };
}

// No match → continue to agent
return { json: { static: false, body: $input.item.json.body } };
```

#### 2.2 Add Router (IF Node)

After `Static_Message_Handler`:
```
IF: {{ $json.static }} === true
  TRUE → Respond to Webhook (return static response)
  FALSE → Voice_Agent (continue to LLM)
```

#### 2.3 Test Static Responses

```bash
# Test greeting (should be instant)
curl -X POST .../v2/ \
  -d '{"text": "السلام عليكم", "session_id": "test-static-1"}' \
  -w "\nTime: %{time_total}s\n"

# Expected: <100ms

# Test waybill (should use agent)
curl -X POST .../v2/ \
  -d '{"text": "NQL123456", "session_id": "test-static-2"}' \
  -w "\nTime: %{time_total}s\n"

# Expected: ~1.2s (unchanged)
```

### Success Criteria ✅
- [ ] Greeting: <100ms
- [ ] Closing: <100ms
- [ ] Complex queries still work: ~1.2s
- [ ] 50% of messages use static responses

**Time investment:** 4-8 hours
**Impact:** -48% additional latency

---

## Phase 3: Per-Stage Routing (WEEK 2-3 - 2 days)

### Objective: Use fast models for simple stages, smart models for complex
**Target:** 2.5s → 1.7s (-32% additional)

### Steps:

#### 3.1 Create Fast Agent

**Add new Conversation Agent node:**
```json
{
  "name": "Fast_Agent",
  "parameters": {
    "promptType": "define",
    "text": "={{ $json.body.text }}",
    "options": {
      "systemMessage": "Role: Naqel Agent\n\nStages:\n1. Greeting: شكرا لاتصالك\n2. Name: اذا ممكن اسمك؟\n3. Waybill: رقم الشحنة؟\n5. Additional: أي خدمه ثانية؟\n\nKeep responses under 30 words.",
      "maxIterations": 1,
      "enableStreaming": true
    }
  }
}
```

**Connect to LLM:**
```json
{
  "model": "gpt-3.5-turbo",
  "maxTokens": 80,
  "temperature": 0.2
}
```

#### 3.2 Add Stage Router

**Code node: `Stage_Router`**
```javascript
const text = $input.item.json.body.text;
const session = await getSessionData($input.item.json.body.session_id);
const stage = session?.stage || 1;

// Detect waybill/phone in text
const hasWaybill = /NQL\d+/i.test(text);
const hasPhone = /\d{10,15}/.test(text);

// Route to complex agent if:
// - Stage 4 (lookup needed)
// - Waybill/phone detected
if (stage === 4 || hasWaybill || hasPhone) {
  return { json: { route: 'complex', ...($input.item.json) } };
}

// Otherwise use fast agent
return { json: { route: 'fast', ...($input.item.json) } };
```

#### 3.3 Wire Connections

```
Webhook → Static_Handler → [Static? Return] or [Continue]
                                               ↓
                                         Stage_Router
                                               ↓
                              ┌────────────────┴────────────────┐
                              ↓                                 ↓
                        Fast_Agent                       Complex_Agent
                      (GPT-3.5-turbo)                    (GPT-4o-mini)
                        No tools                         + Tools
                              ↓                                 ↓
                              └────────────────┬────────────────┘
                                               ↓
                                          Response
```

#### 3.4 Test All Paths

```bash
# Path 1: Static (greeting)
curl -d '{"text": "السلام عليكم", "session_id": "test-1"}' ... # <100ms

# Path 2: Fast agent (name)
curl -d '{"text": "احمد محمد", "session_id": "test-2", "stage": 2}' ... # ~400ms

# Path 3: Complex agent (waybill)
curl -d '{"text": "NQL123456", "session_id": "test-3"}' ... # ~1000ms
```

### Success Criteria ✅
- [ ] Static path: <100ms
- [ ] Fast agent path: <500ms
- [ ] Complex agent path: <1200ms
- [ ] All stages work correctly
- [ ] No errors in 50 test conversations

**Time investment:** 8-16 hours
**Impact:** -32% additional latency

---

## Phase 4: Monitoring & Iteration (ONGOING)

### Objective: Track performance and optimize continuously

### Steps:

#### 4.1 Add Metrics Logging

**Add Set node at workflow end:**
```json
{
  "name": "Log_Metrics",
  "parameters": {
    "values": {
      "number": [
        {
          "name": "latency_ms",
          "value": "={{ Date.now() - $json.request_start }}"
        }
      ],
      "string": [
        {
          "name": "agent_type",
          "value": "={{ $json.route || 'static' }}"
        },
        {
          "name": "stage",
          "value": "={{ $json.stage }}"
        }
      ]
    }
  }
}
```

**Connect to Postgres:**
```sql
INSERT INTO voice_metrics (
  session_id, stage, latency_ms, agent_type, timestamp
) VALUES (
  '{{ $json.session_id }}',
  {{ $json.stage }},
  {{ $json.latency_ms }},
  '{{ $json.agent_type }}',
  NOW()
);
```

#### 4.2 Create Dashboard Query

```sql
-- Daily performance summary
SELECT
  DATE(timestamp) as date,
  agent_type,
  AVG(latency_ms) as avg_latency,
  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency,
  COUNT(*) as count
FROM voice_metrics
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY date, agent_type
ORDER BY date DESC, agent_type;
```

#### 4.3 Set Alerts

**Threshold monitoring:**
```sql
-- Alert if P95 latency > 2000ms
SELECT
  COUNT(*) FILTER (WHERE latency_ms > 2000) * 100.0 / COUNT(*) as slow_percentage
FROM voice_metrics
WHERE timestamp > NOW() - INTERVAL '1 hour'
HAVING slow_percentage > 5;  -- Alert if >5% slow
```

### Success Criteria ✅
- [ ] Metrics logged for all requests
- [ ] Dashboard shows <2s P95 latency
- [ ] Alert system in place
- [ ] Weekly review process established

**Time investment:** 4 hours setup + 1 hour/week review

---

## Rollback Plan

### If Issues Arise

**Problem: Optimized workflow has errors**
```
Solution:
1. In n8n, deactivate new workflow
2. Activate original workflow
3. Update webhook URL back to original
4. Debug issues in test environment
```

**Problem: Static responses incorrect**
```
Solution:
1. Disable Static_Message_Handler node
2. Route all traffic through agent
3. Fix pattern matching logic
4. Re-enable gradually
```

**Problem: Performance degraded**
```
Solution:
1. Check metrics dashboard for bottleneck
2. Review recent changes
3. Revert last change
4. Test in isolation
```

---

## Success Tracking

### Key Metrics

| Metric | Baseline | Phase 1 | Phase 2 | Phase 3 | Target |
|--------|----------|---------|---------|---------|--------|
| Avg Latency | 2500ms | 1200ms | 800ms | 600ms | <1000ms |
| P95 Latency | 3500ms | 1800ms | 1500ms | 1200ms | <2000ms |
| Static % | 0% | 0% | 50% | 50% | >40% |
| Cost/1K | $1.17 | $0.99 | $0.88 | $0.82 | <$1.00 |
| Error Rate | <1% | <1% | <1% | <1% | <1% |

### Weekly Review Checklist

**Every Monday:**
- [ ] Check average latency (should be <1s)
- [ ] Review error logs (should be <1%)
- [ ] Analyze slow queries (>2s)
- [ ] Check cost trends
- [ ] User feedback review

**Monthly:**
- [ ] Full performance audit
- [ ] Compare to Hamsa benchmarks
- [ ] Identify new optimization opportunities
- [ ] Update documentation

---

## Resources

### Documentation
1. [n8n-voice-agent-optimization.md](n8n-voice-agent-optimization.md) - Full technical guide
2. [hamsa-advanced-optimizations.md](hamsa-advanced-optimizations.md) - Hamsa techniques
3. [PERFORMANCE-EVOLUTION.md](PERFORMANCE-EVOLUTION.md) - Visual comparisons
4. [QUICK-OPTIMIZATION-REFERENCE.md](QUICK-OPTIMIZATION-REFERENCE.md) - Quick reference

### Files
- [n8n-optimized-workflow.json](n8n-optimized-workflow.json) - Ready to import
- [voice_agent_direct.py](../scripts/voice_agent_direct.py) - Django alternative

### Support
- n8n Community: https://community.n8n.io
- OpenAI API Status: https://status.openai.com
- Qdrant Docs: https://qdrant.tech/documentation

---

## Next Steps

**Right now:**
1. ✅ Import optimized workflow (1 hour)
2. ✅ Test basic functionality
3. ✅ Deploy to production

**This week:**
4. ✅ Add static messages (1 day)
5. ✅ Monitor performance (ongoing)

**This month:**
6. ✅ Implement per-stage routing (2 days)
7. ✅ Fine-tune and optimize
8. ✅ Document learnings

**Goal: <2s latency by end of month** 🎯

---

## Questions?

Check the documentation or reach out:
- Technical issues: Review troubleshooting sections
- Performance questions: Check PERFORMANCE-EVOLUTION.md
- Implementation help: See code examples in each guide

Good luck! You're about to achieve Hamsa-level performance! 🚀

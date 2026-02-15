# n8n Voice Agent Optimizations

Based on execution analysis, here are the recommended changes:

## 1. OpenAI Chat Model Settings

**Current bottleneck: 6.2s spent on LLM calls**

### Changes to make in `OpenAI_Chat` node:

```json
{
  "model": "gpt-4o-mini",
  "temperature": 0.05,  // Changed from 0.2
  "maxTokens": 150,     // Changed from 200
  "topP": 0.95,         // Changed from 0.9
  "frequencyPenalty": 0.2,  // Changed from 0.3
  "presencePenalty": 0.2,   // Changed from 0.3
  "promptCacheKey": "voice-agent-v2"  // Keep this!
}
```

**Expected improvement**: 15-20% faster LLM responses = ~1-1.5s saved

---

## 2. Embeddings Optimization

**Current: 770ms for embeddings**

### Changes to make in `Embeddings_OpenAI` node:

```json
{
  "model": "text-embedding-3-small",  // Add this
  "batchSize": 16,
  "stripNewLines": true
}
```

**Expected improvement**: 30-40% faster = ~250-300ms saved

---

## 3. Knowledge Base Optimization

**Current: 1.772s total**

### Option A: Increase cache hit rate
- Ensure the same queries are being made
- Check Qdrant collection for duplicates

### Option B: Pre-compute common responses
- If certain waybill statuses are common, pre-cache the KB results
- Reduces real-time search need

---

## 4. Voice Agent Settings

**Current: 3 iterations, batching=12**

### Optimize batching:
```json
{
  "maxIterations": 3,      // Keep this (needed for tools)
  "batching": {
    "batchSize": 16,       // Changed from 12
    "delayBetweenBatches": 0
  }
}
```

**Expected improvement**: Slightly faster streaming

---

## Expected Total Improvement

| Component | Current | After | Savings |
|-----------|---------|-------|---------|
| LLM calls | 6.2s | 5.0s | 1.2s |
| Embeddings | 0.77s | 0.5s | 0.27s |
| KB Search | 1.0s | 0.8s | 0.2s |
| **TOTAL** | **9.1s** | **7.4s** | **1.7s** |

**Target webhook time: ~7-8s** (down from 10s)

Combined with warm STT (2s) and TTS (2-3s):
**Total E2E: ~11-13s** (down from 22s in test #4)

---

## Implementation Priority

1. ✅ **High**: Change OpenAI model settings (5 min, biggest impact)
2. ✅ **High**: Change embedding model (2 min, good impact)
3. 🟡 **Medium**: Optimize batching (1 min, small impact)
4. 🟡 **Low**: Pre-cache common responses (complex, moderate impact)

---

## Testing After Changes

Run this command to test:
```bash
python quick_test.py "7826459301240" 3
```

This will:
- Test with a waybill number (triggers DB + KB tools)
- Run 3 iterations to verify consistency
- Show timing breakdown

**Target**: < 8s average webhook time

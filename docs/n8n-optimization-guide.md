# n8n Voice Agent Optimization Guide

## Current Setup Analysis
Your n8n workflow uses HTTP streaming with the Conversation Agent. This is good, but here are optimizations:

## Recommended n8n Improvements

### 1. **Enable Streaming at Webhook Level**
Current: `"responseMode": "streaming"` ✓ Already enabled

### 2. **Optimize OpenAI Settings**
Current settings in workflow:
```json
{
  "frequencyPenalty": 0,
  "maxTokens": 150,  // ⚠️ This might be too low for Arabic
  "temperature": 0,
  "topP": 0,
  "promptCacheKey": "agent-naqel-v3"
}
```

**Recommendations:**
- `maxTokens`: Increase to 300-500 (Arabic is verbose + your scripts are long)
- `temperature`: Keep at 0 for consistency ✓
- Enable **prompt caching** (you already have the key) ✓
- Consider `gpt-4o-mini` for speed vs `gpt-4o` for quality

### 3. **Add Response Streaming Headers**
Modify your n8n webhook to return proper streaming headers:
- `Transfer-Encoding: chunked`
- `Cache-Control: no-cache`
- `X-Accel-Buffering: no` (if behind nginx)

### 4. **Enable Agent Tool Parallelization**
In your Conversation Agent node, if you use multiple MCP tools, enable parallel execution.

### 5. **Optimize MCP Tool Timeout**
Current: `"timeout": 10000` (10 seconds)
- For NaqelTrackingDB: Reduce to 3000ms (database should be fast)
- For Knowledge_Base: Keep at 10000ms (vector search can be slower)

## Performance Targets

| Metric | Current | Target | How to Measure |
|--------|---------|--------|----------------|
| TTFB (n8n) | ? | <500ms | Check Django logs |
| First token | ? | <200ms after TTFB | Check `[WEBHOOK]` logs |
| Full response | ? | <2s | End-to-end timing |
| TTS start | ? | <800ms | From first sentence ready |

## WebSocket Consideration

**Question:** Should we use WebSocket for Django ↔ n8n?

**Answer:** No, because:
1. n8n webhook node doesn't support WebSocket responses
2. Your HTTP/2 streaming + connection pooling is already optimized
3. Bottleneck is likely in agent thinking time, not transport

**When to Use WebSocket:**
- If you need **client interruption** during agent response
- If you want **bidirectional** communication (e.g., agent asks clarifying questions)
- If you move agent logic **out of n8n** into Django directly

## Alternative: Bypass n8n for Voice

If n8n becomes a bottleneck, consider:

```python
# voice_agent/agent.py
class DirectVoiceAgent:
    """Call MCP tools directly from Django, bypass n8n."""

    async def process(self, text: str, session_id: str):
        # 1. Call Think tool directly
        think_result = await self._call_mcp_tool(
            "https://n8n.../mcp/test/tools/v2/Think",
            {"conversation_history": [...]}
        )

        # 2. Based on Think result, call NaqelTrackingDB or Knowledge_Base
        # 3. Stream response tokens via WebSocket
        # 4. Return to TTS pipeline
```

**Pros:**
- Eliminates n8n HTTP overhead
- Full control over streaming
- Can still use n8n for testing/visualization

**Cons:**
- Lose n8n's workflow visualization
- More code to maintain
- Your team can't modify agent behavior without code changes

**Recommendation:** Keep n8n unless you measure >500ms overhead.

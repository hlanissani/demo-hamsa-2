# Test Cold Start vs Warm Start

## Method 1: Quick Test
1. Wait 10 minutes (let n8n service sleep)
2. Make a request → Record webhook time (should be ~4-5s) ← COLD
3. Immediately make another request → Record webhook time (should be ~2-3s) ← WARM

## Method 2: Check Railway Logs
```bash
# For your n8n service at primary-production-77c2.up.railway.app
railway logs --follow
```

Look for:
- `Starting container...` ← Cold start happening
- Request processed immediately ← Already warm

## Expected Results

### With Cold Start (First Request After Sleep)
```
STT:     2.8s
Webhook: 4.9s  ← Includes 2-3s cold start
TTS:     4.5s
Total:   12.2s
```

### Without Cold Start (Second Request Immediately After)
```
STT:     2.8s
Webhook: 2.0s  ← No cold start! (AI + tools only)
TTS:     4.5s
Total:   9.3s  ← 3 seconds faster!
```

## Solution: Keep N8N Service Alive Too!

You have keep-alive for the voice service, but not the webhook service!

# Voice Agent - Quick Setup Guide

## What You Have

✅ N8N workflows (intent classifier, data lookup, response generator)
✅ MCP server for tools
✅ Knowledge base (Qdrant) with scripts
✅ Database with tracking data

## What You Need

🔲 Voice platform (Twilio/Vapi) - connects phone calls to your n8n
🔲 Bridge server (optional) - converts voice platform API to n8n format

---

## Architecture

```
Phone Call → Voice Platform → Your N8N → Response
            (ASR + TTS)        (Logic)
```

**Flow:**
1. User calls phone number
2. Voice platform transcribes speech → text
3. Platform sends text to your n8n webhook
4. N8N processes and returns response text
5. Platform converts text → speech
6. User hears response

---

## Setup Option 1: Vapi.ai (Easiest - 15 minutes)

### Step 1: Create Vapi Account
- Go to https://vapi.ai/
- Sign up and create new assistant

### Step 2: Configure Assistant

```json
{
  "name": "Majed - Naqel Support",
  "voice": {
    "provider": "11labs",
    "voiceId": "pNInz6obpgDQGcFmaJgB"  // Arabic voice
  },
  "model": {
    "provider": "custom-llm",
    "url": "https://n8n-service-z1ur.onrender.com/webhook/besmart/voice/agent/",
    "requestFormat": {
      "messages": "{{messages}}",
      "sessionId": "{{call.id}}"
    },
    "responseFormat": "text"
  },
  "firstMessage": "شكرا لاتصالك بناقل اكسبرس – معك ماجد – كيف اقدر اساعدك؟",
  "endCallPhrases": ["وداعاً", "شكراً", "goodbye"],
  "recordingEnabled": true,
  "language": "ar"
}
```

### Step 3: Update N8N Response Format

Your n8n currently returns:
```json
{"response": "text here"}
```

Vapi expects:
```json
{"text": "response here"}
```

**Fix:** Update final "Respond" node in orchestrator:
```javascript
// In Response Generator workflow (4-response-generator.json)
// Change final Respond node to:
{
  "parameters": {
    "respondWith": "json",
    "responseBody": "={{ { text: $json.response || $json.text } }}"
  }
}
```

### Step 4: Test
- Call the number Vapi provides
- Say "مرحبا"
- Should hear greeting from Majed

---

## Setup Option 2: Twilio (Production-Ready - 30 minutes)

### Step 1: Get Twilio Account
- Sign up at https://www.twilio.com/
- Buy a phone number ($1/month)
- Get Account SID and Auth Token

### Step 2: Create Bridge Server

This converts Twilio's format → your n8n format.

```python
# bridge.py
from flask import Flask, request
from twilio.twiml.voice_response import VoiceResponse, Gather
import requests

app = Flask(__name__)

N8N_WEBHOOK = "https://n8n-service-z1ur.onrender.com/webhook/besmart/voice/agent/"

@app.route('/voice', methods=['POST'])
def voice_handler():
    """Incoming call handler"""
    response = VoiceResponse()

    # First time: just gather input
    gather = response.gather(
        input='speech',
        action='/process',
        language='ar-SA',
        timeout=5,
        speechTimeout='auto'
    )

    # Optionally say greeting while waiting
    # gather.say("مرحباً", voice='Polly.Zeina', language='ar-SA')

    return str(response)

@app.route('/process', methods=['POST'])
def process_handler():
    """Process each user utterance"""

    # Extract data from Twilio
    user_text = request.form.get('SpeechResult', '')
    call_sid = request.form.get('CallSid')  # Use as session_id

    print(f"User said: {user_text}")

    # Call your n8n workflow
    try:
        n8n_response = requests.post(
            N8N_WEBHOOK,
            json={
                'text': user_text,
                'session_id': call_sid
            },
            timeout=10
        )
        response_data = n8n_response.json()
        agent_text = response_data.get('text') or response_data.get('response', '')

    except Exception as e:
        print(f"Error calling n8n: {e}")
        agent_text = "للاسف، حدث خطأ. الرجاء المحاولة لاحقاً"

    # Create voice response
    response = VoiceResponse()

    # Speak the response
    response.say(
        agent_text,
        voice='Polly.Zeina',  # Amazon Polly Arabic voice
        language='ar-SA'
    )

    # Check if conversation should end
    end_phrases = ['وداعاً', 'شكرا لاتصالك', 'تحويلك للتقييم']
    is_ending = any(phrase in agent_text for phrase in end_phrases)

    if not is_ending:
        # Continue conversation
        gather = response.gather(
            input='speech',
            action='/process',
            language='ar-SA',
            timeout=5
        )
    else:
        # End call
        response.hangup()

    return str(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

### Step 3: Deploy Bridge Server

```bash
# requirements.txt
flask
twilio
requests

# Deploy to Render/Railway
# Or run locally with ngrok for testing:
pip install flask twilio requests
python bridge.py

# In another terminal:
ngrok http 5000
# Copy the ngrok URL (https://xxxx.ngrok.io)
```

### Step 4: Configure Twilio Number

1. Go to Twilio Console → Phone Numbers
2. Click your number
3. Voice & Fax → A CALL COMES IN:
   - Webhook: `https://your-bridge-server.com/voice`
   - HTTP POST
4. Save

### Step 5: Test
- Call your Twilio number
- Say "مرحبا"
- Should work!

---

## Testing Your Setup

### Test 1: N8N Workflow Only
```bash
curl -X POST https://n8n-service-z1ur.onrender.com/webhook/besmart/voice/agent/ \
  -H "Content-Type: application/json" \
  -d '{"text": "اسمي احمد محمد", "session_id": "test-123"}'

# Expected response:
{"text": "أهلاً استاذ احمد محمد اذا ممكن تزودني برقم الشحنة"}
```

### Test 2: Full Voice Flow
1. Call the phone number
2. Say: "مرحبا"
3. Expect: Greeting from Majed
4. Say: "اسمي احمد محمد"
5. Expect: "أهلاً استاذ احمد محمد..."
6. Say: "NQL123456"
7. Expect: Status message

### Test 3: Error Handling
- Say gibberish
- Stay silent for 5 seconds
- Say something out of scope

---

## Common Issues & Fixes

### Issue 1: "Cannot read properties of undefined"
**Cause:** N8N workflow expecting wrong data structure

**Fix:** Check webhook receives:
```json
{
  "body": {
    "text": "user message",
    "session_id": "123"
  }
}
```

### Issue 2: Slow Response (> 5 seconds)
**Cause:** AI calls taking too long

**Fix:**
- Use templates for 70% of responses (done in your split workflows)
- Switch to Claude Haiku for intent classification
- Add timeout to all HTTP requests (3-5 seconds)

### Issue 3: ASR Not Understanding Arabic
**Cause:** Wrong language setting

**Fix (Twilio):**
```python
gather = response.gather(
    input='speech',
    language='ar-SA',  # Make sure this is set!
    speechModel='phone_call'  # Better for phone audio
)
```

**Fix (Vapi):**
```json
{
  "transcriber": {
    "provider": "deepgram",
    "model": "nova-2",
    "language": "ar"
  }
}
```

### Issue 4: TTS Sounds Robotic
**Cause:** Wrong voice or provider

**Best Arabic Voices:**
- **ElevenLabs:** Most natural but expensive
- **Azure:** `ar-SA-HamedNeural` (male) or `ar-SA-ZariyahNeural` (female)
- **Amazon Polly:** `Zeina` (female, Lebanese accent)

**Twilio Update:**
```python
response.say(
    text,
    voice='Polly.Zeina',  # Or use Azure voices via Twilio
    language='ar-SA'
)
```

---

## Cost Estimation

### Twilio Option
| Component | Cost |
|-----------|------|
| Phone number | $1/month |
| Incoming calls | $0.0085/min |
| Outgoing (optional) | $0.013/min |
| Speech recognition | $0.02/min |
| TTS (Polly) | $4/1M chars |

**Example:** 1000 calls/day, 3 min average = $600/month

### Vapi Option
| Component | Cost |
|-----------|------|
| Platform fee | $0.05/min |
| TTS (ElevenLabs) | $0.18/min |
| ASR (Deepgram) | $0.0043/min |

**Example:** 1000 calls/day, 3 min average = $7,000/month

---

## Performance Optimization

### 1. Use Streaming Responses
Instead of waiting for full response, stream word-by-word:

```python
# In bridge server
from twilio.twiml.voice_response import VoiceResponse
response = VoiceResponse()

# Stream response as it generates
response.say(agent_text, voice='Polly.Zeina')
response.pause(length=0)  # No pause between chunks
```

### 2. Cache Common Responses
```python
# In n8n Function node
const cache = {
  "greeting_ar": "شكرا لاتصالك بناقل اكسبرس...",
  "ask_name_ar": "تمام، اذا ممكن تزودني باسمك..."
};

// Check cache first
if (cache[stage + "_" + language]) {
  return {json: {text: cache[stage + "_" + language]}};
}
```

### 3. Parallel Execution
Your split workflows already do this! Each component runs independently.

---

## Monitoring & Analytics

### Log Each Call
```python
# In bridge server
import logging

@app.route('/process', methods=['POST'])
def process_handler():
    call_sid = request.form.get('CallSid')
    user_text = request.form.get('SpeechResult')

    # Log to file/database
    logging.info(f"Call {call_sid}: User said '{user_text}'")

    # ... rest of code
```

### Track Metrics
- **Call duration** (Twilio provides this)
- **Response time** (measure n8n webhook latency)
- **Intent accuracy** (did user get what they needed?)
- **Completion rate** (how many finished vs hung up?)

### N8N Metrics
Add timing to workflows:
```javascript
// In first Function node
const startTime = Date.now();

// In last Function node
const duration = Date.now() - startTime;
console.log(`Workflow took ${duration}ms`);
```

---

## Next Steps

1. **Choose platform:** Vapi (quick) or Twilio (flexible)
2. **Deploy bridge** (if using Twilio)
3. **Test with curl** first
4. **Test with real call**
5. **Monitor performance**
6. **Optimize based on metrics**

---

## Support Resources

- **Twilio Docs:** https://www.twilio.com/docs/voice/twiml
- **Vapi Docs:** https://docs.vapi.ai
- **N8N Voice Examples:** https://n8n.io/workflows/?search=voice
- **Your workflows:** `n8n-workflows/README.md`

---

## Quick Commands

```bash
# Test n8n workflow
curl -X POST https://n8n-service-z1ur.onrender.com/webhook/besmart/voice/agent/ \
  -d '{"text": "test", "session_id": "123"}'

# Run bridge server locally
python bridge.py

# Expose with ngrok
ngrok http 5000

# Check Twilio logs
twilio api:core:calls:list --limit 10

# Monitor n8n executions
# Go to n8n dashboard → Executions
```

**You're ready to build your voice agent! 🎉**

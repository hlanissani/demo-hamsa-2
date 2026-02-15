# Voice Agent Implementation Guide - Naqel Express

## Quick Start

Your voice agent has **3 layers** that work together:

```
┌─────────────────────────────────────────────┐
│  LAYER 1: Voice Platform (Twilio/Vapi)     │
│  - Handles phone calls                      │
│  - ASR: Speech → Text                       │
│  - TTS: Text → Speech                       │
└────────────────┬────────────────────────────┘
                 │
                 │ HTTP POST
                 ▼
┌─────────────────────────────────────────────┐
│  LAYER 2: Your N8N Workflows               │
│  - Intent classification                    │
│  - Data lookup                              │
│  - Response generation                      │
└────────────────┬────────────────────────────┘
                 │
                 │ MCP/Database
                 ▼
┌─────────────────────────────────────────────┐
│  LAYER 3: Backend Services                 │
│  - PostgreSQL (tracking data)               │
│  - Qdrant (knowledge base)                  │
│  - MCP Server (tools)                       │
└─────────────────────────────────────────────┘
```

---

## Step-by-Step Setup

### Step 1: Set Up Voice Platform

#### Option A: Twilio (Recommended for Production)

1. **Create Twilio Account**
   - Sign up at https://www.twilio.com/
   - Get a phone number with voice capabilities
   - Note your Account SID and Auth Token

2. **Configure Voice Webhook**
   ```python
   # app.py - Flask/FastAPI bridge
   from flask import Flask, request
   from twilio.twiml.voice_response import VoiceResponse, Gather
   import requests

   app = Flask(__name__)

   @app.route('/voice/incoming', methods=['POST'])
   def incoming_call():
       """Handle incoming call"""
       response = VoiceResponse()

       # Greeting
       gather = response.gather(
           input='speech',
           action='/voice/process',
           language='ar-SA',  # Saudi Arabic
           timeout=5,
           speechTimeout='auto'
       )

       # Optional: Play greeting while waiting
       # gather.say("مرحباً", voice='Polly.Zeina', language='ar-SA')

       return str(response)

   @app.route('/voice/process', methods=['POST'])
   def process_speech():
       """Process transcribed speech"""
       # Get transcription from Twilio
       user_text = request.form.get('SpeechResult', '')
       call_sid = request.form.get('CallSid')

       # Call your n8n workflow
       n8n_response = requests.post(
           'https://n8n-service-z1ur.onrender.com/webhook/besmart/voice/agent/',
           json={
               'text': user_text,
               'session_id': call_sid
           },
           timeout=10
       )

       response_data = n8n_response.json()

       # Create TwiML response
       response = VoiceResponse()

       # Speak the response
       response.say(
           response_data.get('text', ''),
           voice='Polly.Zeina',  # Amazon Polly Arabic voice
           language='ar-SA'
       )

       # If conversation continues, gather more input
       if not response_data.get('is_closing', False):
           gather = response.gather(
               input='speech',
               action='/voice/process',
               language='ar-SA',
               timeout=5
           )

       return str(response)

   if __name__ == '__main__':
       app.run(port=5000)
   ```

3. **Deploy Bridge Server**
   ```bash
   # Deploy to Render/Railway/Heroku
   pip install flask twilio requests
   python app.py
   ```

4. **Configure Twilio Phone Number**
   - Go to Phone Numbers → Manage → Active Numbers
   - Set Voice & Fax → A CALL COMES IN → Webhook
   - URL: `https://your-bridge-server.com/voice/incoming`
   - Method: HTTP POST

#### Option B: Vapi.ai (Fastest Setup)

1. **Create Vapi Account**
   - Sign up at https://vapi.ai/
   - Create new assistant

2. **Configure Assistant**
   ```json
   {
     "name": "Majed - Naqel Support",
     "voice": {
       "provider": "azure",
       "voiceId": "ar-SA-HamedNeural"
     },
     "model": {
       "provider": "custom-llm",
       "url": "https://n8n-service-z1ur.onrender.com/webhook/besmart/voice/agent/",
       "model": "naqel-voice-agent"
     },
     "firstMessage": "شكرا لاتصالك بناقل اكسبرس – معك ماجد – كيف اقدر اساعدك؟",
     "endCallMessage": "شكرا لاتصالك بناقل اكسبرس",
     "recordingEnabled": true,
     "language": "ar"
   }
   ```

3. **Get Phone Number**
   - Vapi provides phone numbers
   - Or forward from your existing number

---

### Step 2: Update N8N Workflows

Your current workflow already receives:
```json
{
  "text": "اسمي احمد محمد",
  "session_id": "CA123456789"
}
```

**Modification needed:** Return format expected by voice platform

#### Update Final Response Node

<function_calls>
<invoke name="Read">
<parameter name="file_path">C:\Users\Windows.10\Desktop\hamsa ws\n8n-workflows\1-orchestrator-main.json
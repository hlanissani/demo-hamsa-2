#!/usr/bin/env python3
"""
Test persistent TTS connection by sending a query that generates multiple sentences
"""

import asyncio
import json
import websockets


async def test_voice_agent():
    """Connect to voice agent and send test audio"""

    WS_URL = "ws://localhost:8000/ws/agent/test-session/"

    # Dummy audio - the server will process it through STT (though it may not recognize real text)
    # For real testing, we'd need actual Arabic audio
    dummy_audio = "UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA="

    print(f"[*] Connecting to {WS_URL}...")

    async with websockets.connect(WS_URL) as ws:
        print("[+] Connected!")

        # Wait for initial status
        initial = await ws.recv()
        print(f"[<] Received: {initial}")

        # Send audio
        print(f"[>] Sending audio...")
        await ws.send(json.dumps({
            "audio_base64": dummy_audio
        }))

        # Receive all messages
        print("\n[*] Receiving messages:\n")
        async for message in ws:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "status":
                print(f"   [STATUS] {data.get('message')}")
            elif msg_type == "transcription":
                print(f"   [TRANSCRIPTION] {data.get('text')}")
            elif msg_type == "token":
                print(f"   [TOKEN] {data.get('content')}", end='', flush=True)
            elif msg_type == "agent_response":
                print(f"\n   [AGENT] {data.get('text')}")
            elif msg_type == "tts_start":
                print(f"   [TTS] Starting...")
            elif msg_type == "tts_chunk":
                print(".", end='', flush=True)
            elif msg_type == "done":
                print(f"\n   [DONE]")
                break
            elif msg_type == "error":
                print(f"\n   [ERROR] {data.get('message')}")
                break

        print("\n[+] Test complete!")


if __name__ == "__main__":
    try:
        asyncio.run(test_voice_agent())
    except KeyboardInterrupt:
        print("\n[-] Interrupted")
    except Exception as e:
        print(f"\n[-] Error: {e}")

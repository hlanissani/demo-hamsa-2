#!/usr/bin/env python3
"""
Voice Agent Latency Testing Script
Measures end-to-end performance of the voice pipeline
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import websockets


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


class LatencyTimer:
    """Track latency metrics with visual reporting"""

    def __init__(self, test_name: str):
        self.test_name = test_name
        self.start_time = None
        self.metrics = {}
        self.events = []

    def start(self):
        """Start the timer"""
        self.start_time = time.time()
        self.log_event("START", "Timer started")
        return self

    def checkpoint(self, name: str, description: str = ""):
        """Record a checkpoint"""
        if not self.start_time:
            return

        elapsed_ms = (time.time() - self.start_time) * 1000
        self.metrics[name] = elapsed_ms
        self.log_event(name, description, elapsed_ms)
        return elapsed_ms

    def log_event(self, event: str, description: str, elapsed_ms: float = None):
        """Log an event"""
        self.events.append({
            "event": event,
            "description": description,
            "elapsed_ms": elapsed_ms,
            "timestamp": datetime.now().isoformat()
        })

    def get_elapsed(self) -> float:
        """Get total elapsed time in ms"""
        if not self.start_time:
            return 0
        return (time.time() - self.start_time) * 1000

    def print_summary(self):
        """Print a visual summary of timing"""
        total = self.get_elapsed()

        print(f"\n{Colors.HEADER}{'='*80}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}📊 LATENCY REPORT: {self.test_name}{Colors.END}")
        print(f"{Colors.HEADER}{'='*80}{Colors.END}\n")

        # Print metrics table
        print(f"{Colors.BOLD}{'Checkpoint':<30} {'Time (ms)':<15} {'Cumulative':<15}{Colors.END}")
        print(f"{'-'*60}")

        prev_time = 0
        for name, elapsed_ms in self.metrics.items():
            delta = elapsed_ms - prev_time

            # Color code based on performance
            if delta < 500:
                color = Colors.GREEN
            elif delta < 1500:
                color = Colors.YELLOW
            else:
                color = Colors.RED

            print(f"{name:<30} {color}{delta:>10.0f}ms{Colors.END}    {elapsed_ms:>10.0f}ms")
            prev_time = elapsed_ms

        print(f"{'-'*60}")

        # Total time with color coding
        if total < 3000:
            total_color = Colors.GREEN
            rating = "⚡ EXCELLENT"
        elif total < 5000:
            total_color = Colors.YELLOW
            rating = "✓ GOOD"
        else:
            total_color = Colors.RED
            rating = "⚠ SLOW"

        print(f"{Colors.BOLD}{'TOTAL':<30} {total_color}{total:>10.0f}ms{Colors.END}    {rating}")
        print(f"\n{Colors.HEADER}{'='*80}{Colors.END}\n")


async def test_webhook_streaming(webhook_url: str, text: str, session_id: str = "test"):
    """Test the n8n webhook streaming performance"""

    timer = LatencyTimer(f"Webhook Test: '{text}'").start()

    print(f"{Colors.CYAN}🚀 Testing webhook endpoint...{Colors.END}")
    print(f"   URL: {webhook_url}")
    print(f"   Text: {text}")
    print(f"   Session: {session_id}\n")

    import httpx

    first_token = None
    token_count = 0
    response_text = ""

    async with httpx.AsyncClient(timeout=60.0) as client:
        timer.checkpoint("connection_start", "HTTP connection initiated")

        async with client.stream(
            "POST",
            webhook_url,
            json={"text": text, "session_id": session_id},
            headers={"Accept": "application/json"}
        ) as response:
            timer.checkpoint("ttfb", "Time to First Byte (TTFB)")

            buffer = ""
            async for chunk in response.aiter_text():
                buffer += chunk

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                        node_name = data.get("metadata", {}).get("nodeName", "")
                        msg_type = data.get("type", "")
                        content = data.get("content", "")

                        if node_name == "Voice Agent" and msg_type == "item" and content:
                            if first_token is None:
                                timer.checkpoint("first_token", f"First token: '{content}'")
                                first_token = content

                            token_count += 1
                            response_text += content

                            # Visual progress indicator
                            if token_count % 5 == 0:
                                print(f"   {Colors.BLUE}Token #{token_count}: '{response_text[-20:]}'{Colors.END}")

                        elif node_name == "Respond to Webhook" and msg_type == "item":
                            try:
                                output_data = json.loads(content)
                                response_text = output_data.get("output", response_text)
                            except:
                                pass

                    except json.JSONDecodeError:
                        continue

    timer.checkpoint("complete", f"Response complete ({token_count} tokens)")

    print(f"\n{Colors.GREEN}✓ Response received:{Colors.END}")
    print(f"   {response_text}\n")

    timer.print_summary()

    return {
        "text": response_text,
        "tokens": token_count,
        "total_ms": timer.get_elapsed(),
        "ttft_ms": timer.metrics.get("first_token", 0)
    }


async def test_websocket_pipeline(ws_url: str, audio_file: Path = None):
    """Test the full WebSocket pipeline (STT -> Agent -> TTS)"""

    timer = LatencyTimer("WebSocket Full Pipeline").start()

    print(f"{Colors.CYAN}🎤 Testing full voice pipeline...{Colors.END}")
    print(f"   WS URL: {ws_url}\n")

    # Use sample audio or dummy data
    if audio_file and audio_file.exists():
        import base64
        audio_base64 = base64.b64encode(audio_file.read_bytes()).decode()
        print(f"   Using audio file: {audio_file}")
    else:
        # Dummy base64 audio for testing
        audio_base64 = "UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA="
        print(f"   Using dummy audio data")

    transcription = None
    agent_response = None
    tts_chunks = 0

    async with websockets.connect(ws_url) as ws:
        timer.checkpoint("ws_connected", "WebSocket connected")

        # Send audio
        await ws.send(json.dumps({
            "audio_base64": audio_base64
        }))
        timer.checkpoint("audio_sent", "Audio sent to server")

        async for message in ws:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "status":
                print(f"   {Colors.YELLOW}Status: {data.get('message')}{Colors.END}")

            elif msg_type == "transcription":
                transcription = data.get("text")
                timer.checkpoint("stt_complete", f"STT: '{transcription}'")
                print(f"   {Colors.GREEN}Transcription: {transcription}{Colors.END}")

            elif msg_type == "token":
                if "agent_first_token" not in timer.metrics:
                    timer.checkpoint("agent_first_token", "Agent first token")
                content = data.get("content", "")
                print(f"   {Colors.BLUE}Token: {content}{Colors.END}", end="", flush=True)

            elif msg_type == "agent_response":
                agent_response = data.get("text")
                timer.checkpoint("agent_complete", "Agent response complete")
                print(f"\n   {Colors.GREEN}Agent: {agent_response}{Colors.END}")

            elif msg_type == "tts_start":
                timer.checkpoint("tts_start", "TTS started")

            elif msg_type == "tts_chunk":
                if tts_chunks == 0:
                    timer.checkpoint("tts_first_chunk", "First TTS audio chunk")
                tts_chunks += 1
                if tts_chunks % 10 == 0:
                    print(f"   {Colors.CYAN}TTS chunk #{tts_chunks}{Colors.END}")

            elif msg_type == "done":
                timer.checkpoint("pipeline_complete", f"Pipeline done ({tts_chunks} audio chunks)")
                print(f"\n{Colors.GREEN}✓ Pipeline complete!{Colors.END}\n")
                break

            elif msg_type == "error":
                error_msg = data.get("message", "Unknown error")
                print(f"\n{Colors.RED}✗ Error: {error_msg}{Colors.END}\n")
                break

    timer.print_summary()

    return {
        "transcription": transcription,
        "agent_response": agent_response,
        "tts_chunks": tts_chunks,
        "total_ms": timer.get_elapsed()
    }


async def main():
    """Main test runner"""

    print(f"\n{Colors.BOLD}{Colors.HEADER}")
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║         VOICE AGENT LATENCY TESTING TOOL                     ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print(f"{Colors.END}\n")

    # Configuration
    WEBHOOK_URL = "https://n8n-service-z1ur.onrender.com/webhook/besmart/voice/agent/v2/"
    WS_URL = "ws://localhost:8000/ws/voice-agent/test-session/"

    print(f"{Colors.BOLD}Select test mode:{Colors.END}")
    print("1. Test n8n webhook only (fast)")
    print("2. Test full WebSocket pipeline (requires Django running locally)")
    print("3. Run both tests")

    choice = input(f"\n{Colors.CYAN}Enter choice [1-3]:{Colors.END} ").strip()

    if choice in ["1", "3"]:
        print(f"\n{Colors.BOLD}--- TEST 1: n8n Webhook Streaming ---{Colors.END}\n")

        test_text = input(f"{Colors.CYAN}Enter test text (or press Enter for default):{Colors.END} ").strip()
        if not test_text:
            test_text = "السلام عليكم"

        await test_webhook_streaming(WEBHOOK_URL, test_text)

    if choice in ["2", "3"]:
        print(f"\n{Colors.BOLD}--- TEST 2: Full WebSocket Pipeline ---{Colors.END}\n")
        await test_websocket_pipeline(WS_URL)

    print(f"{Colors.GREEN}All tests complete!{Colors.END}\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Test interrupted by user{Colors.END}\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.END}\n")
        sys.exit(1)

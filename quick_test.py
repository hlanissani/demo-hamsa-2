#!/usr/bin/env python3
"""Quick latency test - minimal output, maximum clarity"""

import asyncio
import json
import sys
import time
from datetime import datetime

import httpx


def print_metric(label: str, value_ms: float, threshold_good: float = 1000):
    """Print a metric with color coding"""
    color = "\033[92m" if value_ms < threshold_good else "\033[93m" if value_ms < 2000 else "\033[91m"
    reset = "\033[0m"
    print(f"{label:.<30} {color}{value_ms:>8.0f}ms{reset}")


async def test(url: str, text: str, session_id: str = "quick-test"):
    """Quick test with minimal output"""

    print(f"\n{'='*50}")
    print(f"🎯 QUICK LATENCY TEST")
    print(f"{'='*50}")
    print(f"Text: {text}")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')}\n")

    start = time.time()
    ttfb = None
    first_token = None
    last_token = None
    tokens = 0
    response = ""

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST", url,
            json={"text": text, "session_id": session_id},
            headers={"Accept": "application/json"}
        ) as resp:
            ttfb = (time.time() - start) * 1000

            buffer = ""
            async for chunk in resp.aiter_text():
                buffer += chunk
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if not line.strip():
                        continue

                    try:
                        data = json.loads(line.strip())
                        if data.get("metadata", {}).get("nodeName") == "Voice Agent" and data.get("type") == "item":
                            content = data.get("content", "")
                            if content:
                                if first_token is None:
                                    first_token = (time.time() - start) * 1000
                                tokens += 1
                                response += content
                                last_token = (time.time() - start) * 1000
                    except:
                        pass

    total = (time.time() - start) * 1000

    # Print results
    print(f"RESPONSE: {response}\n")
    print(f"{'─'*50}")
    print_metric("TTFB (Connection)", ttfb, 500)
    print_metric("TTFT (First Token)", first_token, 1000)
    print_metric("Streaming Time", last_token - first_token if first_token else 0, 1000)
    print_metric("Total Time", total, 3000)
    print(f"{'─'*50}")
    print(f"Tokens received: {tokens}")
    print(f"{'='*50}\n")

    return {
        "ttfb": ttfb,
        "ttft": first_token,
        "total": total,
        "tokens": tokens,
        "response": response
    }


async def run_multiple_tests(url: str, texts: list, iterations: int = 1):
    """Run multiple tests and show aggregate stats"""

    all_results = []

    for i in range(iterations):
        if iterations > 1:
            print(f"\n🔄 ITERATION {i+1}/{iterations}")

        for text in texts:
            result = await test(url, text, f"test-{i}-{hash(text)}")
            all_results.append(result)
            await asyncio.sleep(1)  # Small delay between tests

    # Summary
    if len(all_results) > 1:
        print(f"\n{'='*50}")
        print(f"📊 AGGREGATE SUMMARY ({len(all_results)} tests)")
        print(f"{'='*50}\n")

        avg_ttfb = sum(r["ttfb"] for r in all_results) / len(all_results)
        avg_ttft = sum(r["ttft"] for r in all_results if r["ttft"]) / len([r for r in all_results if r["ttft"]])
        avg_total = sum(r["total"] for r in all_results) / len(all_results)

        print_metric("Avg TTFB", avg_ttfb, 500)
        print_metric("Avg TTFT", avg_ttft, 1000)
        print_metric("Avg Total", avg_total, 3000)
        print(f"\n{'='*50}\n")


if __name__ == "__main__":
    # Default config
    URL = "https://n8n-service-z1ur.onrender.com/webhook/besmart/voice/agent/v2/"

    # Parse args
    if len(sys.argv) > 1:
        test_text = sys.argv[1]
    else:
        test_text = "السلام عليكم"

    iterations = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    # Run test
    try:
        asyncio.run(run_multiple_tests(URL, [test_text], iterations))
    except KeyboardInterrupt:
        print("\n❌ Test interrupted\n")
        sys.exit(0)

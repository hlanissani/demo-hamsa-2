#!/usr/bin/env python3
"""Parse Django logs to find performance bottlenecks"""

import re
import sys
from pathlib import Path

def parse_timing_logs(log_file):
    """Extract timing information from Django logs"""

    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find timing patterns
    stt_times = re.findall(r'\[STT\] ([^:]+): (\d+)ms', content)
    webhook_times = re.findall(r'\[WEBHOOK\] ([^:]+): (\d+)ms', content)
    tts_times = re.findall(r'\[TTS-WS\] ([^:]+): (\d+)ms', content)

    print("\n" + "="*60)
    print("📊 PERFORMANCE BREAKDOWN FROM LOGS")
    print("="*60 + "\n")

    if stt_times:
        print("🎤 STT TIMING:")
        for label, ms in stt_times:
            print(f"   {label:<30} {int(ms):>6}ms")
        print()

    if webhook_times:
        print("🔗 WEBHOOK TIMING:")
        for label, ms in webhook_times:
            print(f"   {label:<30} {int(ms):>6}ms")
        print()

    if tts_times:
        print("🔊 TTS TIMING:")
        for label, ms in tts_times:
            print(f"   {label:<30} {int(ms):>6}ms")
        print()

    # Look for slow operations
    print("⚠️  SLOW OPERATIONS (>1000ms):")
    all_times = stt_times + webhook_times + tts_times
    slow_ops = [(label, int(ms)) for label, ms in all_times if int(ms) > 1000]

    if slow_ops:
        for label, ms in sorted(slow_ops, key=lambda x: x[1], reverse=True):
            print(f"   {label:<30} {ms:>6}ms ⚠️")
    else:
        print("   None found ✓")

    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        log_file = sys.argv[1]
    else:
        # Default to most recent task output
        log_file = r"C:\Users\Windows.10\AppData\Local\Temp\claude\c--Users-Windows-10-Desktop-hamsa-ws\tasks\b7e64b7.output"

    if not Path(log_file).exists():
        print(f"❌ Log file not found: {log_file}")
        sys.exit(1)

    parse_timing_logs(log_file)

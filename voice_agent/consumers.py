import asyncio
import base64
import json
import logging
import re
import struct
import sys
import uuid

import httpx
import websockets
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

logger = logging.getLogger(__name__)


def log(msg):
    print(msg, flush=True)


class VoiceAgentConsumer(AsyncWebsocketConsumer):
    # Shared HTTP client for connection pooling (reduces latency)
    _http_client = None

    @classmethod
    def get_http_client(cls):
        """Get or create shared HTTP client with connection pooling."""
        if cls._http_client is None:
            cls._http_client = httpx.AsyncClient(
                timeout=60.0,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
                http2=True  # Enable HTTP/2 for better performance
            )
        return cls._http_client

    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"].get("session_id") or str(uuid.uuid4())
        await self.accept()
        await self._send_status("متصل بالخادم")

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data=None, bytes_data=None):
        if text_data is None:
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self._send_error("Invalid JSON")
            return

        audio_base64 = data.get("audio_base64")
        if not audio_base64:
            await self._send_error("'audio_base64' is required")
            return

        asyncio.create_task(self._run_pipeline(audio_base64))

    async def _run_pipeline(self, audio_base64):
        """Orchestrate: STT -> Webhook+TTS streamed together"""
        try:
            # Step 1: STT
            await self._send_status("جاري التعرف على الصوت...")
            transcription = await self._call_stt(audio_base64)
            log(f"[PIPELINE] STT result: '{transcription}' (len={len(transcription) if transcription else 0})")
            if not transcription:
                await self._send_error("لم يتم التعرف على أي نص")
                return
            await self.send(text_data=json.dumps({
                "type": "transcription", "text": transcription
            }))

            # Step 2+3: Webhook streams tokens → detect sentences → TTS each immediately
            log(f"[PIPELINE] Calling webhook with: '{transcription}'")
            await self._send_status("جاري التفكير...")

            sentence_q = asyncio.Queue()
            tts_task = asyncio.create_task(self._tts_consumer(sentence_q))

            agent_response = await self._call_webhook(transcription, sentence_q)
            log(f"[PIPELINE] Webhook result: '{agent_response}' (len={len(agent_response) if agent_response else 0})")

            # Signal TTS consumer to finish and wait
            await sentence_q.put(None)
            await tts_task

            if not agent_response:
                await self._send_error("لم يتم الحصول على رد من الوكيل")
                return
            await self.send(text_data=json.dumps({
                "type": "agent_response", "text": agent_response
            }))

            # Small delay to ensure all TTS chunks are transmitted over WebSocket
            await asyncio.sleep(0.5)

            await self.send(text_data=json.dumps({"type": "done"}))
            log("[PIPELINE] Done!")

        except Exception as e:
            log(f"[PIPELINE] ERROR: {type(e).__name__}: {e}")
            await self._send_error(str(e))

    async def _tts_consumer(self, sentence_q):
        """Read sentences from queue, TTS each via WebSocket, stream chunks to client."""
        idx = 0
        while True:
            sentence = await sentence_q.get()
            if sentence is None:
                break
            idx += 1
            if idx == 1:
                await self.send(text_data=json.dumps({
                    "type": "tts_start",
                    "sample_rate": 16000,
                }))
            log(f"[TTS-STREAM] sentence {idx}: '{sentence[:80]}'")
            await self._send_status("جاري تحويل الرد إلى صوت...")
            try:
                await self._call_tts_ws(sentence)
            except Exception as e:
                log(f"[TTS-STREAM] ERROR on sentence {idx}: {type(e).__name__}: {e}")

    async def _connect_hamsa_ws(self):
        """Connect to Hamsa WS with retry."""
        url = f"{settings.HAMSA_WS_URL}?api_key={settings.HAMSA_API_KEY}"
        for attempt in range(3):
            try:
                ws = await websockets.connect(url)
                init_msg = await ws.recv()
                log(f"[HAMSA] connected (attempt {attempt + 1}): {init_msg}")
                return ws
            except Exception as e:
                log(f"[HAMSA] connection attempt {attempt + 1} failed: {type(e).__name__}: {e}")
                if attempt < 2:
                    await asyncio.sleep(1)
                else:
                    raise

    async def _call_stt(self, audio_base64):
        """Connect to Hamsa STT WebSocket, send audio, return transcription."""
        import time
        start_time = time.time()

        log(f"[STT] connecting... (audio size: {len(audio_base64)} chars)")
        await self._send_status("جاري الاتصال بخدمة التعرف...")

        transcription = None

        ws = await self._connect_hamsa_ws()
        connect_time = time.time() - start_time
        log(f"[STT] connected in {connect_time:.2f}s")

        try:
            send_start = time.time()
            await ws.send(json.dumps({
                "type": "stt",
                "payload": {
                    "audioBase64": audio_base64,
                    "language": "ar",
                    "isEosEnabled": True,
                    "eosThreshold": 0.3,
                },
            }, ensure_ascii=False))
            send_time = time.time() - send_start
            log(f"[STT] sent audio in {send_time:.2f}s, waiting for response...")
            await self._send_status("جاري معالجة الصوت...")

            while True:
                response = await asyncio.wait_for(ws.recv(), timeout=30)
                log(f"[STT] response type={type(response).__name__} len={len(response) if response else 0}")
                if isinstance(response, bytes):
                    log("[STT] got bytes, skipping")
                    continue
                log(f"[STT] text: {response[:500] if response else ''}")
                try:
                    data = json.loads(response)
                    msg_type = data.get("type", "")
                    log(f"[STT] JSON type='{msg_type}'")
                    if msg_type == "error":
                        err = data.get("payload", {}).get("message", "STT error")
                        log(f"[STT] ERROR: {err}")
                        await self._send_error(err)
                        return None
                    elif msg_type == "end":
                        log("[STT] got end signal")
                        break
                    elif msg_type == "transcription":
                        transcription = data.get("payload", {}).get("text", "")
                        log(f"[STT] transcription from JSON: {transcription}")
                        break
                    else:
                        log(f"[STT] unknown JSON: {data}")
                except json.JSONDecodeError:
                    transcription = response
                    log(f"[STT] transcription (raw text): {transcription}")
                    break
        except asyncio.TimeoutError:
            log("[STT] timeout")
            await self._send_error("STT timeout")
        finally:
            await ws.close()

        total_time = time.time() - start_time
        log(f"[STT] TOTAL TIME: {total_time:.2f}s")
        return transcription

    # More aggressive sentence detection for streaming TTS
    # Matches sentence-ending punctuation OR Arabic comma/pause markers
    _SENTENCE_END_RE = re.compile(r'[.!?؟،–\-:]\s*$')

    async def _call_webhook(self, text, sentence_q=None):
        """Call the webhook agent, stream tokens, push sentences to TTS queue."""
        full_response = ""
        sentence_buf = ""
        sentences_pushed = False

        # Token batching: accumulate tokens and send in batches
        token_batch = ""
        token_count = 0
        BATCH_SIZE = 8  # Send every 8 tokens (adjust for balance between latency/overhead)

        log(f"[WEBHOOK] POST {settings.WEBHOOK_URL}")
        log(f"[WEBHOOK] payload: text='{text}', session_id='{self.session_id}'")

        # Use shared HTTP client for better connection pooling
        client = self.get_http_client()
        async with client.stream(
                "POST",
                settings.WEBHOOK_URL,
                json={"text": text, "session_id": self.session_id},
                headers={"Accept": "application/json"},
            ) as response:
                log(f"[WEBHOOK] HTTP {response.status_code}")
                buffer = ""
                async for chunk in response.aiter_text():
                    log(f"[WEBHOOK] chunk: {chunk[:200]}")
                    buffer += chunk
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            log(f"[WEBHOOK] non-JSON line: {line[:200]}")
                            continue

                        node_name = data.get("metadata", {}).get("nodeName", "")
                        msg_type = data.get("type", "")
                        log(f"[WEBHOOK] node='{node_name}' type='{msg_type}'")

                        if node_name == "Conversation Agent" and msg_type == "item":
                            content = data.get("content", "")
                            if content:
                                full_response += content
                                sentence_buf += content
                                token_batch += content
                                token_count += 1

                                # Send batch when: reaching batch size OR sentence boundary
                                should_flush = (
                                    token_count >= BATCH_SIZE or
                                    self._SENTENCE_END_RE.search(content)
                                )

                                if should_flush and token_batch:
                                    await self.send(text_data=json.dumps({
                                        "type": "token", "content": token_batch
                                    }))
                                    token_batch = ""
                                    token_count = 0

                                # Push sentence to TTS as soon as boundary detected
                                stripped = sentence_buf.strip()
                                # More aggressive streaming: push on punctuation OR length threshold
                                should_stream = (
                                    len(stripped) >= 80 or  # Long enough, flush anyway
                                    (len(stripped) >= 10 and self._SENTENCE_END_RE.search(stripped))  # Has punctuation
                                )
                                if sentence_q and should_stream:
                                    log(f"[WEBHOOK] sentence ready ({len(stripped)} chars): '{stripped[:80]}'")
                                    await sentence_q.put(stripped)
                                    sentence_buf = ""
                                    sentences_pushed = True

                        elif node_name == "Respond to Webhook" and msg_type == "item":
                            content = data.get("content", "")
                            if content:
                                log(f"[WEBHOOK] Respond to Webhook content: {content[:200]}")
                                try:
                                    output = json.loads(content)
                                    full_response = output.get("output", full_response)
                                except json.JSONDecodeError:
                                    pass

                # Flush any remaining batched tokens
                if token_batch:
                    await self.send(text_data=json.dumps({
                        "type": "token", "content": token_batch
                    }))
                    log(f"[WEBHOOK] flushed final batch: {len(token_batch)} chars")

                if buffer.strip():
                    log(f"[WEBHOOK] remaining buffer: {buffer[:200]}")
                    try:
                        data = json.loads(buffer.strip())
                        node_name = data.get("metadata", {}).get("nodeName", "")
                        if node_name == "Respond to Webhook" and data.get("type") == "item":
                            content = data.get("content", "")
                            if content:
                                try:
                                    output = json.loads(content)
                                    full_response = output.get("output", full_response)
                                except json.JSONDecodeError:
                                    pass
                    except json.JSONDecodeError:
                        pass

        # Push any remaining buffered text
        if sentence_q and sentence_buf.strip():
            log(f"[WEBHOOK] pushing remaining buffer: '{sentence_buf.strip()[:80]}'")
            await sentence_q.put(sentence_buf.strip())
            sentences_pushed = True

        # Fallback: if no sentences were streamed, split the final response
        if sentence_q and not sentences_pushed and full_response:
            log("[WEBHOOK] ⚠️ NO STREAMING - Falling back to batch mode split")
            log(f"[WEBHOOK] Sentence detection failed. Full response length: {len(full_response)}")
            for s in self._split_sentences(full_response):
                await sentence_q.put(s)
        elif sentences_pushed:
            log("[WEBHOOK] ✓ STREAMING MODE - Sentences streamed to TTS in real-time")

        log(f"[WEBHOOK] final response: '{full_response[:200]}'")
        return full_response

    @staticmethod
    def _split_sentences(text):
        """Split text into sentence-sized chunks for incremental TTS."""
        # Split on sentence-ending punctuation and major pauses
        parts = re.split(r'(?<=[.!?؟،–\-])\s*', text)
        sentences = [p.strip() for p in parts if p.strip()]
        # Merge very short fragments into the previous sentence
        merged = []
        for s in sentences:
            if merged and len(merged[-1]) < 20:
                merged[-1] += " " + s
            else:
                merged.append(s)
        return merged if merged else [text]

    @staticmethod
    def _wrap_wav(pcm_data, sample_rate=16000, num_channels=1, bit_depth=16):
        """Wrap raw PCM data in a WAV header."""
        data_len = len(pcm_data)
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + data_len,
            b"WAVE",
            b"fmt ",
            16,
            1,  # PCM format
            num_channels,
            sample_rate,
            sample_rate * num_channels * (bit_depth // 8),
            num_channels * (bit_depth // 8),
            bit_depth,
            b"data",
            data_len,
        )
        return header + pcm_data

    async def _call_tts_ws(self, text):
        """Call Hamsa WebSocket TTS, stream audio chunks to client in real-time."""
        ws = await self._connect_hamsa_ws()
        try:
            await ws.send(json.dumps({
                "type": "tts",
                "payload": {
                    "text": text,
                    "speaker": "Majd",
                    "dialect": "ksa",
                    "languageId": "ar",
                    "mulaw": False,
                },
            }, ensure_ascii=False))
            log(f"[TTS-WS] sent request: '{text[:80]}'")

            chunk_count = 0
            total_bytes = 0

            while True:
                response = await asyncio.wait_for(ws.recv(), timeout=30)

                if isinstance(response, bytes):
                    chunk_count += 1
                    total_bytes += len(response)
                    await self.send(text_data=json.dumps({
                        "type": "tts_chunk",
                        "audio_base64": base64.b64encode(response).decode("utf-8"),
                    }))
                    continue

                # JSON control message
                try:
                    data = json.loads(response)
                    msg_type = data.get("type", "")
                    if msg_type == "ack":
                        log(f"[TTS-WS] ack: {data.get('payload', {}).get('message', '')}")
                    elif msg_type == "end":
                        log(f"[TTS-WS] done: {chunk_count} chunks, {total_bytes} bytes")
                        break
                    elif msg_type == "error":
                        log(f"[TTS-WS] error: {data.get('payload', {}).get('message', '')}")
                        break
                    else:
                        log(f"[TTS-WS] msg: {data}")
                except json.JSONDecodeError:
                    log(f"[TTS-WS] non-JSON: {response[:200]}")
        except asyncio.TimeoutError:
            log("[TTS-WS] timeout")
        finally:
            await ws.close()

    async def _call_tts(self, text):
        """Call Hamsa REST TTS API, return audio bytes."""
        url = "https://api.tryhamsa.com/v1/realtime/tts-stream"
        headers = {
            "Authorization": f"Token {settings.HAMSA_API_KEY}",
            "Content-Type": "application/json",
        }
        body = {
            "text": text,
            "speaker": "Majd",
            "dialect": "ksa",
            "mulaw": False,
        }

        log(f"[TTS] POST {url} text='{text[:80]}'")
        audio_chunks = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", url, json=body, headers=headers) as response:
                log(f"[TTS] HTTP {response.status_code}")
                content_type = response.headers.get("content-type", "")
                log(f"[TTS] Content-Type: {content_type}")
                if response.status_code != 200:
                    log(f"[TTS] ERROR: HTTP {response.status_code}")
                    return None
                async for chunk in response.aiter_bytes():
                    audio_chunks.append(chunk)

        total = sum(len(c) for c in audio_chunks)
        log(f"[TTS] total audio: {total} bytes from {len(audio_chunks)} chunks")
        if not audio_chunks:
            return None

        audio_data = b"".join(audio_chunks)

        # If the data already has a WAV header, return as-is
        if audio_data[:4] == b"RIFF":
            log("[TTS] audio already has WAV header")
            return audio_data

        # Raw PCM — wrap in WAV header so the browser can play it
        log("[TTS] wrapping raw PCM in WAV header")
        return self._wrap_wav(audio_data)

    async def _send_status(self, message):
        await self.send(text_data=json.dumps({"type": "status", "message": message}))

    async def _send_error(self, message):
        log(f"[ERROR -> client] {message}")
        await self.send(text_data=json.dumps({"type": "error", "message": message}))

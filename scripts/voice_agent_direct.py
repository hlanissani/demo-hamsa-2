"""
Django Direct Voice Agent - Bypass n8n for Maximum Performance
Target: <800ms total latency for real-time voice
"""

import asyncio
import httpx
from typing import AsyncGenerator, Dict, Any
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import BaseTool
from langchain.prompts import ChatPromptTemplate
from langchain_community.chat_message_histories import PostgresChatMessageHistory
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
import os

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
POSTGRES_CONNECTION_STRING = os.getenv("DATABASE_URL")


class NaqelDBLookupTool(BaseTool):
    """Direct database lookup - no n8n overhead"""
    name = "LookupByWaybill"
    description = "Look up shipment by waybill number (NQL...)"

    async def _arun(self, waybill_number: str) -> Dict[str, Any]:
        """Direct database query - ~20ms"""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT waybillNumber, status, deliveryDate, deliveryTime, signedBy, senderPhone
                FROM shipments
                WHERE waybillNumber = %s
                LIMIT 1
                """,
                [waybill_number]
            )
            row = cursor.fetchone()

            if not row:
                return {"error": "Waybill not found"}

            return {
                "waybillNumber": row[0],
                "status": row[1],
                "deliveryDate": row[2],
                "deliveryTime": row[3],
                "signedBy": row[4],
                "senderPhone": row[5]
            }


class NaqelPhoneLookupTool(BaseTool):
    """Direct phone lookup"""
    name = "LookupByPhone"
    description = "Look up shipment by phone number (9-15 digits)"

    async def _arun(self, phone_number: str) -> Dict[str, Any]:
        """Direct database query"""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT waybillNumber, status, deliveryDate, senderPhone
                FROM shipments
                WHERE senderPhone = %s
                ORDER BY createdAt DESC
                LIMIT 1
                """,
                [phone_number]
            )
            row = cursor.fetchone()

            if not row:
                return {"error": "Phone not found in system"}

            return {
                "waybillNumber": row[0],
                "status": row[1],
                "deliveryDate": row[2],
                "senderPhone": row[3]
            }


class KnowledgeBaseTool(BaseTool):
    """Direct Qdrant RAG - no n8n overhead"""
    name = "Knowledge_Base"
    description = "Get script template by exact keyword search"

    def __init__(self):
        super().__init__()
        self.client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY
        )
        self.collection_name = "nagel-demo-rag"

    async def _arun(self, query: str) -> str:
        """Direct Qdrant query - ~50ms"""
        from langchain_openai import OpenAIEmbeddings

        # Generate embedding
        embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
        query_vector = await embeddings.aembed_query(query)

        # Search Qdrant
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=1,
            score_threshold=0.7
        )

        if not results:
            return "No script found for this query"

        return results[0].payload.get("text", "")


class DirectVoiceAgent:
    """
    High-performance voice agent - direct tool execution

    Latency breakdown:
    - Tool calls: 20-50ms (direct DB/Qdrant)
    - LLM first token: 300-500ms
    - Full response: <800ms
    """

    def __init__(self):
        # Initialize LLM with optimized settings
        self.llm = ChatOpenAI(
            model="gpt-4o-mini-2024-07-18",
            temperature=0.3,
            max_tokens=150,
            streaming=True,
            openai_api_key=OPENAI_API_KEY
        )

        # Initialize tools (direct access, no HTTP)
        self.tools = [
            NaqelDBLookupTool(),
            NaqelPhoneLookupTool(),
            KnowledgeBaseTool()
        ]

        # System prompt (from your n8n workflow)
        self.system_prompt = """## CORE IDENTITY
**Role:** Naqel Express Support Agent (Majed)
**Mission:** Script-driven tracking support using direct tools

## CRITICAL RULES
1. ONE STAGE = ONE RESPONSE → STOP
2. MANDATORY tool calls — never generate data
3. EXACT script delivery from Knowledge_Base (no paraphrasing)
4. Preserve Saudi dialect: اذا ممكن، تزودني، للاسف، عشان، مانقدر
5. Language lock: Match customer's first message
6. Single data display only

## TOOLS
**LookupByWaybill**: Input `waybill_number` (NQL...)
**LookupByPhone**: Input `phone_number`
**Knowledge_Base**: Input `query` (exact keyword)

## FLOW

**STAGE 1: GREETING**
Mirror greeting + AR: `شكرا لاتصالك بناقل اكسبرس – معك "ماجد" – كيف اقدر اساعدك؟` | EN: `Thank you for calling Naqel Express. This is Majed, How may I help you?`
STOP

**STAGE 2: NAME**
AR: `تمام، اذا ممكن تزودني باسمك الكامل من فضلك؟` | EN: `Alright, may I please have your full name?`
STOP → Store as {Customer Full Name}

**STAGE 3: WAYBILL REQUEST**
AR: `أهلاً استاذ {Customer Full Name} اذا ممكن تزودني برقم الشحنة` | EN: `Welcome Mr/Ms {Customer Full Name}. Can I please have the waybill number?`
STOP

**STAGE 4A: WITH WAYBILL**
1. Call `LookupByWaybill(waybill_number=<value>)`
2. Map status → KB keyword
3. Call `Knowledge_Base(query=<keyword>)`
4. Fill placeholders, deliver script

**STAGE 4B: WITHOUT WAYBILL**
**Turn 1:** AR: `اذا ممكن تزودني برقم التواصل المسجل في بيانات الشحنه` | EN: `Please provide the contact number.`
STOP

**Turn 2:**
1. Call `LookupByPhone(phone_number=<value>)`
2. Get script from Knowledge_Base
3. Deliver response

**STAGE 5: ADDITIONAL SERVICE**
AR: `أي خدمه ثانية استاذ {Customer Full Name}` | EN: `Any other service?`

**STAGE 6: CLOSING**
AR: `شكرا لاتصالك بناقل اكسبرس` | EN: `Thank you for calling Naqel Express.`
END

## KB KEYWORDS
delivered → `Shipment Delivered`
in_transit/out_for_delivery → `Shipment Under Delivery`
wrong_address/incomplete_address → `Shipment With Incorrect Address`
refused → `Shipment - Refused Delivery`
"""

        # Create agent
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])

        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=False,
            handle_parsing_errors=True
        )

    async def stream_response(
        self,
        text: str,
        session_id: str
    ) -> AsyncGenerator[str, None]:
        """
        Stream response chunks for real-time voice

        Args:
            text: User input text
            session_id: Session identifier for chat history

        Yields:
            Response chunks as they're generated
        """
        # Get chat history
        message_history = PostgresChatMessageHistory(
            connection_string=POSTGRES_CONNECTION_STRING,
            session_id=session_id
        )

        # Get last 10 messages only (performance optimization)
        chat_history = message_history.messages[-10:]

        # Stream response
        async for chunk in self.agent_executor.astream({
            "input": text,
            "chat_history": chat_history
        }):
            # Extract text from chunk
            if "output" in chunk:
                yield chunk["output"]
            elif "actions" in chunk:
                # Tool being called (optional: log for monitoring)
                pass

    async def get_response(self, text: str, session_id: str) -> str:
        """
        Non-streaming response (for testing)
        """
        message_history = PostgresChatMessageHistory(
            connection_string=POSTGRES_CONNECTION_STRING,
            session_id=session_id
        )

        chat_history = message_history.messages[-10:]

        result = await self.agent_executor.ainvoke({
            "input": text,
            "chat_history": chat_history
        })

        # Save to history
        message_history.add_user_message(text)
        message_history.add_ai_message(result["output"])

        return result["output"]


# Django Integration Example
class VoiceAgentConsumer:
    """
    WebSocket consumer for real-time voice
    Use with Django Channels
    """

    def __init__(self):
        self.agent = DirectVoiceAgent()

    async def receive(self, text_data: str, session_id: str):
        """
        Handle incoming voice transcription
        Stream response back to client
        """
        import json

        data = json.loads(text_data)
        user_text = data.get("text", "")

        # Stream response
        async for chunk in self.agent.stream_response(user_text, session_id):
            await self.send(text_data=json.dumps({
                "type": "voice_response",
                "chunk": chunk
            }))

        # Send end marker
        await self.send(text_data=json.dumps({
            "type": "voice_response_complete"
        }))


# FastAPI Integration Example
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()
agent = DirectVoiceAgent()

@app.post("/voice/agent/")
async def voice_agent_endpoint(text: str, session_id: str):
    """
    FastAPI endpoint for voice agent
    Returns streaming response
    """
    async def generate():
        async for chunk in agent.stream_response(text, session_id):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


# Performance Testing
async def benchmark():
    """
    Test response latency
    """
    import time

    agent = DirectVoiceAgent()

    test_cases = [
        ("السلام عليكم", "test-1"),
        ("رقم الشحنة NQL123456", "test-2"),
        ("0501234567", "test-3")
    ]

    for text, session_id in test_cases:
        start = time.time()
        response = await agent.get_response(text, session_id)
        latency = (time.time() - start) * 1000

        print(f"Input: {text}")
        print(f"Response: {response}")
        print(f"Latency: {latency:.0f}ms\n")


if __name__ == "__main__":
    asyncio.run(benchmark())

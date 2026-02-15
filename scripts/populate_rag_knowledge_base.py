"""
Populate Qdrant Knowledge Base with Voice Agent Scripts
Run this script to upload all conversation templates to Qdrant
"""

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from openai import OpenAI
import os

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "YOUR_QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "YOUR_QDRANT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY")
COLLECTION_NAME = "nagel-demo-rag"

# Initialize clients
qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Define ALL voice agent scripts
VOICE_SCRIPTS = [
    # ===== GREETINGS =====
    {
        "id": "greeting-initial-ar",
        "text": "شكرا لاتصالك بناقل اكسبرس – معك \"ماجد\" – كيف اقدر اساعدك؟",
        "metadata": {
            "stage": "greeting",
            "action": "ask_name",
            "language": "ar",
            "category": "greeting",
            "requires_data": False
        }
    },
    {
        "id": "greeting-initial-en",
        "text": "Thank you for calling Naqel Express. This is Majed, How may I help you?",
        "metadata": {
            "stage": "greeting",
            "action": "ask_name",
            "language": "en",
            "category": "greeting",
            "requires_data": False
        }
    },

    # ===== ASK FOR NAME =====
    {
        "id": "ask-name-ar",
        "text": "تمام، اذا ممكن تزودني باسمك الكامل من فضلك؟",
        "metadata": {
            "stage": "awaiting_name",
            "action": "ask_name",
            "language": "ar",
            "category": "question",
            "requires_data": False
        }
    },
    {
        "id": "ask-name-en",
        "text": "Alright, may I please have your full name?",
        "metadata": {
            "stage": "awaiting_name",
            "action": "ask_name",
            "language": "en",
            "category": "question",
            "requires_data": False
        }
    },

    # ===== ASK FOR WAYBILL =====
    {
        "id": "ask-waybill-ar",
        "text": "أهلاً استاذ {Customer Name} اذا ممكن تزودني برقم الشحنة",
        "metadata": {
            "stage": "awaiting_waybill",
            "action": "ask_waybill",
            "language": "ar",
            "category": "question",
            "requires_data": False
        }
    },
    {
        "id": "ask-waybill-en",
        "text": "Welcome Mr/Ms {Customer Name}. Can I please have the waybill number?",
        "metadata": {
            "stage": "awaiting_waybill",
            "action": "ask_waybill",
            "language": "en",
            "category": "question",
            "requires_data": False
        }
    },

    # ===== ASK FOR PHONE =====
    {
        "id": "ask-phone-ar",
        "text": "اذا ممكن تزودني برقم التواصل المسجل في بيانات الشحنه",
        "metadata": {
            "stage": "awaiting_phone",
            "action": "ask_phone",
            "language": "ar",
            "category": "question",
            "requires_data": False
        }
    },
    {
        "id": "ask-phone-en",
        "text": "Please provide the contact number registered with the shipment.",
        "metadata": {
            "stage": "awaiting_phone",
            "action": "ask_phone",
            "language": "en",
            "category": "question",
            "requires_data": False
        }
    },

    # ===== DELIVERY STATUS: DELIVERED =====
    {
        "id": "delivered-status-ar",
        "text": "شحنتك رقم {Waybill Number} تم تسليمها بتاريخ {Delivery Date} الساعة {Delivery Time} والمستلم {Signed By}",
        "metadata": {
            "stage": "delivered_status",
            "action": "deliver_status",
            "language": "ar",
            "category": "status",
            "status": "delivered",
            "requires_data": True
        }
    },
    {
        "id": "delivered-status-en",
        "text": "Your shipment {Waybill Number} was delivered on {Delivery Date} at {Delivery Time}, signed by {Signed By}",
        "metadata": {
            "stage": "delivered_status",
            "action": "deliver_status",
            "language": "en",
            "category": "status",
            "status": "delivered",
            "requires_data": True
        }
    },

    # ===== DELIVERY STATUS: IN TRANSIT =====
    {
        "id": "in-transit-status-ar",
        "text": "شحنتك رقم {Waybill Number} حالياً في الطريق للتسليم. راح توصلك خلال 24 ساعة ان شاء الله",
        "metadata": {
            "stage": "delivered_status",
            "action": "deliver_status",
            "language": "ar",
            "category": "status",
            "status": "in_transit",
            "requires_data": True
        }
    },
    {
        "id": "in-transit-status-en",
        "text": "Your shipment {Waybill Number} is currently in transit. It will arrive within 24 hours.",
        "metadata": {
            "stage": "delivered_status",
            "action": "deliver_status",
            "language": "en",
            "category": "status",
            "status": "in_transit",
            "requires_data": True
        }
    },

    # ===== DELIVERY STATUS: OUT FOR DELIVERY =====
    {
        "id": "out-for-delivery-status-ar",
        "text": "شحنتك رقم {Waybill Number} خرجت للتسليم. السائق راح يتواصل معك خلال ساعات",
        "metadata": {
            "stage": "delivered_status",
            "action": "deliver_status",
            "language": "ar",
            "category": "status",
            "status": "out_for_delivery",
            "requires_data": True
        }
    },
    {
        "id": "out-for-delivery-status-en",
        "text": "Your shipment {Waybill Number} is out for delivery. The driver will contact you within hours.",
        "metadata": {
            "stage": "delivered_status",
            "action": "deliver_status",
            "language": "en",
            "category": "status",
            "status": "out_for_delivery",
            "requires_data": True
        }
    },

    # ===== DELIVERY STATUS: WRONG ADDRESS =====
    {
        "id": "wrong-address-status-ar",
        "text": "شحنتك رقم {Waybill Number} فيها مشكلة في العنوان. راح نتواصل معك لتحديث البيانات",
        "metadata": {
            "stage": "delivered_status",
            "action": "deliver_status",
            "language": "ar",
            "category": "status",
            "status": "wrong_address",
            "requires_data": True
        }
    },
    {
        "id": "wrong-address-status-en",
        "text": "Your shipment {Waybill Number} has an address issue. We will contact you to update the information.",
        "metadata": {
            "stage": "delivered_status",
            "action": "deliver_status",
            "language": "en",
            "category": "status",
            "status": "wrong_address",
            "requires_data": True
        }
    },

    # ===== DELIVERY STATUS: REFUSED =====
    {
        "id": "refused-status-ar",
        "text": "شحنتك رقم {Waybill Number} تم رفضها من المستلم. راح نرجعها للمرسل",
        "metadata": {
            "stage": "delivered_status",
            "action": "deliver_status",
            "language": "ar",
            "category": "status",
            "status": "refused",
            "requires_data": True
        }
    },
    {
        "id": "refused-status-en",
        "text": "Your shipment {Waybill Number} was refused by the recipient. It will be returned to sender.",
        "metadata": {
            "stage": "delivered_status",
            "action": "deliver_status",
            "language": "en",
            "category": "status",
            "status": "refused",
            "requires_data": True
        }
    },

    # ===== ASK FOR MORE SERVICE =====
    {
        "id": "ask-more-service-ar",
        "text": "أي خدمه ثانية استاذ {Customer Name}؟",
        "metadata": {
            "stage": "awaiting_additional_service",
            "action": "ask_more_service",
            "language": "ar",
            "category": "question",
            "requires_data": False
        }
    },
    {
        "id": "ask-more-service-en",
        "text": "Any other service, Mr/Ms {Customer Name}?",
        "metadata": {
            "stage": "awaiting_additional_service",
            "action": "ask_more_service",
            "language": "en",
            "category": "question",
            "requires_data": False
        }
    },

    # ===== CLOSING =====
    {
        "id": "closing-ar",
        "text": "شكرا لاتصالك بناقل اكسبرس, راح يتم تحويلك للتقييم",
        "metadata": {
            "stage": "closing",
            "action": "close",
            "language": "ar",
            "category": "closing",
            "requires_data": False
        }
    },
    {
        "id": "closing-en",
        "text": "Thank you for calling Naqel Express. Please answer the evaluation.",
        "metadata": {
            "stage": "closing",
            "action": "close",
            "language": "en",
            "category": "closing",
            "requires_data": False
        }
    },

    # ===== OUT OF SCOPE =====
    {
        "id": "out-of-scope-ar",
        "text": "للاسف استاذ {Customer Name} هذا خارج نطاق خدمتنا. اقدر اساعدك في تتبع الشحنات. عندك شحنة تبي تستفسر عنها؟",
        "metadata": {
            "stage": "out_of_scope",
            "action": "handle_out_of_scope",
            "language": "ar",
            "category": "error_handling",
            "requires_data": False
        }
    },
    {
        "id": "out-of-scope-en",
        "text": "I apologize, Mr/Ms {Customer Name}, this is outside our service scope. I can help with shipment tracking. Do you have a shipment to inquire about?",
        "metadata": {
            "stage": "out_of_scope",
            "action": "handle_out_of_scope",
            "language": "en",
            "category": "error_handling",
            "requires_data": False
        }
    },

    # ===== CLARIFICATION =====
    {
        "id": "ask-clarification-ar",
        "text": "عفواً، مافهمت طلبك. ممكن تعيد مرة ثانية؟",
        "metadata": {
            "stage": "any",
            "action": "ask_clarification",
            "language": "ar",
            "category": "error_handling",
            "requires_data": False
        }
    },
    {
        "id": "ask-clarification-en",
        "text": "Sorry, I did not understand. Can you please repeat?",
        "metadata": {
            "stage": "any",
            "action": "ask_clarification",
            "language": "en",
            "category": "error_handling",
            "requires_data": False
        }
    }
]


def generate_embedding(text: str) -> list:
    """Generate embedding using OpenAI"""
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


def create_collection():
    """Create or recreate Qdrant collection"""
    try:
        # Check if collection exists
        collections = qdrant.get_collections().collections
        collection_exists = any(c.name == COLLECTION_NAME for c in collections)

        if collection_exists:
            print(f"⚠️  Collection '{COLLECTION_NAME}' already exists")
            response = input("Do you want to DELETE and recreate it? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Aborted. Exiting.")
                return False

            qdrant.delete_collection(collection_name=COLLECTION_NAME)
            print(f"🗑️  Deleted existing collection")

        # Create new collection
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=1536,  # text-embedding-3-small dimension
                distance=Distance.COSINE
            )
        )
        print(f"✅ Created collection '{COLLECTION_NAME}'")
        return True

    except Exception as e:
        print(f"❌ Error creating collection: {e}")
        return False


def upload_scripts():
    """Upload all scripts to Qdrant"""
    points = []

    print(f"\n📝 Generating embeddings for {len(VOICE_SCRIPTS)} scripts...")

    for idx, script in enumerate(VOICE_SCRIPTS):
        print(f"  {idx + 1}/{len(VOICE_SCRIPTS)}: {script['id']}")

        try:
            # Generate embedding
            embedding = generate_embedding(script["text"])

            # Create point
            point = PointStruct(
                id=idx,
                vector=embedding,
                payload={
                    "text": script["text"],
                    "script_id": script["id"],
                    **script["metadata"]
                }
            )
            points.append(point)

        except Exception as e:
            print(f"    ❌ Error: {e}")
            continue

    # Batch upload
    try:
        qdrant.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        print(f"\n✅ Successfully uploaded {len(points)} scripts to Qdrant!")
        return True
    except Exception as e:
        print(f"\n❌ Error uploading to Qdrant: {e}")
        return False


def test_search():
    """Test RAG search with sample queries"""
    print("\n🧪 Testing RAG searches...")

    test_cases = [
        {
            "query": "ask name اسم العميل",
            "filter": {"action": "ask_name", "language": "ar"},
            "expected_id": "ask-name-ar"
        },
        {
            "query": "delivered status تم التسليم",
            "filter": {"action": "deliver_status", "language": "ar", "status": "delivered"},
            "expected_id": "delivered-status-ar"
        },
        {
            "query": "closing وداعاً",
            "filter": {"action": "close", "language": "ar"},
            "expected_id": "closing-ar"
        }
    ]

    for idx, test in enumerate(test_cases):
        print(f"\n  Test {idx + 1}: {test['query']}")
        print(f"  Filter: {test['filter']}")

        try:
            # Generate query embedding
            query_embedding = generate_embedding(test["query"])

            # Search
            results = qdrant.search(
                collection_name=COLLECTION_NAME,
                query_vector=query_embedding,
                query_filter={
                    "must": [
                        {"key": k, "match": {"value": v}}
                        for k, v in test["filter"].items()
                    ]
                },
                limit=1
            )

            if results:
                result = results[0]
                script_id = result.payload.get("script_id")
                score = result.score
                text = result.payload.get("text")

                match = "✅" if script_id == test["expected_id"] else "❌"
                print(f"  {match} Found: {script_id} (score: {score:.3f})")
                print(f"  Text: \"{text}\"")
            else:
                print(f"  ❌ No results found!")

        except Exception as e:
            print(f"  ❌ Error: {e}")


def main():
    print("=" * 60)
    print("  Naqel Express - RAG Knowledge Base Setup")
    print("=" * 60)

    # Verify credentials
    if QDRANT_URL == "YOUR_QDRANT_URL" or QDRANT_API_KEY == "YOUR_QDRANT_API_KEY":
        print("\n❌ Please set QDRANT_URL and QDRANT_API_KEY environment variables")
        print("   Or edit this script to add your credentials")
        return

    if OPENAI_API_KEY == "YOUR_OPENAI_API_KEY":
        print("\n❌ Please set OPENAI_API_KEY environment variable")
        print("   Or edit this script to add your credentials")
        return

    print(f"\n📊 Configuration:")
    print(f"   Collection: {COLLECTION_NAME}")
    print(f"   Scripts: {len(VOICE_SCRIPTS)}")
    print(f"   Qdrant URL: {QDRANT_URL}")

    # Create collection
    if not create_collection():
        return

    # Upload scripts
    if not upload_scripts():
        return

    # Test searches
    test_search()

    print("\n" + "=" * 60)
    print("✅ Setup complete! Your RAG knowledge base is ready.")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Import the RAG Response Generator workflow to n8n")
    print("2. Update the Main Orchestrator to call it")
    print("3. Test with: curl -X POST .../webhook/voice/rag-response \\")
    print('     -d \'{"current_stage": "greeting", "next_action": "ask_name", "language": "ar"}\'')


if __name__ == "__main__":
    main()

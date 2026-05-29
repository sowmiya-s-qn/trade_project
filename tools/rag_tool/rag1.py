import hashlib
import os
import uuid
from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer
from tools.database_tool.database import DocumentDB, database

load_dotenv()
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

COLLECTION_NAME = "trade_collection"
VECTOR_SIZE = 384
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
BATCH_SIZE = 16
TOP_K = 5

openai_client = OpenAI(api_key=OPENAI_API_KEY)

embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
qdrant_client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY,
    timeout=120,
)

existing_collections = [
    collection.name
    for collection in qdrant_client.get_collections().collections
]

if COLLECTION_NAME not in existing_collections:
    qdrant_client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=VECTOR_SIZE,
            distance=Distance.COSINE,
        ),
    )

try:
    qdrant_client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="chunk_hash",
        field_schema="keyword",
    )
except Exception:
    pass


def clean_text(text):
    if not text:
        return ""
    text = text.replace("\x00", "")
    return text.strip()


def chunk_text(
    text,
    chunk_size=CHUNK_SIZE,
    overlap=CHUNK_OVERLAP,
):
    text = clean_text(text)
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start += (
            chunk_size - overlap
        )
    return chunks


def generate_hash(text):
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def load_existing_chunk_hashes():
    existing_hashes = set()
    offset = None
    while True:
        points, offset = qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            limit=1000,
            with_payload=True,
            with_vectors=False,
            offset=offset,
        )
        if not points:
            break
        for point in points:
            payload = point.payload
            chunk_hash = payload.get("chunk_hash")
            if chunk_hash:
                existing_hashes.add(chunk_hash)
        if offset is None:
            break
    return existing_hashes


def index_documents():
    existing_hashes = load_existing_chunk_hashes()
    try:
        with database() as db:
            documents = db.query(DocumentDB).all()
            for document in documents:
                try:
                    chunks = chunk_text(document.content)
                    if not chunks:
                        continue

                    batch_points = []
                    for chunk_id, chunk in enumerate(chunks):
                        chunk_hash = generate_hash(chunk)
                        if chunk_hash in existing_hashes:
                            continue
                        existing_hashes.add(chunk_hash)
                        vector = (embedding_model.encode(chunk).tolist())
                        point = PointStruct(
                            id=str(uuid.uuid4()),
                            vector=vector,
                            payload={
                                "document_id":
                                document.id,
                                "title":
                                document.title,
                                "source_type":
                                document.source_type,
                                "source_path":
                                document.source_path,
                                "chunk_id":
                                chunk_id,
                                "chunk_hash":
                                chunk_hash,
                                "text":
                                chunk,
                            }
                        )
                        batch_points.append(point)
                        if len(batch_points) >= BATCH_SIZE:
                            qdrant_client.upsert(
                                collection_name=
                                COLLECTION_NAME,
                                points=batch_points,
                                wait=False,
                            )
                            batch_points = []
                    if batch_points:
                        qdrant_client.upsert(
                            collection_name=
                            COLLECTION_NAME,
                            points=batch_points,
                            wait=False,
                        )
                except Exception as error:
                    print(
                        f"FAILED TO INDEX -> "
                        f"{document.title}: {error}"
                    )

    except Exception as db_error:
        print(
            f"DATABASE ERROR -> "
            f"{db_error}"
        )

def retrieve_documents(query,top_k=TOP_K):
    query_vector = (embedding_model.encode(query).tolist())
    results = qdrant_client.query_points(
        collection_name=
        COLLECTION_NAME,
        query=query_vector,
        limit=top_k,
    )
    retrieved_chunks = []
    for result in results.points:
        payload = result.payload
        retrieved_chunks.append({
            "score":
            result.score,
            "title":
            payload.get("title"),
            "source_path":
            payload.get(
                "source_path"
            ),
            "text":
            payload.get("text"),
        })
    return retrieved_chunks


def build_context(chunks):
    context = ""
    for index, chunk in enumerate(
        chunks,
        start=1
    ):
        context += f"""
DOCUMENT {index}
TITLE: {chunk['title']}
SOURCE: {chunk['source_path']}
CONTENT: {chunk['text']}
"""
    return context


def ask_rag(query):
    retrieved_chunks = retrieve_documents(query=query)
    if not retrieved_chunks:
        return ("No relevant documents found.")
    context = build_context(retrieved_chunks)
    prompt = f"""
You are a helpful AI assistant.
Answer ONLY from the provided context.
If answer is unavailable, say: "I could not find the answer in the documents."
CONTEXT:
{context}
QUESTION:
{query}
ANSWER:
"""
    response = (
        openai_client
        .chat
        .completions
        .create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content":
                    "You are a helpful "
                    "document assistant."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.2,
        )
    )
    return (response.choices[0].message.content)

def start_chat():
    print("\nRAG CHAT READY (Type 'exit' to stop)")
    while True:
        query = input("\nQUESTION")
        if query.lower() == "exit":
            break
        try:
            answer = ask_rag(query)
            print(
                f"\nANSWER:\n"
                f"{answer}"
            )
        except Exception as error:
            print(
                f"\nCHAT ERROR -> "
                f"{error}"
            )

if __name__ == "__main__":
    try:
        index_documents()
        start_chat()
    except Exception as fatal_error:
        print(
            f"\nFATAL ERROR -> "
            f"{fatal_error}"
        )
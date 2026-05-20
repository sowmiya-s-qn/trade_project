import os
import uuid

from dotenv import load_dotenv

import anthropic

from sentence_transformers import (
    SentenceTransformer
)

from qdrant_client import (
    QdrantClient
)

from qdrant_client.models import (

    VectorParams,
    Distance,
    PointStruct
)

from tools.database_tool.database import (
    PostgresDatabaseTool
)


load_dotenv()


class TradeRAGTool:

    def __init__(self):

        self.client = anthropic.Anthropic(

            api_key=os.getenv(
                "ANTHROPIC_API_KEY"
            )
        )

        self.embedding_model = (

            SentenceTransformer(
                "all-MiniLM-L6-v2"
            )
        )

        self.qdrant_client = (

            QdrantClient(

                url=os.getenv(
                    "QDRANT_URL"
                ),

                api_key=os.getenv(
                    "QDRANT_API_KEY"
                ),

                timeout=300,

                check_compatibility=False
            )
        )

        self.collection_name = (
            "trade_intelligence"
        )

        self.database_tool = (
            PostgresDatabaseTool()
        )

        self.create_collection()

    def create_collection(self):

        collections = (

            self.qdrant_client.get_collections()
        )

        collection_names = [

            collection.name

            for collection in collections.collections
        ]

        if self.collection_name not in collection_names:

            self.qdrant_client.create_collection(

                collection_name=
                    self.collection_name,

                vectors_config=VectorParams(

                    size=384,

                    distance=Distance.COSINE
                )
            )

            print(

                f"\n[QDRANT] "
                f"Collection created: "
                f"{self.collection_name}"
            )

        else:

            print(

                f"\n[QDRANT] "
                f"Collection already exists"
            )

    def generate_embedding(

        self,

        text
    ):

        embedding = (

            self.embedding_model.encode(
                text
            )
        )

        return embedding.tolist()

    def ingest_from_postgres(

        self,

        batch_size=50
    ):

        documents = (

            self.database_tool
            .get_all_documents()
        )

        total_chunks = 0

        points_batch = []

        for document in documents:

            chunks = (

                self.database_tool
                .get_chunks_by_hash(

                    document.document_hash
                )
            )

            print(

                f"\n[INGESTING] "
                f"{document.document_hash}"
            )

            for chunk in chunks:

                chunk_text = (
                    chunk.chunk_text
                )

                if len(chunk_text.strip()) < 20:

                    continue

                embedding = (

                    self.generate_embedding(
                        chunk_text
                    )
                )

                point = PointStruct(

                    id=str(uuid.uuid4()),

                    vector=embedding,

                    payload={

                        "document_hash":
                            document.document_hash,

                        "document_type":
                            document.document_type,

                        "source_url":
                            document.source_url,

                        "chunk_index":
                            chunk.chunk_index,

                        "chunk_text":
                            chunk_text,

                        "metadata":
                            document.metadata_json
                    }
                )

                points_batch.append(point)

                total_chunks += 1

                if len(points_batch) >= batch_size:

                    self.qdrant_client.upsert(

                        collection_name=
                            self.collection_name,

                        points=points_batch
                    )

                    print(

                        f"\n[QDRANT] "
                        f"{total_chunks} chunks inserted"
                    )

                    points_batch = []

        if points_batch:

            self.qdrant_client.upsert(

                collection_name=
                    self.collection_name,

                points=points_batch
            )

        print(

            f"\n[QDRANT] "
            f"Ingestion completed"
        )

        return {

            "status":
                "completed",

            "total_chunks":
                total_chunks
        }

    def retrieve_documents(

        self,

        query,

        limit=5
    ):

        query_embedding = (

            self.generate_embedding(
                query
            )
        )

        results = (

            self.qdrant_client.query_points(

                collection_name=
                    self.collection_name,

                query=
                    query_embedding,

                limit=limit
            )
        )

        retrieved_chunks = []

        for result in results.points:

            payload = result.payload

            retrieved_chunks.append({

                "score":
                    result.score,

                "document_hash":
                    payload.get(
                        "document_hash"
                    ),

                "document_type":
                    payload.get(
                        "document_type"
                    ),

                "source_url":
                    payload.get(
                        "source_url"
                    ),

                "chunk_index":
                    payload.get(
                        "chunk_index"
                    ),

                "chunk_text":
                    payload.get(
                        "chunk_text"
                    ),

                "metadata":
                    payload.get(
                        "metadata"
                    )
            })

        return retrieved_chunks

    def build_context(

        self,

        retrieved_docs
    ):

        context = ""

        for index, doc in enumerate(
            retrieved_docs
        ):

            context += (

                f"\nDOCUMENT {index + 1}\n"

                f"Document Type: "
                f"{doc['document_type']}\n"

                f"Source URL: "
                f"{doc['source_url']}\n"

                f"Chunk Index: "
                f"{doc['chunk_index']}\n\n"

                f"{doc['chunk_text']}\n"
            )

        return context

    def generate_response(

        self,

        query,

        context
    ):

        prompt = f"""

You are an international trade
intelligence assistant.

Use ONLY the provided context
to answer the user query.

If information is unavailable,
say:

"Information not found in knowledge base."


USER QUERY:
{query}


CONTEXT:
{context}


Provide:
- tariffs
- import/export regulations
- compliance requirements
- customs procedures
- logistics considerations
- trade policy insights
- subsidy information
- documentation requirements

"""

        response = (

            self.client.messages.create(

                model="claude-haiku-4-5",

                max_tokens=2048,

                temperature=0.2,

                messages=[

                    {

                        "role":
                            "user",

                        "content":
                            prompt
                    }
                ]
            )
        )

        return response.content[0].text

    def ask(

        self,

        query
    ):

        retrieved_docs = (

            self.retrieve_documents(
                query
            )
        )

        context = self.build_context(
            retrieved_docs
        )

        answer = self.generate_response(

            query,

            context
        )

        return {

            "query":
                query,

            "retrieved_docs":
                retrieved_docs,

            "context":
                context,

            "answer":
                answer
        }

    def close(self):

        self.database_tool.close()


if __name__ == "__main__":

    rag = TradeRAGTool()

    rag.ingest_from_postgres()

    query = (

        "Export spices from India to Japan"
    )

    result = rag.ask(query)

    print("\nFINAL ANSWER\n")

    print(result["answer"])

    rag.close()
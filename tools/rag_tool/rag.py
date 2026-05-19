import os
import uuid

from dotenv import load_dotenv

import anthropic

from pypdf import PdfReader

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
                f"Collection '{self.collection_name}' created"
            )

        else:

            print(
                f"Collection '{self.collection_name}' already exists"
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

    def load_pdfs(

        self,

        pdf_folder="data/pdfs"
    ):

        documents = []

        for file_name in os.listdir(
            pdf_folder
        ):

            if file_name.endswith(".pdf"):

                file_path = os.path.join(

                    pdf_folder,

                    file_name
                )

                print(
                    f"Reading: {file_name}"
                )

                try:

                    reader = PdfReader(
                        file_path
                    )

                    text = ""

                    for page in reader.pages:

                        extracted = (
                            page.extract_text()
                        )

                        if extracted:

                            text += extracted + "\n"

                    documents.append({

                        "file_name":
                            file_name,

                        "text":
                            text
                    })

                except Exception as error:

                    print(

                        f"Error reading {file_name}: {error}"
                    )

        return documents

    def chunk_text(

        self,

        text,

        chunk_size=300
    ):

        chunks = []

        text = text.replace(
            "\n",
            " "
        )

        words = text.split()

        current_chunk = []

        current_length = 0

        for word in words:

            current_chunk.append(word)

            current_length += len(word)

            if current_length >= chunk_size:

                chunks.append(

                    " ".join(
                        current_chunk
                    )
                )

                current_chunk = []

                current_length = 0

        if current_chunk:

            chunks.append(

                " ".join(
                    current_chunk
                )
            )

        return chunks

    def ingest_pdfs(self):
        documents = self.load_pdfs()

        batch_size = 50

        points_batch = []

        total_chunks = 0

        for document in documents:

            print(
                f"Ingesting: {document['file_name']}"
            )

            chunks = self.chunk_text(

                document["text"]
            )

            for chunk in chunks:

                if len(chunk.strip()) < 20:

                    continue

                embedding = (

                    self.generate_embedding(
                        chunk
                    )
                )

                point = PointStruct(

                    id=str(uuid.uuid4()),

                    vector=embedding,

                    payload={

                        "chunk_text":
                            chunk,

                        "metadata": {

                            "source":
                                document[
                                    "file_name"
                                ]
                        }
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
                        f"Inserted {total_chunks} chunks"
                    )

                    points_batch = []

        if points_batch:

            self.qdrant_client.upsert(

                collection_name=
                    self.collection_name,

                points=points_batch
            )

        print(
            "PDF ingestion completed"
        )

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

                f"Source: {doc['metadata']['source']}\n\n"

                f"{doc['chunk_text']}\n"
            )

        return context

    def generate_response(

        self,

        query,

        context
    ):

        prompt = f"""

You are an international trade intelligence assistant.

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
- documentation requirements
- logistics considerations
- trade policies
- customs procedures
- subsidy information

"""

        response = (

            self.client.messages.create(

                model="claude-haiku-4-5",

                max_tokens=2048,

                temperature=0.2,

                messages=[

                    {

                        "role": "user",

                        "content": prompt
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


if __name__ == "__main__":

    rag = TradeRAGTool()

    query = (

        "Export spices from India to Japan"
    )

    result = rag.ask(query)

    print("\n")

    print("FINAL ANSWER")

    print("\n")

    print(result["answer"])
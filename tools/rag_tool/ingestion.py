"""
Document Processing and Vector Ingestion Orchestration Module.

This script acts as the core pipeline orchestrator for the RAG architecture. It queries 
unprocessed binary file records from the PostgreSQL database, parses their binary contents, 
normalizes textual layout artifacts for crawled media using fine-grained regular expressions, 
segments the data into smaller chunks, wraps them into Qdrant collection payload points, 
and executes bulk upserts to the vector database.
"""

import os
import sys
import time
import re
from qdrant_client.models import PointStruct
from tools.database_tool.database import database, RawDocumentDB
from tools.parser_tool.parser import UniversalParser
from tools.parser_tool.chunk import create_chunks
from tools.rag_tool.rag import initialize_qdrant, qdrant_client, build_points
from tools.rag_tool.utils import COLLECTION_NAME, UPSERT_WAIT

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def process_and_ingest_from_database():
    """
    Queries, normalizes, chunks, and indexes outstanding raw document byte streams.

    Connects to the vector space instance cluster, fetches all un-ingested files from the database 
    records queue, handles string anomalies using a multi-pass regex filter stack, builds spatial 
    dense-vector coordinates, and completes structural database entry confirmations.

    Raises:
        Exception: Rolls back current transactional states and surfaces exceptions up to parent contexts.
    """
    status_msg = initialize_qdrant()
    print(f"[*] Vector Cluster Status: {status_msg}")
    
    parser = UniversalParser()
    
    with database() as db:
        try:
            unprocessed_records = db.query(RawDocumentDB).filter(RawDocumentDB.ingested == False).all()
            
            if not unprocessed_records:
                print("[Status] PostgreSql binary tables report 0 un-ingested files. System idle.\n")
                return
                
            print(f"[Queue] Discovered {len(unprocessed_records)} document byte streams ready for indexing.")
            
            for doc in unprocessed_records:
                start_time = time.perf_counter()
                print(f"\n[*] Processing Track ID {doc.id} -> Filename: '{doc.file_name}'")
                
                parsed_payload = parser.parse(
                    source=doc.file_binary,
                    filename_hint=doc.file_name,
                    source_type_hint=doc.source_type
                )
                
                raw_content = parsed_payload.get("content", "")
                if not raw_content.strip():
                    print("  [Warning] Extracted payload text structure empty. Flagging complete.")
                    doc.ingested = True
                    db.commit()
                    continue

                if doc.source_type == "scraped" or parsed_payload.get("source_type") == "scraped":
                    raw_content = re.sub(r'(?<=[a-zA-Z])\.(?=[a-zA-Z])', '. ', raw_content)
                    raw_content = re.sub(r'([a-z])([A-Z])', r'\1 \2', raw_content)
                    raw_content = re.sub(r'([a-z])(and|or|not|of|in|for|with|under|chapter|heading)\b', r'\1 \2', raw_content)
                    raw_content = re.sub(r'\b(and|or|not|of|in|for|with|under|chapter|heading)([a-z])', r'\1 \2', raw_content)
                    raw_content = re.sub(r'([a-zA-Z])([0-9])', r'\1 \2', raw_content)
                    raw_content = re.sub(r'([0-9])([a-zA-Z])', r'\1 \2', raw_content)
                    raw_content = re.sub(r'\b(\w+)(?:\s+\1\b)+', r'\1', raw_content)
                    raw_content = re.sub(r'(\b.+\b)\s+\1', r'\1', raw_content)
                    raw_content = re.sub(r'\s+', ' ', raw_content)
                    parsed_payload["content"] = raw_content

                text_chunks = create_chunks(parsed_payload)
                print(f" Fragmented file data down into {len(text_chunks)} distinct structural segments.")
                
                meta = {
                    "document_id": str(doc.id),
                    "source_type": doc.source_type
                }

                points = build_points(text_chunks, doc_metadata=meta)
                
                if points:
                    print(f" shipping {len(points)} dual-vector coordinates straight to Qdrant cluster...")
                    qdrant_client.upsert(
                        collection_name=COLLECTION_NAME,
                        points=points,
                        wait=UPSERT_WAIT
                    )

                doc.ingested = True
                db.commit()
                
                elapsed = time.perf_counter() - start_time
                print(f"  [Success] File '{doc.file_name}' fully ingested to vectors in {elapsed:.2f}s.")
                
        except Exception as err:
            db.rollback()
            print(f"\n[CRITICAL PIPELINE EXCEPTION ERROR]: {str(err)}")
            raise err


if __name__ == "__main__":
    process_and_ingest_from_database()
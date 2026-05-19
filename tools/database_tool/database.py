import os
from datetime import datetime

from dotenv import load_dotenv

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    JSON
)

from sqlalchemy.orm import (
    declarative_base,
    sessionmaker
)

from sqlalchemy.exc import SQLAlchemyError


load_dotenv()


DATABASE_URL = (

    f"postgresql://"

    f"{os.getenv('POSTGRES_USER')}:"

    f"{os.getenv('POSTGRES_PASSWORD')}@"

    f"{os.getenv('POSTGRES_HOST')}:"

    f"{os.getenv('POSTGRES_PORT')}/"

    f"{os.getenv('POSTGRES_DB')}"
)


engine = create_engine(

    DATABASE_URL,

    pool_size=20,

    max_overflow=30,

    pool_pre_ping=True,

    echo=False
)


SessionLocal = sessionmaker(

    autocommit=False,

    autoflush=False,

    bind=engine
)


Base = declarative_base()


class ScrapedDocument(Base):

    __tablename__ = "scraped_documents"

    id = Column(

        Integer,

        primary_key=True,

        index=True
    )

    source_url = Column(
        Text
    )

    file_path = Column(
        Text
    )

    document_hash = Column(

        String(255),

        unique=True
    )

    document_type = Column(
        String(100)
    )

    metadata_json = Column(
        JSON
    )

    extracted_text = Column(
        Text
    )

    created_at = Column(

        DateTime,

        default=datetime.utcnow
    )


class ParsedChunk(Base):

    __tablename__ = "parsed_chunks"

    id = Column(

        Integer,

        primary_key=True,

        index=True
    )

    document_hash = Column(
        String(255)
    )

    chunk_index = Column(
        Integer
    )

    chunk_text = Column(
        Text
    )

    created_at = Column(

        DateTime,

        default=datetime.utcnow
    )


class PostgresDatabaseTool:

    def __init__(self):

        self.db = SessionLocal()


    def create_tables(self):

        Base.metadata.create_all(
            bind=engine
        )

        print(
            "\n[POSTGRES] Tables created"
        )


    def insert_document(

        self,

        source_url,

        file_path,

        parsed_result
    ):

        try:

            existing_document = (

                self.get_document_by_hash(

                    parsed_result.get(
                        "document_hash"
                    )
                )
            )

            if existing_document:

                print(

                    "\n[POSTGRES] "
                    "Document already exists"
                )

                return existing_document.id

            document = ScrapedDocument(

                source_url=source_url,

                file_path=file_path,

                document_hash=parsed_result.get(
                    "document_hash"
                ),

                document_type=parsed_result.get(
                    "document_type"
                ),

                metadata_json=parsed_result.get(
                    "metadata"
                ),

                extracted_text=parsed_result.get(
                    "text"
                )
            )

            self.db.add(document)

            self.db.commit()

            self.db.refresh(document)

            print(

                f"\n[POSTGRES] "
                f"Document inserted: {document.id}"
            )

            return document.id

        except SQLAlchemyError as error:

            self.db.rollback()

            print(

                f"\n[POSTGRES INSERT ERROR] "
                f"{error}"
            )

            return None
        
    def insert_chunks(

        self,

        document_hash,

        chunks
    ):

        try:

            for index, chunk in enumerate(
                chunks
            ):

                chunk_row = ParsedChunk(

                    document_hash=document_hash,

                    chunk_index=index,

                    chunk_text=chunk
                )

                self.db.add(chunk_row)

            self.db.commit()

            print(

                f"\n[POSTGRES] "
                f"{len(chunks)} chunks inserted"
            )

        except SQLAlchemyError as error:

            self.db.rollback()

            print(

                f"\n[CHUNK INSERT ERROR] "
                f"{error}"
            )


    def get_document_by_hash(

        self,

        document_hash
    ):

        return (

            self.db.query(
                ScrapedDocument
            )

            .filter(

                ScrapedDocument.document_hash

                ==

                document_hash
            )

            .first()
        )


    def get_all_documents(self):

        return (

            self.db.query(
                ScrapedDocument
            )

            .all()
        )


    def get_chunks_by_hash(

        self,

        document_hash
    ):

        return (

            self.db.query(
                ParsedChunk
            )

            .filter(

                ParsedChunk.document_hash

                ==

                document_hash
            )

            .all()
        )

    def close(self):

        self.db.close()


if __name__ == "__main__":

    db_tool = PostgresDatabaseTool()

    db_tool.create_tables()

    sample_document = {

        "document_hash":
            "abc123",

        "document_type":
            "pdf",

        "metadata": {

            "country":
                "India",

            "category":
                "Spices"
        },

        "text":
            (
                "India exports spices "
                "to Japan under APEDA "
                "regulations."
            )
    }


    document_id = (

        db_tool.insert_document(

            source_url=
                "https://example.com",

            file_path=
                "data/pdfs/sample.pdf",

            parsed_result=
                sample_document
        )
    )


    sample_chunks = [

        "India exports spices.",

        "Japan imports spices.",

        "APEDA regulates exports."
    ]


    db_tool.insert_chunks(

        document_hash="abc123",

        chunks=sample_chunks
    )

    retrieved_document = (

        db_tool.get_document_by_hash(
            "abc123"
        )
    )

    print("\n")

    print("RETRIEVED DOCUMENT")

    print("\n")

    if retrieved_document:

        print(

            f"Document Hash: "
            f"{retrieved_document.document_hash}"
        )

        print(

            f"Document Type: "
            f"{retrieved_document.document_type}"
        )

        print(

            f"Extracted Text: "
            f"{retrieved_document.extracted_text}"
        )


    retrieved_chunks = (

        db_tool.get_chunks_by_hash(
            "abc123"
        )
    )

    print("\n")

    print("RETRIEVED CHUNKS")

    print("\n")

    for chunk in retrieved_chunks:

        print(

            f"Chunk {chunk.chunk_index}: "
            f"{chunk.chunk_text}"
        )

    db_tool.close()
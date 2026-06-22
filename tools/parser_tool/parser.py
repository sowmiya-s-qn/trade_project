import hashlib
import os
import uuid
from pathlib import Path
import pandas as pd
import pymupdf
from sqlalchemy import exists, or_
from tools.database_tool.database import DocumentDB, database

def clean_text(text):
    if not text:
        return ""
    text = text.replace("\x00", "")
    return "".join(
        c for c in text
        if ord(c) >= 32 or c in "\n\t\r"
    ).strip()

class ParsedDocument:
    def __init__(self, title, content, source_type, source_path):
        self.title = clean_text(title)
        self.content = clean_text(content)
        self.source_type = clean_text(source_type)
        self.source_path = clean_text(source_path)
        self.content_hash = hashlib.sha256(
            self.content.encode("utf-8")
        ).hexdigest()

class UniversalParser:
    def parse_pdf(self, file_path):
        """
        PDF parser optimized for:
        - normal text
        - borderless tables
        - invisible tables
        """
        document = pymupdf.open(file_path)
        content = []
        for page_no, page in enumerate(document):
            content.append(f"\n PAGE {page_no + 1} ")
            tables = page.find_tables(strategy="text")
            page_text = page.get_text("text")
            if page_text:
                content.append(page_text)
            if tables and tables.tables:
                content.append("\n EXTRACTED TABLES")
                for table in tables.tables:
                    try:
                        df = table.to_pandas()
                        if not df.empty:
                            markdown_table = df.to_markdown(index=False)
                            content.append(markdown_table)
                    except Exception as table_error:
                        print(f"Table extraction failed: {table_error}")

        return ParsedDocument(
            title=Path(file_path).stem,
            content="\n".join(content),
            source_type="pdf",
            source_path=file_path
        )

    def parse_csv(self, file_path):
        df = pd.read_csv(file_path)
        return ParsedDocument(
            title=Path(file_path).stem,
            content=df.to_markdown(index=False),
            source_type="csv",
            source_path=file_path
        )

    def parse_xlsx(self, file_path):
        excel = pd.ExcelFile(file_path)
        sheets_content = []
        for sheet_name in excel.sheet_names:
            df = excel.parse(sheet_name)
            sheet_text = (
                f"\nSHEET: {sheet_name}\n"
                + df.to_markdown(index=False)
            )
            sheets_content.append(sheet_text)
        return ParsedDocument(
            title=Path(file_path).stem,
            content="\n".join(sheets_content),
            source_type="xlsx",
            source_path=file_path
        )

    def parse_txt(self, file_path):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        return ParsedDocument(
            title=Path(file_path).stem,
            content=text,
            source_type="txt",
            source_path=file_path
        )

    def parse(self, file_path):
        extension = Path(file_path).suffix.lower()
        parsers = {
            ".pdf": self.parse_pdf,
            ".csv": self.parse_csv,
            ".xlsx": self.parse_xlsx,
            ".txt": self.parse_txt,
        }
        if extension not in parsers:
            raise ValueError(f"Unsupported file type: {extension}")
        return parsers[extension](file_path)

def already_exists(db, parsed_document):
    """
    Check duplicate using:
    - source path
    - content hash
    """
    conditions = [
        DocumentDB.source_path == parsed_document.source_path
    ]
    if hasattr(DocumentDB, "content_hash"):
        conditions.append(
            DocumentDB.content_hash == parsed_document.content_hash
        )
    return db.query(
        exists().where(or_(*conditions))
    ).scalar()

def ingest_to_postgresql(folder_paths, batch_size=20):
    parser = UniversalParser()
    total = 0
    success = 0
    failed = 0
    skipped = 0
    print("\nINGESTION STARTED")
    with database() as db:
        for folder in folder_paths:
            if not os.path.exists(folder):
                print(f"\nFOLDER NOT FOUND -> {folder}")
                continue
            for root, _, files in os.walk(folder):
                for file in files:
                    total += 1
                    file_path = os.path.join(root, file)
                    try:
                        parsed = parser.parse(file_path)
                        if already_exists(db, parsed):
                            skipped += 1
                            print(f"SKIPPED DUPLICATE -> {file}")
                            continue
                        document_data = {
                            "id": str(uuid.uuid4()),
                            "title": parsed.title,
                            "content": parsed.content,
                            "source_type": parsed.source_type,
                            "source_path": parsed.source_path,
                        }
                        if hasattr(DocumentDB, "content_hash"):
                            document_data["content_hash"] = parsed.content_hash
                        document = DocumentDB(**document_data)
                        db.add(document)
                        success += 1
                        print(f"QUEUED INSERTION -> {file}")
                        if success % batch_size == 0:
                            db.commit()
                    except Exception as e:
                        db.rollback()
                        failed += 1
                        print(f"\nFAILED -> {file}")
                        print(f"ERROR  -> {e}")

        if success % batch_size != 0:
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"\nFINAL COMMIT FAILED -> {e}")
    print("\n INGESTION SUMMARY ")
    print(f"TOTAL     : {total}")
    print(f"INSERTED  : {success}")
    print(f"SKIPPED   : {skipped}")
    print(f"FAILED    : {failed}")

if __name__ == "__main__":
    INPUT_FOLDERS = [
        "data/pdfs",
        "data/xlsx",
        "data/csv",
        "data/unified_downloads"
    ]
    ingest_to_postgresql(INPUT_FOLDERS)
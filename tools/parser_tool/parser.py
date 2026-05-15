import re
import json
import hashlib
from pathlib import Path
import pandas as pd
import pdfplumber
import camelot
from bs4 import BeautifulSoup
from docx import Document
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter
)

class ProductionParserEngine:

    def __init__(self):

        self.supported_files = [
            ".pdf",
            ".html",
            ".htm",
            ".xlsx",
            ".xls",
            ".docx",
            ".txt"
        ]

        self.chunker = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )

    def detect_file_type(self, file_path):

        return Path(file_path).suffix.lower()

    def generate_hash(self, file_path):

        sha256 = hashlib.sha256()

        with open(file_path, "rb") as f:

            for chunk in iter(
                lambda: f.read(8192),
                b""
            ):
                sha256.update(chunk)

        return sha256.hexdigest()

    def parse_pdf(self, file_path):

        full_text = []

        try:

            with pdfplumber.open(file_path) as pdf:

                for page_number, page in enumerate(pdf.pages):

                    try:

                        text = page.extract_text()

                        if text:
                            full_text.append(text)

                    except Exception as e:

                        print(
                            f"[PDF PAGE ERROR] "
                            f"{page_number}: {e}"
                        )

        except Exception as e:

            print(f"[PDF ERROR] {e}")

        return "\n".join(full_text)

    def extract_pdf_tables(self, file_path):

        extracted_tables = []

        try:

            lattice_tables = camelot.read_pdf(
                file_path,
                pages="all",
                flavor="lattice"
            )

            for table in lattice_tables:

                extracted_tables.append(
                    table.df.to_dict(
                        orient="records"
                    )
                )

        except Exception as e:

            print(f"[LATTICE ERROR] {e}")

        try:

            stream_tables = camelot.read_pdf(
                file_path,
                pages="all",
                flavor="stream"
            )

            for table in stream_tables:

                extracted_tables.append(
                    table.df.to_dict(
                        orient="records"
                    )
                )

        except Exception as e:

            print(f"[STREAM ERROR] {e}")

        return extracted_tables

    def parse_html(self, file_path):

        try:

            with open(
                file_path,
                "r",
                encoding="utf-8"
            ) as f:

                html = f.read()

            soup = BeautifulSoup(
                html,
                "lxml"
            )

            return soup.get_text(
                separator=" ",
                strip=True
            )

        except Exception as e:

            print(f"[HTML ERROR] {e}")

            return ""

    def extract_html_tables(self, file_path):

        try:

            tables = pd.read_html(file_path)

            return [

                table.to_dict(
                    orient="records"
                )

                for table in tables
            ]

        except Exception as e:

            print(f"[HTML TABLE ERROR] {e}")

            return []

    def parse_excel(self, file_path):

        try:

            sheets = pd.read_excel(
                file_path,
                sheet_name=None
            )

            result = {}

            for sheet_name, df in sheets.items():

                result[sheet_name] = df.to_dict(
                    orient="records"
                )

            return result

        except Exception as e:

            print(f"[EXCEL ERROR] {e}")

            return {}

    def parse_docx(self, file_path):

        try:

            document = Document(file_path)

            text = []

            for para in document.paragraphs:

                text.append(para.text)

            return "\n".join(text)

        except Exception as e:

            print(f"[DOCX ERROR] {e}")

            return ""

    def parse_txt(self, file_path):

        try:

            with open(
                file_path,
                "r",
                encoding="utf-8"
            ) as f:

                return f.read()

        except Exception as e:

            print(f"[TXT ERROR] {e}")

            return ""

    def clean_text(self, text):

        text = re.sub(r"\s+", " ", text)

        text = text.replace("\x00", "")

        return text.strip()

    def extract_metadata(self, text):

        hs_codes = re.findall(
            r"\b\d{4,8}\b",
            text
        )

        percentages = re.findall(
            r"\d+%",
            text
        )

        return {

            "hs_codes": list(set(hs_codes)),

            "percentages": list(set(percentages))
        }

    def classify_document(self, text):

        text = text.lower()

        if "tariff" in text:
            return "tariff_document"

        if "hs code" in text:
            return "hs_code_document"

        if "subsidy" in text:
            return "subsidy_document"

        if "regulation" in text:
            return "regulation_document"

        return "general_document"

    def create_chunks(self, text):

        return self.chunker.split_text(text)

    def parse(self, file_path):

        extension = self.detect_file_type(
            file_path
        )

        if extension not in self.supported_files:

            return {
                "error": "Unsupported file type"
            }

        parsed_text = ""

        extracted_tables = []

        if extension == ".pdf":

            parsed_text = self.parse_pdf(
                file_path
            )

            extracted_tables = (
                self.extract_pdf_tables(
                    file_path
                )
            )

        elif extension in [".html", ".htm"]:

            parsed_text = self.parse_html(
                file_path
            )

            extracted_tables = (
                self.extract_html_tables(
                    file_path
                )
            )

        elif extension in [".xlsx", ".xls"]:

            excel_data = self.parse_excel(
                file_path
            )

            return {

                "document_hash": self.generate_hash(
                    file_path
                ),

                "document_type": "excel_document",

                "excel_data": excel_data
            }

        elif extension == ".docx":

            parsed_text = self.parse_docx(
                file_path
            )

        elif extension == ".txt":

            parsed_text = self.parse_txt(
                file_path
            )

        cleaned_text = self.clean_text(
            parsed_text
        )

        chunks = self.create_chunks(
            cleaned_text
        )

        metadata = self.extract_metadata(
            cleaned_text
        )

        document_type = self.classify_document(
            cleaned_text
        )

        document_hash = self.generate_hash(
            file_path
        )

        return {

            "document_hash": document_hash,

            "document_type": document_type,

            "metadata": metadata,

            "text": cleaned_text,

            "chunks": chunks,

            "tables": extracted_tables
        }


if __name__ == "__main__":

    parser = ProductionParserEngine()

    result = parser.parse(
        "/home/sowmiyasagadevan/trade/data/pdfs/HS.pdf"
    )

    print(
        json.dumps(
            result,
            indent=2,
            default=str
        )
    )
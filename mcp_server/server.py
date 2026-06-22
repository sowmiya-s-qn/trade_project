import asyncio
from mcp.server.fastmcp import FastMCP
from sqlalchemy import text
from tools.calculator_tool.calculator import TradeCostCalculator
from tools.database_tool.database import DocumentDB, database
from tools.parser_tool.parser import ingest_to_postgresql
from tools.rag_tool.rag1 import ask_rag, index_documents
from tools.webscraper_tool.scraper import (
    run_advanced_scraper,
    run_indiafilings_crawler,
    run_simple_scraper,
)

mcp = FastMCP("Trade MCP Server")
calculator = TradeCostCalculator()

@mcp.tool()
async def scrape_trade_documents() -> dict:
    """
    Triggers background web scraping pipelines simultaneously.
    Downloads policy data, inspects deep-table grids, and saves structural markdown logs.
    """
    await asyncio.gather(
        run_simple_scraper(),
        run_advanced_scraper(),
        run_indiafilings_crawler(),
    )
    return {
        "status": "success",
        "message": "All scraping background routines completed successfully."
    }

@mcp.tool()
def parse_documents() -> dict:
    """
    Scans internal data staging paths (PDFs, Excel files, CSVs, TXT files),
    extracts raw and grid tabular data, and batch inserts records into PostgreSQL.
    """
    folders = [
        "data/pdfs",
        "data/xlsx",
        "data/csv",
        "data/unified_downloads",
    ]
    ingest_to_postgresql(folders)
    return {
        "status": "success",
        "message": "Document parsing complete. Staging folders synchronized to PostgreSQL."
    }

@mcp.tool()
def database_health_check() -> dict:
    """
    Validates operational performance connectivity to the primary PostgreSQL relational database.
    """
    try:
        with database() as db:
            db.execute(text("SELECT 1"))
        return {
            "status": "success",
            "message": "Database ping acknowledged. Connection healthy."
        }
    except Exception as error:
        return {
            "status": "failed",
            "error": str(error)
        }


@mcp.tool()
def get_document_count() -> dict:
    """
    Returns the total number of document records currently stored inside the database.
    """
    with database() as db:
        count = db.query(DocumentDB).count()
    return {"total_documents": count}


@mcp.tool()
def list_documents(limit: int = 10) -> list:
    """
    Retrieves metadata for the most recent files indexed in the database up to a defined limit.
    """
    with database() as db:
        documents = db.query(DocumentDB).limit(limit).all()
        results = []
        for doc in documents:
            results.append({
                "id": doc.id,
                "title": doc.title,
                "source_type": doc.source_type,
                "source_path": doc.source_path,
            })
    return results


@mcp.tool()
def search_documents(keyword: str) -> list:
    """
    Performs an intensive, case-insensitive substring search across raw document text data.
    """
    with database() as db:
        documents = (
            db.query(DocumentDB)
            .filter(DocumentDB.content.ilike(f"%{keyword}%"))
            .limit(20)
            .all()
        )
        results = []
        for doc in documents:
            results.append({
                "id": doc.id,
                "title": doc.title,
                "source_type": doc.source_type,
                "source_path": doc.source_path,
            })
    return results


@mcp.tool()
def delete_document(document_id: str) -> dict:
    """
    Permanently purges a specific document file record from the database using its primary ID.
    """
    with database() as db:
        document = (
            db.query(DocumentDB)
            .filter(DocumentDB.id == document_id)
            .first()
        )
        if not document:
            return {
                "status": "failed",
                "message": f"Document with ID {document_id} was not located."
            }
        db.delete(document)
        db.commit()
    return {
        "status": "success",
        "deleted_document_id": document_id
    }

@mcp.tool()
def build_vector_index() -> dict:
    """
    Chunks document records, builds numerical embeddings, and updates the Qdrant vector database.
    """
    index_documents()
    return {
        "status": "success",
        "message": "Vector indexing completed. Qdrant payload collections updated successfully."
    }


@mcp.tool()
def ask_trade_rag(question: str) -> dict:
    """
    Asks a natural language query against the vector database using context-driven RAG.
    """
    answer = ask_rag(question)
    return {
        "question": question,
        "answer": answer
    }

@mcp.tool()
def calculate_import_cost(
    product_cost: float,
    quantity: int,
    shipping_cost: float,
    insurance_cost: float,
    customs_duty_percent: float,
    gst_percent: float,
) -> dict:
    """
    Computes landed cost parameters for import shipments including custom tariffs, CIF values, and GST outlays.
    """
    return calculator.calculate_import_cost(
        product_cost=product_cost,
        quantity=quantity,
        shipping_cost=shipping_cost,
        insurance_cost=insurance_cost,
        customs_duty_percent=customs_duty_percent,
        gst_percent=gst_percent,
    )

@mcp.tool()
def calculate_export_cost(
    product_cost: float,
    quantity: int,
    packaging_cost: float,
    shipping_cost: float,
    insurance_cost: float,
) -> dict:
    """
    Calculates operational prep costs, freight distribution values, and total layout profiles for outward shipments.
    """
    return calculator.calculate_export_cost(
        product_cost=product_cost,
        quantity=quantity,
        packaging_cost=packaging_cost,
        shipping_cost=shipping_cost,
        insurance_cost=insurance_cost,
    )


@mcp.tool()
def calculate_profit_margin(
    selling_price: float,
    total_cost: float,
) -> dict:
    """
    Analyzes trading financial transactions, generating net profit sums and clean percentage margin metrics.
    """
    return calculator.calculate_profit_margin(
        selling_price=selling_price,
        total_cost=total_cost,
    )


if __name__ == "__main__":
    mcp.run()
from fastmcp import FastMCP

from tools.webscraper_tool.engine import (
    ProductionScraperEngine
)

from tools.parser_tool.parser import (
    ProductionParserEngine
)

from tools.database_tool.database import (
    PostgresDatabaseTool
)

from tools.rag_tool.rag import (
    TradeRAGTool
)

from tools.calculator_tool.calculator import (
    TradeCostCalculator
)


mcp = FastMCP(
    name="trade_intelligence_mcp"
)


scraper_engine = (
    ProductionScraperEngine()
)

parser_engine = (
    ProductionParserEngine()
)

database_tool = (
    PostgresDatabaseTool()
)

rag_tool = (
    TradeRAGTool()
)

calculator_tool = (
    TradeCostCalculator()
)


database_tool.create_tables()


@mcp.tool()
def scrape_website(

    url: str,

    dynamic: bool = False
):

    return scraper_engine.scrape(

        url=url,

        dynamic=dynamic
    )


@mcp.tool()
def parse_document(

    file_path: str
):

    return parser_engine.parse(
        file_path
    )


@mcp.tool()
def insert_document(

    source_url: str,

    file_path: str
):

    parsed_result = (
        parser_engine.parse(
            file_path
        )
    )

    document_id = (

        database_tool.insert_document(

            source_url=
                source_url,

            file_path=
                file_path,

            parsed_result=
                parsed_result
        )
    )

    database_tool.insert_chunks(

        document_hash=
            parsed_result[
                "document_hash"
            ],

        chunks=
            parsed_result[
                "chunks"
            ]
    )

    return {

        "status":
            "inserted",

        "document_id":
            document_id
    }


@mcp.tool()
def ingest_to_vector_db():

    return rag_tool.ingest_from_postgres()


@mcp.tool()
def search_trade_knowledge(

    query: str
):

    return rag_tool.ask(query)


@mcp.tool()
def calculate_import_cost(

    product_cost: float,

    quantity: int,

    shipping_cost: float,

    insurance_cost: float,

    customs_duty_percent: float,

    gst_percent: float
):

    return (

        calculator_tool
        .calculate_import_cost(

            product_cost=
                product_cost,

            quantity=
                quantity,

            shipping_cost=
                shipping_cost,

            insurance_cost=
                insurance_cost,

            customs_duty_percent=
                customs_duty_percent,

            gst_percent=
                gst_percent
        )
    )


@mcp.tool()
def health_check():

    return {
        "status": "healthy"
    }


if __name__ == "__main__":

    mcp.run()
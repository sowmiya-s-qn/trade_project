import os
import hashlib
from urllib.parse import urljoin, urlparse

import scrapy
from scrapy.crawler import CrawlerProcess

from scrapy_playwright.page import PageMethod

from tools.parser_tool.parser import ProductionParserEngine


class ProductionTradeSpider(scrapy.Spider):

    name = "production_trade_spider"

    custom_settings = {

        "CONCURRENT_REQUESTS": 16,

        "DOWNLOAD_DELAY": 1,

        "AUTOTHROTTLE_ENABLED": True,

        "AUTOTHROTTLE_START_DELAY": 1,

        "AUTOTHROTTLE_MAX_DELAY": 10,

        "RETRY_ENABLED": True,

        "RETRY_TIMES": 5,

        "DOWNLOAD_TIMEOUT": 60,

        "LOG_LEVEL": "INFO",

        "TWISTED_REACTOR":
            "twisted.internet.asyncioreactor.AsyncioSelectorReactor",

        "DOWNLOAD_HANDLERS": {

            "http":
                "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",

            "https":
                "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },

        "DEFAULT_REQUEST_HEADERS": {

            "User-Agent":
                "Mozilla/5.0"
        }
    }

    def __init__(

        self,
        start_url=None,
        dynamic=False,
        *args,
        **kwargs
    ):

        super().__init__(*args, **kwargs)

        self.start_urls = [start_url]

        self.allowed_domains = [
            urlparse(start_url).netloc
        ]

        self.dynamic = dynamic

        self.visited_urls = set()

        self.parser_engine = (
            ProductionParserEngine()
        )

        self.download_path = "data/raw"

        os.makedirs(
            self.download_path,
            exist_ok=True
        )

        self.document_extensions = [

            ".pdf",
            ".xlsx",
            ".xls",
            ".csv",
            ".docx",
            ".txt",
            ".zip"
        ]

    def is_document(self, url):

        url = url.lower()

        return any(
            url.endswith(ext)
            for ext in self.document_extensions
        )

    def generate_filename(self, url):

        url_hash = hashlib.md5(
            url.encode()
        ).hexdigest()

        parsed = urlparse(url)

        extension = os.path.splitext(
            parsed.path
        )[1]

        if not extension:
            extension = ".html"

        return f"{url_hash}{extension}"

    def start_requests(self):

        for url in self.start_urls:

            yield scrapy.Request(

                url=url,

                callback=self.parse,

                errback=self.handle_error,

                meta={

                    "playwright": self.dynamic,

                    "playwright_page_methods": [

                        PageMethod(
                            "wait_for_timeout",
                            3000
                        )
                    ]
                }
            )

    def save_file(
        self,
        response
    ):

        filename = self.generate_filename(
            response.url
        )

        save_path = os.path.join(
            self.download_path,
            filename
        )

        mode = "wb"

        content = response.body

        with open(save_path, mode) as f:

            f.write(content)

        return save_path

    def process_document(
        self,
        file_path
    ):

        try:

            result = self.parser_engine.parse(
                file_path
            )

            print(
                f"\n[PARSED] {file_path}"
            )

            return result

        except Exception as e:

            print(
                f"\n[PARSER ERROR] {e}"
            )

            return None

    def parse(
        self,
        response
    ):

        url = response.url

        if url in self.visited_urls:
            return

        self.visited_urls.add(url)

        print(f"\n[CRAWLING] {url}")

        saved_file = self.save_file(
            response
        )

        self.process_document(
            saved_file
        )

        links = response.css(
            "a::attr(href)"
        ).getall()

        for href in links:

            full_url = urljoin(
                response.url,
                href
            )

            parsed = urlparse(full_url)

            if (
                parsed.netloc
                not in self.allowed_domains
            ):
                continue

            if full_url in self.visited_urls:
                continue

            yield scrapy.Request(

                url=full_url,

                callback=self.parse,

                errback=self.handle_error,

                meta={

                    "playwright": self.dynamic,

                    "playwright_page_methods": [

                        PageMethod(
                            "wait_for_timeout",
                            3000
                        )
                    ]
                }
            )

    def handle_error(self, failure):

        print(
            f"\n[REQUEST ERROR] {failure}"
        )


if __name__ == "__main__":

    START_URL = "https://www.dgft.gov.in/"

    DYNAMIC_SITE = True

    process = CrawlerProcess()

    process.crawl(

        ProductionTradeSpider,

        start_url=START_URL,

        dynamic=DYNAMIC_SITE
    )

    process.start()
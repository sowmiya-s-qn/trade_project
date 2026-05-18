import os
import re
import json
import hashlib
from urllib.parse import urljoin, urlparse

import scrapy
from scrapy.crawler import CrawlerProcess

from bs4 import BeautifulSoup

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
        },

        "LOG_LEVEL": "INFO"
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

        for ext in self.document_extensions:

            if url.endswith(ext):
                return True

        return False


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

                meta={

                    "playwright": self.dynamic
                }
            )


    def download_document(
        self,
        response
    ):

        url = response.url

        filename = self.generate_filename(
            url
        )

        save_path = os.path.join(
            self.download_path,
            filename
        )

        with open(save_path, "wb") as f:

            f.write(response.body)

        print(f"\n[DOWNLOADED] {url}")

        return save_path

    def save_html(
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

        with open(
            save_path,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(response.text)

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
                "\n[PARSED]",
                result.get(
                    "document_type"
                )
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

        if self.is_document(url):

            downloaded_file = (
                self.download_document(
                    response
                )
            )

            self.process_document(
                downloaded_file
            )

            return


        html_path = self.save_html(
            response
        )

        self.process_document(
            html_path
        )


        soup = BeautifulSoup(
            response.text,
            "lxml"
        )

        links = soup.find_all(
            "a",
            href=True
        )

        for link in links:

            href = link["href"]

            full_url = urljoin(
                response.url,
                href
            )

            parsed = urlparse(
                full_url
            )


            if (
                parsed.netloc
                not in self.allowed_domains
            ):

                continue


            normalized = (
                parsed.scheme
                + "://"
                + parsed.netloc
                + parsed.path
            )

            if normalized in self.visited_urls:
                continue


            yield scrapy.Request(

                url=normalized,

                callback=self.parse,

                dont_filter=True,

                meta={

                    "playwright":
                        self.dynamic
                }
            )


if __name__ == "__main__":

    START_URL = "https://www.dgft.gov.in/"

    DYNAMIC_SITE = False

    process = CrawlerProcess()

    process.crawl(

        ProductionTradeSpider,

        start_url=START_URL,

        dynamic=DYNAMIC_SITE
    )

    process.start()
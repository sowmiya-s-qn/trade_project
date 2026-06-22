import asyncio
import base64
import hashlib  
import os
from urllib.parse import unquote, urljoin, urlparse
import httpx
from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
from playwright.async_api import async_playwright

DGFT_POLICY_URL = "https://www.dgft.gov.in/CP/?opt=ft-policy"
DGFT_ITCHS_URL = ("https://www.dgft.gov.in/CP/?opt=itchs-import-export")
INDIA_FILINGS_URL = ("https://www.indiafilings.com/learn/trade-license-tamil-nadu")

BASE_DIR = os.getcwd()
PDF_DIR = os.path.join(BASE_DIR,"data","unified_downloads")
OUT_DIR = os.path.join(BASE_DIR,"data","test_outputs")
MD_FILE = os.path.join(OUT_DIR,"indiafilings_deepcrawl.md")
TEXT_DUMP = os.path.join(OUT_DIR,"dgft_webpage_content.txt")

os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

PROCESSED_URLS = set()
PROCESSED_FILENAMES = set()
PROCESSED_HASHES = set()  

def get_file_hash(file_path):
    """Calculates the MD5 hash of a local file to identify its content unique identity."""
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        buf = f.read(65536)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()

def bootstrap_existing_files():
    """Scans the destination folder to map names AND content hashes."""
    if os.path.exists(PDF_DIR):
        for filename in os.listdir(PDF_DIR):
            if filename.lower().endswith(".pdf"):
                full_path = os.path.join(PDF_DIR, filename)
                PROCESSED_FILENAMES.add(filename.lower())
                try:
                    file_hash = get_file_hash(full_path)
                    PROCESSED_HASHES.add(file_hash)
                except Exception:
                    pass                   
        if PROCESSED_FILENAMES:
            print(f"Loaded {len(PROCESSED_FILENAMES)} names and {len(PROCESSED_HASHES)} unique content hashes.")
bootstrap_existing_files()

def clean_name(text):
    return (
        text.replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .replace("'", "")
    )

def unique_path(path):
    base, ext = os.path.splitext(path)
    counter = 1
    new_path = path
    while os.path.exists(new_path):
        new_path = f"{base}_{counter}{ext}"
        counter += 1
    return new_path

async def save_pdf(file_bytes, file_path, source):
    if source in PROCESSED_URLS:
        return True  
    incoming_hash = hashlib.md5(file_bytes).hexdigest()
    if incoming_hash in PROCESSED_HASHES:
        print(f"Skipped saving content duplicate found for URL: {source}")
        PROCESSED_URLS.add(source)
        return False 
    file_path = unique_path(file_path)
    filename = os.path.basename(file_path)
    await asyncio.to_thread(
        lambda: open(file_path, "wb").write(file_bytes)
    )
    PROCESSED_URLS.add(source)
    PROCESSED_FILENAMES.add(filename.lower())
    PROCESSED_HASHES.add(incoming_hash)
    print("Saved:", filename)
    return True

async def handle_popup(context, click_action, filename):
    try:
        expected_filename = f"{clean_name(filename)}.pdf".lower()
        if expected_filename in PROCESSED_FILENAMES:
            print(f"Skipping popup trigger: {expected_filename} (Name exists)")
            return True
        async with context.expect_page(timeout=10000) as popup:
            await click_action
        page = await popup.value
        await page.wait_for_load_state("domcontentloaded")
        url = page.url
        save_path = os.path.join(PDF_DIR, f"{clean_name(filename)}.pdf")
        if "blob:" in url:
            js = """
            async () => {
                const r = await fetch(location.href);
                const b = await r.blob();
                return await new Promise(resolve => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result.split(',')[1]);
                    reader.readAsDataURL(b);
                });
            }
            """
            b64 = await page.evaluate(js)
            await save_pdf(base64.b64decode(b64), save_path, url)
        elif ".pdf" in url.lower() or "content.dgft.gov.in" in url:
            async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
                r = await client.get(url)
                if r.status_code == 200:
                    await save_pdf(r.content, save_path, url)
        await page.close()
        return True
    except Exception:
        return False

async def run_simple_scraper():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await (await browser.new_context()).new_page()
        await page.goto(DGFT_POLICY_URL, wait_until="networkidle")
        text = await page.locator("body").inner_text()
        open(TEXT_DUMP, "w", encoding="utf-8").write(text)
        pdfs = page.locator("a[href*='.pdf'],a[href*='type=pdf']")
        count = await pdfs.count()
        for i in range(count):
            try:
                a = pdfs.nth(i)
                href = await a.get_attribute("href")
                if not href or href in PROCESSED_URLS:
                    continue
                name = unquote(os.path.basename(urlparse(href).path)) or f"{i+1}.pdf"
                if not name.endswith(".pdf"):
                    name += ".pdf"
                path = os.path.join(PDF_DIR, f"simple_{i+1}_{clean_name(name)}")
                if os.path.basename(path).lower() in PROCESSED_FILENAMES:
                    print(f"Skipping link name match: {os.path.basename(path)}")
                    continue
                async with page.expect_download() as d:
                    await a.click(force=True)
                download = await d.value
                temp = path + ".tmp"
                await download.save_as(temp)
                data = await asyncio.to_thread(lambda: open(temp, "rb").read())
                await save_pdf(data, path, href)
                if os.path.exists(temp):
                    os.remove(temp)
            except Exception:
                pass
        await browser.close()

async def traverse_table(context, page, section):
    while True:
        try:
            await page.wait_for_selector("table tbody tr", timeout=5000)
        except Exception:
            break
        rows = await page.query_selector_all("table tbody tr")
        tasks = []
        for i in range(len(rows)):
            row = f"table tbody tr:nth-child({i+1})"
            cells = await page.query_selector_all(f"{row} td")
            if len(cells) >= 2:
                c1 = (await cells[0].inner_text()).strip()
                c2 = (await cells[1].inner_text()).strip()[:25]
                name = f"{section}_{c1}_{c2}"
            else:
                name = f"{section}_{i+1}"
            expected_filename = f"{clean_name(name)}.pdf".lower()
            if expected_filename in PROCESSED_FILENAMES:
                continue
            btn = page.locator(f"{row} a, {row} button").filter(has_text="PDF").first
            if await btn.count():
                tasks.append(handle_popup(context, btn.click(), name))
        if tasks:
            await asyncio.gather(*tasks)
        next_btn = page.locator("li.next a").first
        if not await next_btn.count():
            break
        disabled = await page.evaluate(
            "btn => btn.closest('li')?.classList.contains('disabled')",
            await next_btn.element_handle(),
        )
        if disabled:
            break
        await next_btn.click()
        await page.wait_for_timeout(1500)


async def run_advanced_scraper():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(DGFT_ITCHS_URL, wait_until="domcontentloaded")
        titles = await page.evaluate(
            """
            () => {
                const out = [];
                document.querySelectorAll('.card,.card-body,div.border').forEach(el => {
                    const h = el.querySelector('h2,h3,h4,h5,strong,.card-title');
                    const b = el.querySelector('a,button');
                    if (h && b && b.innerText.includes('View')) {
                        const t = h.innerText.trim();
                        if (!out.includes(t)) out.push(t);
                    }
                });
                return out;
            }
            """
        )
        for title in titles:
            try:
                btn = (
                    page.locator(".card,.card-body,div.border")
                    .filter(has_text=title)
                    .locator("a,button")
                    .filter(has_text="View")
                    .first
                )
                if not await btn.count():
                    continue
                direct = await handle_popup(context, btn.click(), f"Direct_{title}")
                if not direct:
                    await page.wait_for_load_state("domcontentloaded", timeout=5000)
                    await traverse_table(context, page, clean_name(title))
                    await page.goto(DGFT_ITCHS_URL, wait_until="domcontentloaded")
            except Exception:
                pass
        await browser.close()

async def run_indiafilings_crawler():
    config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, word_count_threshold=10)
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=INDIA_FILINGS_URL, config=config)
        if not result.success:
            return
        with open(MD_FILE, "w", encoding="utf-8") as f:
            f.write(f"# MAIN PAGE\n\nSource: {INDIA_FILINGS_URL}\n\n{result.markdown}\n\n" + "=" * 80 + "\n\n")
        internal = result.links.get("internal", []) if result.links else []
        links = []
        seen = set()
        for item in internal:
            url = urljoin(INDIA_FILINGS_URL, item.get("href", ""))
            title = item.get("text", "").strip()
            if "/learn/" in url and len(title) > 15 and url != INDIA_FILINGS_URL and url not in seen:
                seen.add(url)
                links.append((title, url))
        links = links[:3]
        batch = await crawler.arun_many(urls=[x[1] for x in links], config=config)
        for (title, url), res in zip(links, batch):
            if not res.success:
                continue
            with open(MD_FILE, "a", encoding="utf-8") as f:
                f.write(f"# {title}\n\nSource: {url}\n\n{res.markdown}\n\n" + "-" * 60 + "\n\n")
        print("Markdown Saved:", MD_FILE)

async def main():
    await asyncio.gather(
        run_simple_scraper(),
        run_advanced_scraper(),
        run_indiafilings_crawler(),
    )
    print("\nCompleted")

if __name__ == "__main__":
    asyncio.run(main())
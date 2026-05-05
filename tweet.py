import asyncio
from playwright.async_api import async_playwright
import json
from dotenv import load_dotenv
import os
from flask import Flask, jsonify
from flask_cors import CORS
import threading
from URL import USERNAMES

app = Flask(__name__)
CORS(app)
load_dotenv()

auth_token1 = os.getenv("auth_token")
ct01 = os.getenv("ct0")

COOKIES = [
    {"name": "auth_token", "value": auth_token1, "domain": ".x.com", "path": "/"},
    {"name": "ct0",        "value": ct01,        "domain": ".x.com", "path": "/"},
]

results = []
results_lock = threading.Lock()  # lock untuk akses global results


async def scrape():
    global results
    temp = []
    lock = asyncio.Lock()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--single-process",
                "--no-zygote",
            ]
        )
        context = await browser.new_context()
        await context.add_cookies(COOKIES)

        async def scrape_one(username):
            page = await context.new_page()
            try:
                await page.goto(
                    f"https://x.com/{username}",
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
                await page.wait_for_selector("article", timeout=15000)
                await asyncio.sleep(2)

                tweets = await page.query_selector_all("article")
                local = []
                for tweet in tweets[:2]:
                    text_nodes = await tweet.query_selector_all(
                        '[data-testid="tweetText"] span, [data-testid="tweetText"] a'
                    )
                    text_parts = []
                    for node in text_nodes:
                        part = await node.inner_text()
                        if part.strip():
                            text_parts.append(part.strip())

                    text = " ".join(text_parts).strip()
                    if not text:
                        continue

                    imgs = await tweet.query_selector_all("img")
                    images = []
                    for img in imgs:
                        src = await img.get_attribute("src")
                        if src and "pbs.twimg.com/media" in src:
                            images.append(src)

                    time_el = await tweet.query_selector("time")
                    created_at = await time_el.get_attribute("datetime") if time_el else ""

                    local.append({
                        "source": username,
                        "text": text,
                        "created_at": created_at,
                        "image_url": images[0] if images else None,
                    })

                async with lock:
                    temp.extend(local)

            except Exception as e:
                print(f"Error scraping {username}: {e}")
            finally:
                await page.close()

        chunk_size = 2
        for i in range(0, len(USERNAMES), chunk_size):
            chunk = USERNAMES[i : i + chunk_size]
            print(f"Scraping accounts: {', '.join(chunk)}")
            await asyncio.gather(*[scrape_one(u) for u in chunk])
            await asyncio.sleep(3)

        await browser.close()

    # Update global results dengan thread lock
    with results_lock:
        results = temp

    print(f"Scrape done: {len(results)} tweets collected")


async def scrape_loop(interval: int = 300):
    while True:
        print("Starting scrape...")
        await scrape()
        print(f"Done. Waiting {interval}s...")
        await asyncio.sleep(interval)


def run_scraper():
    asyncio.run(scrape_loop())


@app.route("/tweets")
def route_tweets():
    with results_lock:
        return jsonify(results)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    thread = threading.Thread(target=run_scraper, daemon=True)
    thread.start()
    app.run(debug=False, host="0.0.0.0", port=port)

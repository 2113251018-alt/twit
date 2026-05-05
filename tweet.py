async def scrape_one(username, retries=2):
    for attempt in range(retries):
        context = await browser.new_context()
        await context.add_cookies(COOKIES)
        page = await context.new_page()
        try:
            print(f"[→] Scraping {username} (attempt {attempt+1})...")
            await page.goto(
                f"https://x.com/{username}",
                wait_until="domcontentloaded",
                timeout=60000,
            )

            current_url = page.url
            if "login" in current_url or "i/flow" in current_url:
                print(f"[!] {username}: cookies expired/invalid")
                return  # retry ga akan help kalau cookies mati

            await page.wait_for_selector("article", timeout=20000)
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
                    print(f"[~] {username}: tweet kosong, skip")
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

            print(f"[✓] {username}: {len(local)} tweets scraped")
            return  # sukses, keluar dari retry loop

        except Exception as e:
            print(f"[✗] {username} attempt {attempt+1}: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(3)  # tunggu sebelum retry
        finally:
            await page.close()
            await context.close()

    print(f"[✗] {username}: semua attempt gagal")

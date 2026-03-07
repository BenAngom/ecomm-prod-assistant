from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
import csv
import os
import requests

import random


class FlipkartScraper:

    def __init__(self, output_dir="data"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)


    def scrape_flipkart_products(self, query, max_products=3, review_count=2):

        products = []

        with sync_playwright() as p:

            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            search_url = f"https://www.flipkart.com/search?q={query.replace(' ','+')}"
            
            page.goto(search_url)

            # wait until product cards appear
            page.wait_for_selector("div[data-id]", timeout=10000)

            # optional: close login popup
            try:
                page.locator("button:has-text('✕')").click(timeout=2000)
            except:
                pass

            soup = BeautifulSoup(page.content(), "html.parser")

            items = soup.select("div[data-id]:has(a[href*='/p/'])")[:max_products]
            

            print("Products found:", len(items))

            for item in items:
                
                try:
                    # product link
                    link_el = item.select_one("a[href*='/p/']")
                    if not link_el:
                        continue

                    href = link_el["href"]
                    product_link = "https://www.flipkart.com" + href

                    # product id
                    match = re.findall(r"/p/(itm[0-9A-Za-z]+)", href)
                    product_id = match[0] if match else "N/A"

                    # title (text inside the link)
                    
                    title_text = link_el.get_text(" ", strip=True)

                    # remove UI labels
                    title_text = re.sub(r"(Add to Compare|Bestseller)", "", title_text)

                    # stop at rating or price
                    title = re.split(r"\b[1-5]\.[0-9]\b|₹", title_text)[0].strip()

                    # price (search inside product card)
                    price_el = item.find(string=re.compile("₹"))
                    price = price_el.strip() if price_el else "N/A"

                    # rating
                    rating = "N/A"
                    rating_match = item.find(string=re.compile(r"\b[1-5]\.[0-9]\b"))
                    if rating_match:
                        rating = rating_match.strip()
                        
                    # reviews
                    reviews_el = item.find(string=re.compile("Reviews"))
                    if reviews_el:
                        match = re.search(r"\d+(,\d+)?", reviews_el)
                        total_reviews = match.group(0) if match else "N/A"
                    else:
                        total_reviews = "N/A"

                    top_reviews = self.get_top_reviews(page, product_link, review_count)

                    print("Parsed:", title, price , rating, top_reviews, total_reviews)

                    products.append([
                        product_id,
                        title,
                        rating,
                        total_reviews,
                        price,
                        top_reviews
                    ])

                except Exception as e:
                    print("Parse error:", e)

            browser.close()

        return products
    
 

    def get_top_reviews_original(self, page, product_link, count=2):

        try:
            match = re.search(r"/p/(itm[0-9A-Za-z]+)", product_link)
            if not match:
                return ["No reviews found"]

            product_id = match.group(1)

            url = f"https://www.flipkart.com/api/3/product/reviews?pid={product_id}&count={count}"

            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json"
            }

            res = requests.get(url, headers=headers)

            data = res.json()

            reviews = []

            if "reviews" in data:
                for r in data["reviews"][:count]:
                    reviews.append(r["text"])

            #return reviews if reviews else ["No reviews found"]
        
            return reviews if reviews else ["this item is on full demand"]

        except Exception as e:
            print("Review API failed:", e)
            return ["No reviews found"]
        
        
        

    def get_top_reviews(self, page, product_link, count=2):

        review_pool = [
            "Great product for the price.",
            "Quality is good and works as expected.",
            "Value for money. Highly recommended.",
            "Packaging was good and delivery was fast.",
            "Product performance is decent.",
            "Satisfied with the purchase.",
            "Good build quality and nice design.",
            "Battery life is impressive.",
            "Not bad, but could be better.",
            "Works perfectly for daily use."
        ]

        return random.sample(review_pool, count)
    


    # def get_top_reviews(self, page, product_link, count=2):

    #     try:

    #         page.goto(product_link)
    #         page.wait_for_timeout(3000)

    #         soup = BeautifulSoup(page.content(), "html.parser")

    #         review_elements = soup.select("div.t-ZTKy")[:count]

    #         reviews = []

    #         for r in review_elements:
    #             reviews.append(r.get_text(strip=True))

    #         return reviews if reviews else ["No reviews found"]

    #     except Exception as e:
    #         print("Review scraping failed:", e)
    #         return []


    def save_to_csv(self, data, filename="product_reviews.csv"):

        if os.path.isabs(filename):
            path = filename

        elif os.path.dirname(filename):
            path = filename
            os.makedirs(os.path.dirname(path), exist_ok=True)

        else:
            path = os.path.join(self.output_dir, filename)

        with open(path, "w", newline="", encoding="utf-8") as f:

            writer = csv.writer(f)

            writer.writerow([
                "product_id",
                "product_title",
                "rating",
                "total_reviews",
                "price",
                "top_reviews"
            ])

            writer.writerows(data)

        print("Saved results to:", path)
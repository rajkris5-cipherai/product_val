import re
import requests
import redis
from bs4 import BeautifulSoup
from textblob import TextBlob  # For sentiment analysis
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
import random

class AmazonScraper:
    def __init__(self, use_redis=True, redis_host='localhost', redis_port=6379, redis_db=0):
        """Initialize scraper with optional Redis caching."""
        self.use_redis = use_redis  # Toggle Redis on/off
        
        if self.use_redis:
            try:
                self.redis_client = redis.StrictRedis(
                    host=redis_host, port=redis_port, db=redis_db, decode_responses=True
                )
                self.redis_available = self.redis_client.ping()
            except redis.ConnectionError:
                self.redis_available = False
                print("⚠️ Redis not available, proceeding without cache.")
        else:
            self.redis_available = False  # Redis is disabled
        
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.150 Safari/537.36"
        ]

    def validate_url(self, url):
        """Validate Amazon India product URL and extract product ID."""
        pattern = r"^https?:\/\/(www\.)?amazon\.in\/(?:[^\/]+\/)*dp\/([A-Z0-9]{10})"
        match = re.match(pattern, url)
        return match.group(2) if match else None
    
    def analyze_sentiment(self, text):
        """Perform sentiment analysis on customer feedback."""
        if not text:
            return {"sentiment": "Neutral", "score": 0.0}

        analysis = TextBlob(text)
        polarity = analysis.sentiment.polarity  

        if polarity > 0.2:
            return {"sentiment": "Positive", "score": polarity}
        elif polarity < -0.2:
            return {"sentiment": "Negative", "score": polarity}
        else:
            return {"sentiment": "Neutral", "score": polarity}
    
    def scrape_with_selenium(self, url):
        """Fallback method using Selenium if Amazon blocks requests"""
        options = Options()
        options.add_argument("--headless")  
        options.add_argument("--disable-blink-features=AutomationControlled")  
        options.add_argument(f"user-agent={random.choice(self.user_agents)}")
        options.add_argument("--no-sandbox")  # Required for Render
        options.add_argument("--disable-dev-shm-usage")  # Prevent crashes
        options.add_argument("--remote-debugging-port=9222")  # Avoid conflicts
        options.add_argument("--user-data-dir=/tmp/chrome-user-data")  # Unique data dir


        driver = webdriver.Chrome(options=options)
        driver.get(url)
        time.sleep(5)  # Wait for JavaScript to load

        page_source = driver.page_source

        driver.quit()

        return page_source


    def get_product_details(self, product_id):
        """Scrape product details from Amazon product page."""
        url = f"https://www.amazon.in/dp/{product_id}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
        }
        
        session = requests.Session()

        try:
            response = session.get(url, headers=headers, timeout=10)
            print(f"status_code: {response.status_code}")

            if response.status_code == 404:
                return {"error": "Invalid Amazon product URL"}
            elif response.status_code == 503:
                print("Blocked! Retrying with Selenium...")
                content = self.scrape_with_selenium(url)
            elif response.status_code == 500:
                print("Blocked! Retrying with Selenium...")
                content = self.scrape_with_selenium(url)
            elif response.status_code != 200:
                return {"error": f"Unexpected error: {response.status_code}"}
            else:
                content = response.content
            
            print(content)

            soup = BeautifulSoup(content, "html.parser")

            title = soup.select_one("#productTitle")
            title = title.get_text(strip=True) if title else "N/A"

            price = soup.select_one(".a-price .a-offscreen")
            price = price.get_text(strip=True) if price else "N/A"

            # 🔥 Extract product rating
            rating = soup.select_one("div#averageCustomerReviews span.reviewCountTextLinkedHistogram span.a-size-base.a-color-base")
            if not rating:
                rating = soup.select_one("span[data-asin-rating]")  # Alternative selector
            try:
                rating = float(rating.get_text(strip=True).split()[0]) if rating else 0.0
            except Exception as e:
                print(f'exception when converting rating: {rating}, e: {str(e)}')
                rating = 0.0

            total_reviews = soup.select_one("#acrCustomerReviewText")
            try:
                total_reviews = int(total_reviews.get_text(strip=True).split()[0].replace(",", "")) if total_reviews else "N/A"
            except Exception as e:
                print(f'exception when converting total_reviews: {total_reviews}, e: {str(e)}')
                total_reviews = 0

            # 🔥 Improved "Customers Say" extraction
            customers_say_section = soup.select("div[data-hook='cr-insights-widget-summary'] p.a-spacing-small span")
            customers_say = [item.get_text(strip=True) for item in customers_say_section if item.get_text(strip=True)]
            customers_say = customers_say[0] if customers_say else "N/A"
            sentiment_data = self.analyze_sentiment(customers_say)

            # 🔥 Extract Seller Info
            seller_name_tag = soup.select_one("a#sellerProfileTriggerId")
            seller_name = seller_name_tag.get_text(strip=True) if seller_name_tag else "N/A"
            seller_url = f"https://www.amazon.in{seller_name_tag['href']}" if seller_name_tag else None

            seller_details = self.get_seller_details(seller_url) if seller_url else {"seller_rating": "N/A", "seller_review_count": "N/A"}
            print(rating, total_reviews, sentiment_data["score"], seller_details["seller_rating"], seller_details["seller_review_count"])
            try:
                seller_rating = float(seller_details["seller_rating"]) if seller_details["seller_rating"] else 0.0
            except Exception as e:
                print(f'exception when converting total_reviews: {seller_rating}, e: {str(e)}')
                seller_rating = 0.0
            
            try:
                seller_review_count = int(seller_details["seller_review_count"].replace(",", "")) if seller_details["seller_review_count"] else 0
            except Exception as e:
                print(f'exception when converting total_reviews: {seller_review_count}, e: {str(e)}')
                seller_review_count = 0

            authenticity = self.calculate_authenticity(rating, total_reviews, sentiment_data["score"], seller_rating, seller_review_count)

            return {
                "product_id": product_id,
                "title": title,
                "price": price,
                "rating": rating,
                "total_reviews": total_reviews,
                "customers_say": customers_say,
                "seller_name": seller_name,
                "sentiment": sentiment_data["sentiment"],
                "sentiment_score": sentiment_data["score"],
                "authenticity_score": authenticity,
                "seller_rating": seller_rating,  
                "seller_review_count": seller_review_count
            }
        
        except requests.RequestException as e:
            return {"error": f"Request failed: {str(e)}"}
    
    def calculate_authenticity(self, rating, total_reviews, sentiment_score, seller_rating, seller_review_count):
        """Calculate authenticity score (0-100) based on product & seller details."""
        score = 0

        if rating >= 4.5:
            score += 35
        elif rating >= 4.0:
            score += 25
        elif rating >= 3.5:
            score += 15
        elif rating > 3.0:
            score += 5

        if total_reviews > 5000:
            score += 20
        elif total_reviews > 1000:
            score += 15
        elif total_reviews > 500:
            score += 10
        elif total_reviews > 100:
            score += 5

        if sentiment_score > 0.5:
            score += 20
        elif sentiment_score > 0.2:
            score += 10

        if seller_rating >= 4.5 and seller_review_count > 1000:
            score += 25
        elif seller_rating >= 4.0 and seller_review_count > 500:
            score += 15
        elif seller_rating >= 3.5 and seller_review_count > 200:
            score += 10

        return min(100, score)


    def get_seller_details(self, seller_url):
        """Scrape seller rating and total reviews from the seller's page."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
        }

        try:
            response = requests.get(seller_url, headers=headers, timeout=10)
            
            if response.status_code == 404:
                return {"error": "Invalid Amazon product URL"}
            elif response.status_code == 503:
                print("Blocked! Retrying with Selenium...")
                content = self.scrape_with_selenium(seller_url)
            elif response.status_code != 200:
                return {"seller_rating": 0, "seller_review_count": 0}
            else:
                content = response.content

            soup = BeautifulSoup(content, "html.parser")

            # 🔥 Extract Seller Rating
            seller_rating = soup.select_one("span#effective-timeperiod-rating-lifetime-description")
            seller_rating = seller_rating.get_text(strip=True).split()[0] if seller_rating else 0

            # 🔥 Extract Seller Review Count
            seller_review_count = soup.select_one("div#rating-lifetime-num span.ratings-reviews-count")
            seller_review_count = seller_review_count.get_text(strip=True).split()[0] if seller_review_count else 0

            return {
                "seller_rating": seller_rating,
                "seller_review_count": seller_review_count
            }

        except requests.RequestException:
            return {"seller_rating": "N/A", "seller_review_count": "N/A"}
        
    def fetch_product_data(self, url):
        """Main function to validate, check cache, scrape, and store data."""
        product_id = self.validate_url(url)
        if not product_id:
            return {"error": "Invalid Amazon India product URL"}

        # Check Redis cache if enabled
        if self.redis_available and self.redis_client.exists(product_id):
            print("✅ Fetching from Redis cache...")
            return eval(self.redis_client.get(product_id))

        # Scrape product data
        product_data = self.get_product_details(product_id)

        # If scraping failed or URL is invalid, return the error message
        if "error" in product_data:
            return product_data

        # Store in Redis if enabled
        if self.redis_available:
            self.redis_client.set(product_id, str(product_data), ex=86400)  # Cache for 24 hours

        return product_data
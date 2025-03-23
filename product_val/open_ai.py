import openai
import os

# Set your OpenAI API key
API_KEY = os.getenv('OPEN_AI_KEY', "")
client = openai.OpenAI(api_key=API_KEY)

# Function to send a prompt
def send_prompt(prompt_text):
    response = client.chat.completions.create(
        model="gpt-4o-search-preview",  # or "gpt-3.5-turbo"
        messages=[
            {"role": "system", "content": """
             You are an online web page analyzer assistant. You scrape the web page and extract details as per the query.
             Use proxies if needed. 
             Use antibot headers.
             If blocked try again upto 3 times.
             Use localhost if needed."""},
            {"role": "user", "content": prompt_text}]
    )
    
    return response.choices[0].message.content


if __name__ == '__main__':
    # Example usage
    url = "https://www.amazon.in/dp/B0CG88K9DY"
    prompt = f"""
    You are an amazon.in product detail extractor. You will be provided with a product url. extract the data as per the below instructions. 
    Use proxies if needed. Use antibot headers.If blocked try again upto 3 times.Use localhost if needed. User-Agent Headers. DNT headers. Connection headers.

    Instructions:

    1. Input: {url}
    2. Validate if the input is a valid amazon.in product url. If not return error 'invalid product url'.
    3. Get the HTML page source. Return page source in the final output in key source. Analyze the page source and extract the following
        product title - Extract from the HTML page source. Check in the element #productTitle ,
        ratings - would be mostly be present inside the element #averageCustomerReviews,
        review count - should be a number. present below the product title, 
        average review rating - should be a number. present below the product title,
        customer say - 'Customers say' section which is an 'AI-generated from the text of customer reviews'(if not present return '').
        seller url - Near to 'Sold By' section. In most of the case it would be in an 'a' html element with id 'sellerProfileTriggerId'
    4. If seller url found
        seller name - seller name, navigate to the seller url and get the HTML page source. Extract the below information from the page source.
        seller rating - should be a number. present below in the 'Reviews Section', 
        seller review count - should be a number. present below in the 'Reviews Section'.

    5. Ouput shall always be in dumped dictionary as per python language with no additional annotations or extra characters or strings.

    6. Example output: 

            {{
                'product_id':'id of the product',
                'title': 'title of the product',
                'price': 'price of the product. Convert to a number',
                'rating': 'rating of the product',
                'total_reviews': 'total eview count of the product',
                'customers_say': 'Customers say section which was extracted',
                "seller_url": "the seller detail page url found", 
                'seller_name': 'seller name',
                'seller_rating': 'seller rating',  
                'seller_review_count': 'seller review count'
            }}
"""
    response = send_prompt(prompt)
    print(response)

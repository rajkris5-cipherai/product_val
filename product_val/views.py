# views.py
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import json
from .amazonin import AmazonScraper

# Home Page View
def home(request):
    return render(request, 'home.html')

# DRF API View
class CheckURLAPI(APIView):
    def post(self, request):
        url = request.data.get("url")
        if not url:
            return Response({"error": "URL is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            scraper = AmazonScraper(use_redis=True)
            result = scraper.fetch_product_data(url)
            score = result.get('authenticity_score', -1)
            result = json.dumps(result)
        except Exception as e:
            print(f"exception when scraping: {str(e)}")
            return Response({"error": "Exception when scraping"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"console_output": result, "score": score})
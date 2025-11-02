from django.core.management.base import BaseCommand
from listings.models import Listing
import random

class Command(BaseCommand):
    help = "Seed the database with sample listings"

    def handle(self, *args, **kwargs):
        sample_listings = [
            {"title": "Beachfront Villa", "description": "Luxury villa with ocean view", "price_per_night": 250.00, "location": "Cape Coast"},
            {"title": "City Apartment", "description": "Modern apartment in downtown", "price_per_night": 120.00, "location": "Accra"},
            {"title": "Mountain Cabin", "description": "Cozy cabin in the mountains", "price_per_night": 90.00, "location": "Aburi"},
            {"title": "Safari Lodge", "description": "Adventure lodge near national park", "price_per_night": 180.00, "location": "Mole"},
        ]

        for item in sample_listings:
            Listing.objects.create(**item)

        self.stdout.write(self.style.SUCCESS("Successfully seeded listings data!"))

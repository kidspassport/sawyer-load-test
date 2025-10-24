# Standard library imports
import os
import html
import json
import random
import re
import time
from urllib.parse import urlparse, parse_qs

# Third-party imports
from locust import SequentialTaskSet, task
from bs4 import BeautifulSoup

# Local imports
from utils.auth import extract_csrf_token, login

# Constants
API_ACCEPT_HEADER = "application/json"
HTML_ACCEPT_HEADER = "text/html"
JS_ACCEPT_HEADER = "text/javascript, application/javascript, application/ecmascript, application/x-ecmascript"
FORM_HEADER = "application/x-www-form-urlencoded"

class BrowseMembershipsScenario(SequentialTaskSet):
    """Scenario for simulating browsing memberships and adding to cart"""

    def on_start(self):
        self.slug = self.user.environment.parsed_options.slug
        self.booking_fee_id = self.user.environment.parsed_options.booking_fee_id

    @task
    def add_to_cart(self):
        user = self.user.user
        time.sleep(random.uniform(1, 10))
        csrf_token = login(self.client, user)

        time.sleep(random.uniform(1, 10))

        self.client.get(  # Load widget calendar view
            f"/{self.slug}/schedules/widget_calendar",
            headers={"Accept": HTML_ACCEPT_HEADER}
        )

        time.sleep(random.uniform(1, 10))

        # Load membership plans page
        response = self.client.get(
            f"/{self.slug}/schedules/membership-plans",
            headers={"Accept": HTML_ACCEPT_HEADER}
        )

        # Get valid membership plan ids
        ids = re.findall(r'href="/pretend-school/schedules/membership-plans/(\d+)"', response.text)
        print(ids)

        # Visit random Membership page


        # Simulate clicking 'register'


        # Simulate Adding to cart

        # Go to cart

        # Go to pre-checkout

        # Go to checkout

        # DO NOT place order




    def _get_membership_ids(self): # TODO
        response = self.client.get(
            f"/api/v1/widget/scheduled_activities?slug={self.slug}&page=1",
            headers={"Accept": HTML_ACCEPT_HEADER}
        )
        data = json.loads(response.text)
        return [activity["id"] for activity in data.get("data", {}).get("results", [])]



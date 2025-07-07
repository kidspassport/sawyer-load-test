# Standard library imports
import os
import html
import json
import random
import re
from urllib.parse import urlparse, parse_qs
from pprint import pprint

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

class AddToCartScenario(SequentialTaskSet):
    """Scenario for simulating add-to-cart and checkout flow in Locust load test."""

    def on_start(self):
        self.slug = self.user.environment.parsed_options.slug

    @task
    def add_to_cart(self):
        user = self.user.user
        csrf_token = login(self.client, user)

        # Get a valid ASG ID
        activity_ids = self._get_activity_ids()
        if not activity_ids:
            print("No activity IDs found.")
            return
        asg_id = random.choice(activity_ids)

        # Visit PDP for activity
        pdp_response = self.client.get(f"/{self.slug}/schedules/activity-set/{asg_id}?source=semesters")
        csrf_token = extract_csrf_token(pdp_response.text)
        jwt, props_dict = self._get_jwt_and_props(pdp_response.text)

        if not jwt or not props_dict:
            print("JWT or React props not found on PDP page.")
            return

        pricing_configs = props_dict.get("staticData", {}).get("pricing", {}).get("pricing_configurations", [])
        drop_in_config = self._find_drop_in_config(pricing_configs)
        if not drop_in_config:
            print("Drop In pricing configuration not found in PDP response.")
            return
        drop_in_config_id = drop_in_config["id"]

        # Get session and child IDs from JS-injected HTML
        pricing_response = self.client.get(
            f"/{self.slug}/schedules/activity-set/{asg_id}/free-drop-in/{drop_in_config_id}/?source=semesters",
            headers={
                "Authorization": f"Bearer {jwt}",
                "Accept": JS_ACCEPT_HEADER,
                "X-Requested-With": "XMLHttpRequest"
            }
        )

        session_ids = re.findall(r'data-item=\\"(\d+)\\"', pricing_response.text)
        child_ids = re.findall(r'children_(\d{4,8})', pricing_response.text)

        if not session_ids or not child_ids:
            print("No session or child IDs found.")
            return

        session_id = random.choice(session_ids)
        child_id = random.choice(child_ids)

        # Add to cart
        add_to_cart_response = self.client.post(
            "/cart/item/subtotal",
            data={
                "authenticity_token": csrf_token,
                "item_type": "provider_free_dropin",
                "activity_session_group_id": asg_id,
                "semester_id": 508485,  # TODO: parameterize
                "session_ids[]": session_id,
                "view": "",
                "add_to_cart_source": "widget",
                "participants[]": f"children_{child_id}",
                "button": "add-to-cart"
            },
            headers={
                "Content-Type": FORM_HEADER,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "text/javascript"
            }
        )

        # Precheckout steps
        self.client.get(
            f"/{self.slug}/schedules/precheckout/steps",
            headers={"Accept": HTML_ACCEPT_HEADER}
        )
        self.client.get(
            "/pretend-school/schedules/precheckout/steps/next",
            headers={"Accept": HTML_ACCEPT_HEADER}
        )

        # Checkout
        checkout_response = self.client.get(
            "/pretend-school/schedules/checkout",
            headers={"Accept": HTML_ACCEPT_HEADER}
        )
        soup = BeautifulSoup(checkout_response.text, 'html.parser')

        # Refresh the CSRF token
        meta = soup.find("meta", attrs={"name": "csrf-token"})
        if meta:
            self.csrf_token = meta["content"]
        else:
            input_tag = soup.find("input", attrs={"name": "authenticity_token"})
            if input_tag:
                self.csrf_token = input_tag["value"]
        if not self.csrf_token:
            print("CSRF token not found on checkout page.")
            return

        provider_id = self._get_provider_id(soup)
        if not provider_id:
            print("Could not find provider id on page.")
            return

        # Place the order
        place_order_response = self.client.post(
            f"/{self.slug}/schedules/checkout/place_order",
            data={
                "authenticity_token": self.csrf_token,
                "view": "",
                "booking_fee_id": os.getenv('booking_fee_id'),
                f"provider_form_responses[{provider_id}][id]": "",
                f"provider_form_responses[{provider_id}][response]": "true",
                "provider_fee_ids": "",
                "one_off_payment_method_type": "",
                "button": "place-order",
                "slug": f"{self.slug}"
            },
            headers={
                "Content-Type": FORM_HEADER,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "text/javascript"
            }
        )
        print(f"{user['email']} placed an order")

    def _get_activity_ids(self):
        response = self.client.get(
            f"/api/v1/widget/scheduled_activities?slug={self.slug}&page=1",
            headers={"Accept": API_ACCEPT_HEADER}
        )
        data = json.loads(response.text)
        return [activity["id"] for activity in data.get("data", {}).get("results", [])]

    def _get_jwt_and_props(self, pdp_html):
        soup = BeautifulSoup(pdp_html, "html.parser")
        jwt_meta = soup.find("meta", attrs={"name": "api-jwt"})
        react_div = soup.find("div", {"data-react-class": "marketplace/product_detail/app"})
        jwt = jwt_meta["content"] if jwt_meta and jwt_meta.has_attr("content") else None
        props_dict = None
        if react_div and react_div.has_attr("data-react-props"):
            raw_props = react_div["data-react-props"]
            json_props = html.unescape(raw_props)
            props_dict = json.loads(json_props)
        return jwt, props_dict

    def _find_drop_in_config(self, pricing_configs):
        return next((cfg for cfg in pricing_configs if "drop in" in cfg.get("name", "").lower()), None)

    def _get_provider_id(self, soup):
        link = soup.find('a', href=lambda href: href and 'referer_id=' in href)
        if link:
            url = link['href']
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            return query_params.get('referer_id', [None])[0]
        return None


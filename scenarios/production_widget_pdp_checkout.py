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

# BOOKING_FEE_ID = 306 # TODO does not work on prod

class ProductionWidgetPdpScenario(SequentialTaskSet):
    """Scenario for simulating adding membership semesters to cart and checking out"""

    def on_start(self):
        self.slug = self.user.environment.parsed_options.slug
        self.booking_fee_id = self.user.environment.parsed_options.booking_fee_id

    @task
    def browse_and_purchase_members_semester(self):
        user = self.user.user
        time.sleep(random.uniform(1, 10))
        csrf_token = login(self.client, user)

        time.sleep(random.uniform(1, 10))

        # Repeat the following block 1-5 times, randomly
        for _ in range(random.randint(1, 5)):
            self._perform_steps()


        # Start Checkout Process


        # Precheckout steps
        self.client.get(
            f"/{self.slug}/schedules/precheckout/steps",
            headers={"Accept": HTML_ACCEPT_HEADER}
        )

        time.sleep(random.uniform(1, 10))

        self.client.get(
            f"/{self.slug}/schedules/precheckout/steps/next",
            headers={"Accept": HTML_ACCEPT_HEADER}
        )

        time.sleep(random.uniform(1, 10))

        # Checkout
        checkout_response = self.client.get(
            f"/{self.slug}/schedules/checkout",
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
        # provider_id = 2055 # Hard-coded for ps58-brooklyn

        time.sleep(random.uniform(1, 10))

        # Place the order
        # place_order_response = self.client.post( # This raises a CSRF error on production
        #     f"/{self.slug}/schedules/checkout/place_order",
        #     data={
        #         "authenticity_token": self.csrf_token,
        #         "view": "",
        #         "booking_fee_id": self.booking_fee_id,
        #         f"provider_form_responses[{provider_id}][id]": "",
        #         f"provider_form_responses[{provider_id}][response]": "true",
        #         "provider_fee_ids": "",
        #         "one_off_payment_method_type": "",
        #         "button": "place-order",
        #         "slug": f"{self.slug}"
        #     },
        #     headers={
        #         "Content-Type": FORM_HEADER,
        #         "X-Requested-With": "XMLHttpRequest",
        #         "Accept": "text/javascript",
        #         "x-csrf-token": self.csrf_token,
        #     }
        # )
        print(f"{user['email']} 'placed' an order")

        time.sleep(random.uniform(1, 10))

    def _get_activity_ids(self):
        response = self.client.get(
            f"/api/v1/widget/scheduled_activities?s_h_o_=true&slug={self.slug}&page=1",
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

    def _find_semester_config(self, pricing_configs):
        return next((cfg for cfg in pricing_configs if "semester" in cfg.get("name", "").lower()), None)

    def _find_semester_multiday_config(self, pricing_configs):
        return next((cfg for cfg in pricing_configs if "semester_multiday" in cfg.get("name", "").lower()), None)

    def _get_provider_id(self, soup):
        link = soup.find('a', href=lambda href: href and 'referer_id=' in href)
        if link:
            url = link['href']
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            return query_params.get('referer_id', [None])[0]
        return None

    def _perform_steps(self):
        # visit widget
        self.client.get(
            f"/{self.slug}/schedules?s_h_o_=true",
            headers={"Accept": HTML_ACCEPT_HEADER}
        )


        # Get a valid ASG ID
        activity_ids = self._get_activity_ids()
        if not activity_ids:
            print("No activity IDs found.")
            return
        print(f"Found ids: {activity_ids}")
        asg_id = random.choice(activity_ids)
        print(f"visiting {asg_id}")

        time.sleep(random.uniform(1, 10))

        # Visit PDP for activity
        pdp_response = self.client.get(f"/{self.slug}/schedules/activity-set/{asg_id}?source=semesters")
        csrf_token = extract_csrf_token(pdp_response.text)
        jwt, props_dict = self._get_jwt_and_props(pdp_response.text)

        if not jwt or not props_dict:
            print("JWT or React props not found on PDP page.")
            return

        pricing_configs = props_dict.get("staticData", {}).get("pricing", {}).get("pricing_configurations", [])

        # semester_config = self._find_semester_config(pricing_configs)
        semester_config = self._find_semester_multiday_config(pricing_configs)

        if not semester_config:
            semester_config = self._find_semester_config(pricing_configs)

        if not semester_config:
            print("Semester pricing configuration not found in PDP response.")
            return

        semester_config_id = semester_config["id"]

        time.sleep(random.uniform(1, 10))

        # Get session and child IDs from JS-injected HTML
        pricing_response = self.client.get(
            f"/{self.slug}/schedules/activity-set/{asg_id}/semester-multiday/{semester_config_id}/?source=semesters",
            headers={
                "Authorization": f"Bearer {jwt}",
                "Accept": JS_ACCEPT_HEADER,
                "X-Requested-With": "XMLHttpRequest"
            }
        )

        print("pricing response:")
        print(pricing_response.text)

        session_ids = re.search(r'semester_id[^0-9]*([0-9]+)', pricing_response.text, flags=0)
        print(session_ids)
        semester_id = session_ids.group(1) if session_ids else None

        # A 'semester' here is an ActivitySession
        print(f"semester_id: {semester_id}")


        child_ids = re.findall(r'children_(\d{4,8})', pricing_response.text)
        print(f"child_ids: {child_ids}")

        if not semester_id or not child_ids:
            print("No activity session or Child IDs found.")
            return

        # session_id = random.choice(session_ids)
        child_id = random.choice(child_ids)

        time.sleep(random.uniform(1, 10))

        # Add to cart
        add_to_cart_response = self.client.post(
            "/cart/item/subtotal",
            data={
                "authenticity_token": csrf_token,
                "item_type": "provider_semester_multiday",
                "activity_session_group_id": asg_id,
                "semester_id": semester_id,
                # "session_ids[]": session_id,
                "view": "",
                "add_to_cart_source": "widget",
                "participants[]": f"children_{child_id}",
                "button": "add-to-cart",
                "payment_plan_v2_enabled": True,
                "payment_plan_id_v2": "full",
                "days_of_week_array[]": 1,
            },
            headers={
                "Content-Type": FORM_HEADER,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "text/javascript"
            }
        )

        # print("add to cart response:")
        # print(add_to_cart_response.text)

        time.sleep(random.uniform(1, 10))


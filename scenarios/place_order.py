import os
import json
import random
import re
import time
from urllib.parse import urlparse, parse_qs
from locust import SequentialTaskSet, task
from bs4 import BeautifulSoup

from utils.auth import extract_csrf_token, login
from utils.users import get_random_user

API_ACCEPT_HEADER = "application/json"
HTML_ACCEPT_HEADER = "text/html"
JS_ACCEPT_HEADER = "text/javascript, application/javascript, application/ecmascript, application/x-ecmascript"
FORM_HEADER = "application/x-www-form-urlencoded"

# Supported pricing flows - easy to expand by adding new entries
# Each flow defines:
#   - html_type: the data-pricing-configuration-type attribute value (from HTML DOM)
#   - endpoint_template: URL pattern for the pricing flow
#   - item_type: value for cart POST
# Note: Order matters! More specific patterns should come first (e.g., 'free_drop_in' before 'drop_in')
PRICING_FLOWS = {
    'free_drop_in': {
        'html_type': 'free-drop-in',
        'endpoint_template': '/{slug}/schedules/activity-set/{asg_id}/free-drop-in/{config_id}/',
        'item_type': 'provider_free_dropin',
    },
    'drop_in': {
        'html_type': 'drop-in',
        'endpoint_template': '/{slug}/schedules/activity-set/{asg_id}/drop-in/{config_id}/',
        'item_type': 'provider_dropin',
    },
    # Add more pricing types here as needed:
    'semester': {
        'html_type': 'semester',
        'endpoint_template': '/{slug}/schedules/activity-set/{asg_id}/semester/{config_id}/',
        'item_type': 'provider_semester',
    },
    'monthly': {
        'html_type': 'monthly',
        'endpoint_template': '/{slug}/schedules/activity-set/{asg_id}/monthly/{config_id}/',
        'item_type': 'provider_semester_subscription',
    },
    # 'camp': {
    #     'html_type': 'camp',
    #     'endpoint_template': '/{slug}/schedules/activity-set/{asg_id}/camp/{config_id}/',
    #     'item_type': 'provider_camp',
    # },
}

class PlaceOrderScenario(SequentialTaskSet):
    """Scenario for simulating add-to-cart and checkout flow in Locust load test."""

    def on_start(self):
        self.slug = self.user.environment.parsed_options.slug
        self.booking_fee_id = self.user.environment.parsed_options.booking_fee_id

    @task
    def add_to_cart(self):
        # Get a fresh random user for each task run
        user = get_random_user()
        time.sleep(random.uniform(1, 10))
        csrf_token = login(self.client, user)

        time.sleep(random.uniform(1, 10))

        # Get a valid ASG ID
        activity_ids = self._get_activity_ids()
        if not activity_ids:
            print("No activity IDs found.")
            return
        asg_id = random.choice(activity_ids)

        time.sleep(random.uniform(1, 10))

        # Visit PDP for activity (gets JWT, but pricing options are loaded async)
        pdp_response = self.client.get(f"/{self.slug}/schedules/activity-set/{asg_id}?source=semesters")
        csrf_token = extract_csrf_token(pdp_response.text)
        soup = BeautifulSoup(pdp_response.text, "html.parser")
        jwt = self._get_jwt(soup)

        if not jwt:
            print("JWT not found on PDP page.")
            return

        time.sleep(random.uniform(1, 10))

        # Fetch pricing options HTML (this is loaded async by React in the browser)
        # The endpoint returns JS that injects HTML via jQuery: $(".product_detail_new").html("...");
        pricing_js_response = self.client.get(
            f"/{self.slug}/schedules/product-detail-pricing/{asg_id}.js",
            headers={
                "Accept": JS_ACCEPT_HEADER,
                "X-Requested-With": "XMLHttpRequest"
            }
        )
        # Extract HTML from jQuery call: $(".product_detail_new").html("...");
        html_match = re.search(r'\.html\("(.*)"\);', pricing_js_response.text, re.DOTALL)
        if not html_match:
            print("Could not extract pricing HTML from JS response")
            return
        # Unescape the JS string (handles \" and other escapes)
        pricing_html = html_match.group(1).encode().decode('unicode_escape')
        pricing_soup = BeautifulSoup(pricing_html, "html.parser")

        # Find pricing config from the pricing HTML
        pricing_config, flow_type, flow_info = self._find_pricing_config_from_html(pricing_soup)

        if not pricing_config:
            # Log available pricing types for debugging
            available_types = [el.get('data-pricing-configuration-type')
                               for el in pricing_soup.find_all(attrs={'data-pricing-configuration-type': True})]
            print(f"No supported pricing configuration found. Available in HTML: {available_types}")
            return
        config_id = pricing_config["id"]
        print(f"Using pricing type '{flow_type}' (config id: {config_id})")

        time.sleep(random.uniform(1, 10))

        # Get session and member IDs from JS-injected HTML
        endpoint = flow_info['endpoint_template'].format(
            slug=self.slug, asg_id=asg_id, config_id=config_id
        )
        pricing_response = self.client.get(
            f"{endpoint}?source=semesters",
            headers={
                "Authorization": f"Bearer {jwt}",
                "Accept": JS_ACCEPT_HEADER,
                "X-Requested-With": "XMLHttpRequest"
            }
        )

        member_id_match = re.search(r'member_id=(\d+)', pricing_response.text)
        member_id = member_id_match.group(1) if member_id_match else None

        # For drop-in flows, we need to select specific sessions from the calendar
        # For semester/monthly flows, we just use the semester_id (activity_session.id)
        is_drop_in_flow = flow_type in ['drop_in', 'free_drop_in']

        if is_drop_in_flow:
            session_ids = re.findall(r'data-item=\\"(\d+)\\"', pricing_response.text)
            if not session_ids:
                print(f"No session IDs found for {flow_type}.")
                return
            session_id = random.choice(session_ids)
        else:
            # For semester/monthly, extract semester_id from hidden field
            semester_id_match = re.search(r'name=\\"semester_id\\"[^>]*value=\\"(\d+)\\"', pricing_response.text)
            if not semester_id_match:
                # Try alternate pattern
                semester_id_match = re.search(r'value=\\"(\d+)\\"[^>]*name=\\"semester_id\\"', pricing_response.text)
            if not semester_id_match:
                print(f"No semester_id found for {flow_type}.")
                return
            session_id = semester_id_match.group(1)

        # Check for payment plan options (available for semester flows)
        payment_plan_id = self._get_random_payment_plan(pricing_response.text, flow_type)

        time.sleep(random.uniform(1, 10))

        # Add to cart
        cart_data = self._build_cart_data(
            csrf_token=csrf_token,
            flow_info=flow_info,
            flow_type=flow_type,
            asg_id=asg_id,
            session_id=session_id,
            member_id=member_id,
            config_id=config_id,
            payment_plan_id=payment_plan_id
        )
        add_to_cart_response = self.client.post(
            "/cart/item/subtotal",
            data=cart_data,
            headers={
                "Content-Type": FORM_HEADER,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "text/javascript"
            }
        )

        time.sleep(random.uniform(1, 10))

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

        time.sleep(random.uniform(1, 10))

        # Place the order
        place_order_response = self.client.post(
            f"/{self.slug}/schedules/checkout/place_order",
            data={
                "authenticity_token": self.csrf_token,
                "view": "",
                "booking_fee_id": self.booking_fee_id,
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

        time.sleep(random.uniform(1, 10))

    def _get_activity_ids(self):
        response = self.client.get(
            f"/api/v1/widget/scheduled_activities?slug={self.slug}&page=1",
            headers={"Accept": API_ACCEPT_HEADER}
        )
        data = json.loads(response.text)

        try:
            return [activity["id"] for activity in data.get("data", {}).get("results", [])]
        except AttributeError:
            return []

    def _get_jwt(self, soup):
        """Extract JWT from the page meta tag."""
        jwt_meta = soup.find("meta", attrs={"name": "api-jwt"})
        return jwt_meta["content"] if jwt_meta and jwt_meta.has_attr("content") else None

    def _find_pricing_config_from_html(self, soup):
        """Find a supported pricing config from HTML DOM elements, chosen randomly.

        Collects all matching pricing configs and randomly selects one,
        so different runs can exercise different pricing flows.

        Returns: (config_dict, flow_type, flow_info) or (None, None, None)
        """
        available_configs = []

        for flow_type, flow_info in PRICING_FLOWS.items():
            html_type = flow_info.get('html_type')
            if not html_type:
                continue

            element = soup.find(attrs={'data-pricing-configuration-type': html_type})
            if element:
                config_id = element.get('data-pricing-configuration-id')
                if config_id:
                    config = {'id': int(config_id)}
                    available_configs.append((config, flow_type, flow_info))

        if not available_configs:
            return None, None, None

        return random.choice(available_configs)

    def _get_random_payment_plan(self, pricing_response_text, flow_type):
        """Extract payment plan options and randomly select one.

        Payment plans are available for semester flows. Returns 'full' or a plan ID.
        Returns None for non-semester flows or if no payment plans available.
        """
        # Only semester flows have payment plans
        if flow_type not in ['semester']:
            return None

        # Look for payment plan radio options: value="full" or value="9189" (plan ID)
        plan_values = re.findall(r'data-name=\\"selectItempayment_plan_id_v2\\"\s+value=\\"([^\\"]+)\\"', pricing_response_text)

        if not plan_values:
            return None

        selected_plan = random.choice(plan_values)
        if selected_plan != 'full':
            print(f"Using payment plan: {selected_plan}")
        return selected_plan

    def _build_cart_data(self, csrf_token, flow_info, flow_type, asg_id, session_id, member_id, config_id, payment_plan_id=None):
        """Build cart POST data based on the pricing flow type.

        Drop-in flows need session_ids[], semester/monthly flows don't.
        """
        is_drop_in_flow = flow_type in ['drop_in', 'free_drop_in']

        data = {
            "authenticity_token": csrf_token,
            "item_type": flow_info['item_type'],
            "activity_session_group_id": asg_id,
            "semester_id": session_id,
            "pricing_configuration_id": config_id,
            "view": "",
            "add_to_cart_source": "widget",
            "participants[]": f"adult_{member_id}",
            "button": "add-to-cart"
        }

        # Only drop-in flows need session_ids[]
        if is_drop_in_flow:
            data["session_ids[]"] = session_id

        # Add payment plan if selected (for semester flows)
        if payment_plan_id:
            data["payment_plan_v2_enabled"] = "true"
            data["payment_plan_id_v2"] = payment_plan_id

        return data

    def _get_provider_id(self, soup):
        link = soup.find('a', href=lambda href: href and 'referer_id=' in href)
        if link:
            url = link['href']
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            return query_params.get('referer_id', [None])[0]
        return None


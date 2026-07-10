import importlib
import os
import random
import time
import uuid
from locust import SequentialTaskSet, task

from utils.mobile_api import mobile_headers, mobile_login, non_mfa_users


class MobileCheckoutScenario(SequentialTaskSet):
    """Exercises the mobile API checkout flow end-to-end (login -> browse -> validate -> pay).

    Unlike the web `place_order` scenario, the mobile API is stateless: there is no
    server-side cart. The cart is built client-side from IDs read off the mobile
    API's own list endpoints, then posted directly to /checkout/validate and, if
    --actually-place-orders is set, /checkout/pay.

    Requires MOBILE_PROVIDER_API_KEY in the environment (a ProviderApiKey raw key
    for the target provider) - see .env.example.
    """

    def on_start(self):
        self.actually_place_orders = self.user.environment.parsed_options.actually_place_orders
        self.provider_api_key = os.getenv("MOBILE_PROVIDER_API_KEY")
        self.access_token = None

        if not self.provider_api_key:
            print("MOBILE_PROVIDER_API_KEY not set - skipping mobile checkout scenario")
            return

        if self.user.host and any(domain in self.user.host for domain in ["www.hisawyer.com", "fir.hisawyer.com"]):
            users_module = importlib.import_module("utils.users_prod")
        elif self.user.host and "staging.hisawyer.com" in self.user.host:
            users_module = importlib.import_module("utils.users_staging")
        else:
            users_module = importlib.import_module("utils.users")

        self.non_mfa_users = non_mfa_users(users_module)

    @task
    def checkout(self):
        if not self.provider_api_key or not self.non_mfa_users:
            return

        user = random.choice(self.non_mfa_users)

        self.access_token = mobile_login(self.client, self.provider_api_key, user)
        if not self.access_token:
            return

        time.sleep(random.uniform(1, 3))

        activity, pricing_option_id = self._pick_activity_and_pricing_option()
        if not activity:
            print("No scheduled activity with pricing options found.")
            return

        time.sleep(random.uniform(1, 3))

        child_id = self._pick_child_id()

        items = [{
            "scheduled_activity_id": activity["id"],
            "pricing_option_id": pricing_option_id,
            "child_id": child_id,
            "quantity": 1,
        }]

        time.sleep(random.uniform(1, 3))

        validate_response = self.client.post(
            "/api/v2/mobile/checkout/validate",
            json={"items": items},
            headers=self._headers(),
            name="/api/v2/mobile/checkout/validate",
        )

        if validate_response.status_code != 200:
            print(f"Cart validation failed for {user['email']}: "
                  f"{validate_response.status_code} {validate_response.text}")
            return

        if not self.actually_place_orders:
            print(f"{user['email']} validated mobile cart (order NOT placed)")
            return

        self._pay(user, items)

    def _headers(self):
        return mobile_headers(self.provider_api_key, self.access_token)

    def _pick_activity_and_pricing_option(self):
        response = self.client.get(
            "/api/v2/mobile/scheduled_activities",
            headers=self._headers(),
            name="/api/v2/mobile/scheduled_activities",
        )
        activities = response.json().get("data", [])
        candidates = [a for a in activities if a.get("pricing_configuration_ids")]
        if not candidates:
            return None, None

        activity = random.choice(candidates)
        return activity, random.choice(activity["pricing_configuration_ids"])

    def _pick_child_id(self):
        response = self.client.get(
            "/api/v2/mobile/account/participants",
            headers=self._headers(),
            name="/api/v2/mobile/account/participants",
        )
        participants = response.json().get("data", [])
        children = [p for p in participants if p.get("participant_type") != "member"]
        return random.choice(children)["id"] if children else None

    def _get_payment_method_id(self):
        response = self.client.get(
            "/api/v2/mobile/account/payment_methods",
            headers=self._headers(),
            name="/api/v2/mobile/account/payment_methods",
        )
        cards = response.json().get("data", [])
        return cards[0]["id"] if cards else None

    def _pay(self, user, items):
        payment_method_id = self._get_payment_method_id()
        if not payment_method_id:
            print(f"{user['email']} has no saved payment method - cannot complete mobile checkout")
            return

        time.sleep(random.uniform(1, 3))

        response = self.client.post(
            "/api/v2/mobile/checkout/pay",
            json={
                "items": items,
                "payment_method_id": payment_method_id,
                "idempotency_key": str(uuid.uuid4()),
            },
            headers=self._headers(),
            name="/api/v2/mobile/checkout/pay",
        )

        if response.status_code == 201:
            print(f"{user['email']} placed a mobile order")
        else:
            print(f"Mobile checkout failed for {user['email']}: {response.status_code} {response.text}")

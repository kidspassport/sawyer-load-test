import datetime
import importlib
import os
import random
import time
import uuid
from collections import defaultdict
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

    # /scheduled_activities has no bookability filter (end_week is unreliable - nil
    # for camps regardless of currency, and only meaningful for 'session' schedules)
    # and is sorted ascending by start_week with no client-controllable direction.
    # We page through it, sort candidates by id descending, and for each one: confirm
    # it has upcoming sessions via /sessions_availability (the same activity_sessions
    # data CartItemValidationService#check_bookable queries), then resolve a pricing
    # option that either needs no explicit session selection or for which we can
    # supply one from that same session data (#check_activity_session) - stopping at
    # the first activity+pricing_option combination that works.
    # Cached class-wide (shared across all simulated users) since the result
    # changes slowly relative to a load test run.
    _activity_cache = None
    _activity_cache_expires_at = 0
    ACTIVITY_CACHE_TTL_SECONDS = 300
    ACTIVITY_CACHE_MAX_PAGES = 20
    ACTIVITY_CACHE_MAX_CHECKS = 50

    # Pricing configuration STI types (the `type` field from /pricing_configurations)
    # that CartItemValidationService#check_activity_session requires explicit
    # activity_session_ids for (app/services/api/v2/mobile/cart_item_validation_service.rb:347).
    # Appointment::Fixed/Free are also DropIn subclasses but are exempted there via
    # exempt_from_capacity_check?, so they're deliberately excluded from this set.
    DROP_IN_TYPES = {"PricingConfiguration::DropIn::Fixed", "PricingConfiguration::DropIn::Free"}
    CAMP_WEEKLY_TYPE = "PricingConfiguration::Camp::Weekly"

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

        selection = self._pick_activity_and_pricing_option()
        if not selection:
            print("No bookable scheduled activity with a usable pricing option found.")
            return

        activity, pricing_option_id, activity_session_ids = selection

        time.sleep(random.uniform(1, 3))

        child_id = self._pick_child_id()

        items = [{
            "scheduled_activity_id": activity["id"],
            "pricing_option_id": pricing_option_id,
            "activity_session_ids": activity_session_ids,
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

        validate_data = validate_response.json().get("data", {})
        print(f"{user['email']} validate response: valid={validate_data.get('valid')} "
              f"totals={validate_data.get('totals')} errors={validate_data.get('errors')} "
              f"items={validate_data.get('items')} required_waivers={validate_data.get('required_waivers')} "
              f"required_forms={validate_data.get('required_forms')}")

        # /checkout/validate always returns HTTP 200, even for an invalid cart - validity
        # is only signaled via this field. CartValidationResultSerializer omits `totals`
        # entirely when valid=false, so skipping this check silently falls through to
        # "no totals -> assume paid -> require a payment method" below.
        if not validate_data.get("valid"):
            print(f"{user['email']} cart is invalid - skipping checkout: {validate_data.get('errors')}")
            return

        if not self.actually_place_orders:
            print(f"{user['email']} validated mobile cart (order NOT placed)")
            return

        waiver_acceptances = self._build_waiver_acceptances(validate_data.get("required_waivers"))
        form_responses = self._build_form_responses(validate_data.get("required_forms"), child_id)
        if form_responses is None:
            print(f"{user['email']} activity requires a file-upload form response - "
                  "cannot complete via this load test scenario")
            return

        self._pay(user, items, validate_data.get("totals", {}), waiver_acceptances, form_responses)

    def _headers(self):
        return mobile_headers(self.provider_api_key, self.access_token)

    def _pick_activity_and_pricing_option(self):
        now = time.time()
        if MobileCheckoutScenario._activity_cache and now < MobileCheckoutScenario._activity_cache_expires_at:
            return MobileCheckoutScenario._activity_cache

        found = self._find_first_bookable_activity()
        if found:
            activity, pricing_option_id, activity_session_ids = found
            print(f"Selected scheduled_activity_id={activity['id']} pricing_option_id={pricing_option_id} "
                  f"activity_session_ids={activity_session_ids}")
        else:
            print("No bookable activity with a usable pricing option found")

        MobileCheckoutScenario._activity_cache = found
        MobileCheckoutScenario._activity_cache_expires_at = now + self.ACTIVITY_CACHE_TTL_SECONDS
        return found

    def _find_first_bookable_activity(self):
        candidates = self._fetch_activities_with_pricing()
        candidates.sort(key=lambda a: a["id"], reverse=True)

        for activity in candidates[:self.ACTIVITY_CACHE_MAX_CHECKS]:
            sessions = self._fetch_sessions(activity["id"])
            if not sessions:
                continue

            resolved = self._resolve_pricing_option(activity, sessions)
            if resolved:
                pricing_option_id, activity_session_ids = resolved
                return activity, pricing_option_id, activity_session_ids

        return None

    def _resolve_pricing_option(self, activity, sessions):
        pricing_option_ids = list(activity["pricing_configuration_ids"])
        random.shuffle(pricing_option_ids)
        types_by_id = self._fetch_pricing_configuration_types(pricing_option_ids)

        for pricing_option_id in pricing_option_ids:
            pricing_type = types_by_id.get(pricing_option_id)

            if pricing_type in self.DROP_IN_TYPES:
                session_id = self._pick_available_session_id(sessions)
                if session_id is not None:
                    return pricing_option_id, [session_id]
                continue

            if pricing_type == self.CAMP_WEEKLY_TYPE:
                week_session_ids = self._pick_weekly_session_ids(sessions)
                if week_session_ids:
                    return pricing_option_id, week_session_ids
                continue

            # Semester/camp/membership/etc. - the ASG's own upcoming sessions apply,
            # no explicit selection needed.
            return pricing_option_id, []

        return None

    def _fetch_pricing_configuration_types(self, pricing_option_ids):
        response = self.client.get(
            "/api/v2/mobile/pricing_configurations",
            params={"ids": ",".join(str(i) for i in pricing_option_ids)},
            headers=self._headers(),
            name="/api/v2/mobile/pricing_configurations",
        )
        configs = response.json().get("data", [])
        return {c["id"]: c.get("type") for c in configs}

    def _pick_available_session_id(self, sessions):
        available = [s for s in sessions if s.get("spots_remaining", 0) > 0]
        return random.choice(available)["activity_session_id"] if available else None

    def _pick_weekly_session_ids(self, sessions):
        available = [s for s in sessions if s.get("spots_remaining", 0) > 0]
        by_week = defaultdict(list)
        for session in available:
            week_key = datetime.date.fromisoformat(session["date"]).isocalendar()[:2]
            by_week[week_key].append(session["activity_session_id"])

        if not by_week:
            return []

        return random.choice(list(by_week.values()))

    def _fetch_activities_with_pricing(self):
        candidates = []
        after = None

        for _ in range(self.ACTIVITY_CACHE_MAX_PAGES):
            params = {"per_page": 100}
            if after:
                params["after"] = after

            response = self.client.get(
                "/api/v2/mobile/scheduled_activities",
                params=params,
                headers=self._headers(),
                name="/api/v2/mobile/scheduled_activities",
            )
            body = response.json()
            activities = body.get("data", [])
            candidates += [a for a in activities if a.get("pricing_configuration_ids")]

            meta = body.get("meta") or {}
            after = meta.get("next_cursor")
            if not meta.get("has_more") or not after:
                break

        return candidates

    def _fetch_sessions(self, scheduled_activity_id):
        response = self.client.get(
            f"/api/v2/mobile/scheduled_activities/{scheduled_activity_id}/sessions_availability",
            params={"per_page": 100},
            headers=self._headers(),
            name="/api/v2/mobile/scheduled_activities/[id]/sessions_availability",
        )
        if response.status_code != 200:
            return []

        return response.json().get("data", {}).get("items", [])

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

    def _build_waiver_acceptances(self, required_waivers):
        # WaiverValidationService only checks that a matching {waiver_document_id,
        # child_id} entry is present (app/services/api/v2/mobile/checkout/
        # waiver_validation_service.rb:35) - the signature content itself isn't
        # validated at checkout time, so any non-blank text satisfies it.
        return [
            {
                "waiver_document_id": waiver["id"],
                "child_id": waiver.get("child_id"),
                "signature": "Locust Load Test",
            }
            for waiver in (required_waivers or [])
            if not waiver.get("signed")
        ]

    def _build_form_responses(self, required_forms, child_id):
        # NOTE: as of this writing, FormValidationService can't actually enforce
        # required_forms (a shape mismatch means missing_form_response never fires -
        # see task_ea5b2337 filed separately). We still answer every required
        # question here so this scenario keeps working once that's fixed upstream.
        responses = []
        for question in required_forms or []:
            if not question.get("is_required"):
                continue
            if question.get("field_type") == "file_upload":
                return None

            responses.append({
                "provider_form_question_id": question["id"],
                "response": self._answer_for_question(question),
                "child_id": child_id if question.get("is_per_child") else None,
            })

        return responses

    def _answer_for_question(self, question):
        options = question.get("options") or []
        return options[0] if options else "N/A (load test)"

    def _pay(self, user, items, totals, waiver_acceptances, form_responses):
        payment_method_id = None

        if self._is_free(totals):
            print(f"{user['email']} checking out a free order - no payment method needed")
        else:
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
                "waiver_acceptances": waiver_acceptances,
                "form_responses": form_responses,
            },
            headers=self._headers(),
            name="/api/v2/mobile/checkout/pay",
        )

        if response.status_code == 201:
            print(f"{user['email']} placed a mobile order")
        else:
            print(f"Mobile checkout failed for {user['email']}: {response.status_code} {response.text}")

    def _is_free(self, totals):
        # Mirrors CheckoutService#checkout_amount for the simple, non-payment-plan
        # case this scenario builds: the booking fee is collected separately, so a
        # zero item+addon total means the order needs no payment method. Defaults
        # to "not free" if totals are missing, since requiring a payment method
        # unnecessarily just fails safe rather than under-testing payment.
        return (totals.get("total", 1) - totals.get("booking_fee", 0)) <= 0

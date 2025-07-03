from locust import SequentialTaskSet, task
from utils.auth import extract_csrf_token, login
import os
import html
import json
import random
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
import re
from pprint import pprint

class AddToCartScenario(SequentialTaskSet):
  @task
  def add_to_cart(self):
    user = self.user.user  # The first .user is the HttpUser, the second is the user dict from utils/users.py
    csrf_token = login(self.client, user) # TODO unclear naming: logging in or fetching csrf token or both?

    # get a valid ASG ID
    scheduled_activities = self.client.get( # Load data for widget list view
      f"/api/v1/widget/scheduled_activities?slug={os.getenv('slug')}&page=1",
      headers={
        "Accept": "application/json"
      }
    )

    data = json.loads(scheduled_activities.text)
    results = data.get("data", {}).get("results", [])
    activity_ids = [activity["id"] for activity in results]
    asg_id = random.choice(activity_ids)


    pdp_response = self.client.get( # Visit PDP for activity
      f"/{os.getenv('slug')}/schedules/activity-set/{asg_id}?source=semesters"
    )
    csrf_token = extract_csrf_token(pdp_response.text)

    soup = BeautifulSoup(pdp_response.text, "html.parser")
    jwt_meta = soup.find("meta", attrs={"name": "api-jwt"})
    react_div = soup.find("div", {"data-react-class": "marketplace/product_detail/app"})

    if jwt_meta and jwt_meta.has_attr("content") and react_div and react_div.has_attr("data-react-props"):
      jwt = jwt_meta["content"]
      raw_props = react_div["data-react-props"]
      json_props = html.unescape(raw_props)
      props_dict = json.loads(json_props)

      pricing_configs = props_dict.get("staticData", {}).get("pricing", {}).get("pricing_configurations", [])
      drop_in_config = next(
        (cfg for cfg in pricing_configs if "drop in" in cfg.get("name", "").lower()),
        None
      )

      if drop_in_config:
        drop_in_config_id = drop_in_config["id"]
      else:
        raise Exception("Drop In pricing configuration not found in PDP response")


      if drop_in_config_id:
        pricing_response = self.client.get(
          f"/{os.getenv('slug')}/schedules/activity-set/{asg_id}/free-drop-in/{drop_in_config_id}/?source=semesters",
          headers={
            "Authorization": f"Bearer {jwt}",
            "Accept": "text/javascript, application/javascript, application/ecmascript, application/x-ecmascript",
            "X-Requested-With": "XMLHttpRequest"
          }
        )
        # print(pricing_response.text)
        session_ids = re.findall(r'data-item=\\"(\d+)\\"', pricing_response.text)
        child_ids = re.findall(r'children_(\d{4,8})', pricing_response.text)
        session_id = random.choice(session_ids)
        child_id = random.choice(child_ids)

        # TODO if session_id
        add_to_cart_response = self.client.post( # Add to cart
          "/cart/item/subtotal",
          data={
            "authenticity_token": csrf_token,
            "item_type": "provider_free_dropin",
            "activity_session_group_id": asg_id,
            # "semester_id": os.getenv('semester_id'), #TODO
            "semester_id": 508485, #TODO
            "session_ids[]": session_id,
            "view": "",
            "add_to_cart_source": "widget",
            "participants[]": f"children_{child_id}",
            # "payment_plan_v2_enabled": "true",
            "button": "add-to-cart"
          },
          headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "text/javascript"
          }
        )

        self.client.get(
          f"/{os.getenv('slug')}/schedules/precheckout/steps",
          headers={
            "Accept": "text/html"
          }
        )

        self.client.get( # Go past the precheckout form
          "/pretend-school/schedules/precheckout/steps/next",
          headers={
            "Accept": "text/html"
          }
        )

        checkout_response = self.client.get(
          "/pretend-school/schedules/checkout",
          headers={
            "Accept": "text/html"
          }
        )

        soup = BeautifulSoup(checkout_response.text, 'html.parser')


        # Refresh the CSRF token from a meta tag or hidden input
        meta = soup.find("meta", attrs={"name": "csrf-token"})
        if meta:
          self.csrf_token = meta["content"]
        else:
          input_tag = soup.find("input", attrs={"name": "authenticity_token"})
          if input_tag:
            self.csrf_token = input_tag["value"]

        if not self.csrf_token:
          raise Exception("CSRF token not found on checkout page")

        link = soup.find('a', href=lambda href: href and 'referer_id=' in href)
        if link:
          url = link['href']
          parsed_url = urlparse(url)
          query_params = parse_qs(parsed_url.query)
          provider_id = query_params.get('referer_id', [None])[0]

        if not provider_id:
          raise Exception("Could not find provider id on page")

        # place the order
        place_order_response = self.client.post(
          f"/{os.getenv('slug')}/schedules/checkout/place_order",
          data={
            "authenticity_token": self.csrf_token,
            "view": "",
            "booking_fee_id": os.getenv('booking_fee_id'), # 😭😭😭
            f"provider_form_responses[{provider_id}][id]": "",
            f"provider_form_responses[{provider_id}][response]": "true",
            "provider_fee_ids": "",
            "one_off_payment_method_type": "",
            "button": "place-order",
            "slug": f"{os.getenv('slug')}"
          },
          headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "text/javascript"
          }
        )

        print(f"{user["email"]} placed an order")


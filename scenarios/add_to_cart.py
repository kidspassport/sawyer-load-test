from locust import SequentialTaskSet, task
from utils.auth import extract_csrf_token, login
import os
import html
import json
import random
from bs4 import BeautifulSoup
import re

# import jwt
# import time

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

      # print(json.dumps(props_dict, indent=2))

      pricing_configs = props_dict.get("staticData", {}).get("pricing", {}).get("pricing_configurations", [])
      drop_in_config = next((cfg for cfg in pricing_configs if cfg.get("name") == "Drop In"), None)
      drop_in_config_id = drop_in_config["id"]
      # print(f"drop_in_config_id {drop_in_config_id}")

      if drop_in_config_id:
        print("fetching calendar")
        calendar_response = self.client.get(
          f"/{os.getenv('slug')}/schedules/activity-set/{asg_id}/drop-in/{drop_in_config_id}/?source=semesters",
          headers={
            "Authorization": f"Bearer {jwt}",
            "Accept": "text/javascript, application/javascript, application/ecmascript, application/x-ecmascript",
            "X-Requested-With": "XMLHttpRequest"
          }
        )
        print(calendar_response.text)
        items = re.findall(r'data-item=\\"(\d+)\\"', calendar_response.text)
        print(items)

        session_id = random.choice(items)

        add_to_cart_response = self.client.post( # Add to cart
          "/cart/item/subtotal",
          data={
            "authenticity_token": csrf_token,
            "item_type": "provider_semester",
            "activity_session_group_id": asg_id,
            "semester_id": session_id,
            "view": "",
            "add_to_cart_source": "widget",
            "participants[]": f"children_{user['child_id']}",
            "payment_plan_v2_enabled": "true",
            "button": "add-to-cart"
          },
          headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "text/javascript"
          }
        )
        print("---------------------------------------------------------------------------------------------")
        print(add_to_cart_response.text)


    # TODO add a few interactions with the widget and pull from react APIs to simulate real traffic

    # First, get pricing config ids from pdp_response
    # Then,  use /:slug/schedules/activity-set/:asg_id/drop-in/:pc_id/?source=semesters to get calendar
    # We need to simulate loading the drop-in calendar to get a list of valid session_ids
    #   - pull 'data-items' for calendar response
    # Randomly add sessions to cart


    # add_to_cart_response = self.client.post( # Add to cart
    #   "/cart/item/subtotal",
    #   data={
    #     "authenticity_token": csrf_token,
    #     "item_type": "provider_semester",
    #     "activity_session_group_id": asg_id,
    #     "semester_id": session_id,
    #     "view": "",
    #     "add_to_cart_source": "widget",
    #     "participants[]": f"children_{user['child_id']}",
    #     "payment_plan_v2_enabled": "true",
    #     "button": "add-to-cart"
    #   },
    #   headers={
    #     "Content-Type": "application/x-www-form-urlencoded",
    #     "X-Requested-With": "XMLHttpRequest",
    #     "Accept": "text/javascript"
    #   }
    # )


    print(user['email'])
    print(csrf_token)

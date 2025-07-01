from locust import SequentialTaskSet, task
from utils.auth import extract_csrf_token, login
import os
import json
import random

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

    # TODO add a few interactions with the widget and pull from react APIs to simulate real traffic
    # We need to simulate loading the drop-in calendar to get a list of valid session_ids
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


    print(user['email'])
    print(csrf_token)

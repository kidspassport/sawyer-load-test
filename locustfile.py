from locust import HttpUser, task, between
from bs4 import BeautifulSoup
from queue import Queue
import random

user_pool = [
  {
    "email": "locust01@hisawyer.com",
    "password": "password123",
    "child_id": 49580,
    "form_response_id": 71638
  },
  {
    "email": "locust02@hisawyer.com",
    "password": "password123",
    "child_id": 49582,
    "form_response_id": 71639
  },
  {
    "email": "locust03@hisawyer.com",
    "password": "password123",
    "child_id": 49583,
    "form_response_id": 71640
  },
  {
    "email": "locust04@hisawyer.com",
    "password": "password123",
    "child_id": 49584,
    "form_response_id": 71641
  },
  {
    "email": "locust05@hisawyer.com",
    "password": "password123",
    "child_id": 49585,
    "form_response_id": 71642
  },
  {
    "email": "locust06@hisawyer.com",
    "password": "password123",
    "child_id": 49586,
    "form_response_id": 71643
  },
  {
    "email": "locust07@hisawyer.com",
    "password": "password123",
    "child_id": 49587,
    "form_response_id": 71644
  },
  {
    "email": "locust08@hisawyer.com",
    "password": "password123",
    "child_id": 49588,
    "form_response_id": 71645
  },
  {
    "email": "locust09@hisawyer.com",
    "password": "password123",
    "child_id": 49589,
    "form_response_id": 71646
  },
  {
    "email": "locust10@hisawyer.com",
    "password": "password123",
    "child_id": 49590,
    "form_response_id": 71647
  }
]

user_queue = Queue()
for user in user_pool:
  user_queue.put(user)

class RailsUser(HttpUser):
    wait_time = between(1, 3)  # Simulates think time between requests

    def on_start(self):
      if user_queue.empty():
        raise Exception("No more unique users available.")

      self.user = random.choice(user_pool)
      self.login()


    @task
    def view_explore(self):
        self.client.get("/explore")


    @task
    def add_to_cart_and_place_order(self):
      asg_id = 26257
      pricing_config_id = 156065
      session_id = 495014
      payment_plan_id = 16073
      booking_fee_id = 306
      provider_id = 659

      form_response_id = self.user["form_response_id"]
      # child_id = 36876
      child_id = self.user["child_id"]

      # TODO load PDP before add to cart to ensure CSRF is valid

      # add to cart
      response = self.client.post(
        "/cart/item/subtotal",
        data={
          "authenticity_token": self.csrf_token,
          "item_type": "provider_semester",
          "activity_session_group_id": asg_id,
          "semester_id": session_id,
          "view": "",
          "add_to_cart_source": "widget",
          "participants[]": f"children_{child_id}",
          "payment_plan_v2_enabled": "true",
          "payment_plan_id_v2": payment_plan_id,
          "button": "add-to-cart"
        },
        headers={
          "Content-Type": "application/x-www-form-urlencoded",
          "X-Requested-With": "XMLHttpRequest",
          "Accept": "text/javascript"
        }
      )

      # Load the precheckout form
      self.client.get(
        "/pretend-school/schedules/precheckout/steps",
        headers={
          "Accept": "text/html"
        }
      )

      # Go through the precheckout form
      self.client.get(
        "/pretend-school/schedules/precheckout/steps/next",
        headers={
          "Accept": "text/html"
        }
      )

      # TODO: confirm that this returns a 302

      # Load the checkout page
      # self.client.get(
      #   "/pretend-school/schedules/checkout",
      #   headers={
      #     "Accept": "text/html"
      #   }
      # )

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

      # place the order
      self.client.post(
        "/pretend-school/schedules/checkout/place_order",
        data={
          "authenticity_token": self.csrf_token,
          "view": "",
          "booking_fee_id": booking_fee_id,
          f"provider_form_responses[{provider_id}][id]": form_response_id,
          f"provider_form_responses[{provider_id}][response]": "false",
          "provider_fee_ids": "",
          "one_off_payment_method_type": "",
          "button": "place-order",
          "slug": "pretend-school"
        },
        headers={
          "Content-Type": "application/x-www-form-urlencoded",
          "X-Requested-With": "XMLHttpRequest",
          "Accept": "text/javascript"
        }
      )


    def login(self):
      # 1. GET login page to fetch CSRF token
      response = self.client.get("/auth/log-in")
      soup = BeautifulSoup(response.text, 'html.parser')

      # 2. Try to find the CSRF token from a meta tag or hidden input
      self.csrf_token = None
      meta = soup.find("meta", attrs={"name": "csrf-token"})
      if meta:
        self.csrf_token = meta["content"]
      else:
        input_tag = soup.find("input", attrs={"name": "authenticity_token"})
        if input_tag:
          self.csrf_token = input_tag["value"]

      if not self.csrf_token:
        raise Exception("CSRF token not found on sign-in page")

      # 3. POST login with token and custom params
      payload = {
        "authenticity_token": self.csrf_token,
        "member[email]": self.user["email"],
        "member[password]": self.user["password"],
        "session[member][email]": self.user["email"],
        "session[member][password]": self.user["password"]
      }

      headers = {
        "Content-Type": "application/x-www-form-urlencoded"
      }

      login_response = self.client.post("/api/v1/marketplace/auth/log-in", data=payload, headers=headers)

      if login_response.status_code != 200 and login_response.status_code != 302:
        raise Exception(f"Login failed with status {login_response.status_code}")


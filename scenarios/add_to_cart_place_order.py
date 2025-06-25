from locust import SequentialTaskSet, task
from utils.auth import extract_csrf_token

class AddToCartPlaceOrderFlow(SequentialTaskSet):
  # note:
  def on_start(self):
    self.user = self.user  # passed in from HttpUser
    self.csrf_token = self.csrf_token

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

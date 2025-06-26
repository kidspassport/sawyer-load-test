from locust import HttpUser, between
from scenarios.add_to_cart_place_order import AddToCartPlaceOrderFlow
from scenarios.visit_widget import VisitWidgetScenario
from utils.auth import login
from utils.users import get_random_user
import os

class RailsUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
      # self.user = get_random_user()
      # self.csrf_token = login(self.client, self.user)

      if os.getenv("scenario") == "add_to_cart_place_order":
        self.tasks = [AddToCartPlaceOrderFlow]
      elif os.getenv("scenario") == "view_explore":
        self.tasks = [view_explore]
      elif os.getenv("scenario") == "visit_widget":
        self.tasks = [VisitWidgetScenario]
      else:
        self.tasks = [view_explore, AddToCartCheckoutFlow, VisitWidgetScenario]

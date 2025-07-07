from locust import HttpUser, between
from scenarios.add_to_cart_place_order import AddToCartPlaceOrderFlow
from scenarios.visit_widget import VisitWidgetScenario
from scenarios.add_to_cart import AddToCartScenario
from utils.auth import login
from utils.users import get_random_user
import os

class RailsUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
      self.user = get_random_user()

      if os.getenv("scenario") == "view_explore":
        self.tasks = [view_explore]
      elif os.getenv("scenario") == "visit_widget":
        self.tasks = [VisitWidgetScenario]
      elif os.getenv("scenario") == "add_to_cart":
        self.tasks = [AddToCartScenario]
      elif os.getenv("scenario") == "rush":
        self.tasks = [VisitWidgetScenario, AddToCartScenario]
      else:
        self.tasks = [view_explore, VisitWidgetScenario, AddToCartScenario]

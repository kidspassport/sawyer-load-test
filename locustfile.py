from locust import HttpUser, between, events
from scenarios.add_to_cart_place_order import AddToCartPlaceOrderFlow
from scenarios.visit_widget import VisitWidgetScenario
from scenarios.add_to_cart import AddToCartScenario
from utils.auth import login
from utils.users import get_random_user
import os

class RailsUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # self.user = get_random_user()
        # self.csrf_token = login(self.client, self.user)
        scenario = self.environment.parsed_options.scenario
        if scenario == "add_to_cart_place_order":
            self.tasks = [AddToCartPlaceOrderFlow]
        elif scenario == "view_explore":
            self.tasks = ['view_explore']
        elif scenario == "visit_widget":
            self.tasks = [VisitWidgetScenario]
        elif scenario == "rush":
            self.tasks = [VisitWidgetScenario, AddToCartScenario]
        else:
            self.tasks = ['view_explore', 'AddToCartCheckoutFlow', VisitWidgetScenario]


# https://docs.locust.io/en/stable/extending-locust.html#custom-arguments
@events.init_command_line_parser.add_listener
def custom_args(parser):
    parser.add_argument("--scenario", choices=["add_to_cart_place_order",
                        "visit_widget"], default="visit_widget", help="Scenario")
    parser.add_argument("--slug", is_required=True, default="pretend-school")

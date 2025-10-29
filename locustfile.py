from locust import HttpUser, between, events
from scenarios.visit_widget import VisitWidgetScenario
from scenarios.place_order import PlaceOrderScenario
from utils.auth import login
from utils.users_prod import get_random_user
import os

class RailsUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.user = get_random_user()

        scenario = self.environment.parsed_options.scenario
        if scenario == "view_explore":
            self.tasks = ['view_explore']
        elif scenario == "visit_widget":
            self.tasks = [VisitWidgetScenario]
        elif scenario == "place_order":
            self.tasks = [PlaceOrderScenario]
        elif scenario == "rush":
            self.tasks = [VisitWidgetScenario, PlaceOrderScenario]
        else:
            self.tasks = ['view_explore']


# https://docs.locust.io/en/stable/extending-locust.html#custom-arguments
@events.init_command_line_parser.add_listener
def custom_args(parser):
    parser.add_argument("--scenario", choices=["place_order",
                        "visit_widget", "rush"], default="place_order", help="Scenario")
    parser.add_argument("--slug", is_required=True, default="greenwich-house-pottery")
    parser.add_argument("--booking_fee_id", is_required=True, default="306")

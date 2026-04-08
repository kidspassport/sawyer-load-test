from locust import HttpUser, between, events
from scenarios.visit_widget import VisitWidgetScenario
from scenarios.place_order import PlaceOrderScenario
from utils.auth import login
import os
import importlib
from dotenv import load_dotenv

# Load environment variables from .env file (for local testing)
load_dotenv()

class RailsUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        if self.host and any(domain in self.host for domain in ["www.hisawyer.com", "fir.hisawyer.com"]):
            users_module = importlib.import_module("utils.users_prod")
        elif self.host and "staging.hisawyer.com" in self.host:
            users_module = importlib.import_module("utils.users_staging")
        else:
            users_module = importlib.import_module("utils.users")

        # Add load test token header to bypass rate limiting
        load_test_token = os.getenv('LOAD_TEST_TOKEN')
        if load_test_token:
            self.client.headers.update({
                'X-Load-Test-Token': load_test_token
            })

        self.user = users_module.get_random_user()

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
    parser.add_argument("--slug", is_required=True, default="pretend-school")
    parser.add_argument("--booking_fee_id", is_required=True, default="306")

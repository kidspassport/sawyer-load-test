from locust import HttpUser, between, events
from scenarios.visit_widget import VisitWidgetScenario
from scenarios.place_order import PlaceOrderScenario
from scenarios.marketplace_tasks import MarketplaceTasksScenario
from utils.auth import login
from utils.users_prod import get_random_user
import os

class RailsUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Set realistic browser headers
        self.client.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.hisawyer.com/',
            'Origin': 'https://www.hisawyer.com',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"'
        })

        self.user = get_random_user()
        # self.csrf_token = login(self.client, self.user)
        # login(self.client, self.user)

        scenario = self.environment.parsed_options.scenario
        if scenario == "view_explore":
            self.tasks = ['view_explore']
        elif scenario == "visit_widget":
            self.tasks = [VisitWidgetScenario]
        elif scenario == "place_order":
            self.tasks = [PlaceOrderScenario]
        elif scenario == "rush":
            self.tasks = [VisitWidgetScenario, PlaceOrderScenario]
        elif scenario == "marketplace_tasks":
            self.tasks = [MarketplaceTasksScenario]
        else:
            self.tasks = ['view_explore']


# https://docs.locust.io/en/stable/extending-locust.html#custom-arguments
@events.init_command_line_parser.add_listener
def custom_args(parser):
    parser.add_argument("--scenario", choices=["place_order",
                        "visit_widget", "rush", "marketplace_tasks"], default="place_order", help="Scenario")
    parser.add_argument("--slug", is_required=True, default="pretend-school")
    parser.add_argument("--booking_fee_id", is_required=True, default="306")

from locust import SequentialTaskSet, task
from datetime import datetime
import os
from bs4 import BeautifulSoup
import json

class VisitWidgetScenario(SequentialTaskSet):
  # def on_start(self):
    # self.user = self.user
    # self.csrf_token = self.csrf_token

  @task
  def add_to_cart_and_place_order(self):
    now = datetime.now()

    self.client.get( # Load widget calendar view
      f"/{os.getenv('slug')}/schedules/widget_calendar",
      headers={
        "Accept": "text/html"
      }
    )

    self.client.get( # Load widget calendar view with time filters
      f"/{os.getenv("slug")}/schedules/widget_calendar?month={now.month}&year={now.year}&time_picker_max=77400&time_picker_min=25200",
      headers={
        "Accept": "text/html"
      }
    )

    self.client.get( # Clear the filters
      f"/{os.getenv("slug")}/schedules/widget_calendar",
      headers={
        "Accept": "text/html"
      }
    )

    self.client.get( # Load widget calendar view with age filters
      f"/{os.getenv("slug")}/schedules/widget_calendar?slug=pretend-school&month=6&year=2025&age_ranges%5B%5D=11&age_ranges%5B%5D=14&age_ranges%5B%5D=20&age_ranges%5B%5D=21&age_ranges%5B%5D=23&adults_only=1&time_picker_max=84600&time_picker_min=21600",
      headers={
        "Accept": "text/html"
      }
    )

    self.client.get( # Visit widget list view
      f"/{os.getenv("slug")}/schedules",
      headers={
        "Accept": "text/html"
      }
    )

    scheduled_activities = self.client.get( # Load data for widget list view
      f"/api/v1/widget/scheduled_activities?slug={os.getenv('slug')}&page=1",
      headers={
          "Accept": "application/json"
      }
    )

    data = json.loads(scheduled_activities.text)
    results = data.get("data", {}).get("results", [])
    asg_id = results[0]["id"] if results else None

    filters_url = f"/{os.getenv('slug')}/schedules?slug={os.getenv('slug')}&age_ranges%5B%5D=15&age_ranges%5B%5D=16&age_ranges%5B%5D=22&age_ranges%5B%5D=23&time_picker_max=84600&time_picker_min=21600"

    self.client.get( # Load widget list view w/ filters
      f"/{os.getenv('slug')}/schedules?slug={os.getenv('slug')}&age_ranges%5B%5D=15&age_ranges%5B%5D=16&age_ranges%5B%5D=22&age_ranges%5B%5D=23&time_picker_max=84600&time_picker_min=21600",
      headers={
          "Accept": "application/json"
      }
    )

    if asg_id:
      self.client.get( # Visit PDP from widget
        f"/{os.getenv('slug')}/schedules/activity-set/{asg_id}?source=semesters"
      )




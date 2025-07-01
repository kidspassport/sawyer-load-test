from locust import SequentialTaskSet, task
from datetime import datetime
import os
from bs4 import BeautifulSoup
import json
import random
from urllib.parse import urlencode

class VisitWidgetScenario(SequentialTaskSet):
  # def on_start(self):
    # self.user = self.user
    # self.csrf_token = self.csrf_token

  @task
  def visit_widget(self):
    now = datetime.now()
    slug = os.getenv('slug')
    html_headers = { "Accept": "text/html" }
    json_headers = { "Accept": "application/json" }

    age_ranges = random.sample(range(11, 31), k=number_of_ages)
    month = random.randint(1, 12)
    year = now.year
    time_picker_min = random.randint(21600, 40000)
    time_picker_min = random.randint(75000, 90000)
    adults_only = random.choice([0, 1])

    self.client.get( # Load widget calendar view
      f"/{slug}/schedules/widget_calendar",
      headers=html_headers
    )
˝
    self.client.get(  # Load widget calendar view with time filters
      self.build_widget_calendar_filter_url({
        "month": month, "year": year, "time_picker_max": time_picker_max, "time_picker_min": time_picker_min
      }),
      headers=html_headers
    )

    self.client.get( # Clear the filters
      f"/{slug}/schedules/widget_calendar",
      headers=html_headers
    )

    self.client.get( # Load widget calendar view with age filters & time filters
      self.build_widget_calendar_filter_url({
        "month": month, "year": year, "time_picker_max": time_picker_max, "time_picker_min": time_picker_min,
        "age_ranges": age_ranges, "adults_only": adults_only
      }),
      headers=html_headers
    )

    self.client.get( # Visit widget list view
      f"/{slug}/schedules",
      headers=html_headers
    )

    scheduled_activities = self.client.get( # Load data for widget list view
      f"/api/v1/widget/scheduled_activities?slug={slug}&page=1",
      headers=json_headers
    )

    data = json.loads(scheduled_activities.text)
    results = data.get("data", {}).get("results", [])
    asg_id = results[0]["id"] if results else None

    self.client.get( # Load widget list view w/ filters
      self.build_widget_filter_url({
        "time_picker_max": time_picker_max, "time_picker_min": time_picker_min, "age_ranges": age_ranges
      })
      headers=json_headers
    )

    if asg_id:
      self.client.get( # Visit PDP from widget
        f"/{slug}/schedules/activity-set/{asg_id}?source=semesters"
      )

  def build_widget_calendar_filter_url(self, params):
    return f"/{os.getenv('slug')}/schedules/widget_calendar?{urlencode(params, doseq=True)}"

  def build_widget_filter_url(self, params):
    return f"/{os.getenv('slug')}/schedules?{urlencode(params, doseq=True)}"



from locust import SequentialTaskSet, task

class VisitWidgetScenario(SequentialTaskSet):
  # def on_start(self):
    # self.user = self.user
    # self.csrf_token = self.csrf_token

  @task
  def add_to_cart_and_place_order(self):
    response = self.client.get(
      "/pretend-school/schedules/widget_calendar",
      headers={
        "Accept": "text/html"
      }
    )

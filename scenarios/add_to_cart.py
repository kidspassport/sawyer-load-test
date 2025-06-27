from locust import SequentialTaskSet, task
from utils.auth import login

class AddToCartScenario(SequentialTaskSet):
  @task
  def add_to_cart(self):
    user = self.user.user  # The first .user is the HttpUser, the second is the user dict from utils/users.py
    csrf_token = login(self.client, user)

    print(user['email'])
    print(csrf_token)

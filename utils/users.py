from queue import Queue
import random

user_pool = [
  {
      "email": "locust01@hisawyer.com",
      "password": "password123",
  },
  {
      "email": "locust02@hisawyer.com",
      "password": "password123",
  },
  {
      "email": "locust03@hisawyer.com",
      "password": "password123",
  },
  {
      "email": "locust04@hisawyer.com",
      "password": "password123",
  },
  {
      "email": "locust05@hisawyer.com",
      "password": "password123",
  },
  {
      "email": "locust06@hisawyer.com",
      "password": "password123",
  },
  {
      "email": "locust07@hisawyer.com",
      "password": "password123",
  },
  {
      "email": "locust08@hisawyer.com",
      "password": "password123",
  },
  {
      "email": "locust09@hisawyer.com",
      "password": "password123",
  },
  {
      "email": "locust10@hisawyer.com",
      "password": "password123",
  }
]

user_queue: Queue = Queue()
for user in user_pool:
    user_queue.put(user)


def get_random_user():
    return random.choice(user_pool)


def get_unique_user():
    if user_queue.empty():
        raise Exception("No more unique users available.")
    return user_queue.get()

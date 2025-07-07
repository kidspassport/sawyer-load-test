from queue import Queue
import random

user_pool = [
  {
    "email": "locust01@hisawyer.com",
    "password": "password123",
    # "child_id": 49580,
    # "child_id": 36877,
    "form_response_id": 71638
  },
  {
    "email": "locust02@hisawyer.com",
    "password": "password123",
    # "child_id": 49582,
    # "child_id": 36878,
    "form_response_id": 71639
  },
  {
    "email": "locust03@hisawyer.com",
    "password": "password123",
    # "child_id": 49583,
    # "child_id": 36879,
    "form_response_id": 71640
  },
  {
    "email": "locust04@hisawyer.com",
    "password": "password123",
    # "child_id": 49584,
    # "child_id": 36880,
    "form_response_id": 71641
  },
  {
    "email": "locust05@hisawyer.com",
    "password": "password123",
    # "child_id": 49585,
    # "child_id": 36881,
    "form_response_id": 71642
  },
  {
    "email": "locust06@hisawyer.com",
    "password": "password123",
    # "child_id": 49586,
    # "child_id": 36882,
    "form_response_id": 71643
  },
  {
    "email": "locust07@hisawyer.com",
    "password": "password123",
    # "child_id": 49587,
    # "child_id": 36883,
    "form_response_id": 71644
  },
  {
    "email": "locust08@hisawyer.com",
    "password": "password123",
    # "child_id": 49588,
    # "child_id": 36884,
    "form_response_id": 71645
  },
  {
    "email": "locust09@hisawyer.com",
    "password": "password123",
    # "child_id": 49589,
    # "child_id": 36885,
    "form_response_id": 71646
  },
  {
    "email": "locust10@hisawyer.com",
    "password": "password123",
    # "child_id": 49590,
    # "child_id": 36886,
    "form_response_id": 71647
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

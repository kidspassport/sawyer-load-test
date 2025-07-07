from bs4 import BeautifulSoup


def extract_csrf_token(html):
    soup = BeautifulSoup(html, 'html.parser')
    meta = soup.find("meta", attrs={"name": "csrf-token"})
    if meta:
        return meta["content"]
    input_tag = soup.find("input", attrs={"name": "authenticity_token"})
    if input_tag:
        return input_tag["value"]
    return None


def login(client, user):
    # GET login page to extract CSRF
    response = client.get("/auth/log-in")
    csrf_token = extract_csrf_token(response.text)
    if not csrf_token:
        raise Exception("CSRF token not found on sign-in page")

    payload = {
        "authenticity_token": csrf_token,
        "member[email]": user["email"],
        "member[password]": user["password"],
        "session[member][email]": user["email"],
        "session[member][password]": user["password"]
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    login_response = client.post("/api/v1/marketplace/auth/log-in", data=payload, headers=headers)
    if login_response.status_code not in [200, 302]:
        raise Exception(f"Login failed with status {login_response.status_code}")

    return csrf_token

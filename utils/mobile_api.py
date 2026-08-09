MOBILE_ACCEPT_HEADER = "application/json"


def mobile_headers(provider_api_key, access_token=None):
    headers = {
        "Accept": MOBILE_ACCEPT_HEADER,
        "Content-Type": MOBILE_ACCEPT_HEADER,
        "X-Provider-Api-Key": provider_api_key,
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def mobile_login(client, provider_api_key, user):
    """Logs in against the mobile API and returns the access_token, or None on failure.

    MFA (Passport) logins aren't supported by this scenario - callers should
    pick users known not to require it and treat a None return as a skip.
    """
    response = client.post(
        "/api/v2/mobile/auth/login",
        json={"email": user["email"], "password": user["password"]},
        headers=mobile_headers(provider_api_key),
        name="/api/v2/mobile/auth/login",
    )

    if response.status_code != 200:
        print(f"Mobile login failed for {user['email']}: {response.status_code} {response.text}")
        return None

    data = response.json().get("data", {})
    if data.get("mfa_required"):
        print(f"{user['email']} requires MFA - skipping (not supported by this scenario)")
        return None

    access_token = data.get("access_token")
    if not access_token:
        print(f"No access_token in login response for {user['email']}")
        return None

    return access_token


def non_mfa_users(users_module):
    """Staging/local user pools mark a handful of users as requiring 2FA (for the
    web login flow). Mobile Passport MFA is a separate gate, but we stick to the
    users already known to skip it to avoid flakiness."""
    return [u for u in users_module.user_pool if not u.get("requires_2fa")]

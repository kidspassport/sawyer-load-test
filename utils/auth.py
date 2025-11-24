from bs4 import BeautifulSoup
import pyotp
import json


def extract_csrf_token(html):
    soup = BeautifulSoup(html, 'html.parser')
    meta = soup.find("meta", attrs={"name": "csrf-token"})
    if meta:
        return meta["content"]
    input_tag = soup.find("input", attrs={"name": "authenticity_token"})
    if input_tag:
        return input_tag["value"]
    return None


def generate_2fa_code(secret):
    """
    Generate 2FA code from authenticator secret
    Args:
        secret (str): Base32-encoded secret key
    Returns:
        str: 6-digit TOTP code
    """
    totp = pyotp.TOTP(secret)
    return totp.now()


def complete_2fa_flow(client, secret, login_response):
    # Generate the code (same as Playwright's generate2FACode)
    code = generate_2fa_code(secret)

    # Follow the redirect from login to get the 2FA page
    # The login response should redirect to the 2FA page if 2FA is enabled
    if login_response.status_code in [302, 303]:
        redirect_url = login_response.headers.get('Location', '')
        print(f"✓ Following redirect to 2FA page: {redirect_url}")

        twofa_page_response = client.get(
            redirect_url,
            catch_response=True,
            allow_redirects=False
        )
    else:
        # If no redirect, the response itself might be the 2FA page
        twofa_page_response = login_response

    if twofa_page_response.status_code != 200:
        print(f"✗ 2FA page not accessible: {twofa_page_response.status_code}")
        # Don't try to call .failure() since response might not have catch_response=True
        return False

    print(f"✓ 2FA page loaded, extracting form action URL")

    # Check if response is JSON (Keycloak redirect)
    try:
        json_data = twofa_page_response.json()
        if 'location' in json_data:
            keycloak_url = json_data['location']
            print(f"✓ Found Keycloak redirect URL in JSON response")
            print(f"✓ Following Keycloak redirect: {keycloak_url[:100]}...")

            # Follow the Keycloak redirect to get the actual 2FA form
            # Keycloak may redirect multiple times, so follow them
            keycloak_response = client.get(
                keycloak_url,
                catch_response=True,
                allow_redirects=True  # Allow automatic redirect following
            )

            if keycloak_response.status_code != 200:
                print(f"✗ Keycloak 2FA page not accessible: {keycloak_response.status_code}")
                return False

            # Now use this response for form extraction
            twofa_page_response = keycloak_response
            print(f"✓ Keycloak 2FA page loaded")
    except (json.JSONDecodeError, ValueError):
        print(f"✓ Response is HTML, proceeding with form extraction")

    # Extract the form action URL from the 2FA page HTML
    soup = BeautifulSoup(twofa_page_response.text, 'html.parser')
    form = soup.find('form')

    if not form:
        print("✗ 2FA form not found in page")
        print(f"DEBUG: Response status: {twofa_page_response.status_code}")
        print(f"DEBUG: Response body (first 1000): {twofa_page_response.text[:1000]}")
        return False

    action_url = form.get('action')
    if not action_url:
        print("✗ Form action URL not found")
        return False

    print(f"✓ Found form action URL: {action_url}")

    payload = {
        "otp": code,
        "totp": code,  # Some forms use 'totp' instead of 'otp'
        "login": "Submit"
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    # Submit to the actual form action URL
    twofa_submit_response = client.post(
        action_url,  # Dynamic URL from the form
        data=payload,
        headers=headers,
        catch_response=True,
        allow_redirects=False  # Check redirect to confirm success
    )

    # Check for successful 2FA (usually redirects or returns 200)
    if twofa_submit_response.status_code in [200, 302, 303]:
        print(f"✓ 2FA verification successful")

        # Follow the redirect chain back to the app to complete OAuth and set session
        if twofa_submit_response.status_code in [302, 303]:
            callback_url = twofa_submit_response.headers.get('Location', '')
            print(f"✓ Following OAuth callback redirect: {callback_url[:100]}...")

            # Follow all redirects to complete the OAuth flow and get session cookie
            callback_response = client.get(
                callback_url,
                catch_response=True,
                allow_redirects=True  # Follow entire redirect chain
            )

            print(f"✓ OAuth callback completed, final URL: {callback_response.url}")
            print(f"✓ Session cookies set: {bool(client.cookies)}")

        return True
    else:
        print(f"✗ 2FA verification failed: {twofa_submit_response.status_code}")
        return False

def login(client, user, require_2fa=False, totp_secret=None):
    """
    Args:
        client: Locust HttpSession client
        user (dict): User credentials with 'email' and 'password'
        require_2fa (bool): Whether user has 2FA enabled
        totp_secret (str): Shared 2FA secret for all load test users

    Returns:
        str: CSRF token for subsequent requests
    """
    print(f"{user['email']} logging in")

    # Step 1: GET login page to extract CSRF token
    response = client.get("/auth/log-in")
    csrf_token = extract_csrf_token(response.text)
    if not csrf_token:
        raise Exception("CSRF token not found on sign-in page")

    # Step 2: Submit login credentials
    payload = {
        "member": {
            "email": user["email"],
            "password": user["password"]
        },
        "source_url": response.url  # Use the actual login page URL
    }

    headers = {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrf_token
    }

    # First request - initial login
    login_response = client.post(
        "/api/v1/marketplace/auth/log-in",
        json=payload,
        headers=headers,
        catch_response=True,
        allow_redirects=False
    )

    # Always make the second smees request regardless of first response
    smees_payload = {"auth_smee_source": "standalone"}

    smees_response = client.post(
        "/api/v1/marketplace/smees/log_in",
        json=smees_payload,
        headers=headers,
        catch_response=True,
        allow_redirects=False
    )

    # Save the first login response for 2FA (it has the Keycloak URL)
    login_response_first = login_response

    # Use smees response to check overall login success
    login_response = smees_response

    if login_response.status_code not in [200, 301, 302, 303]:
        raise Exception(f"{user['email']} login failed with status {login_response.status_code}")

    print(f"Initial login successful for {user['email']}")

    # Step 3: Handle 2FA if required
    if user["requires_2fa"]:
        if not user["totp_secret"]:
            raise Exception("2FA required but no secret provided")

        print(f"✓ 2FA is required, completing 2FA flow...")

        # The actual 2FA redirect is in the first login response JSON, not smees response
        # Pass the first login_response (before smees) to complete_2fa_flow
        success = complete_2fa_flow(client, user["totp_secret"], login_response_first)

        if not success:
            raise Exception("2FA authentication failed")

        print(f"✓ Successfully logged in with 2FA for {user['email']}")
    else:
        print(f"✓ Login complete (no 2FA) for {user['email']}")

    return csrf_token

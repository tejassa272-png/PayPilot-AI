import os
import time
import requests
from requests.auth import HTTPBasicAuth

class MockPayPalClient:
    """Used for the Adversarial Test Suite to safely inject infrastructure failures."""
    def __init__(self, failure_mode=None):
        # failure_mode can be 'timeout', '500_error', or None
        self.failure_mode = failure_mode 

    def create_invoice(self, amount: float, payee_email: str, invoice_id: str):
        if self.failure_mode == 'timeout':
            time.sleep(3) # Simulated timeout
            raise TimeoutError("Mock: API connection timed out.")
        if self.failure_mode == '500_error':
            raise Exception("Mock: 500 Internal Server Error.")
            
        return {
            "status": "CREATED", 
            "id": f"MOCK-{invoice_id}",
            "checkout_link": f"https://sandbox.paypal.com/mock-checkout/{invoice_id}"
        }

class RealPayPalClient:
    """Connects to the actual PayPal Sandbox REST API."""
    def __init__(self):
        self.client_id = os.getenv("PAYPAL_CLIENT_ID")
        self.secret = os.getenv("PAYPAL_SECRET")
        self.base_url = "https://api-m.sandbox.paypal.com"
        self.token = self._get_access_token()

    def _get_access_token(self):
        url = f"{self.base_url}/v1/oauth2/token"
        headers = {"Accept": "application/json", "Accept-Language": "en_US"}
        data = {"grant_type": "client_credentials"}
        response = requests.post(url, headers=headers, data=data, auth=HTTPBasicAuth(self.client_id, self.secret))
        response.raise_for_status()
        return response.json()["access_token"]

    def create_invoice(self, amount: float, payee_email: str, invoice_id: str):
        url = f"{self.base_url}/v2/invoicing/invoices"
        unique_invoice_id = f"{invoice_id}-{int(time.time()) % 10000}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
            "PayPal-Request-Id": unique_invoice_id
        }

        payload = {
            "detail": {
                "invoice_number": unique_invoice_id,
                "currency_code": "USD"
            },
            "primary_recipients": [{"billing_info": {"email_address": payee_email}}],
            "items": [
                {
                    "name": "B2B Services",
                    "quantity": "1",
                    "unit_amount": {
                        "currency_code": "USD",
                        "value": f"{amount:.2f}" 
                    }
                }
            ]
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        # GLASS BOX ENHANCEMENT: Parse exact PayPal validation errors for the UI Ledger
        if not response.ok:
            error_msg = f"HTTP {response.status_code}"
            try:
                error_data = response.json()
                if "details" in error_data:
                    issues = [f"{d.get('field', 'Field')}: {d.get('description', 'Invalid')}" for d in error_data["details"]]
                    error_msg += f" - {', '.join(issues)}" # Changed | to -
                else:
                    error_msg += f" - {error_data.get('message', 'Bad Request')}" # Changed | to -
            except Exception:
                error_msg += f" - {response.text}" # Changed | to -
            raise Exception(error_msg)
            
        return response.json()
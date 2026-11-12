from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Optional
import os
import hmac
import hashlib
import json

from core_graph import paypilot_graph, generate_audit_entry
from paypal_client import MockPayPalClient, RealPayPalClient
from extraction import extract_invoice_data
from database import get_db_connection
from seed_db import seed_database
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI(title="PayPilot AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class InvoiceRequest(BaseModel):
    invoice_id: str
    customer_id: str
    requested_payee: str
    amount: float
    use_mock: bool = True
    failure_mode: Optional[str] = None
    
class RawInvoiceRequest(BaseModel):
    raw_text: str

# --- API Endpoints ---
@app.get("/api/customer/score")
def get_customer_score():
    """Fetches the current reliability score for the demo customer."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # For the UI demo, we fetch the specific demo customer's score to display in the header
        cursor.execute("SELECT reliability_score FROM customers WHERE id = 'CUST-999'")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return {"score": result[0]}
        return {"score": 85.0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/process_invoice")
def process_invoice(req: InvoiceRequest):
    """Entry point for the React Glass Box UI to trigger the state machine."""
    initial_state = {
        "invoice_id": req.invoice_id,
        "customer_id": req.customer_id,
        "requested_payee": req.requested_payee,
        "amount": req.amount,
        "status": "PROPOSED",
        "risk_flags": [],
        "audit_log": []
    }
    
    result = paypilot_graph.invoke(initial_state)
    
    checkout_data = None
    if result["status"] == "EXECUTION_PENDING":
        current_state = {"invoice_id": req.invoice_id, "audit_log": result["audit_log"]}
        
        try:
            client = MockPayPalClient(req.failure_mode) if req.use_mock else RealPayPalClient()
            checkout_data = client.create_invoice(req.amount, req.requested_payee, req.invoice_id)
            result["status"] = "EXECUTED"
            
            real_hash = generate_audit_entry(current_state, "SUCCESS", "Payment execution completed via API.")
            result["audit_log"].append(real_hash)
            
        except TimeoutError:
            result["status"] = "OUTCOME_UNKNOWN"
            real_hash = generate_audit_entry(current_state, "TIMEOUT_ERROR", "Payment API timed out. Idempotency lock engaged.")
            result["audit_log"].append(real_hash)
            
        except Exception as e:
            result["status"] = "EXECUTION_FAILED"
            real_hash = generate_audit_entry(current_state, "EXECUTION_ERROR", str(e))
            result["audit_log"].append(real_hash)

    return {
        "final_status": result["status"],
        "risk_flags": result.get("risk_flags", []),
        "audit_log": result["audit_log"],
        "payment_details": checkout_data
    }

def process_webhook_async(event_id: str, event_type: str, resource: dict):
    """Background task to update DB without delaying the 200 OK response to PayPal."""
    if event_type == "INVOICING.INVOICE.PAID":
        customer_email = resource.get("primary_recipients", [{}])[0].get("billing_info", {}).get("email_address")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Idempotency check
        cursor.execute("SELECT 1 FROM audit_logs WHERE event_hash = %s", (event_id,))
        if not cursor.fetchone():
            # FIX: Dynamically update the score for whichever customer matches the webhook email
            cursor.execute("""
                UPDATE customers 
                SET reliability_score = LEAST(reliability_score + 5.0, 100.0) 
                WHERE email = %s
            """, (customer_email,))
            
            cursor.execute("""
                INSERT INTO audit_logs (invoice_id, event_hash, previous_hash)
                VALUES (%s, %s, %s)
            """, (resource.get("id"), event_id, "WEBHOOK_VERIFIED"))
            conn.commit()
        
        cursor.close()
        conn.close()

@app.post("/api/webhooks/paypal")
async def real_paypal_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receives GENUINE webhooks from PayPal via ngrok. 
    V2 Roadmap: Implement PAYPAL-TRANSMISSION-SIG verification using PayPal's certs.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_id = payload.get("id")
    event_type = payload.get("event_type")
    resource = payload.get("resource", {})

    background_tasks.add_task(process_webhook_async, event_id, event_type, resource)
    return {"status": "received"}

@app.post("/api/webhooks/simulate")
async def simulate_paypal_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    HMAC-secured simulation endpoint for the Glass Box UI.
    Requires X-PayPilot-Signature to prevent unauthorized score inflation.
    """
    raw_body = await request.body()
    webhook_secret = os.getenv("WEBHOOK_SECRET", "demo_secret_key").encode()
    expected_signature = hmac.new(webhook_secret, raw_body, hashlib.sha256).hexdigest()
    
    provided_signature = request.headers.get("X-PayPilot-Signature")
    
    if not provided_signature or not hmac.compare_digest(expected_signature, provided_signature):
        print("\n🚨 SECURITY ALERT: Forged webhook signature detected and blocked! 🚨\n")
        raise HTTPException(status_code=401, detail="Invalid webhook signature. Payload rejected.")
        
    try:
        payload = json.loads(raw_body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_id = payload.get("id")
    event_type = payload.get("event_type")
    resource = payload.get("resource", {})

    background_tasks.add_task(process_webhook_async, event_id, event_type, resource)
    return {"status": "received"}

@app.post("/api/extract")
def extract_invoice(req: RawInvoiceRequest):
    """AI Engine: Extracts structured data from raw text."""
    try:
        extracted_data = extract_invoice_data(req.raw_text)
        return extracted_data.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reset")
def reset_demo_state():
    """Resets the database to a known baseline for seamless demo repetition."""
    try:
        seed_database()
        return {"status": "SUCCESS", "message": "Database reset to baseline."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
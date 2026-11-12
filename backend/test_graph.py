from core_graph import paypilot_graph

def run_test(test_name: str, initial_state: dict):
    print(f"\n--- RUNNING: {test_name} ---")
    
    # Execute the LangGraph state machine
    result = paypilot_graph.invoke(initial_state)
    
    print(f"FINAL STATUS: {result['status']}")
    print(f"RISK FLAGS: {result.get('risk_flags', [])}")
    print("TAMPER-EVIDENT LOG:")
    for log in result['audit_log']:
        print(f"  -> {log}")

if __name__ == "__main__":
    # Test 1: Happy Path (Trusted Supplier)
    run_test(
        "Trusted Supplier Payment", 
        {
            "invoice_id": "INV-001",
            "customer_id": "CUST-999",
            "requested_payee": "billing@acmecorp.com",
            "amount": 5000.00
        }
    )

    # Test 2: Adversarial Attack (Business Email Compromise)
    run_test(
        "BEC Attack (Fake Supplier Domain)", 
        {
            "invoice_id": "INV-002",
            "customer_id": "CUST-999",
            "requested_payee": "billing@acmeco.com", # Missing the 'rp'
            "amount": 50000.00
        }
    )
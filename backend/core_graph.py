import hashlib
import json
from datetime import datetime
from typing import TypedDict, Annotated, List
from operator import add
from langgraph.graph import StateGraph, END

# 1. State Definition
class PayPilotState(TypedDict):
    invoice_id: str
    customer_id: str
    requested_payee: str
    amount: float
    
    # Security & Validation
    supplier_verified: bool
    risk_flags: Annotated[List[str], add]
    
    # State Machine Status
    status: str 
    
    # Cryptographic Audit Log
    audit_log: Annotated[List[str], add]

# 2. Tamper-Evident Ledger Function
def generate_audit_entry(state: PayPilotState, action: str, details: str) -> str:
    """Hashes the current event with the previous hash to create an unbreakable chain."""
    prev_hash = state.get("audit_log", ["genesis_hash"])[-1] if state.get("audit_log") else "genesis_hash"
    
    # Extract only the actual hash value if it's already a formatted string
    if prev_hash != "genesis_hash" and "|" in prev_hash:
        prev_hash = prev_hash.split("|")[0].strip()
        
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "invoice_id": state.get("invoice_id"),
        "action": action,
        "details": details
    }
    
    # Canonical serialization for deterministic hashing
    payload = json.dumps(event, sort_keys=True) + prev_hash
    new_hash = hashlib.sha256(payload.encode()).hexdigest()
    
    return f"{new_hash} | {action}: {details}"

# 3. LangGraph Nodes
def node_proposed(state: PayPilotState):
    log = generate_audit_entry(state, "PROPOSED", f"Received invoice for ${state.get('amount')}")
    return {"status": "STRATEGY_SELECTION", "audit_log": [log]}

def node_validating(state: PayPilotState):
    # LAYER 1: The Approved Supplier Ledger (Simulated offline JSON for now)
    approved_ledgers = {"billing@acmecorp.com", "payments@trusted-vendor.io"}
    payee = state.get("requested_payee", "")
    
    is_verified = payee in approved_ledgers
    flags = []
    
    if not is_verified:
        flags.append(f"BEC_RISK: Domain {payee.split('@')[-1]} not in offline ledger.")
        log = generate_audit_entry(state, "VALIDATION_FAILED", "Potential Business Email Compromise detected.")
    else:
        log = generate_audit_entry(state, "VALIDATED", "Supplier identity cryptographically verified.")
        
    return {
        "supplier_verified": is_verified, 
        "risk_flags": flags, 
        "status": "VALIDATING", 
        "audit_log": [log]
    }

def node_approved(state: PayPilotState):
    log = generate_audit_entry(state, "APPROVED", "Transaction passed all security gates.")
    return {"status": "EXECUTION_PENDING", "audit_log": [log]}

def node_approval_needed(state: PayPilotState):
    log = generate_audit_entry(state, "HALTED", "Transaction frozen pending human review.")
    return {"status": "APPROVAL_NEEDED", "audit_log": [log]}

# 4. Routing Logic (The Authorization Fork)
def route_validation(state: PayPilotState) -> str:
    if len(state.get("risk_flags", [])) > 0:
        return "approval_needed"
    return "approved"

# 5. Compile the Graph
builder = StateGraph(PayPilotState)

builder.add_node("proposed", node_proposed)
builder.add_node("validating", node_validating)
builder.add_node("approved", node_approved)
builder.add_node("approval_needed", node_approval_needed)

builder.set_entry_point("proposed")
builder.add_edge("proposed", "validating")
builder.add_conditional_edges("validating", route_validation, {
    "approved": "approved",
    "approval_needed": "approval_needed"
})
builder.add_edge("approved", END)
builder.add_edge("approval_needed", END)

paypilot_graph = builder.compile()
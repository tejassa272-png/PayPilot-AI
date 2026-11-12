# 🚀 PayPilot AI: Hackathon MVP

**An AI finance agent that helps businesses get paid faster without giving AI unchecked control over their money.**

## 🛠️ System Architecture & Tech Stack
* **Frontend (The "Glass Box"):** React, TypeScript, SCSS, AG Grid.
* **Backend & API:** Python, FastAPI.
* **AI Engine (LLM):** Groq (Llama 3 / Qwen) with Google Gemini Fallback for unstructured data extraction.
* **Agent Architecture:** LangGraph (Deterministic 4-node state machine).
* **Payments & Finance:** PayPal Sandbox REST API integration.
* **Infrastructure & Testing:** Docker, PostgreSQL, and a Custom Mock Payment Adapter (for latency/failure injection).

---

## ⚙️ Core MVP Features

### 1. Deterministic State Machine & Mock Adapter
Every AI-generated extraction is routed through a strict, server-side LangGraph state machine designed to demonstrate real-world failure handling.
* **The Workflow:** `PROPOSED` → `VALIDATING` → {`APPROVED` | `APPROVAL_NEEDED`}.
* **Timeout Handling:** `APPROVED` transitions to an `EXECUTION_PENDING` block. If a PayPal API timeout occurs, the system flags `OUTCOME_UNKNOWN` rather than blindly retrying, demonstrating the foundation for idempotent execution.

### 2. The Payment Change Firewall (Layer 1)
A risk-screening pipeline designed to intercept Business Email Compromise (BEC).
* **Approved Supplier Ledger:** The system extracts the supplier identity from unstructured text and cross-references the requested payment destination against an in-memory ledger of verified suppliers.
* **Actionable Halts:** Any destination mismatch freezes automatic execution, instantly routing the graph to `APPROVAL_NEEDED` and blocking the API call.

### 3. Asynchronous Webhook Loop & Reliability Scoring
PayPilot demonstrates an automated feedback loop between payment execution and customer risk profiling.
* **Dynamic Scoring:** The backend listens for simulated `INVOICING.INVOICE.PAID` payloads and dynamically increments the payer's Reliability Score in PostgreSQL.
* **HMAC Security:** To prevent artificial score inflation, the simulated webhook endpoint strictly enforces HMAC-SHA256 signature verification, rejecting any unauthenticated payloads with a 401 error before they touch the database.

### 4. Per-Transaction Tamper-Evident Ledger
To answer the core question—*Would you trust an AI with your money?*—the system leaves a cryptographic trail for every execution.
* Through canonical serialization, every authorization decision, API call result, and policy check within a transaction's lifecycle is hashed using SHA-256 and chained to the previous entry, proving exactly why the deterministic engine approved or blocked a request.

### 5. The "Glass Box" Dashboard
A React mission control interface prioritizing transparency.
* **Live vs. Test Mode Toggle:** Instantly switch routing between the Real PayPal Sandbox API and a local Mock Stub API for deliberate failure injection.
* **Resettable State:** A single button wipes the Tamper-Evident Ledger and resets the PostgreSQL database to a known baseline (`85.0` Reliability Score) for seamless demo repetition.
* **Adversarial Test Suite:** Dedicated UI triggers to safely inject BEC domain mismatches and API timeouts, proving the backend guardrails catch them in real-time.

---

## 🚀 Quick Start (Running Locally)

This project is fully containerized for a zero-friction evaluation.

1. Clone the repository:
   ```bash
   git clone [https://github.com/tejassa272-png/PayPilot-AI.git](https://github.com/tejassa272-png/PayPilot-AI.git)
   cd PayPilot-AI

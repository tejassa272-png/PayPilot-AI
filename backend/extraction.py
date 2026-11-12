import os
import requests
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class ExtractedInvoice(BaseModel):
    invoice_id: str = Field(description="The unique invoice number or ID.")
    customer_id: str = Field(default="CUST-999", description="The customer ID.")
    requested_payee: str = Field(description="The billing email address of the supplier/payee.")
    amount: float = Field(description="The total monetary amount requested as a float.")

def get_active_groq_models(api_key: str) -> list[str]:
    """Fetches the live list of active chat models directly from Groq's API."""
    resp = requests.get(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=10
    )
    resp.raise_for_status()
    all_models = [m["id"] for m in resp.json().get("data", [])]
    
    # Exclude non-chat models (audio, TTS, guardrails, embeddings)
    excluded = ("whisper", "guard", "tts", "embed", "playai", "orpheus", "allam")
    chat_models = [
        m for m in all_models 
        if not any(ex in m.lower() for ex in excluded)
    ]
    
    # Prioritize Llama models first
    chat_models.sort(key=lambda m: (0 if "llama" in m.lower() else 1, m))
    return chat_models

def extract_invoice_data(raw_text: str) -> ExtractedInvoice:
    """Parses unstructured text using live Groq model discovery, with Gemini as fallback."""
    prompt = f"Extract the financial invoice details from the following text/email:\n\n{raw_text}"
    
    # --- ATTEMPT 1: Groq (Dynamic Model Discovery) ---
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        try:
            candidate_models = get_active_groq_models(groq_key)
            print(f"\n🔍 Active Groq models found: {candidate_models}")
            
            for model_id in candidate_models:
                try:
                    print(f"🔄 Trying Groq model: {model_id}...")
                    llm_groq = ChatGroq(
                        model=model_id,
                        temperature=0,
                        api_key=groq_key,
                        max_retries=1
                    )
                    structured_groq = llm_groq.with_structured_output(ExtractedInvoice)
                    result = structured_groq.invoke(prompt)
                    print(f"✅ Extracted successfully using: {model_id}\n")
                    return result
                except Exception as model_err:
                    print(f"⚠️ {model_id} skipped ({model_err}). Trying next...")
                    continue
        except Exception as e:
            print(f"\n⚠️ Groq discovery failed ({e}). Falling back to Gemini...\n")

    # --- ATTEMPT 2: Google Gemini (Fallback) ---
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key:
        llm_gemini = ChatGoogleGenerativeAI(
            model="models/gemini-3.8-flash", 
            temperature=0,
            api_key=gemini_key,
            max_retries=1
        )
        structured_gemini = llm_gemini.with_structured_output(ExtractedInvoice)
        return structured_gemini.invoke(prompt)

    raise ValueError("CRITICAL: Both Groq and Gemini failed to extract invoice data.")
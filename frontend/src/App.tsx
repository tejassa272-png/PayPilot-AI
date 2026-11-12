import { useState, useEffect } from 'react';
import axios from 'axios';
import { AgGridReact } from 'ag-grid-react';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css'; // Keep the base theme
import './App.scss';
export default function App() {
  const [status, setStatus] = useState<string>("IDLE");
  const [riskFlags, setRiskFlags] = useState<string[]>([]);
  const [auditLog, setAuditLog] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [rawText, setRawText] = useState("Hi PayPilot, please process $4250.00 for INV-7781 to billing@acmecorp.com as soon as possible.");
  const [reliabilityScore, setReliabilityScore] = useState<number>(85.0);
  
  // New Global Toggle State
  const [useRealApi, setUseRealApi] = useState<boolean>(false);

  const columnDefs = [
    { field: 'hash', headerName: 'SHA-256 Hash', width: 250, cellClass: 'hash-font' },
    { field: 'action', headerName: 'Node Action', width: 180 },
    { field: 'details', headerName: 'Execution Details', flex: 1 }
  ];
  
  const fetchScore = async () => {
    try {
      const response = await axios.get('http://localhost:8000/api/customer/score');
      setReliabilityScore(response.data.score);
    } catch (error) {
      console.error("Failed to fetch score:", error);
    }
  };

  useEffect(() => { 
    fetchScore(); 
  }, []);

  const triggerAI = async () => {
    setIsLoading(true);
    setStatus("EXTRACTING DATA...");
    setRiskFlags([]);
    setAuditLog([]);

    try {
      const aiResponse = await axios.post('http://localhost:8000/api/extract', { raw_text: rawText });
      const extractedData = aiResponse.data;

      setStatus("EVALUATING GRAPH...");

      const payload = {
        invoice_id: extractedData.invoice_id,
        customer_id: extractedData.customer_id,
        requested_payee: extractedData.requested_payee,
        amount: extractedData.amount,
        use_mock: !useRealApi, // Dynamic configuration based on toggle
        failure_mode: null
      };

      const response = await axios.post('http://localhost:8000/api/process_invoice', payload);
      const data = response.data;
      
      setStatus(data.final_status);
      setRiskFlags(data.risk_flags);
      
      const parsedLogs = data.audit_log.map((entry: string) => {
        const [hash, message] = entry.split(" | ");
        const [action, ...details] = message ? message.split(": ") : ["", ""];
        return { hash: hash?.trim(), action: action?.trim(), details: details.join(": ").trim() };
      });
      
      parsedLogs.unshift({
        hash: "AI_EXTRACT_" + Math.random().toString(36).substring(7),
        action: "AI_EXTRACTION",
        details: `Parsed ${extractedData.invoice_id} for $${extractedData.amount} to ${extractedData.requested_payee}`
      });
      
      setAuditLog(parsedLogs);
    } catch (error) {
      console.error("AI Error:", error);
      setStatus("EXTRACTION_FAILED");
    } finally {
      setIsLoading(false);
    }
  };

  const triggerPipeline = async (scenario: string) => {
    setIsLoading(true);
    setStatus("PROCESSING...");
    setRiskFlags([]);
    setAuditLog([]);

    const payload = {
      invoice_id: `INV-${Math.floor(Math.random() * 10000)}`,
      customer_id: "CUST-999",
      requested_payee: "billing@acmecorp.com", 
      amount: 5000.00,
      use_mock: !useRealApi, // Dynamic configuration based on toggle
      failure_mode: null as string | null
    };
    
    if (scenario === 'BEC') {
      payload.requested_payee = "billing@acmeco.com";
      payload.amount = 50000.00;
    } else if (scenario === 'TIMEOUT') {
      payload.failure_mode = 'timeout';
    }

    try {
      const response = await axios.post('http://localhost:8000/api/process_invoice', payload);
      const data = response.data;
      
      setStatus(data.final_status);
      setRiskFlags(data.risk_flags);
      
      const parsedLogs = data.audit_log.map((entry: string) => {
        const [hash, message] = entry.split(" | ");
        const [action, ...details] = message ? message.split(": ") : ["", ""];
        return { hash: hash?.trim(), action: action?.trim(), details: details.join(": ").trim() };
      });
      setAuditLog(parsedLogs);

    } catch (error) {
      console.error("API Error:", error);
      setStatus("SYSTEM_ERROR");
    } finally {
      setIsLoading(false);
    }
  };

  const simulatePaymentWebhook = async () => {
    setIsLoading(true);
    setStatus("AWAITING WEBHOOK...");
    try {
      const payloadObj = {
        id: `WH-DEMO-${Math.floor(Math.random() * 100000)}`,
        event_type: "INVOICING.INVOICE.PAID",
        resource: {
          id: "INV-DEMO",
          primary_recipients: [
            { billing_info: { email_address: "billing@acmecorp.com" } }
          ]
        }
      };
      
      const payloadString = JSON.stringify(payloadObj);
      
      const encoder = new TextEncoder();
      const keyData = encoder.encode("demo_secret_key"); 
      const cryptoKey = await crypto.subtle.importKey(
          'raw', keyData, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']
      );
      const signatureBuffer = await crypto.subtle.sign('HMAC', cryptoKey, encoder.encode(payloadString));
      const signatureHex = Array.from(new Uint8Array(signatureBuffer))
          .map(b => b.toString(16).padStart(2, '0')).join('');

      await axios.post('http://localhost:8000/api/webhooks/simulate', payloadString, {
        headers: {
          'Content-Type': 'application/json',
          'X-PayPilot-Signature': signatureHex 
        }
      });
      
      setTimeout(async () => {
        await fetchScore();
        setStatus("IDLE");
        setIsLoading(false);
      }, 500);
      
    } catch (error) {
      console.error("Webhook simulation failed:", error);
      setStatus("SYSTEM_ERROR");
      setIsLoading(false);
    }
  };

  const resetDemoState = async () => {
    setIsLoading(true);
    setStatus("RESETTING...");
    try {
      await axios.post('http://localhost:8000/api/reset');
      setStatus("IDLE");
      setRiskFlags([]);
      setAuditLog([]);
      setRawText("Hi PayPilot, please process $4250.00 for INV-7781 to billing@acmecorp.com as soon as possible.");
      await fetchScore(); 
    } catch (error) {
      console.error("Failed to reset:", error);
      setStatus("SYSTEM_ERROR");
      alert("❌ Failed to reset demo state.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="mission-control">
      <header className="header">
        <h1>
          <span className="logo-icon">🚀</span>
          <span className="logo-text">PayPilot <span className="ai-highlight">AI</span></span>
          <span className="subtitle">Glass Box</span>
        </h1>
        <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center' }}>
            <div style={{ fontWeight: '600', color: '#475569', background: '#f8fafc', padding: '0.5rem 1rem', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                Reliability Score: <span style={{ color: reliabilityScore >= 90 ? '#059669' : reliabilityScore >= 70 ? '#d97706' : '#dc2626', fontWeight: 'bold', fontSize: '1.1rem' }}>{reliabilityScore}</span>
            </div>
            <div className={`status-badge ${status.toLowerCase().replace(/ /g, '_')}`}>
              STATE: {status}
            </div>
        </div>
      </header>

      <div className="layout">
        <aside className="adversarial-sidebar">
          <h3>Adversarial Test Suite</h3>
          <p>Inject infrastructure failures or fraud to watch the deterministic engine catch them.</p>

          <div style={{ display: 'flex', alignItems: 'center', marginBottom: '1.5rem', background: '#ffffff', padding: '0.75rem 1rem', borderRadius: '6px', border: '1px solid #bae6fd', justifyContent: 'space-between' }}>
            <span style={{ fontWeight: '600', color: '#0c4a6e', fontSize: '0.85rem', letterSpacing: '0.5px' }}>
              MODE: {useRealApi ? 'LIVE SANDBOX 🟢' : 'MOCK TESTING 🟡'}
            </span>
            <label style={{ position: 'relative', display: 'inline-block', width: '36px', height: '20px' }}>
              <input type="checkbox" checked={useRealApi} onChange={(e) => setUseRealApi(e.target.checked)} style={{ opacity: 0, width: 0, height: 0 }} />
              <span style={{ position: 'absolute', cursor: 'pointer', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: useRealApi ? '#10b981' : '#94a3b8', transition: '.3s', borderRadius: '20px' }}>
                <span style={{ position: 'absolute', content: '""', height: '14px', width: '14px', left: useRealApi ? '19px' : '3px', bottom: '3px', backgroundColor: 'white', transition: '.3s', borderRadius: '50%' }}></span>
              </span>
            </label>
          </div>
          
          <button disabled={isLoading} onClick={() => triggerPipeline('HAPPY_PATH')} className="btn-safe">
            {isLoading && status === 'PROCESSING...' ? '⏳ Processing...' : '▶ Trusted Supplier (Happy Path)'}
          </button>
          
          <button disabled={isLoading} onClick={() => triggerPipeline('BEC')} className="btn-danger">
            {isLoading && status === 'PROCESSING...' ? '⏳ Processing...' : '☣ Simulate BEC Attack'}
          </button>
          
          <button disabled={isLoading} onClick={() => triggerPipeline('TIMEOUT')} className="btn-warn">
            {isLoading && status === 'PROCESSING...' ? '⏳ Processing...' : '⏱ Simulate API Timeout'}
          </button>

          <hr style={{ borderColor: '#bae6fd', margin: '1.5rem 0' }} />

          <h3>Unstructured Data Engine</h3>
          <textarea 
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
            rows={4}
            disabled={isLoading}
            style={{ width: '100%', boxSizing: 'border-box', marginBottom: '1rem', background: '#ffffff', color: '#0f172a', padding: '0.75rem', borderRadius: '6px', border: '1px solid #bae6fd', fontFamily: 'monospace', resize: 'vertical' }}
          />
          <button disabled={isLoading} onClick={triggerAI} style={{ background: 'linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%)', color: 'white', border: 'none' }}>
            {isLoading && (status === 'EXTRACTING DATA...' || status === 'EVALUATING GRAPH...') ? '🧠 Thinking...' : '🧠 Extract & Execute Invoice'}
          </button>

          <hr style={{ borderColor: '#bae6fd', margin: '1.5rem 0' }} />
          
          <button 
            disabled={isLoading} 
            onClick={simulatePaymentWebhook} 
            style={{ background: 'linear-gradient(135deg, #14b8a6 0%, #0f766e 100%)', color: 'white', border: 'none' }}
          >
            {isLoading && status === 'AWAITING WEBHOOK...' ? '📡 Transmitting...' : '💸 Simulate Customer Payment'}
          </button>

          <button 
            disabled={isLoading} 
            onClick={resetDemoState} 
            style={{ background: '#334155', color: 'white', border: 'none' }}
          >
            {isLoading && status === 'RESETTING...' ? '🔄 Resetting DB...' : '🔄 Reset Demo State'}
          </button>
        </aside>

        <main className="content">
          {riskFlags.length > 0 && (
            <div className="risk-alert">
              <strong>⚠️ Halting Execution:</strong> {riskFlags[0]}
            </div>
          )}

          <div className="ledger-container">
            <h3>Tamper-Evident Ledger</h3>
            <div className="ag-theme-alpine" style={{ height: 500, width: '100%' }}>
              <AgGridReact
                rowData={auditLog}
                columnDefs={columnDefs}
                animateRows={true}
              />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
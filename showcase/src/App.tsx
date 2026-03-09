import { useState, useEffect } from 'react';
import './index.css';

// Mock Data Types
type AgentTask = {
  id: string;
  agent: string;
  action: string;
  detail: string;
  time: string;
};

function App() {
  const [activeAgents, setActiveAgents] = useState(812);
  const [throughput, setThroughput] = useState(21.4);
  const [logs, setLogs] = useState<AgentTask[]>([]);
  const [encryptedData, setEncryptedData] = useState('');
  const [inputText, setInputText] = useState('Retrieve financial summary FY2023 for project Alpha...');

  // Simulate real-time activity
  useEffect(() => {
    const interval = setInterval(() => {
      setActiveAgents(prev => prev + Math.floor(Math.random() * 5) - 2);
      setThroughput(prev => +(prev + (Math.random() * 2 - 1)).toFixed(1));
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  // Simulate Encryption Flow
  const handleEncrypt = () => {
    // Fake a hex/encrypted string
    const chars = '0123456789ABCDEFghijklmnopqrstuvwxyz!@#$%^&*()';
    let noise = '';
    for(let i=0; i<150; i++) {
        noise += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    setEncryptedData(noise);

    // Add to logs
    const now = new Date().toLocaleTimeString('en-US', { hour12: false });
    setLogs(prev => [
      ...prev.slice(-4), // Keep last 4
      { id: Date.now().toString(), agent: 'Researcher', action: 'Write', detail: 'Allocating 1024 bytes (AES-GCM-256)', time: now },
      { id: (Date.now()+1).toString(), agent: 'Privacy Shield', action: 'Encrypt', detail: `Ciphertext generated. Len: ${noise.length}`, time: now }
    ]);
  };

  return (
    <div className="dashboard">
      <header>
        <div className="logo">
          <div className="logo-icon"></div>
          SUPERBRAIN SDK SHOWCASE
        </div>
        <div className="status-bar">
          <span>CONTROL CENTER</span>
          <span>SECURE DISTRIBUTED MEMORY</span>
        </div>
      </header>

      <aside>
         <div className="nav-item">🏠 Overview</div>
         <div className="nav-item active">🛡️ Secure Fabric</div>
         <div className="nav-item">🔒 Privacy Shield</div>
         <div className="nav-item">💬 Agent Feed</div>
         <div className="nav-item" style={{ marginTop: 'auto' }}>⚙️ Settings</div>
      </aside>

      <main>
        {/* Top Section: Visualization */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column' }}>
           <div className="panel-title">1. SECURE FABRIC VISUALIZATION</div>
           <div className="fabric-vis">
              {/* Simulated 3D Network (Simplified CSS for demo) */}
              <div className="coordinator-node pulse">
                 <div className="logo-icon" style={{width: 40, height: 40}}></div>
              </div>
              {/* Fake Agents */}
              <div style={{position: 'absolute', top: '20%', left: '20%', padding: '4px 8px', border: '1px solid var(--accent-cyan)', borderRadius: 4, background: 'var(--glass-bg)', fontSize: '0.75rem', color: 'var(--accent-green)'}}>Agent 4A9<br/>Active</div>
              <div style={{position: 'absolute', bottom: '30%', right: '15%', padding: '4px 8px', border: '1px solid var(--accent-cyan)', borderRadius: 4, background: 'var(--glass-bg)', fontSize: '0.75rem', color: 'var(--accent-cyan)'}}>Agent 7D1<br/>Syncing</div>
           </div>
           
           <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 12, borderTop: '1px solid var(--panel-border)', paddingTop: 12 }}>
              <div>
                <div style={{fontSize: '0.7rem', color: 'var(--text-secondary)'}}>NETWORK STATUS</div>
                <div style={{fontSize: '1.2rem', fontWeight: 600, color: 'var(--accent-cyan)'}}>🟢 {activeAgents} Agents</div>
              </div>
              <div>
                <div style={{fontSize: '0.7rem', color: 'var(--text-secondary)'}}>THROUGHPUT</div>
                <div style={{fontSize: '1.2rem', fontWeight: 600, color: 'var(--accent-cyan)'}}>⚡ {throughput} GB/s</div>
              </div>
           </div>
        </div>

        {/* Bottom Section: Feed */}
        <div className="panel">
           <div className="panel-title">3. REAL-TIME AGENT INTERACTION FEED</div>
           <div className="terminal">
              {logs.map(log => (
                 <div key={log.id} className="log-entry">
                    <span className="log-time">[{log.time}]</span>
                    <span className="log-agent">{log.agent}:</span>
                    <span className="log-msg"> {log.action} - {log.detail}</span>
                 </div>
              ))}
              {logs.length === 0 && <div style={{opacity: 0.5}}>Waiting for agent activity...</div>}
           </div>
        </div>
      </main>

      <div className="right-sidebar">
         {/* Privacy Shield */}
         <div className="panel shield-container">
            <div className="panel-title">2. PRIVACY SHIELD (E2EE)</div>
            
            <div className="data-flow">
               <div>
                 <div style={{fontSize: '0.7rem', color: 'var(--text-secondary)', marginBottom: 4}}>INPUT DATA (Plaintext)</div>
                 <textarea 
                    className="data-bubble plaintext" 
                    style={{width: '100%', minHeight: '60px', background: 'transparent', border: '1px solid var(--accent-green)', resize: 'none', color: 'var(--accent-green)'}}
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                 />
               </div>
               
               <button 
                  onClick={handleEncrypt}
                  style={{padding: '8px', background: 'var(--accent-cyan)', color: '#000', border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 600, marginTop: 8}}
               >
                  🛡️ Simulate E2EE Transport
               </button>

               <div style={{marginTop: 12}}>
                 <div style={{fontSize: '0.7rem', color: 'var(--text-secondary)', marginBottom: 4}}>ENCRYPTED RAM PAYLOAD (Noise)</div>
                 <div className="data-bubble encrypted" style={{minHeight: '100px'}}>
                   {encryptedData || '[ Awaiting Payload ]'}
                 </div>
                 {encryptedData && <div style={{fontSize: '0.6rem', color: 'var(--accent-cyan)', marginTop: 4, textAlign: 'right'}}>Encryption Latency: {Math.floor(Math.random() * 5 + 1)}ms</div>}
               </div>
            </div>
         </div>
      </div>

    </div>
  );
}

export default App;

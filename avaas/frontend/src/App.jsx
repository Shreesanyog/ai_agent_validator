import { useState } from "react";
import TenantPanel from "./components/TenantPanel.jsx";
import AgentOnboardingForm from "./components/AgentOnboardingForm.jsx";
import RequirementsPanel from "./components/RequirementsPanel.jsx";
import RunPanel from "./components/RunPanel.jsx";
import RunsList from "./components/RunsList.jsx";
import ReportView from "./components/ReportView.jsx";

export default function App() {
  const [tab, setTab] = useState("configure");
  const [agent, setAgent] = useState(null);
  const [useCase, setUseCase] = useState("");
  const [requirements, setRequirements] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [selectedRun, setSelectedRun] = useState(null);

  return (
    <>
      <header className="app-header">
        <h1>AVaaS <span>Agent Validator as a Service — multi-tenant AI agent governance</span></h1>
        <nav className="tabs">
          <button className={tab === "configure" ? "active" : ""} onClick={() => setTab("configure")}>Configure</button>
          <button className={tab === "analytics" ? "active" : ""} onClick={() => setTab("analytics")}>Analytics</button>
        </nav>
      </header>

      {tab === "configure" && (
        <div className="layout">
          <div>
            <TenantPanel />
            {agent && (
              <div className="panel">
                <h2>Active Agent</h2>
                <p><b>{agent.name}</b></p>
                <p className="hint">{agent.id}</p>
              </div>
            )}
          </div>
          <div>
            <AgentOnboardingForm onAgentCreated={setAgent} />
            <RequirementsPanel
              agentId={agent?.id}
              useCase={useCase}
              setUseCase={setUseCase}
              requirements={requirements}
              setRequirements={setRequirements}
            />
            <RunPanel
              agentId={agent?.id}
              useCase={useCase}
              requirements={requirements}
              onRunComplete={(report) => {
                setSelectedRun(report);
                setRefreshKey((k) => k + 1);
                setTab("analytics");
              }}
            />
          </div>
        </div>
      )}

      {tab === "analytics" && (
        <div className="layout">
          <RunsList agentId={agent?.id} refreshKey={refreshKey} onSelectRun={setSelectedRun} selectedRunId={selectedRun?.run_id} />
          <ReportView report={selectedRun} />
        </div>
      )}
    </>
  );
}

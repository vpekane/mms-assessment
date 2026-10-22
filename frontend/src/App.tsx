import { useCallback, useEffect, useState } from 'react'
import './App.css'

type ContractVersion = {
  contract_name: string
  display_name: string
  version: string
}

type ContractsResponse = {
  contracts: ContractVersion[]
}

type LoadState = 'loading' | 'success' | 'error'

function contractKey(contract: ContractVersion): string {
  return `${contract.contract_name}::${contract.version}`
}

function App() {
  const [contracts, setContracts] = useState<ContractVersion[]>([])
  const [selectedKey, setSelectedKey] = useState('')
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [error, setError] = useState('')

  const loadContracts = useCallback(async () => {
    setLoadState('loading')
    setError('')

    try {
      const response = await fetch('/contracts')

      if (!response.ok) {
        throw new Error(
          `The API returned HTTP ${response.status}.`,
        )
      }

      const data: ContractsResponse = await response.json()

      if (!Array.isArray(data.contracts)) {
        throw new Error('The API returned an unexpected response.')
      }

      setContracts(data.contracts)

      // Keep the current selection if it still exists.
      // Otherwise, select the first available contract version.
      setSelectedKey((currentKey) => {
        const selectionStillExists = data.contracts.some(
          (contract) => contractKey(contract) === currentKey,
        )

        if (selectionStillExists) {
          return currentKey
        }

        return data.contracts.length > 0
          ? contractKey(data.contracts[0])
          : ''
      })

      setLoadState('success')
    } catch (err) {
      setLoadState('error')

      setError(
        err instanceof Error
          ? err.message
          : 'An unexpected error occurred while loading contracts.',
      )
    }
  }, [])

  useEffect(() => {
    void loadContracts()
  }, [loadContracts])

  const selectedContract = contracts.find(
    (contract) => contractKey(contract) === selectedKey,
  )

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Sentinel home">
          <span className="brand-mark">S</span>

          <span className="brand-copy">
            <strong>Sentinel</strong>
            <span>Data quality monitoring</span>
          </span>
        </a>

        <div className="connection-status">
          <span
            className={`status-dot ${
              loadState === 'success'
                ? 'status-dot-connected'
                : loadState === 'error'
                  ? 'status-dot-error'
                  : 'status-dot-loading'
            }`}
          />

          {loadState === 'loading'
            ? 'Connecting to API'
            : loadState === 'success'
              ? 'API connected'
              : 'API unavailable'}
        </div>
      </header>

      <main className="main-content">
        <section className="page-intro">
          <p className="eyebrow">DATA QUALITY WORKSPACE</p>

          <h1>Validate a dataset</h1>

          <p className="intro-description">
            Check incoming data against an explicitly selected contract.
            Identify schema changes, invalid records, and business-rule
            violations before they become integration problems.
          </p>
        </section>

        <div className="workspace-grid">
          <section className="panel contract-panel">
            <div className="panel-heading">
              <span className="step-number">01</span>

              <div>
                <h2>Select a contract</h2>
                <p>
                  Choose the rules your CSV file is expected to follow.
                </p>
              </div>
            </div>

            {loadState === 'loading' && (
              <div className="message-box" role="status">
                <span className="loading-spinner" />
                Loading available contracts…
              </div>
            )}

            {loadState === 'error' && (
              <div className="error-box" role="alert">
                <strong>Couldn't load contracts</strong>

                <p>{error}</p>

                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => void loadContracts()}
                >
                  Try again
                </button>
              </div>
            )}

            {loadState === 'success' && contracts.length === 0 && (
              <div className="message-box">
                No contracts are currently available. Add a valid
                contract to Sentinel before validating a dataset.
              </div>
            )}

            {loadState === 'success' && contracts.length > 0 && (
              <>
                <label className="field-label" htmlFor="contract-select">
                  Contract and version
                </label>

                <select
                  id="contract-select"
                  className="contract-select"
                  value={selectedKey}
                  onChange={(event) => setSelectedKey(event.target.value)}
                >
                  {contracts.map((contract) => (
                    <option
                      key={contractKey(contract)}
                      value={contractKey(contract)}
                    >
                      {contract.display_name} — v{contract.version}
                    </option>
                  ))}
                </select>

                {selectedContract && (
                  <div className="selected-contract">
                    <div className="selected-contract-heading">
                      <div className="contract-icon" aria-hidden="true">
                        <svg
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.7"
                        >
                          <path
                            d="M7 3.75h7l4 4v12.5H7a2 2 0 0 1-2-2v-12.5a2 2 0 0 1 2-2Z"
                            strokeLinejoin="round"
                          />
                          <path
                            d="M14 3.75v4h4M9 12h6M9 15.5h6"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      </div>

                      <div>
                        <h3>{selectedContract.display_name}</h3>
                        <p>Selected validation contract</p>
                      </div>

                      <span className="version-badge">
                        v{selectedContract.version}
                      </span>
                    </div>

                    <div className="contract-metadata">
                      <div>
                        <span>Contract identifier</span>
                        <strong>{selectedContract.contract_name}</strong>
                      </div>

                      <div>
                        <span>Selected version</span>
                        <strong>{selectedContract.version}</strong>
                      </div>
                    </div>
                  </div>
                )}

                <div className="info-note">
                  <span className="info-icon" aria-hidden="true">
                    i
                  </span>

                  <p>
                    Sentinel validates data against the contract you
                    select. It does not automatically change the expected
                    schema based on the uploaded file.
                  </p>
                </div>
              </>
            )}
          </section>

          <aside className="panel workflow-panel">
            <p className="eyebrow">VALIDATION WORKFLOW</p>

            <h2>From upload to insight</h2>

            <p className="workflow-description">
              Every validation follows the same traceable process.
            </p>

            <div className="workflow-steps">
              <div className="workflow-step workflow-step-active">
                <span className="workflow-step-icon">1</span>

                <div>
                  <strong>Select a contract</strong>
                  <p>Define the expected data structure and rules.</p>
                </div>

                <span className="step-state">Current</span>
              </div>

              <div className="workflow-connector" />

              <div className="workflow-step">
                <span className="workflow-step-icon">2</span>

                <div>
                  <strong>Upload a CSV</strong>
                  <p>Submit the dataset you want to inspect.</p>
                </div>
              </div>

              <div className="workflow-connector" />

              <div className="workflow-step">
                <span className="workflow-step-icon">3</span>

                <div>
                  <strong>Review the report</strong>
                  <p>Understand the results and investigate issues.</p>
                </div>
              </div>
            </div>

            <div className="workflow-footer">
              <span className="footer-check" aria-hidden="true">
                ✓
              </span>

              <p>
                <strong>Explicit rules. Traceable results.</strong>
                <br />
                Each job uses the selected contract version.
              </p>
            </div>
          </aside>
        </div>

        <footer className="page-footer">
          <span>Sentinel</span>
          <span>Automated Data Quality &amp; Integration Monitoring</span>
        </footer>
      </main>
    </div>
  )
}

export default App
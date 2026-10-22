import {
  useCallback,
  useEffect,
  useState,
} from 'react'
import type { FormEvent } from 'react'
import './App.css'
import { Show, SignInButton, SignUpButton, UserButton } from '@clerk/react'
import BackendAuthCheck from './BackendAuthCheck'


type ContractVersion = {
  contract_name: string
  display_name: string
  version: string
}

type ContractsResponse = {
  contracts: ContractVersion[]
}

type LoadState = 'loading' | 'success' | 'error'

type ValidationIssue = {
  row: number | null
  field: string | null
  code: string
  message: string
}

type ValidationReport = {
  status: string
  total_records: number
  valid_records: number
  invalid_records: number
  issues: ValidationIssue[]
}

type JobStatus = {
  job_id: string
  contract_name: string
  contract_version: string
  status: string
  created_at: string
  started_at: string | null
  finished_at: string | null
  result: ValidationReport | null
  error: string | null
}

function contractKey(contract: ContractVersion): string {
  return `${contract.contract_name}::${contract.version}`
}

function getErrorMessage(
  payload: unknown,
  fallback: string,
): string {
  if (typeof payload === 'object' && payload !== null) {
    const data = payload as Record<string, unknown>

    if (typeof data.error === 'string') {
      if (typeof data.details === 'string') {
        return `${data.error}: ${data.details}`
      }

      return data.error
    }
  }

  return fallback
}

function statusClass(status: string): string {
  const normalizedStatus = status
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')

  return `status-pill status-${normalizedStatus}`
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return '—'
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString()
}

function App() {
  const [contracts, setContracts] = useState<ContractVersion[]>([])
  const [selectedKey, setSelectedKey] = useState('')
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [contractError, setContractError] = useState('')

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [fileError, setFileError] = useState('')

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')

  const [activeJobId, setActiveJobId] = useState('')
  const [job, setJob] = useState<JobStatus | null>(null)
  const [pollError, setPollError] = useState('')

  const loadContracts = useCallback(async () => {
    setLoadState('loading')
    setContractError('')

    try {
      const response = await fetch('/contracts')

      const payload = await response.json().catch(() => null)

      if (!response.ok) {
        throw new Error(
          getErrorMessage(
            payload,
            `The API returned HTTP ${response.status}.`,
          ),
        )
      }

      if (
        typeof payload !== 'object' ||
        payload === null ||
        !Array.isArray(payload.contracts)
      ) {
        throw new Error('The API returned an unexpected response.')
      }

      const data = payload as ContractsResponse

      setContracts(data.contracts)

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
    } catch (error) {
      setLoadState('error')

      setContractError(
        error instanceof Error
          ? error.message
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

  function selectFile(file: File | undefined) {
    if (!file) {
      return
    }

    if (!file.name.toLowerCase().endsWith('.csv')) {
      setSelectedFile(null)
      setFileError('Please select a CSV file with a .csv extension.')
      return
    }

    setSelectedFile(file)
    setFileError('')
    setSubmitError('')
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!selectedContract) {
      setSubmitError('Please select a contract and version.')
      return
    }

    if (!selectedFile) {
      setFileError('Please select a CSV file before submitting.')
      return
    }

    setIsSubmitting(true)
    setSubmitError('')
    setPollError('')
    setJob(null)
    setActiveJobId('')

    try {
      const formData = new FormData()

      formData.append('file', selectedFile)
      formData.append(
        'contract_name',
        selectedContract.contract_name,
      )
      formData.append(
        'contract_version',
        selectedContract.version,
      )

      const response = await fetch('/jobs', {
        method: 'POST',
        body: formData,
      })

      const payload = await response.json().catch(() => null)

      if (!response.ok) {
        throw new Error(
          getErrorMessage(
            payload,
            `Job submission failed with HTTP ${response.status}.`,
          ),
        )
      }

      if (
        typeof payload !== 'object' ||
        payload === null ||
        typeof payload.job_id !== 'string'
      ) {
        throw new Error(
          'The API accepted the request but did not return a job ID.',
        )
      }

      setActiveJobId(payload.job_id)
    } catch (error) {
      setSubmitError(
        error instanceof Error
          ? error.message
          : 'An unexpected error occurred during submission.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  useEffect(() => {
    if (!activeJobId) {
      return
    }

    let cancelled = false
    let timeoutId: number | undefined

    async function pollJob() {
      try {
        const response = await fetch(
          `/jobs/${encodeURIComponent(activeJobId)}`,
        )

        const payload = await response.json().catch(() => null)

        if (!response.ok) {
          throw new Error(
            getErrorMessage(
              payload,
              `Status request failed with HTTP ${response.status}.`,
            ),
          )
        }

        if (cancelled) {
          return
        }

        const currentJob = payload as JobStatus

        setJob(currentJob)
        setPollError('')

        if (
          currentJob.status === 'QUEUED' ||
          currentJob.status === 'RUNNING'
        ) {
          timeoutId = window.setTimeout(() => {
            void pollJob()
          }, 1500)
        }
      } catch (error) {
        if (cancelled) {
          return
        }

        setPollError(
          error instanceof Error
            ? error.message
            : 'Unable to retrieve the job status.',
        )

        // Retry status checks if the API is temporarily unavailable.
        timeoutId = window.setTimeout(() => {
          void pollJob()
        }, 3000)
      }
    }

    void pollJob()

    return () => {
      cancelled = true

      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId)
      }
    }
  }, [activeJobId])

  const jobInProgress = Boolean(
    activeJobId &&
      (!job ||
        job.status === 'QUEUED' ||
        job.status === 'RUNNING'),
  )

  const activeWorkflowStep = !activeJobId
    ? selectedFile
      ? 2
      : 1
    : job?.status === 'COMPLETED' || job?.status === 'FAILED'
      ? 3
      : 2

  return (
    <div className="app-shell">
      <header className="topbar">
        <Show when="signed-out">
          <SignInButton />
          <SignUpButton />
        </Show>

        <Show when="signed-in">
          <UserButton />
        </Show>
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
        <Show when="signed-out">
          <section className="page-intro">
            <p className="eyebrow">WELCOME TO SENTINEL</p>
            <h1>Sign in to access Sentinel</h1>
            <p className="intro-description">
              Sign in or create an account to validate datasets and review validation results.
            </p>
          </section>
        </Show>

        <Show when="signed-in">
          <BackendAuthCheck />
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
                  <p>{contractError}</p>

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
                <div
                  className={`workflow-step ${
                    activeWorkflowStep === 1 ? 'workflow-step-active' : ''
                  }`}
                >
                  <span className="workflow-step-icon">1</span>

                  <div>
                    <strong>Select a contract</strong>
                    <p>Define the expected data structure and rules.</p>
                  </div>

                  {activeWorkflowStep === 1 && (
                    <span className="step-state">Current</span>
                  )}
                </div>

                <div className="workflow-connector" />

                <div
                  className={`workflow-step ${
                    activeWorkflowStep === 2 ? 'workflow-step-active' : ''
                  }`}
                >
                  <span className="workflow-step-icon">2</span>

                  <div>
                    <strong>Upload a CSV</strong>
                    <p>Submit the dataset you want to inspect.</p>
                  </div>

                  {activeWorkflowStep === 2 && (
                    <span className="step-state">Current</span>
                  )}
                </div>

                <div className="workflow-connector" />

                <div
                  className={`workflow-step ${
                    activeWorkflowStep === 3 ? 'workflow-step-active' : ''
                  }`}
                >
                  <span className="workflow-step-icon">3</span>

                  <div>
                    <strong>Review the report</strong>
                    <p>Understand the results and investigate issues.</p>
                  </div>

                  {activeWorkflowStep === 3 && (
                    <span className="step-state">Current</span>
                  )}
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

          <section className="panel upload-panel">
            <div className="panel-heading">
              <span className="step-number">02</span>

              <div>
                <h2>Upload your CSV</h2>
                <p>
                  Choose the data you want Sentinel to validate against the
                  selected contract.
                </p>
              </div>
            </div>

            <form onSubmit={handleSubmit}>
              <label
                className={`upload-dropzone ${
                  isDragging ? 'upload-dropzone-dragging' : ''
                } ${selectedFile ? 'upload-dropzone-selected' : ''}`}
                htmlFor="csv-file"
                onDragOver={(event) => {
                  event.preventDefault()
                  setIsDragging(true)
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={(event) => {
                  event.preventDefault()
                  setIsDragging(false)
                  selectFile(event.dataTransfer.files.item(0) ?? undefined)
                }}
              >
                <input
                  id="csv-file"
                  className="file-input"
                  type="file"
                  accept=".csv,text/csv"
                  onChange={(event) => {
                    selectFile(event.currentTarget.files?.[0])
                    event.currentTarget.value = ''
                  }}
                />

                <span className="upload-icon" aria-hidden="true">
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.7"
                  >
                    <path
                      d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                    <path
                      d="M5 14v4a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-4"
                      strokeLinecap="round"
                    />
                  </svg>
                </span>

                <strong>
                  {selectedFile
                    ? selectedFile.name
                    : 'Drop your CSV file here'}
                </strong>

                <span className="upload-instructions">
                  or <span className="browse-link">browse files</span>
                </span>

                <span className="upload-hint">
                  CSV files only
                  {selectedFile
                    ? ` · ${(selectedFile.size / 1024).toFixed(1)} KB`
                    : ' · Select a file from your computer'}
                </span>
              </label>

              {fileError && (
                <p className="inline-error" role="alert">
                  {fileError}
                </p>
              )}

              <div className="submission-summary">
                <div>
                  <span className="summary-label">Selected contract</span>

                  <strong>
                    {selectedContract
                      ? `${selectedContract.display_name} · v${selectedContract.version}`
                      : 'No contract selected'}
                  </strong>
                </div>

                <span className="summary-separator" />

                <div>
                  <span className="summary-label">Processing</span>
                  <strong>Asynchronous validation</strong>
                </div>
              </div>

              {submitError && (
                <div className="error-box submission-error" role="alert">
                  <strong>Could not submit validation</strong>
                  <p>{submitError}</p>
                </div>
              )}

              <div className="submission-actions">
                <p>
                  Sentinel will create a job and validate the file in the
                  background.
                </p>

                <button
                  className="primary-button"
                  type="submit"
                  disabled={
                    !selectedContract ||
                    !selectedFile ||
                    isSubmitting ||
                    jobInProgress
                  }
                >
                  {isSubmitting
                    ? 'Submitting…'
                    : jobInProgress
                      ? 'Validation in progress…'
                      : 'Validate dataset'}
                  <span aria-hidden="true">→</span>
                </button>
              </div>
            </form>
          </section>

          {activeJobId && (
            <section className="panel results-panel" aria-live="polite">
              <div className="results-heading">
                <div className="panel-heading results-title">
                  <span className="step-number">03</span>

                  <div>
                    <h2>Validation results</h2>
                    <p>
                      {job
                        ? `${job.contract_name} · version ${job.contract_version}`
                        : 'Your job has been accepted by Sentinel.'}
                    </p>
                  </div>
                </div>

                <span className={statusClass(job?.status ?? 'QUEUED')}>
                  {job?.status ?? 'QUEUED'}
                </span>
              </div>

              <div className="job-id-row">
                <span>Job ID</span>
                <code>{activeJobId}</code>
                <span className="job-created">
                  Created: {formatTimestamp(job?.created_at ?? null)}
                </span>
              </div>

              {pollError && (
                <div className="poll-warning" role="status">
                  We couldn't refresh the job status: {pollError}
                  <br />
                  Sentinel will try again automatically.
                </div>
              )}

              {!job && (
                <div className="message-box result-message" role="status">
                  <span className="loading-spinner" />
                  Retrieving job status…
                </div>
              )}

              {job?.status === 'QUEUED' && (
                <div className="message-box result-message" role="status">
                  <span className="loading-spinner" />
                  Your job is queued and waiting for a worker.
                </div>
              )}

              {job?.status === 'RUNNING' && (
                <div className="message-box result-message" role="status">
                  <span className="loading-spinner" />
                  Sentinel is validating your CSV against the selected
                  contract.
                </div>
              )}

              {job?.status === 'FAILED' && (
                <div className="error-box job-failure" role="alert">
                  <strong>Job processing failed</strong>
                  <p>
                    {job.error || 'Sentinel could not process this job.'}
                  </p>
                </div>
              )}

              {job?.status === 'COMPLETED' && job.result && (
                <>
                  <div className="quality-summary">
                    <div>
                      <span className="summary-label">Data quality</span>

                      <span
                        className={statusClass(job.result.status)}
                      >
                        {job.result.status}
                      </span>
                    </div>

                    <p>
                      {job.result.status === 'READY'
                        ? 'The dataset passed the contract checks.'
                        : 'The dataset contains issues that need attention.'}
                    </p>
                  </div>

                  <div className="metrics-grid">
                    <div className="metric-card">
                      <span>Total records</span>
                      <strong>{job.result.total_records}</strong>
                    </div>

                    <div className="metric-card">
                      <span>Valid records</span>
                      <strong>{job.result.valid_records}</strong>
                    </div>

                    <div className="metric-card">
                      <span>Invalid records</span>
                      <strong>{job.result.invalid_records}</strong>
                    </div>

                    <div className="metric-card">
                      <span>Issues detected</span>
                      <strong>{job.result.issues.length}</strong>
                    </div>
                  </div>

                  <div className="issues-section">
                    <div className="issues-heading">
                      <div>
                        <h3>Detected issues</h3>
                        <p>
                          Findings reported by the validation engine.
                        </p>
                      </div>

                      <span className="issue-count">
                        {job.result.issues.length}
                      </span>
                    </div>

                    {job.result.issues.length === 0 ? (
                      <div className="no-issues">
                        <span aria-hidden="true">✓</span>
                        <div>
                          <strong>No issues detected</strong>
                          <p>
                            The uploaded data passed all checks defined by
                            this contract.
                          </p>
                        </div>
                      </div>
                    ) : (
                      <div className="issues-table-wrapper">
                        <table className="issues-table">
                          <thead>
                            <tr>
                              <th>Row</th>
                              <th>Field</th>
                              <th>Issue code</th>
                              <th>Description</th>
                            </tr>
                          </thead>

                          <tbody>
                            {job.result.issues.map((issue, index) => (
                              <tr
                                key={`${issue.row}-${issue.field}-${issue.code}-${index}`}
                              >
                                <td>
                                  {issue.row ?? 'Dataset'}
                                </td>
                                <td>
                                  <code>{issue.field ?? '—'}</code>
                                </td>
                                <td>
                                  <span className="issue-code">
                                    {issue.code}
                                  </span>
                                </td>
                                <td>{issue.message}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>

                  <div className="job-timestamps">
                    <span>
                      Started: {formatTimestamp(job.started_at)}
                    </span>
                    <span>
                      Finished: {formatTimestamp(job.finished_at)}
                    </span>
                  </div>
                </>
              )}

              {job?.status === 'COMPLETED' && !job.result && (
                <div className="error-box job-failure" role="alert">
                  The job completed, but no validation report was returned.
                </div>
              )}
            </section>
          )}

          <footer className="page-footer">
            <span>Sentinel</span>
            <span>
              Automated Data Quality &amp; Integration Monitoring
            </span>
          </footer>
        </Show>
      </main>
    </div>
  )
}

export default App
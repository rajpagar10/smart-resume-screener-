import { useEffect, useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function formatSkills(skills) {
  return skills?.length ? skills.join(', ') : '—'
}

function App() {
  const [candidates, setCandidates] = useState([])
  const [jdText, setJdText] = useState('')
  const [jdFile, setJdFile] = useState(null)
  const [resumeFiles, setResumeFiles] = useState([])
  const [status, setStatus] = useState('Loading demo candidates…')
  const [busy, setBusy] = useState(false)

  async function loadCandidates() {
    const response = await fetch(`${API_URL}/candidates`)
    if (!response.ok) throw new Error('Could not load candidates.')
    const data = await response.json()
    setCandidates(data)
  }

  useEffect(() => {
    loadCandidates()
      .then(() => setStatus('Demo data is ready. Upload a role and resumes to run a live evaluation.'))
      .catch(() => setStatus('API unavailable. Start the FastAPI backend, then refresh.'))
  }, [])

  async function uploadJobDescription(event) {
    event.preventDefault()
    if (!jdFile && !jdText.trim()) {
      setStatus('Add pasted job-description text or choose a PDF/TXT file.')
      return
    }
    setBusy(true)
    try {
      const form = new FormData()
      if (jdFile) form.append('file', jdFile)
      else form.append('text', jdText.trim())
      const response = await fetch(`${API_URL}/upload-jd`, { method: 'POST', body: form })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Job description upload failed.')
      setStatus(`Job description saved (ID ${data.id}). Now upload resumes and evaluate.`)
      setJdText('')
      setJdFile(null)
      event.target.reset()
    } catch (error) {
      setStatus(error.message)
    } finally {
      setBusy(false)
    }
  }

  async function uploadResumes(event) {
    event.preventDefault()
    if (!resumeFiles.length) {
      setStatus('Choose one or more PDF/TXT resumes first.')
      return
    }
    setBusy(true)
    try {
      const form = new FormData()
      resumeFiles.forEach((file) => form.append('files', file))
      const response = await fetch(`${API_URL}/upload-resumes`, { method: 'POST', body: form })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Resume upload failed.')
      setStatus(`${data.uploaded} resume${data.uploaded === 1 ? '' : 's'} uploaded. Ready to evaluate.`)
      setResumeFiles([])
      event.target.reset()
    } catch (error) {
      setStatus(error.message)
    } finally {
      setBusy(false)
    }
  }

  async function evaluate() {
    setBusy(true)
    try {
      const response = await fetch(`${API_URL}/evaluate`, { method: 'POST' })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Evaluation failed.')
      await loadCandidates()
      setStatus(
        data.failed
          ? `${data.evaluated} evaluated; ${data.failed} failed: ${data.errors.join(' | ')}`
          : `${data.evaluated} candidate${data.evaluated === 1 ? '' : 's'} evaluated successfully.`,
      )
    } catch (error) {
      setStatus(error.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="app-shell">
      <header>
        <p className="eyebrow">Recruiting intelligence</p>
        <h1>Smart Resume Screener</h1>
        <p className="lede">Upload a role and a stack of resumes. Groq extracts structured evidence and ranks the best fits.</p>
      </header>

      <section className="upload-grid" aria-label="Upload controls">
        <form className="card" onSubmit={uploadJobDescription}>
          <h2>1. Add job description</h2>
          <label htmlFor="jd-text">Paste role details</label>
          <textarea id="jd-text" value={jdText} onChange={(event) => setJdText(event.target.value)} placeholder="Senior Backend Engineer…" disabled={busy || Boolean(jdFile)} />
          <label className="file-label" htmlFor="jd-file">or choose a PDF / TXT</label>
          <input id="jd-file" type="file" accept=".pdf,.txt" onChange={(event) => setJdFile(event.target.files?.[0] || null)} disabled={busy || Boolean(jdText)} />
          <button type="submit" disabled={busy}>Save job description</button>
        </form>

        <form className="card" onSubmit={uploadResumes}>
          <h2>2. Add resumes</h2>
          <p>Multiple PDF or UTF-8 TXT files are supported.</p>
          <input type="file" accept=".pdf,.txt" multiple onChange={(event) => setResumeFiles(Array.from(event.target.files || []))} disabled={busy} />
          <small>{resumeFiles.length ? `${resumeFiles.length} file(s) selected` : 'No files selected'}</small>
          <button type="submit" disabled={busy}>Upload resumes</button>
        </form>

        <section className="card evaluate-card">
          <h2>3. Evaluate</h2>
          <p>Runs structured extraction and Groq-powered matching for all stored resumes against the current role.</p>
          <button type="button" onClick={evaluate} disabled={busy}>Run evaluation</button>
          <p className="status" role="status">{status}</p>
        </section>
      </section>

      <section className="results" aria-live="polite">
        <div className="results-heading">
          <div>
            <p className="eyebrow">Ranked candidates</p>
            <h2>{candidates.length} evaluated candidate{candidates.length === 1 ? '' : 's'}</h2>
          </div>
          <span className="legend"><i /> Shortlisted at score 7+</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Candidate</th><th>Score</th><th>Matched skills</th><th>Missing skills</th><th>Recruiter rationale</th></tr>
            </thead>
            <tbody>
              {candidates.map((candidate) => (
                <tr className={candidate.shortlisted ? 'shortlisted' : ''} key={candidate.id}>
                  <td><strong>{candidate.name}</strong><br /><span>{candidate.email || 'No email extracted'}</span></td>
                  <td><span className={`score score-${candidate.score}`}>{candidate.score}/10</span></td>
                  <td>{formatSkills(candidate.matched_skills)}</td>
                  <td>{formatSkills(candidate.missing_skills)}</td>
                  <td>{candidate.justification}</td>
                </tr>
              ))}
              {!candidates.length && <tr><td colSpan="5" className="empty">No evaluated candidates for the current job description yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  )
}

export default App

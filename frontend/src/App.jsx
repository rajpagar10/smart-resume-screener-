import { useEffect, useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function formatSkills(skills) {
  return skills?.length ? skills : []
}

function SkillList({ skills, tone = 'neutral' }) {
  const values = formatSkills(skills)
  if (!values.length) return <span className="no-skills">—</span>

  return (
    <div className={`skill-list ${tone}`}>
      {values.map((skill) => <span className="skill-pill" key={skill}>{skill}</span>)}
    </div>
  )
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

  const shortlistedCount = candidates.filter((candidate) => candidate.shortlisted).length
  const averageScore = candidates.length
    ? (candidates.reduce((total, candidate) => total + candidate.score, 0) / candidates.length).toFixed(1)
    : '—'

  return (
    <main className="app-shell">
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow"><span className="pulse-dot" />Recruiting intelligence</p>
          <h1>Find the signal<br /><em>in every resume.</em></h1>
          <p className="lede">Upload a role and a stack of resumes. Claude turns unstructured experience into clear evidence and a defensible ranking.</p>
          <div className="hero-stats" aria-label="Candidate summary">
            <div><strong>{candidates.length}</strong><span>candidates ranked</span></div>
            <div><strong>{shortlistedCount}</strong><span>shortlist ready</span></div>
            <div><strong>{averageScore}</strong><span>average fit</span></div>
          </div>
        </div>
        <aside className="hero-panel" aria-label="AI workflow status">
          <div className="panel-topline"><span className="live-indicator" /> LIVE WORKSPACE</div>
          <div className="panel-orbit"><span>AI</span></div>
          <h2>Candidate clarity,<br />in one workflow.</h2>
          <p>Claude Sonnet 4.6 extracts details, compares requirements, and explains every score.</p>
          <div className="panel-footer"><span>Structured</span><span>Explainable</span><span>Ranked</span></div>
        </aside>
      </header>

      <section className="upload-grid" aria-label="Upload controls">
        <form className="card" onSubmit={uploadJobDescription}>
          <span className="step-number">01</span>
          <h2>Add job description</h2>
          <label htmlFor="jd-text">Paste role details</label>
          <textarea id="jd-text" value={jdText} onChange={(event) => setJdText(event.target.value)} placeholder="Senior Backend Engineer…" disabled={busy || Boolean(jdFile)} />
          <label className="file-label" htmlFor="jd-file">or choose a PDF / TXT</label>
          <input id="jd-file" type="file" accept=".pdf,.txt" onChange={(event) => setJdFile(event.target.files?.[0] || null)} disabled={busy || Boolean(jdText)} />
          <button type="submit" disabled={busy}>Save job description</button>
        </form>

        <form className="card" onSubmit={uploadResumes}>
          <span className="step-number">02</span>
          <h2>Add resumes</h2>
          <p>Multiple PDF or UTF-8 TXT files are supported.</p>
          <input type="file" accept=".pdf,.txt" multiple onChange={(event) => setResumeFiles(Array.from(event.target.files || []))} disabled={busy} />
          <small>{resumeFiles.length ? `${resumeFiles.length} file(s) selected` : 'No files selected'}</small>
          <button type="submit" disabled={busy}>Upload resumes</button>
        </form>

        <section className="card evaluate-card">
          <span className="step-number">03</span>
          <h2>Evaluate and rank</h2>
          <p>Runs Claude extraction and matching for every stored resume against the current role.</p>
          <button className="evaluate-button" type="button" onClick={evaluate} disabled={busy}>{busy ? 'Working…' : 'Run evaluation'} <span aria-hidden="true">→</span></button>
          <p className="status" role="status">{status}</p>
        </section>
      </section>

      <section className="results" aria-live="polite">
        <div className="results-heading">
          <div>
            <p className="eyebrow">Ranked candidates</p>
            <h2>{candidates.length} evaluated candidate{candidates.length === 1 ? '' : 's'}</h2>
          </div>
          <span className="legend"><i /> Score 7+ is shortlist-ready</span>
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
                  <td><span className={`score score-${candidate.score}`}><b>{candidate.score}</b><small>/10</small></span></td>
                  <td><SkillList skills={candidate.matched_skills} tone="matched" /></td>
                  <td><SkillList skills={candidate.missing_skills} tone="missing" /></td>
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

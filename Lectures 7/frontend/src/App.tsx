import { useEffect, useMemo, useState } from 'react'
import './App.css'
import { fetchCourses, fetchHealth, type Course } from './api'
import ChatPanel from './components/ChatPanel'
import CourseCard from './components/CourseCard'
import CourseModal from './components/CourseModal'
import { SearchIcon } from './components/Icons'

const QUICK_FILTERS = ['Core', 'Finance', 'Marketing', 'Economics', 'Operations']

export default function App() {
  // Keep the query each result belongs to, so "loading" is derived rather than a
  // second piece of state flipped from inside the effect.
  const [data, setData] = useState<{ q: string; rows: Course[] } | null>(null)
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const [error, setError] = useState<{ q: string; message: string } | null>(null)
  const [online, setOnline] = useState<boolean | null>(null)
  const [selected, setSelected] = useState<Course | null>(null)

  const courses = data?.rows ?? []
  const settled = data?.q === debounced || error?.q === debounced
  const loading = !settled

  // Debounce so typing doesn't fire a request per keystroke.
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query), 260)
    return () => clearTimeout(t)
  }, [query])

  useEffect(() => {
    const ctrl = new AbortController()
    fetchHealth(ctrl.signal).then(setOnline)
    return () => ctrl.abort()
  }, [])

  useEffect(() => {
    const ctrl = new AbortController()
    const q = debounced
    fetchCourses(q, ctrl.signal)
      .then((rows) => {
        setData({ q, rows })
        setError(null)
      })
      .catch((err: unknown) => {
        if (ctrl.signal.aborted) return
        setError({
          q,
          message: `Could not load courses — ${
            err instanceof Error ? err.message : String(err)
          }. Is the backend running on port 8000?`,
        })
        setData({ q, rows: [] })
      })
    return () => ctrl.abort()
  }, [debounced])

  const activeFilter = useMemo(
    () => QUICK_FILTERS.find((f) => f.toLowerCase() === query.toLowerCase()) ?? null,
    [query],
  )

  return (
    <div className="app">
      <header className="masthead">
        <div className="masthead__inner">
          <span className="bell" aria-hidden="true" />
          <div>
            <h1 className="masthead__title">Yale SOM Course Explorer</h1>
            <p className="masthead__sub">234 courses · fall term · ask anything</p>
          </div>
          <span className="masthead__spacer" />
          <span className="pill-count">
            {loading ? '…' : `${courses.length} shown`}
          </span>
          <span
            className={`status ${
              online === null ? '' : online ? 'status--up' : 'status--down'
            }`}
          >
            <span className="status__dot" />
            {online === null ? 'checking' : online ? 'API up' : 'API down'}
          </span>
        </div>
      </header>

      <main className="layout">
        <section>
          <div className="toolbar">
            <div className="search">
              <span className="search__icon">
                <SearchIcon />
              </span>
              <input
                className="search__input"
                placeholder="Search by title, number, instructor, topic…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                aria-label="Search courses"
              />
              {query && (
                <button
                  className="search__clear"
                  onClick={() => setQuery('')}
                  aria-label="Clear search"
                >
                  ×
                </button>
              )}
            </div>
            <div className="chips">
              {QUICK_FILTERS.map((f) => (
                <button
                  key={f}
                  className="chip"
                  aria-pressed={activeFilter === f}
                  onClick={() => setQuery(activeFilter === f ? '' : f)}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          {error && <div className="banner-error">{error.message}</div>}

          {loading ? (
            <div className="grid">
              {Array.from({ length: 6 }, (_, i) => (
                <div key={i} className="skeleton" />
              ))}
            </div>
          ) : courses.length === 0 && !error ? (
            <div className="empty">
              <strong>No courses matched “{debounced}”</strong>
              Try a broader term — an instructor's last name, or a topic like
              “finance”.
            </div>
          ) : (
            <div className="grid">
              {courses.map((c) => (
                <CourseCard key={c.key} course={c} onOpen={setSelected} />
              ))}
            </div>
          )}
        </section>

        <ChatPanel />
      </main>

      <footer className="footer">
        MGT 409 · Lecture 7 · FastAPI + pydantic-ai + React
      </footer>

      {selected && (
        <CourseModal course={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}

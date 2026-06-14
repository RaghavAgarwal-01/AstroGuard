import { useState, useEffect } from 'react'
import Globe from './components/Globe'
import { fetchSatellites, runAnalysis, fetchAISummary } from './api/astroguard'

export default function App() {
  const [satellites, setSatellites] = useState([])
  const [events, setEvents] = useState([])
  const [selectedEvent, setSelectedEvent] = useState(null)
  const [loading, setLoading] = useState(false)
  const [aiSummary, setAiSummary] = useState('')
  const [summaryLoading, setSummaryLoading] = useState(false)

  useEffect(() => {
    fetchSatellites().then(setSatellites)
  }, [])

  async function handleRunAnalysis() {
    setLoading(true)
    setSelectedEvent(null)
    setAiSummary('')
    try {
      const data = await runAnalysis()
      setEvents(data)
    } catch (err) {
      console.error('Analysis failed:', err)
    } finally {
      setLoading(false)
    }
  }

  async function selectEvent(ev) {
    setSelectedEvent(ev)
    setAiSummary('')
    setSummaryLoading(true)
    try {
      const data = await fetchAISummary(ev.id)
      setAiSummary(data.summary)
    } catch (err) {
      setAiSummary('Summary unavailable.')
    } finally {
      setSummaryLoading(false)
    }
  }

  function getRiskColor(dist) {
    if (dist < 5) return '#ef4444'
    if (dist < 15) return '#f97316'
    return '#eab308'
  }

  function getRiskLabel(dist) {
    if (dist < 5) return 'CRITICAL'
    if (dist < 15) return 'HIGH'
    return 'MODERATE'
  }

  return (
    <div style={{ width: '100vw', height: '100vh', background: '#0a0a1a', display: 'flex', flexDirection: 'column' }}>

      {/* Top bar */}
      <div style={{
        height: 52, padding: '0 20px', display: 'flex', alignItems: 'center', gap: 12,
        background: 'rgba(10,10,26,0.95)', borderBottom: '1px solid #1e293b', flexShrink: 0, zIndex: 10
      }}>
        <span style={{ color: 'white', fontWeight: 700, fontSize: 18 }}>🛰 AstroGuard</span>
        <button
          onClick={handleRunAnalysis}
          disabled={loading}
          style={{
            marginLeft: 16, padding: '6px 18px', background: loading ? '#1e40af' : '#2563eb',
            color: 'white', border: 'none', borderRadius: 6,
            cursor: loading ? 'not-allowed' : 'pointer', fontSize: 13, fontWeight: 500
          }}
        >
          {loading ? '⏳ Analyzing...' : 'Run Analysis'}
        </button>
        {events.length > 0 && (
          <span style={{ color: '#4ade80', fontSize: 13, marginLeft: 8 }}>
            ✓ {events.length} conjunction events detected
          </span>
        )}
      </div>

      {/* Main content */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

        {/* Globe */}
        <div style={{ flex: 1 }}>
          <Globe
            satellites={satellites}
            events={events}
            selectedEvent={selectedEvent}
          />
        </div>

        {/* Side panel */}
        <div style={{
          width: 320, background: '#0f172a', borderLeft: '1px solid #1e293b',
          display: 'flex', flexDirection: 'column', overflow: 'hidden'
        }}>
          <div style={{ padding: '14px 16px', borderBottom: '1px solid #1e293b' }}>
            <div style={{ color: '#94a3b8', fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              Conjunction Events
            </div>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
            {events.length === 0 ? (
              <div style={{ color: '#475569', fontSize: 13, textAlign: 'center', marginTop: 40 }}>
                Click "Run Analysis" to detect close-approach events
              </div>
            ) : (
              events
                .slice()
                .sort((a, b) => a.min_dist_km - b.min_dist_km)
                .map(ev => (
                  <div
                    key={ev.id}
                    onClick={() => selectEvent(ev)}
                    style={{
                      padding: 12, marginBottom: 8, borderRadius: 8, cursor: 'pointer',
                      background: selectedEvent?.id === ev.id ? '#1e293b' : '#111827',
                      border: `1px solid ${selectedEvent?.id === ev.id ? '#334155' : '#1e293b'}`,
                      transition: 'background 0.15s'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span style={{
                        fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 4,
                        background: getRiskColor(ev.min_dist_km) + '22',
                        color: getRiskColor(ev.min_dist_km), letterSpacing: '0.05em'
                      }}>
                        {getRiskLabel(ev.min_dist_km)}
                      </span>
                      <span style={{ color: getRiskColor(ev.min_dist_km), fontSize: 12, fontWeight: 600 }}>
                        {ev.min_dist_km} km
                      </span>
                    </div>
                    <div style={{ color: '#e2e8f0', fontSize: 13, fontWeight: 500, marginBottom: 3 }}>
                      {ev.obj_a} ↔ {ev.obj_b}
                    </div>
                    <div style={{ color: '#64748b', fontSize: 11 }}>
                      {new Date(ev.closest_time).toUTCString().replace('GMT', 'UTC')}
                    </div>
                    <div style={{ color: '#475569', fontSize: 11, marginTop: 2 }}>
                      Relative velocity: {ev.rel_velocity_kms} km/s
                    </div>
                  </div>
                ))
            )}

            {/* AI Risk Briefing */}
            {selectedEvent && (
              <div style={{
                marginTop: 12, padding: 12, borderRadius: 8,
                background: '#0f0a1e', border: '1px solid #4c1d95'
              }}>
                <div style={{
                  color: '#a78bfa', fontSize: 11, fontWeight: 600,
                  letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 8
                }}>
                  ✦ AI Risk Briefing
                </div>
                {summaryLoading
                  ? <div style={{ color: '#6d28d9', fontSize: 13 }}>Generating summary...</div>
                  : <div style={{ color: '#c4b5fd', fontSize: 13, lineHeight: 1.6 }}>{aiSummary}</div>
                }
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
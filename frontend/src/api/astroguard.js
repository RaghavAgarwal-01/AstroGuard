const BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  "https://astroguard-pljt.onrender.com"
console.log("BASE_URL =", BASE_URL)

const USE_MOCK = false

import { mockSatellites, mockEvents } from '../data/mockData'

const mockSummaries = {
  0: "At 18:32 UTC, ISS will pass within 4.2 km of Cosmos debris fragment 1274 at a closing speed of 7.1 km/s. Given the proximity and high relative velocity, this event warrants immediate flagging for maneuver review by flight operations.",
  1: "Starlink-1 and Debris-807 are projected to approach within 11.8 km at 21:15 UTC with a relative velocity of 5.3 km/s. Risk is moderate — recommend continued monitoring and preparation of contingency maneuver parameters."
}

export async function fetchSatellites() {
  if (USE_MOCK) {
    await delay(300)
    return mockSatellites
  }
  const res = await fetch(`${BASE_URL}/api/objects`)
  return res.json()
}

export async function runAnalysis() {
  if (USE_MOCK) {
    await delay(1500)
    return mockEvents
  }
  const res = await fetch(`${BASE_URL}/api/run-analysis?threshold_km=50`, { method: 'POST' })
  return res.json()
}

export async function fetchAISummary(eventId) {
  if (USE_MOCK) {
    await delay(1000)
    return { summary: mockSummaries[eventId] || "Risk summary unavailable." }
  }
  const res = await fetch(`${BASE_URL}/api/ai-summary/${eventId}`)
  return res.json()
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}  
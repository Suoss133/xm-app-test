import http from './http'

export const getHealth = () => http.get('/api/health')
export const getDevices = () => http.get('/api/devices')
export const getSuites = () => http.get('/api/suites')
export const getSuite = (name) => http.get(`/api/suites/${name}`)
export const updateSuite = (name, body) => http.put(`/api/suites/${name}`, body)

export const createJob = (body) => http.post('/api/jobs', body)
export const getJob = (id) => http.get(`/api/jobs/${id}`)
export const listJobs = (limit = 50) => http.get('/api/jobs', { params: { limit } })
export const stopJob = (id) => http.post(`/api/jobs/${id}/stop`)
export const runPipeline = (body) => http.post('/api/jobs/pipeline', body)
export const jobsSummary = () => http.get('/api/meta/jobs-summary')
export const getReports = () => http.get('/api/reports')
export const getJobLogs = (id) => http.get(`/api/jobs/${id}/logs`)

export function jobLogWsUrl(jobId) {
  const base = import.meta.env.VITE_API_BASE || window.location.origin
  const wsBase = base.replace(/^http/, 'ws')
  return `${wsBase}/ws/jobs/${jobId}`
}
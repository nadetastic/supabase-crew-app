// Supabase page for Kiro Crew.
// Shows your Supabase organizations and projects. The data comes from the
// app backend (/api/apps/supabase), which a background agent fills using the
// hosted Supabase MCP server. This page never talks to Supabase directly.
import { useState, useEffect, useCallback, useRef } from 'react'
import { jsx as h, jsxs as hs } from 'react/jsx-runtime'

const API = '/api/apps/supabase'
const POLL_MS = 3000

async function api(path, opts) {
  const r = await fetch(API + path, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  let body = null
  try { body = await r.json() } catch { /* empty body */ }
  if (!r.ok && r.status !== 202) {
    const msg = (body && (typeof body.error === 'string' ? body.error : body.error?.message)) || `Request failed (${r.status})`
    throw new Error(msg)
  }
  return body || {}
}

const S = {
  page: { padding: '24px', maxWidth: '1100px', margin: '0 auto', color: 'var(--text)', background: 'var(--bg)', fontFamily: 'var(--font-body, inherit)' },
  header: { display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' },
  title: { fontSize: '20px', fontWeight: 600, color: 'var(--text-strong, var(--text))', margin: 0 },
  muted: { color: 'var(--muted)', fontSize: '13px' },
  spacer: { flex: 1 },
  button: (disabled) => ({
    padding: '6px 14px', borderRadius: 'var(--radius-md, 8px)', border: '1px solid var(--accent)',
    background: 'var(--accent)', color: 'var(--accent-fg)', cursor: disabled ? 'default' : 'pointer',
    opacity: disabled ? 0.6 : 1, fontSize: '13px', fontWeight: 500,
  }),
  banner: (kind) => ({
    padding: '10px 14px', borderRadius: 'var(--radius-md, 8px)', marginBottom: '16px', fontSize: '13px',
    background: kind === 'error' ? 'var(--danger-subtle)' : 'var(--accent-subtle)',
    color: kind === 'error' ? 'var(--danger)' : 'var(--text)',
    border: `1px solid ${kind === 'error' ? 'var(--danger)' : 'var(--border)'}`,
  }),
  stats: { display: 'flex', gap: '12px', marginBottom: '20px', flexWrap: 'wrap' },
  stat: { padding: '12px 16px', borderRadius: 'var(--radius-md, 8px)', background: 'var(--card)', color: 'var(--text)', border: '1px solid var(--border)', minWidth: '140px' },
  statNum: { fontSize: '22px', fontWeight: 600 },
  card: { borderRadius: 'var(--radius-md, 8px)', background: 'var(--card)', color: 'var(--text)', border: '1px solid var(--border)', marginBottom: '16px', overflow: 'hidden' },
  cardHead: { padding: '12px 16px', borderBottom: '1px solid var(--border)', fontWeight: 600, display: 'flex', gap: '8px', alignItems: 'baseline' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '13px' },
  th: { textAlign: 'left', padding: '8px 16px', color: 'var(--muted)', fontWeight: 500, borderBottom: '1px solid var(--border)' },
  td: { padding: '8px 16px', borderBottom: '1px solid var(--border)', verticalAlign: 'top' },
  link: { color: 'var(--accent)', textDecoration: 'none' },
  pill: (ok) => ({
    display: 'inline-block', padding: '1px 8px', borderRadius: '999px', fontSize: '12px',
    background: ok ? 'var(--ok-subtle)' : 'var(--warn-subtle)', color: ok ? 'var(--ok)' : 'var(--warn)',
  }),
  empty: { padding: '40px 16px', textAlign: 'center', color: 'var(--muted)' },
}

function timeAgo(iso) {
  if (!iso) return ''
  const s = Math.max(0, (Date.now() - Date.parse(iso)) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.round(s / 60)} min ago`
  if (s < 86400) return `${Math.round(s / 3600)} h ago`
  return new Date(iso).toLocaleString()
}

function statusLabel(status) {
  return (status || 'UNKNOWN').replace(/_/g, ' ').toLowerCase()
}

function TablesCell({ tables }) {
  const [open, setOpen] = useState(false)
  if (!Array.isArray(tables)) return h('span', { style: S.muted, children: '—' })
  if (tables.length === 0) return h('span', { style: S.muted, children: 'none' })
  return hs('div', {
    children: [
      h('a', {
        href: '#', style: S.link,
        onClick: (e) => { e.preventDefault(); setOpen(!open) },
        children: `${tables.length} table${tables.length === 1 ? '' : 's'}`,
      }),
      open ? h('div', { style: { ...S.muted, marginTop: '4px' }, children: tables.join(', ') }) : null,
    ],
  })
}

function ProjectRow({ p }) {
  const healthy = p.status === 'ACTIVE_HEALTHY'
  return hs('tr', {
    children: [
      h('td', { style: S.td, children: hs('div', { children: [
        h('div', { style: { fontWeight: 500 }, children: p.name }),
        h('div', { style: S.muted, children: p.id }),
      ] }) }),
      h('td', { style: S.td, children: p.region || '—' }),
      h('td', { style: S.td, children: h('span', { style: S.pill(healthy), children: statusLabel(p.status) }) }),
      h('td', { style: S.td, children: h(TablesCell, { tables: p.tables }) }),
      h('td', { style: S.td, children: h('a', {
        href: `https://supabase.com/dashboard/project/${encodeURIComponent(p.id)}`,
        target: '_blank', rel: 'noopener noreferrer', style: S.link, children: 'Open',
      }) }),
    ],
  })
}

function OrgCard({ org, projects }) {
  return hs('div', {
    style: S.card,
    children: [
      hs('div', { style: S.cardHead, children: [
        h('span', { children: org.name }),
        h('span', { style: S.muted, children: `${projects.length} project${projects.length === 1 ? '' : 's'}` }),
      ] }),
      projects.length === 0
        ? h('div', { style: { ...S.empty, padding: '16px' }, children: 'No projects in this organization.' })
        : h('table', { style: S.table, children: [
            h('thead', { key: 'h', children: hs('tr', { children: ['Project', 'Region', 'Status', 'Public tables', ''].map((t) => h('th', { style: S.th, children: t }, t)) }) }),
            h('tbody', { key: 'b', children: projects.map((p) => h(ProjectRow, { p }, p.id)) }),
          ] }),
    ],
  })
}

export default function SupabaseApp() {
  const [data, setData] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [starting, setStarting] = useState(false)
  const timer = useRef(null)

  const load = useCallback(async () => {
    try {
      const d = await api('/overview')
      setData(d)
      setLoadError('')
      return d
    } catch (e) {
      setLoadError(e.message)
      return null
    }
  }, [])

  // Poll while a refresh is running.
  useEffect(() => {
    load()
    return () => clearTimeout(timer.current)
  }, [load])
  useEffect(() => {
    clearTimeout(timer.current)
    if (data?.refreshing) timer.current = setTimeout(load, POLL_MS)
  }, [data, load])

  const refresh = async () => {
    setStarting(true)
    try {
      await api('/refresh', { method: 'POST', body: '{}' })
      await load()
    } catch (e) {
      setLoadError(e.message)
    } finally {
      setStarting(false)
    }
  }

  const ov = data?.overview
  const refreshing = starting || !!data?.refreshing
  const orgs = ov?.organizations || []
  const projects = ov?.projects || []
  const known = new Set(orgs.map((o) => o.id))
  const orphans = projects.filter((p) => !known.has(p.organization_id))
  const groups = orgs.map((o) => ({ org: o, projects: projects.filter((p) => p.organization_id === o.id) }))
  if (orphans.length) groups.push({ org: { id: '_other', name: 'Other projects' }, projects: orphans })
  const tableCount = projects.reduce((n, p) => n + (Array.isArray(p.tables) ? p.tables.length : 0), 0)

  const children = [
    hs('div', { key: 'head', style: S.header, children: [
      h('h1', { style: S.title, children: 'Supabase' }),
      ov?.updated_at ? h('span', { style: S.muted, children: `Updated ${timeAgo(ov.updated_at)}` }) : null,
      h('div', { style: S.spacer }),
      h('button', { style: S.button(refreshing), disabled: refreshing, onClick: refresh, children: refreshing ? 'Refreshing…' : 'Refresh' }),
    ] }),
  ]

  if (refreshing) children.push(h('div', { key: 'busy', style: S.banner('info'), children: 'An agent is reading your Supabase account. This takes about 10 to 30 seconds.' }))
  if (loadError) children.push(h('div', { key: 'le', style: S.banner('error'), children: loadError }))
  if (data?.refresh_error) children.push(h('div', { key: 're', style: S.banner('error'), children: data.refresh_error }))
  if (ov?.error) children.push(h('div', { key: 'oe', style: S.banner('error'), children: `Last refresh: ${ov.error}. If Supabase needs sign-in, ask the supabase agent in a chat to "list my Supabase projects" once, then refresh here.` }))

  if (!ov && data && !refreshing) {
    children.push(h('div', { key: 'empty', style: { ...S.card, ...S.empty }, children: 'No data yet. Select Refresh to load your organizations and projects.' }))
  } else if (ov && !ov.error) {
    children.push(hs('div', { key: 'stats', style: S.stats, children: [
      ['Organizations', orgs.length], ['Projects', projects.length], ['Public tables', tableCount],
    ].map(([label, n]) => hs('div', { style: S.stat, children: [
      h('div', { style: S.statNum, children: n }), h('div', { style: S.muted, children: label }),
    ] }, label)) }))
    if (groups.length === 0) children.push(h('div', { key: 'none', style: { ...S.card, ...S.empty }, children: 'No organizations found on this Supabase account.' }))
    for (const g of groups) children.push(h(OrgCard, { org: g.org, projects: g.projects }, g.org.id))
  }

  return h('div', { style: S.page, children })
}

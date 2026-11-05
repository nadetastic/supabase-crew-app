// Supabase page for Kiro Crew.
// Shows your Supabase organizations and projects. The data comes from the
// app backend (/api/apps/supabase), which reads Supabase with the
// app backend's own Supabase OAuth sign-in. Tokens never reach this page.
import { useState, useEffect, useCallback, useRef } from 'react'
import { jsx as h, jsxs as hs } from 'react/jsx-runtime'

const API = '/api/apps/supabase'

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
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')  // '', 'refresh', 'signin', 'signout'
  const [notice, setNotice] = useState('')

  const load = useCallback(async () => {
    try {
      const d = await api('/status')
      setData(d)
      setError('')
      return d
    } catch (e) {
      setError(e.message)
      return null
    }
  }, [])

  const refresh = useCallback(async () => {
    setBusy('refresh')
    try {
      const d = await api('/refresh', { method: 'POST', body: '{}' })
      setData(d)
      setError('')
    } catch (e) {
      setError(e.message)
      load()
    } finally {
      setBusy('')
    }
  }, [load])

  // On load, read the result of a sign-in redirect (?supabase=...), then tidy the URL.
  const first = useRef(true)
  useEffect(() => {
    if (!first.current) return
    first.current = false
    const params = new URLSearchParams(window.location.search)
    const result = params.get('supabase')
    if (result) {
      params.delete('supabase')
      const qs = params.toString()
      window.history.replaceState(null, '', window.location.pathname + (qs ? '?' + qs : '') + window.location.hash)
    }
    if (result === 'denied') setNotice('Supabase sign-in was canceled.')
    if (result === 'failed') setError('Supabase sign-in did not finish. Try again.')
    load().then((d) => {
      if (result === 'connected' && d?.connected) refresh()
    })
  }, [load, refresh])

  // Wait until the popup reports back, or /status shows we are signed in.
  const waitForSignIn = (popup) => new Promise((resolve) => {
    let done = false
    let checking = false
    const finish = (result) => {
      if (done) return
      done = true
      window.removeEventListener('message', onMessage)
      clearInterval(poll)
      clearTimeout(timeout)
      resolve(result)
    }
    const signedIn = async () => {
      if (checking) return false
      checking = true
      try { return !!(await api('/status'))?.connected } catch { return false } finally { checking = false }
    }
    const onMessage = (event) => {
      if (event.origin !== window.location.origin) return
      if (event.data?.type !== 'supabase-oauth-complete') return
      finish(event.data.result)
    }
    window.addEventListener('message', onMessage)
    const poll = setInterval(async () => {
      if (await signedIn()) { finish('connected'); return }
      if (popup && popup.closed) finish((await signedIn()) ? 'connected' : 'closed')
    }, 1000)
    const timeout = setTimeout(() => finish('timeout'), 5 * 60 * 1000)
  })

  const signIn = async () => {
    // Open the window first, inside the click, so it is not blocked as a popup.
    const popup = window.open('about:blank', 'supabase-oauth-' + Date.now(), 'popup=yes,width=560,height=760')
    if (!popup) {
      setError('The sign-in window was blocked. Allow popups for Kiro Crew and try again.')
      return
    }
    setBusy('signin')
    setError('')
    setNotice('')
    try {
      const d = await api('/oauth/start', {
        method: 'POST',
        body: JSON.stringify({ origin: window.location.origin, return_to: window.location.pathname }),
      })
      if (!d?.authorizationUrl) throw new Error('Supabase returned no sign-in link.')
      popup.location.replace(d.authorizationUrl)
      const result = await waitForSignIn(popup)
      try { popup.close() } catch { /* already closed */ }
      if (result === 'connected') {
        await load()
        await refresh()
      } else if (result === 'denied') {
        setNotice('Supabase sign-in was canceled.')
      } else if (result === 'closed') {
        setNotice('The sign-in window was closed before it finished.')
      } else {
        setError(result === 'timeout' ? 'Supabase sign-in timed out. Try again.' : 'Supabase sign-in did not finish. Try again.')
      }
    } catch (e) {
      try { popup.close() } catch { /* already closed */ }
      setError(e.message)
    } finally {
      setBusy((b) => (b === 'signin' ? '' : b))
    }
  }

  const signOut = async () => {
    setBusy('signout')
    try {
      setData(await api('/oauth/disconnect', { method: 'POST', body: '{}' }))
      setNotice('Signed out of Supabase.')
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy('')
    }
  }

  const connected = !!data?.connected
  const ov = data?.overview
  const orgs = ov?.organizations || []
  const projects = ov?.projects || []
  const known = new Set(orgs.map((o) => o.id))
  const orphans = projects.filter((p) => !known.has(p.organization_id))
  const groups = orgs.map((o) => ({ org: o, projects: projects.filter((p) => p.organization_id === o.id) }))
  if (orphans.length) groups.push({ org: { id: '_other', name: 'Other projects' }, projects: orphans })
  const tableCount = projects.reduce((n, p) => n + (Array.isArray(p.tables) ? p.tables.length : 0), 0)
  const ghost = { ...S.button(!!busy), background: 'transparent', color: 'var(--text)', border: '1px solid var(--border)' }

  const head = [
    h('h1', { key: 't', style: S.title, children: 'Supabase' }),
    ov?.updated_at ? h('span', { key: 'u', style: S.muted, children: `Updated ${timeAgo(ov.updated_at)}` }) : null,
    h('div', { key: 's', style: S.spacer }),
  ]
  if (connected) {
    head.push(h('button', { key: 'r', style: S.button(!!busy), disabled: !!busy, onClick: refresh, children: busy === 'refresh' ? 'Refreshing…' : 'Refresh' }))
    head.push(h('button', { key: 'o', style: ghost, disabled: !!busy, onClick: signOut, children: 'Sign out' }))
  }
  const children = [hs('div', { key: 'head', style: S.header, children: head })]

  if (notice) children.push(h('div', { key: 'n', style: S.banner('info'), children: notice }))
  if (error) children.push(h('div', { key: 'e', style: S.banner('error'), children: error }))

  if (!data) {
    if (!error) children.push(h('div', { key: 'l', style: { ...S.card, ...S.empty }, children: 'Loading…' }))
  } else if (!connected) {
    children.push(hs('div', { key: 'signin', style: { ...S.card, ...S.empty }, children: [
      h('div', { style: { color: 'var(--text)', fontSize: '15px', fontWeight: 500, marginBottom: '6px' }, children: 'Sign in to see your Supabase organizations and projects' }),
      h('div', { style: { marginBottom: '16px' }, children: 'You will go to Supabase to approve read access, then come back here.' }),
      h('button', { style: S.button(!!busy), disabled: !!busy, onClick: signIn, children: busy === 'signin' ? 'Waiting for Supabase…' : 'Sign in with Supabase' }),
    ] }))
  } else if (!ov) {
    children.push(h('div', { key: 'empty', style: { ...S.card, ...S.empty }, children: busy === 'refresh' ? 'Reading your Supabase account…' : 'Signed in. Select Refresh to load your organizations and projects.' }))
  } else {
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

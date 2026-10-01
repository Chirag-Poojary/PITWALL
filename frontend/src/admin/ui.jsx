import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react'

export const AdminCtx = createContext(null)
export const useAdmin = () => useContext(AdminCtx)

export function PageHeader({ title, desc, children }) {
  return (
    <div className="a-head">
      <div>
        <h1>{title}</h1>
        {desc && <p>{desc}</p>}
      </div>
      {children && <div className="a-head-tools">{children}</div>}
    </div>
  )
}

export function Card({ title, sub, children, span = 1, tools, className = '' }) {
  return (
    <section className={`a-card span-${span} ${className}`}>
      {(title || tools) && (
        <header>
          <div><h3>{title}</h3>{sub && <p>{sub}</p>}</div>
          {tools}
        </header>
      )}
      <div className="a-card-body">{children}</div>
    </section>
  )
}

export function Kpis({ items }) {
  return (
    <div className="a-kpis">
      {items.map(([label, value, hint]) => (
        <div key={label} className="a-kpi"><span>{label}</span><b>{value}</b>{hint && <small>{hint}</small>}</div>
      ))}
    </div>
  )
}

export function Field({ label, children }) {
  return <label className="a-field"><span>{label}</span>{children}</label>
}

export function MultiSelect({ options, value, onChange, placeholder = 'Select…', max = 6, labelKey = 'name', idKey = 'id', sub }) {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const ref = useRef(null)
  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  const byId = useMemo(() => new Map(options.map((o) => [o[idKey], o])), [options, idKey])
  const shown = options.filter((o) => !q || String(o[labelKey]).toLowerCase().includes(q.toLowerCase())).slice(0, 80)
  const toggle = (id) => onChange(value.includes(id) ? value.filter((v) => v !== id) : value.length >= max ? value : [...value, id])
  return (
    <div className="a-ms" ref={ref}>
      <div className="a-ms-box" onClick={() => setOpen(true)}>
        {value.map((id) => (
          <span key={id} className="a-tag">{byId.get(id)?.[labelKey] ?? id}<button onClick={(e) => { e.stopPropagation(); toggle(id) }}>×</button></span>
        ))}
        <input value={q} onChange={(e) => { setQ(e.target.value); setOpen(true) }} placeholder={value.length ? '' : placeholder} />
      </div>
      {open && (
        <div className="a-ms-list">
          {shown.map((o) => (
            <button key={o[idKey]} className={value.includes(o[idKey]) ? 'on' : ''} onClick={() => toggle(o[idKey])}>
              <span>{o[labelKey]}</span>{sub && <small>{sub(o)}</small>}
            </button>
          ))}
          {!shown.length && <div className="a-empty">No matches</div>}
        </div>
      )}
    </div>
  )
}

export function Table({ columns, rows, maxHeight = 420, dense, onRowClick, rowClass }) {
  const [sort, setSort] = useState(null)
  const sorted = useMemo(() => {
    if (!sort) return rows
    const { key, dir } = sort
    return [...rows].sort((a, b) => {
      const x = a[key], y = b[key]
      if (x === y) return 0
      if (x === null || x === undefined) return 1
      if (y === null || y === undefined) return -1
      return (x > y ? 1 : -1) * dir
    })
  }, [rows, sort])
  return (
    <div className="a-table-wrap" style={{ maxHeight }}>
      <table className={`a-table ${dense ? 'dense' : ''}`}>
        <thead>
          <tr>{columns.map((c) => (
            <th key={c.key} className={c.num ? 'num' : ''} onClick={() => setSort((s) => ({ key: c.key, dir: s?.key === c.key ? -s.dir : (c.num ? -1 : 1) }))}>
              {c.label}{sort?.key === c.key ? (sort.dir > 0 ? ' ▲' : ' ▼') : ''}
            </th>
          ))}</tr>
        </thead>
        <tbody>
          {sorted.map((r, i) => (
            <tr key={i} onClick={onRowClick ? () => onRowClick(r) : undefined} className={`${onRowClick ? 'click' : ''} ${rowClass ? rowClass(r) : ''}`}>
              {columns.map((c) => <td key={c.key} className={c.num ? 'num' : ''}>{c.render ? c.render(r[c.key], r) : r[c.key] ?? '–'}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Segmented({ value, onChange, items }) {
  return (
    <div className="a-seg">
      {items.map(([k, l]) => <button key={k} className={value === k ? 'on' : ''} onClick={() => onChange(k)}>{l}</button>)}
    </div>
  )
}

export function Note({ children }) {
  return <p className="a-note">{children}</p>
}

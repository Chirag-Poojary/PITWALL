// Approximate livery colours for well-known constructors (used as chart / card accents).
const TEAM_COLORS = {
  'Red Bull': '#3671C6', Ferrari: '#E8002D', Mercedes: '#00A19C', McLaren: '#FF8000',
  'Aston Martin': '#229971', 'Alpine F1 Team': '#0093CC', Alpine: '#0093CC', Williams: '#1868DB',
  'RB F1 Team': '#6692FF', AlphaTauri: '#5E8FAA', 'Toro Rosso': '#469BFF', 'Haas F1 Team': '#9AA0A6',
  Haas: '#9AA0A6', Sauber: '#52E252', 'Kick Sauber': '#52E252', 'Alfa Romeo': '#C92D4B', Renault: '#FFD800',
  'Racing Point': '#F596C8', 'Force India': '#FF80C7', Lotus: '#B8860B', 'Lotus F1': '#B8860B',
  'Team Lotus': '#2E6B30', Brawn: '#B8FD6E', 'BMW Sauber': '#6CA0DC', Toyota: '#CC0000', Honda: '#E6E6E6',
  BAR: '#B0B0B0', Jaguar: '#0B6E4F', Jordan: '#F2C200', Minardi: '#333333', Benetton: '#00A651',
  Tyrrell: '#1E3A8A', Brabham: '#1F4E79', Ligier: '#3B82F6', Prost: '#2D5DA8', Stewart: '#FFFFFF',
  Arrows: '#F97316', Cooper: '#0E7C3A', BRM: '#4B5563', Maserati: '#B91C1C', Matra: '#1D4ED8',
  'Alfa Romeo Racing': '#C92D4B', Cadillac: '#C8C8C8', Audi: '#BB0A30',
}
const PALETTE = ['#2563eb', '#dc2626', '#059669', '#d97706', '#7c3aed', '#0891b2', '#db2777', '#65a30d',
  '#9333ea', '#ea580c', '#0d9488', '#4f46e5', '#b45309', '#be123c']

export function teamColor(name, i = 0) {
  if (name && TEAM_COLORS[name]) return TEAM_COLORS[name]
  if (name) {
    const key = Object.keys(TEAM_COLORS).find((k) => name.toLowerCase().includes(k.toLowerCase()))
    if (key) return TEAM_COLORS[key]
  }
  return PALETTE[i % PALETTE.length]
}
export const palette = (i) => PALETTE[i % PALETTE.length]

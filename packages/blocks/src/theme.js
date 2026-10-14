export const DEFAULT_THEME = Object.freeze({
  preset: 'violet',
  accent: '#534ab7',
  fontPair: 'golos',
  radius: 'soft',
  mode: 'light',
  logo: null,
  favicon: null,
})

/** Готовые сочетания цвета, шрифтов и скруглений. Организатор может поменять любое значение. */
export const THEME_PRESETS = Object.freeze({
  violet: { title: 'Фиолетовая', accent: '#534ab7', fontPair: 'golos', radius: 'soft' },
  emerald: { title: 'Изумрудная', accent: '#0f6e56', fontPair: 'manrope', radius: 'soft' },
  ocean: { title: 'Морская', accent: '#1d5fbf', fontPair: 'unbounded', radius: 'round' },
  classic: { title: 'Классическая', accent: '#8a2b2b', fontPair: 'serif', radius: 'sharp' },
})

export const FONT_PAIRS = Object.freeze({
  golos: { title: 'Golos', display: 'Golos Text', body: 'Golos Text' },
  unbounded: { title: 'Unbounded + Golos', display: 'Unbounded', body: 'Golos Text' },
  manrope: { title: 'Manrope', display: 'Manrope', body: 'Manrope' },
  serif: { title: 'PT Serif + PT Sans', display: 'PT Serif', body: 'PT Sans' },
})

export const RADII = Object.freeze({ sharp: ['Острые', '2px'], soft: ['Мягкие', '14px'], round: ['Круглые', '28px'] })

const MODES = {
  light: { bg: '#ffffff', mutedBg: '#f5f4fb', fg: '#1d1a2b', muted: '#5f5a75', line: '#e6e3f0' },
  dark: { bg: '#14121c', mutedBg: '#1e1b2b', fg: '#f2f0fa', muted: '#aaa4c4', line: '#2f2b40' },
}

export function resolveTheme(theme = {}) {
  return { ...DEFAULT_THEME, ...theme }
}

export function themeToCssVars(theme = {}) {
  const t = resolveTheme(theme)
  const fonts = FONT_PAIRS[t.fontPair] ?? FONT_PAIRS.golos
  const mode = MODES[t.mode] ?? MODES.light
  return {
    '--skb-accent': t.accent,
    '--skb-font-display': `"${fonts.display}", system-ui, sans-serif`,
    '--skb-font-body': `"${fonts.body}", system-ui, sans-serif`,
    '--skb-radius': (RADII[t.radius] ?? RADII.soft)[1],
    '--skb-bg': mode.bg,
    '--skb-muted-bg': mode.mutedBg,
    '--skb-fg': mode.fg,
    '--skb-muted': mode.muted,
    '--skb-line': mode.line,
  }
}

const GOOGLE_FAMILIES = {
  'Golos Text': 'Golos+Text:wght@400;500;600;700',
  Unbounded: 'Unbounded:wght@500;700',
  Manrope: 'Manrope:wght@400;600;700;800',
  'PT Serif': 'PT+Serif:wght@400;700',
  'PT Sans': 'PT+Sans:wght@400;700',
}

/** Ссылка на Google Fonts только с нужными теме шрифтами. */
export function themeFontsHref(theme = {}) {
  const fonts = FONT_PAIRS[resolveTheme(theme).fontPair] ?? FONT_PAIRS.golos
  const families = [...new Set([fonts.display, fonts.body])].map((name) => `family=${GOOGLE_FAMILIES[name]}`)
  return `https://fonts.googleapis.com/css2?${families.join('&')}&display=swap`
}

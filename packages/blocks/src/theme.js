export const DEFAULT_THEME = Object.freeze({
  accent: '#534ab7',
  fontPair: 'golos',
  radius: 'soft',
  mode: 'light',
})

const FONT_PAIRS = {
  golos: ['"Golos Text"', '"Golos Text"'],
  unbounded: ['"Unbounded"', '"Golos Text"'],
  manrope: ['"Manrope"', '"Manrope"'],
  serif: ['"PT Serif"', '"PT Sans"'],
}

export function themeToCssVars(theme = {}) {
  const t = { ...DEFAULT_THEME, ...theme }
  const [display, body] = FONT_PAIRS[t.fontPair] ?? FONT_PAIRS.golos
  return {
    '--skb-accent': t.accent,
    '--skb-font-display': `${display}, system-ui, sans-serif`,
    '--skb-font-body': `${body}, system-ui, sans-serif`,
    '--skb-radius': t.radius === 'sharp' ? '2px' : '14px',
  }
}

// Small SVG charts for the results dashboard: a coverage ring and a radar chart.
// Each chart has role="img" and a text label, so screen readers get the numbers too.
// Lines differ by style AND shape (solid/circles vs dashed/diamonds), never by colour alone.

import { s } from './dom.js';

const reduceMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ---------------------------------------------------------------------------
// Coverage ring (0-100)
// ---------------------------------------------------------------------------

export function ring(score, { size = 150, label = '' } = {}) {
  const value = Math.max(0, Math.min(100, Number(score) || 0));
  const r = 52;
  const length = 2 * Math.PI * r;
  const arc = s('circle', {
    cx: 65, cy: 65, r, class: 'ring-arc', transform: 'rotate(-90 65 65)',
    'stroke-dasharray': `${length} ${length}`,
  });
  const target = length * (1 - value / 100);
  if (reduceMotion()) {
    arc.style.strokeDashoffset = String(target);
  } else {
    arc.style.strokeDashoffset = String(length);
    // Two frames later, so the browser animates from empty to the value.
    requestAnimationFrame(() => requestAnimationFrame(() => { arc.style.strokeDashoffset = String(target); }));
  }
  return s('svg', { viewBox: '0 0 130 130', width: size, height: size, role: 'img', 'aria-label': label, class: 'ring' },
    s('circle', { cx: 65, cy: 65, r, class: 'ring-track' }),
    arc,
    s('text', { x: 65, y: 67, 'text-anchor': 'middle', 'dominant-baseline': 'middle', class: 'ring-text' },
      `${Math.round(value)}%`));
}

// ---------------------------------------------------------------------------
// Radar chart: syllabus coverage vs job-ad demand per category (both 0-100)
// ---------------------------------------------------------------------------

const R = 86;                                   // radius of the 100% ring
const LEVELS = [25, 50, 75, 100];

function wrap(text, max = 13) {
  const lines = [];
  for (const word of String(text).split(' ')) {
    const last = lines[lines.length - 1];
    if (last && (last + ' ' + word).length <= max) lines[lines.length - 1] = `${last} ${word}`;
    else lines.push(word);
  }
  return lines;
}

export function radar(categories, { label = '' } = {}) {
  const n = categories.length;
  const angle = (i) => -Math.PI / 2 + (2 * Math.PI * i) / n;      // first category at the top, clockwise
  const point = (i, value) => [Math.cos(angle(i)) * R * value / 100, Math.sin(angle(i)) * R * value / 100];
  const poly = (values) => values.map((v, i) => point(i, v).map((c) => c.toFixed(1)).join(',')).join(' ');

  const svg = s('svg', {
    viewBox: '-175 -128 350 256', class: 'radar', role: 'img', 'aria-label': label,
    preserveAspectRatio: 'xMidYMid meet',
  });

  // Grid rings and spokes
  for (const level of LEVELS) {
    svg.append(s('polygon', { points: poly(categories.map(() => level)), class: 'radar-grid' }));
  }
  categories.forEach((_, i) => {
    const [x, y] = point(i, 100);
    svg.append(s('line', { x1: 0, y1: 0, x2: x.toFixed(1), y2: y.toFixed(1), class: 'radar-spoke' }));
  });

  // Scale numbers, halfway between the first two spokes (so they never sit on a line)
  const mid = -Math.PI / 2 + Math.PI / n;
  for (const level of LEVELS) {
    const x = Math.cos(mid) * R * level / 100;
    const y = Math.sin(mid) * R * level / 100;
    svg.append(s('text', { x: x.toFixed(1), y: y.toFixed(1), class: 'radar-scale', 'text-anchor': 'middle', 'dominant-baseline': 'middle' },
      level === 100 ? '100%' : String(level)));
  }

  // Data: demand (dashed, diamonds) underneath, coverage (solid, circles) on top
  const demand = categories.map((c) => c.demand);
  const coverage = categories.map((c) => c.coverage);
  svg.append(s('polygon', { points: poly(demand), class: 'radar-demand' }));
  svg.append(s('polygon', { points: poly(coverage), class: 'radar-coverage' }));
  demand.forEach((v, i) => {
    const [x, y] = point(i, v);
    svg.append(s('rect', { x: (x - 3.6).toFixed(1), y: (y - 3.6).toFixed(1), width: 7.2, height: 7.2,
      transform: `rotate(45 ${x.toFixed(1)} ${y.toFixed(1)})`, class: 'radar-dot-demand' }));
  });
  coverage.forEach((v, i) => {
    const [x, y] = point(i, v);
    svg.append(s('circle', { cx: x.toFixed(1), cy: y.toFixed(1), r: 3.8, class: 'radar-dot-coverage' }));
  });

  // Category names around the outside, wrapped onto two lines when long
  categories.forEach((c, i) => {
    const [x, y] = point(i, 100);
    const lx = x * 1.13;
    const ly = y * 1.13;
    const anchor = lx > 6 ? 'start' : lx < -6 ? 'end' : 'middle';
    const lines = wrap(c.category);
    const lineHeight = 11;
    const firstDy = ly < -6 ? -(lines.length - 1) * lineHeight : ly > 6 ? lineHeight * 0.6 : -((lines.length - 1) * lineHeight) / 2;
    const text = s('text', { x: lx.toFixed(1), y: (ly + firstDy).toFixed(1), 'text-anchor': anchor, class: 'radar-label', 'dominant-baseline': 'middle' });
    lines.forEach((line, k) => text.append(s('tspan', { x: lx.toFixed(1), dy: k === 0 ? 0 : lineHeight }, line)));
    svg.append(text);
  });
  return svg;
}

// Tiny line samples for the radar legend.
export function legendLine(kind) {
  const solid = kind === 'coverage';
  return s('svg', { viewBox: '0 0 30 12', width: 30, height: 12, 'aria-hidden': 'true', class: 'legend-swatch' },
    s('line', { x1: 1, y1: 6, x2: 29, y2: 6, class: solid ? 'legend-coverage' : 'legend-demand' }),
    solid
      ? s('circle', { cx: 15, cy: 6, r: 3.6, class: 'radar-dot-coverage' })
      : s('rect', { x: 11.6, y: 2.6, width: 6.8, height: 6.8, transform: 'rotate(45 15 6)', class: 'radar-dot-demand' }));
}

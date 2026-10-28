// Wording, evidence highlighting and CSV helpers shared by the Results and Validate pages.

import { h } from './dom.js';

// Status wording agreed with the team (never "missing").
export const LABEL = {
  detected: 'Detected in syllabus',
  brief: 'Briefly mentioned',
  not_detected: 'Not detected in syllabus text',
  gap: 'Potential skill gap',
};
export const ICON = { detected: '✔', brief: '◐', not_detected: '○', gap: '⚠' };
export const METHOD_NAME = { level1: 'Exact', level2: 'Smart' };

// "gap" = not detected AND mentioned in at least `threshold` (0.20) of job ads.
export const statusKey = (skill, threshold) =>
  skill.status === 'not_detected' ? (skill.demand >= threshold ? 'gap' : 'not_detected') : skill.status;

export function badge(key) {
  return h('span', { class: `badge badge-${key}` }, h('span', { 'aria-hidden': 'true' }, ICON[key]), ' ', LABEL[key]);
}

// The evidence sentence with the matched words in <mark>. Everything stays text, never HTML.
export function highlighted(skill) {
  const text = skill.evidence || '';
  const span = skill.evidence_span;
  if (Array.isArray(span) && span[0] >= 0 && span[1] > span[0] && span[1] <= text.length) {
    return ['“', text.slice(0, span[0]), h('mark', {}, text.slice(span[0], span[1])), text.slice(span[1]), '”'];
  }
  const terms = (skill.matched_terms || []).filter(Boolean).sort((a, b) => b.length - a.length);
  if (!terms.length) return ['“', text, '”'];
  const escaped = terms.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const pattern = new RegExp(`(?<![\\w])(${escaped.join('|')})(?![\\w])`, 'g');
  const out = ['“'];
  let last = 0;
  for (const m of text.matchAll(pattern)) {
    out.push(text.slice(last, m.index), h('mark', {}, m[0]));
    last = m.index + m[0].length;
  }
  out.push(text.slice(last), '”');
  return out;
}

// ---------------------------------------------------------------------------
// CSV, made in the browser (nothing is sent anywhere)
// ---------------------------------------------------------------------------

export function toCsv(rows, columns) {
  const cell = (value) => {
    let text = value === null || value === undefined ? '' : String(value);
    // Stop spreadsheet formulas: a cell starting with = + - @ is shown as text.
    if (typeof value === 'string' && /^[=+\-@\t\r]/.test(text)) text = `'${text}`;
    return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  return [columns.join(','), ...rows.map((row) => columns.map((c) => cell(row[c])).join(','))].join('\r\n');
}

export function downloadCsv(filename, csv) {
  // The BOM makes Excel open the file as UTF-8.
  const url = URL.createObjectURL(new Blob(['\ufeff', csv], { type: 'text/csv;charset=utf-8' }));
  const link = h('a', { href: url, download: filename });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export const slug = (text) => String(text).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

// "2024-04 to 2024-04" -> "Apr 2024"
export function formatMonth(range) {
  if (!range) return '';
  const [from, to] = String(range).split(' to ');
  const label = (ym) => {
    const [y, m] = ym.split('-').map(Number);
    if (!y || !m) return ym;
    return new Date(y, m - 1, 1).toLocaleString('en-GB', { month: 'short', year: 'numeric' });
  };
  return from === to || !to ? label(from) : `${label(from)} – ${label(to)}`;
}

// Reads a file as base64 (without the "data:...;base64," prefix).
export function readAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1] || '');
    reader.onerror = () => reject(new Error('This file could not be read. Please try another file.'));
    reader.readAsDataURL(file);
  });
}

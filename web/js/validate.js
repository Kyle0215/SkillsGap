// Validate page: published pilot results, and a check of the current analysis
// against a lecturer's reference answer (precision / recall / F1, Exact vs Smart).
//
// The lecturer's CSV is sent once to the server, which reads it in memory with
// the tested Python code (analysis/validation.py) and forgets it. The page keeps
// the answer in memory only; a new analysis clears it.

import { $, h, pct } from './dom.js';
import { ApiError, validateReference } from './api.js';
import { currentMethod } from './results.js';
import { METHOD_NAME, badge, downloadCsv, highlighted, readAsBase64, slug, statusKey, toCsv } from './shared.js';

const METHODS = ['level1', 'level2'];
const vs = { analysis: null, fileName: null, data: null, brief: true, method: 'level2', busy: false };
let app = null;   // {meta, analysis}

export function showValidate(state) {
  app = state;
  if (!state.meta) {
    $('#validate-body').replaceChildren(h('p', { class: 'hint' }, 'Loading…'));
    return;
  }
  if (vs.analysis !== state.analysis) {
    Object.assign(vs, { analysis: state.analysis, fileName: null, data: null, busy: false });
  }
  if (state.analysis) vs.method = currentMethod();
  $('#validate-body').replaceChildren(pilotCard(state.meta), state.analysis ? checkSection() : emptyCard());
  if (state.analysis) renderResults();
}

// ---------------------------------------------------------------------------
// Published pilot (from data/validation_results.json, via /api/meta)
// ---------------------------------------------------------------------------

function pilotCard(meta) {
  const pilot = meta.pilot;
  if (!meta.pilot_evaluated || !pilot) {
    return h('section', { class: 'card pilot', 'aria-labelledby': 'pilot-title' },
      h('h2', { class: 'kicker', id: 'pilot-title' }, 'Published pilot'),
      h('p', { class: 'tile-big' }, 'Not yet evaluated'),
      h('p', { class: 'hint' }, 'No lecturer comparison has been published yet.'));
  }
  const num = (v) => (typeof v === 'number' ? v : null);
  const score = (v) => (num(v) === null ? 'Not reported' : v <= 1 ? pct(v) : String(v));
  const sample = `${num(pilot.skills_reviewed) ?? 'UNKNOWN'} skills in ${num(pilot.syllabi_reviewed) ?? 'UNKNOWN'} syllabi`;
  return h('section', { class: 'card pilot', 'aria-labelledby': 'pilot-title' },
    h('div', { class: 'pilot-head' },
      h('h2', { class: 'kicker', id: 'pilot-title' }, 'Published pilot'),
      h('span', { class: 'pill' }, 'Pilot · small sample · not generalisable')),
    h('div', { class: 'metrics' },
      metric('Precision', score(pilot.precision), sample),
      metric('Recall', score(pilot.recall), sample),
      metric('F1', num(pilot.f1) === null ? 'Not reported' : pilot.f1.toFixed(2), sample),
      metric('Lecturer usefulness', num(pilot.lecturer_usefulness_avg) === null ? 'Not reported'
        : `${pilot.lecturer_usefulness_avg.toFixed(1)} / 5`, 'average rating')),
    pilot.notes ? h('p', { class: 'hint' }, pilot.notes) : null);
}

function emptyCard() {
  return h('section', { class: 'card empty-card' },
    h('p', { class: 'tile-big' }, 'Analyse a syllabus first'),
    h('p', { class: 'hint' }, 'The check compares the current analysis with a lecturer’s answers.'),
    h('a', { class: 'btn-primary btn-small', href: '#/' }, 'Go to Analyze ', h('span', { 'aria-hidden': 'true' }, '→')));
}

// ---------------------------------------------------------------------------
// Reference check: controls (built once per visit)
// ---------------------------------------------------------------------------

function checkSection() {
  const r = vs.analysis.results.level2;
  const role = r.role;

  const fileInput = h('input', { type: 'file', id: 'ref-file', accept: '.csv,text/csv' });
  fileInput.addEventListener('change', () => upload(fileInput.files[0]));
  const drop = h('label', { class: 'drop drop-small', id: 'ref-drop' },
    fileInput,
    h('b', {}, 'Drop the lecturer’s CSV'),
    h('span', {}, `or click to browse · max ${app.meta.max_reference_mb} MB`));
  ['dragenter', 'dragover'].forEach((t) => drop.addEventListener(t, () => drop.classList.add('is-over')));
  ['dragleave', 'drop'].forEach((t) => drop.addEventListener(t, () => drop.classList.remove('is-over')));

  const brief = h('input', { type: 'checkbox', id: 'brief-switch', checked: vs.brief });
  brief.addEventListener('change', () => { vs.brief = brief.checked; renderResults(); });

  const methodSeg = h('div', { class: 'seg seg-inline', role: 'radiogroup', 'aria-label': 'Matching' },
    METHODS.map((m) => {
      const input = h('input', { type: 'radio', name: 'val-method', value: m, checked: vs.method === m });
      input.addEventListener('change', () => { vs.method = m; renderResults(); });
      return h('label', {}, input, h('span', {}, METHOD_NAME[m]));
    }));

  return h('section', { class: 'check', 'aria-labelledby': 'check-title' },
    h('h2', { class: 'section-title', id: 'check-title' }, `Check: ${role}`,
      h('span', { class: 'sub-inline' }, ` · ${vs.analysis.source_label}`)),
    h('div', { class: 'check-steps' },
      h('div', { class: 'card step-box' },
        h('p', { class: 'step-title' }, h('span', { class: 'step-num', 'aria-hidden': 'true' }, '1'), 'Get the template'),
        h('button', { type: 'button', class: 'btn-ghost', onclick: downloadTemplate },
          h('span', { 'aria-hidden': 'true' }, '⬇'), ` Template (${r.skills.length} skills)`),
        h('p', { class: 'hint' }, 'The lecturer marks each skill: covered · brief · not_covered')),
      h('div', { class: 'card step-box' },
        h('p', { class: 'step-title' }, h('span', { class: 'step-num', 'aria-hidden': 'true' }, '2'), 'Upload their answers'),
        drop,
        h('div', { class: 'file-chosen file-chosen-small', id: 'ref-chosen', hidden: true },
          h('span', { class: 'file-badge', 'aria-hidden': 'true' }, 'CSV'),
          h('span', { class: 'file-text' }, h('span', { class: 'file-name', id: 'ref-name' }), h('span', { class: 'file-size', id: 'ref-status' })),
          h('button', { type: 'button', class: 'btn-link', onclick: clearFile }, 'Remove')))),
    h('p', { id: 'ref-error', class: 'form-error', role: 'alert', hidden: true }),
    h('div', { class: 'check-controls', id: 'check-controls', hidden: true },
      h('label', { class: 'switch' }, brief, h('span', {}, 'Count “brief” as covered')),
      methodSeg),
    h('div', { id: 'val-results', 'aria-live': 'polite' }));
}

function downloadTemplate() {
  const r = vs.analysis.results.level2;
  const rows = [...r.skills].map((s) => s.skill).sort((a, b) => a.localeCompare(b))
    .map((skill) => ({ skill, reviewer_status: '' }));
  downloadCsv(`skillsgap_reference_${slug(r.role)}.csv`, toCsv(rows, ['skill', 'reviewer_status']));
}

async function upload(file) {
  showError(null);
  if (!file) return;
  if (!file.name.toLowerCase().endsWith('.csv')) { showError('Please choose a CSV file (start from the template).'); return; }
  if (file.size === 0) { showError('This file is empty.'); return; }
  if (file.size > app.meta.max_reference_mb * 1024 * 1024) { showError('This file is too large (limit 1 MB).'); return; }

  vs.busy = true;
  vs.fileName = file.name;
  showChosen('Checking…');
  try {
    const reference_base64 = await readAsBase64(file);
    vs.data = await validateReference({ reference_base64, results: vs.analysis.results });
    showChosen(`${vs.data.rows} skills answered${vs.data.blank ? ` · ${vs.data.blank} left blank` : ''}`);
  } catch (err) {
    vs.data = null;
    showError(err instanceof ApiError || err instanceof Error ? err.message : 'Something went wrong. Please try again.');
    clearFile(false);
  } finally {
    vs.busy = false;
    $('#ref-file').value = '';
    renderResults();
  }
}

function showChosen(status) {
  $('#ref-drop').hidden = true;
  $('#ref-chosen').hidden = false;
  $('#ref-name').textContent = vs.fileName;
  $('#ref-status').textContent = status;
}

function clearFile(focus = true) {
  vs.fileName = null;
  vs.data = null;
  $('#ref-drop').hidden = false;
  $('#ref-chosen').hidden = true;
  if (focus) $('#ref-file').focus();
  renderResults();
}

function showError(message) {
  const box = $('#ref-error');
  box.hidden = !message;
  box.textContent = message || '';
}

// ---------------------------------------------------------------------------
// Results of the check (re-drawn when the toggles change)
// ---------------------------------------------------------------------------

function renderResults() {
  const area = $('#val-results');
  if (!area) return;
  $('#check-controls').hidden = !vs.data;
  if (!vs.data) { area.replaceChildren(); return; }

  const set = vs.data.comparisons[vs.brief ? 'brief_on' : 'brief_off'];
  const c = set[vs.method];
  const role = vs.analysis.results[vs.method].role;

  if (c.n_compared === 0) {
    area.replaceChildren(h('p', { class: 'form-error' },
      `None of the skills in this file are in the ${role} list. Did you use the template for another role?`));
    return;
  }

  const warnings = [];
  if (c.small_sample) {
    const n = c.n_compared;
    warnings.push(`Only ${n} skill${n === 1 ? '' : 's'} compared (fewer than ${app.meta.min_reliable_skills}). Too few to draw conclusions.`);
  }
  if (c.not_in_analysis.length) {
    warnings.push(`Not in the ${role} list, so not compared: ${c.not_in_analysis.slice(0, 8).join(', ')}${c.not_in_analysis.length > 8 ? '…' : ''}.`);
  }

  area.replaceChildren(
    ...warnings.map((w) => h('p', { class: 'banner banner-warn' }, h('span', { 'aria-hidden': 'true' }, '⚠ '), w)),
    h('div', { class: 'metrics metrics-main' },
      metric('Precision', c.precision === null ? '—' : pct(c.precision),
        c.precision === null ? 'Not defined: the app marked no compared skill as covered'
          : `${c.tp} of ${c.precision_den} the app found were confirmed`),
      metric('Recall', c.recall === null ? '—' : pct(c.recall),
        c.recall === null ? 'Not defined: the lecturer marked no compared skill as covered'
          : `Found ${c.tp} of the ${c.recall_den} the lecturer marked covered`),
      metric('F1', c.f1 === null ? '—' : c.f1.toFixed(2), 'Balance of precision and recall (0–1)'),
      metric('Compared', String(c.n_compared), `${METHOD_NAME[vs.method]} matching · this syllabus only`)),
    h('div', { class: 'check-grid' },
      compareCard(set),
      agreementCard(c)),
    disagreements(c),
    formulas(c),
  );
}

function metric(label, value, caption) {
  return h('div', { class: 'metric' },
    h('p', { class: 'kicker' }, label),
    h('p', { class: 'metric-value' }, value),
    h('p', { class: 'hint' }, caption));
}

function compareCard(set) {
  const one = set.level1;
  const two = set.level2;
  const row = (label, key, format) => h('tr', {},
    h('th', { scope: 'row' }, label),
    ...METHODS.map((m) => {
      const value = set[m][key];
      const fill = h('span', { class: 'fill fill-score' });
      requestAnimationFrame(() => { fill.style.width = `${(value ?? 0) * 100}%`; });
      return h('td', {}, h('span', { class: 'cmp-val' }, value === null ? '—' : format(value)),
        h('span', { class: 'bar', 'aria-hidden': 'true' }, fill));
    }));
  const diff = (n, noun) => (n === 0 ? `the same number of ${noun}` : `${Math.abs(n)} ${n > 0 ? 'more' : 'fewer'} ${noun}`);
  return h('section', { class: 'card', 'aria-labelledby': 'cmp-title' },
    h('h3', { class: 'kicker', id: 'cmp-title' }, 'Exact vs Smart'),
    h('table', { class: 'cmp' },
      h('thead', {}, h('tr', {}, h('th', { scope: 'col' }, h('span', { class: 'visually-hidden' }, 'Measure')),
        h('th', { scope: 'col' }, 'Exact'), h('th', { scope: 'col' }, 'Smart'))),
      h('tbody', {},
        row('Precision', 'precision', (v) => pct(v)),
        row('Recall', 'recall', (v) => pct(v)),
        row('F1', 'f1', (v) => v.toFixed(2)))),
    h('p', { class: 'cmp-note' },
      `Smart finds ${diff(two.tp - one.tp, 'correct skills')}, with ${diff(two.fp - one.fp, 'false detections')}.`));
}

function agreementCard(c) {
  const covered = vs.brief ? 'covered or brief' : 'covered';
  return h('section', { class: 'card', 'aria-labelledby': 'agree-title' },
    h('h3', { class: 'kicker', id: 'agree-title' }, 'Agreement'),
    h('table', { class: 'agree' },
      h('thead', {}, h('tr', {}, h('th', { scope: 'col' }, h('span', { class: 'visually-hidden' }, 'App')),
        h('th', { scope: 'col' }, `Lecturer: ${covered}`), h('th', { scope: 'col' }, 'Lecturer: not covered'))),
      h('tbody', {},
        h('tr', {}, h('th', { scope: 'row' }, 'App: found'),
          h('td', { class: 'agree-ok' }, h('b', {}, c.tp), ' correct'),
          h('td', { class: 'agree-bad' }, h('b', {}, c.fp), ' false detections')),
        h('tr', {}, h('th', { scope: 'row' }, 'App: not found'),
          h('td', { class: 'agree-bad' }, h('b', {}, c.fn), ' missed'),
          h('td', { class: 'agree-ok' }, h('b', {}, c.tn), ' both say no')))));
}

function disagreements(c) {
  const skills = new Map(vs.analysis.results[vs.method].skills.map((s) => [s.skill, s]));
  const fns = c.disagreements.filter((d) => d.type === 'False negative');
  const fps = c.disagreements.filter((d) => d.type === 'False positive');
  const threshold = app.meta.gap_threshold;
  return h('div', { class: 'check-grid' },
    h('section', { class: 'card', 'aria-labelledby': 'fn-title' },
      h('h3', { class: 'kicker', id: 'fn-title' }, `Missed by the app (${fns.length})`),
      fns.length
        ? [h('p', { class: 'hint' }, 'Often taught under another name: a synonym the dictionary lacks.'),
          h('ul', { class: 'dis-list' }, fns.map((d) => h('li', {},
            h('span', { class: 'dis-skill' }, d.skill),
            h('span', { class: 'hint' }, `Lecturer: ${d.reviewer_status.replace('_', ' ')}`))))]
        : h('p', { class: 'empty' }, '✔ None')),
    h('section', { class: 'card', 'aria-labelledby': 'fp-title' },
      h('h3', { class: 'kicker', id: 'fp-title' }, `False detections (${fps.length})`),
      fps.length
        ? h('ul', { class: 'dis-list' }, fps.map((d) => {
          const skill = skills.get(d.skill) || d;
          return h('li', { class: 'dis-fp' },
            h('span', { class: 'dis-skill' }, d.skill, ' ', badge(statusKey(skill, threshold))),
            skill.evidence ? h('blockquote', { class: 'quote quote-small' }, highlighted(skill)) : null);
        }))
        : h('p', { class: 'empty' }, '✔ None')));
}

function formulas(c) {
  const covered = vs.brief
    ? '“Covered” = the app found it (Detected or Briefly mentioned) and the lecturer said covered or brief.'
    : '“Covered” = the app Detected it and the lecturer said covered (“brief” counts as not covered).';
  return h('details', { class: 'card help-card' },
    h('summary', {}, 'How are these calculated?'),
    h('ul', {},
      h('li', {}, h('b', {}, 'Precision'), ` = correct detections ÷ all detections by the app = ${c.tp} ÷ ${c.precision_den}`),
      h('li', {}, h('b', {}, 'Recall'), ` = correct detections ÷ all skills the lecturer says are covered = ${c.tp} ÷ ${c.recall_den}`),
      h('li', {}, h('b', {}, 'F1'), ' = 2 × precision × recall ÷ (precision + recall)'),
      h('li', {}, covered)),
    h('p', { class: 'hint' }, 'These numbers describe this syllabus and this lecturer only. They are not a general accuracy figure.'));
}

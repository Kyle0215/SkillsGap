// Results dashboard: seven draggable tiles, a full skills table, downloads and a 1-5 rating.
//
// Reads only the analyze() results sent by the server (both matching methods),
// so "Smart" / "Exact" switch instantly. Everything stays in memory: reviews
// and the rating are never sent or saved anywhere.

import { $, $$, h, pct } from './dom.js';
import { DraggableGrid } from './grid.js';
import { legendLine, radar, ring } from './charts.js';
import {
  ICON, LABEL, METHOD_NAME, badge, downloadCsv as download, highlighted, slug, statusKey as statusFor, toCsv,
} from './shared.js';

const SOFT = 'Soft Skills';
const FOUND_LIMIT = 14;          // chips shown in "Found in syllabus" before "+N more"
const GAPS_LIMIT = 6;

const ctx = {
  analysis: null, meta: null, method: 'level2', selected: null,
  reviews: new Map(), rating: null, grid: null, tiles: null,
};

const current = () => ctx.analysis.results[ctx.method];
const isSoft = (skill) => skill.category === SOFT;
const statusKey = (skill) => statusFor(skill, ctx.meta.gap_threshold);
const findSkill = (name) => current().skills.find((s) => s.skill === name);
const announce = (message) => { $('#sr-live').textContent = message; };

// ---------------------------------------------------------------------------
// Public
// ---------------------------------------------------------------------------

// Called once when the page loads: header controls, table toggle and rating.
export function initResults() {
  $$('input[name="view-method"]').forEach((radio) =>
    radio.addEventListener('change', () => setMethod(radio.value)));
  $('#csv-btn').addEventListener('click', downloadResults);
  $('#reset-layout').addEventListener('click', () => ctx.grid?.reset());
  $$('#rating button').forEach((button) => button.addEventListener('click', () => rate(Number(button.dataset.value))));
}

// The matching method currently shown on the dashboard ('level1' or 'level2').
export const currentMethod = () => ctx.method;

// Called after each new analysis.
export function showResults(analysis, meta) {
  ctx.analysis = analysis;
  ctx.meta = meta;
  ctx.method = analysis.method in analysis.results ? analysis.method : 'level2';
  ctx.reviews = new Map();
  ctx.rating = null;
  ctx.selected = defaultSkill();

  $('#results-title').textContent = current().role;
  $('#results-sub').textContent = analysis.source_label;
  $$('input[name="view-method"]').forEach((radio) => { radio.checked = radio.value === ctx.method; });
  $('#all-skills').open = false;
  renderRating();

  const firstTime = !ctx.grid;
  if (firstTime) buildGrid();
  renderAll();
  if (firstTime) {
    ctx.tiles.forEach((t, i) => {
      t.el.classList.add('tile-in');
      t.el.style.animationDelay = `${i * 55}ms`;
    });
  }
}

// ---------------------------------------------------------------------------
// Tiles
// ---------------------------------------------------------------------------

const TILES = [
  { id: 'coverage', size: 'lg', title: 'Coverage', render: renderCoverage },
  { id: 'gaps', size: 'tall', title: 'Top gaps', render: renderGaps },
  { id: 'soft', size: 'sm', title: 'Soft skills', render: renderSoft },
  { id: 'validation', size: 'sm', title: 'Validation', render: renderValidation },
  { id: 'category', size: 'lg', title: 'By category', render: renderCategory },
  { id: 'found', size: 'wide', title: 'Found in syllabus', render: renderFound },
  { id: 'evidence', size: 'wide', title: 'Evidence', render: renderEvidence },
];

function buildGrid() {
  ctx.tiles = TILES.map((t) => {
    const titleId = `tile-${t.id}-title`;
    const heading = h('h2', { id: titleId }, t.title);
    const body = h('div', { class: 'tile-body' });
    const el = h('section', { class: `tile size-${t.size}`, 'aria-labelledby': titleId, 'data-tile': t.id },
      h('header', { class: 'tile-head' }, heading, h('span', { class: 'grip', 'aria-hidden': 'true' }, '⠿')),
      body);
    return { ...t, el, body, heading, label: t.title };
  });
  ctx.grid = new DraggableGrid($('#bento'), ctx.tiles, { describedBy: 'grid-help', announce });
}

function renderAll() {
  for (const t of ctx.tiles) t.render(t);
  renderTable();
}

const tile = (id) => ctx.tiles.find((t) => t.id === id);

// A clickable skill (opens its evidence). Accessible name says everything in words.
function skillButton(skill, className, children) {
  const key = statusKey(skill);
  return h('button', {
    type: 'button', class: className, 'data-skill': skill.skill,
    'aria-pressed': String(skill.skill === ctx.selected),
    'aria-label': `${skill.skill}: ${LABEL[key]}, in ${pct(skill.demand)} of job ads. Show evidence.`,
    onclick: () => select(skill.skill),
  }, children);
}

// ----- Coverage -----
function renderCoverage(t) {
  const r = current();
  const keys = r.skills.map(statusKey);
  const count = (k) => keys.filter((x) => x === k).length;
  const stat = (method) => {
    const score = ctx.analysis.results[method].coverage_score;
    const isCurrent = method === ctx.method;
    return h('button', {
      type: 'button', class: `stat${isCurrent ? ' is-current' : ''}`, 'data-method': method,
      'aria-pressed': String(isCurrent), onclick: () => setMethod(method, true),
    }, h('b', {}, `${Math.round(score)}%`), `${METHOD_NAME[method]} match`);
  };
  t.body.replaceChildren(
    h('div', { class: 'cov' },
      ring(r.coverage_score, { size: 168, label: `${Math.round(r.coverage_score)}% of employer demand covered` }),
      h('div', { class: 'cov-text' },
        h('p', { class: 'cov-title' }, 'of employer demand', h('br'), 'is covered'),
        h('p', { class: 'hint' }, `${r.skills_checked} skills · ${r.postings_used.toLocaleString('en-US')} job ads`),
        h('ul', { class: 'counts', 'aria-label': 'Skills by status' },
          h('li', { class: 'badge badge-detected' }, h('span', { 'aria-hidden': 'true' }, '✔ '), `${count('detected')} found`),
          h('li', { class: 'badge badge-brief' }, h('span', { 'aria-hidden': 'true' }, '◐ '), `${count('brief')} brief`),
          h('li', { class: 'badge badge-gap' }, h('span', { 'aria-hidden': 'true' }, '⚠ '), `${count('gap')} gaps`)))),
    h('div', { class: 'stats' },
      stat('level1'), stat('level2'),
      h('div', { class: 'stat stat-static' }, h('b', {}, `${ctx.analysis.elapsed_seconds.toFixed(2)} s`), 'Analysis time')),
    h('details', { class: 'help' },
      h('summary', {}, 'How is this scored?'),
      h('p', {}, 'Each skill counts by how often job ads mention it. Found twice or more counts fully, once counts half. ',
        'Placeholder formula.')),
  );
}

// ----- Top gaps (technical) -----
function gapRows(skills, { bars }) {
  const max = Math.max(...skills.map((s) => s.demand), 0.01);
  return h('ul', { class: 'gap-list' }, skills.map((skill) => {
    const key = statusKey(skill);
    const children = [
      h('span', { class: 'name' }, h('span', { class: `ico ico-${key}`, 'aria-hidden': 'true' }, ICON[key]), ' ', skill.skill),
      h('span', { class: 'val' }, pct(skill.demand)),
    ];
    if (bars) {
      const fill = h('span', { class: `fill fill-${key}` });
      requestAnimationFrame(() => { fill.style.width = `${(skill.demand / max) * 100}%`; });
      children.push(h('span', { class: 'bar', 'aria-hidden': 'true' }, fill));
    }
    return h('li', {}, skillButton(skill, 'skill-row', children));
  }));
}

function renderGaps(t) {
  const rows = current().skills
    .filter((s) => !isSoft(s) && s.gap_score > 0)
    .sort((a, b) => b.gap_score - a.gap_score || b.demand - a.demand)
    .slice(0, GAPS_LIMIT);
  t.body.replaceChildren(rows.length
    ? gapRows(rows, { bars: true })
    : h('p', { class: 'empty' }, '✔ No technical gaps found'),
  h('p', { class: 'hint tile-foot' }, '% of job ads that mention it'));
}

// ----- Soft skills -----
function renderSoft(t) {
  const rows = current().skills
    .filter((s) => isSoft(s) && s.gap_score > 0)
    .sort((a, b) => b.gap_score - a.gap_score)
    .slice(0, 3);
  t.body.replaceChildren(rows.length ? gapRows(rows, { bars: false }) : h('p', { class: 'empty' }, '✔ All soft skills found'));
}

// ----- Validation -----
function renderValidation(t) {
  const evaluated = ctx.meta.pilot_evaluated;
  t.body.replaceChildren(
    h('p', { class: 'tile-big' }, evaluated ? 'Pilot results available' : 'Not yet evaluated'),
    h('p', { class: 'hint' }, evaluated ? 'Small pilot sample' : 'No lecturer check published yet'),
    h('a', { class: 'tile-link', href: '#/validate' }, 'Check with a lecturer ', h('span', { 'aria-hidden': 'true' }, '→')),
  );
}

// ----- By category (radar) -----
function renderCategory(t) {
  const cats = current().category_summary || [];
  if (cats.length < 3) {
    t.body.replaceChildren(h('p', { class: 'empty' }, 'Not enough categories for a chart.'));
    return;
  }
  const summary = cats.map((c) => `${c.category}: coverage ${Math.round(c.coverage)}%, demand ${Math.round(c.demand)}%`).join('; ');
  // With no coverage at all, the solid line collapses to one dot in the centre,
  // so say it in words: the visible shape is job-ad demand only.
  const noCoverage = cats.every((c) => c.coverage === 0);
  t.body.replaceChildren(
    h('div', { class: 'radar-wrap' }, radar(cats, { label: `Coverage and job-ad demand by category. ${summary}.` })),
    h('p', { class: 'legend' },
      h('span', {}, legendLine('coverage'), 'Syllabus coverage'),
      h('span', {}, legendLine('demand'), 'Job-ad demand')),
    noCoverage
      ? h('p', { class: 'radar-note' },
        'No skills found yet, so the coverage line sits at the centre. The shape shows job-ad demand only.')
      : null,
  );
}

// ----- Found in syllabus -----
function renderFound(t) {
  const found = current().skills
    .filter((s) => s.status !== 'not_detected')
    .sort((a, b) => (a.status === b.status ? b.demand - a.demand : a.status === 'detected' ? -1 : 1));
  if (!found.length) {
    t.body.replaceChildren(h('p', { class: 'empty' }, 'No skills from the list were found in the text.'));
    return;
  }
  const shown = found.slice(0, FOUND_LIMIT);
  const chips = shown.map((skill) => {
    const key = statusKey(skill);
    return skillButton(skill, `chip-btn badge badge-${key}`,
      [h('span', { 'aria-hidden': 'true' }, ICON[key]), ' ', skill.skill]);
  });
  if (found.length > FOUND_LIMIT) {
    chips.push(h('button', { type: 'button', class: 'chip-btn chip-more', onclick: openTable },
      `+${found.length - FOUND_LIMIT} more`));
  }
  t.body.replaceChildren(h('div', { class: 'found' }, chips));
}

// ----- Evidence -----
function renderEvidence(t) {
  const skill = findSkill(ctx.selected) || findSkill(defaultSkill());
  if (!skill) {
    t.body.replaceChildren(h('p', { class: 'empty' }, 'Click a skill to see its evidence.'));
    return;
  }
  ctx.selected = skill.skill;
  const key = statusKey(skill);
  t.heading.textContent = `Evidence · ${skill.skill}`;

  const mentions = `${skill.mentions} mention${skill.mentions === 1 ? '' : 's'}`;
  const parts = [
    h('div', { class: 'ev-top' }, badge(key), h('span', { class: 'hint ev-meta' }, `${mentions} · in ${pct(skill.demand)} of job ads`)),
  ];
  if (skill.evidence) {
    parts.push(h('blockquote', { class: 'quote' }, highlighted(skill)));
  } else {
    parts.push(h('p', { class: 'ev-none' }, 'Not found in the syllabus text. It may be taught under another name.'));
  }

  const review = ctx.reviews.get(reviewKey(skill.skill));
  const reviewButton = (value, icon) => h('button', {
    type: 'button', 'data-judgement': value, 'aria-pressed': String(review?.reviewer_judgement === value),
    onclick: () => judge(skill, value),
  }, h('span', { 'aria-hidden': 'true' }, icon), ' ', value);
  parts.push(h('div', { class: 'review' },
    h('span', { class: 'review-q', id: 'review-q' }, 'Is this right?'),
    h('div', { class: 'review-btns', role: 'group', 'aria-labelledby': 'review-q' },
      reviewButton('Correct', '✔'), reviewButton('Wrong', '✖'), reviewButton('Unsure', '?')),
    h('button', { type: 'button', class: 'btn-link review-dl', hidden: ctx.reviews.size === 0, onclick: downloadReview },
      `Download my review (${ctx.reviews.size})`)));
  t.body.replaceChildren(...parts);
}

// ---------------------------------------------------------------------------
// Interactions
// ---------------------------------------------------------------------------

function defaultSkill() {
  const skills = current().skills;
  const detected = skills.filter((s) => s.status === 'detected').sort((a, b) => b.demand - a.demand);
  return (detected[0] || skills.find((s) => statusKey(s) === 'gap') || skills[0])?.skill ?? null;
}

function select(name) {
  ctx.selected = name;
  $$('#bento [data-skill], #skills-table [data-skill]').forEach((el) => {
    el.setAttribute('aria-pressed', String(el.dataset.skill === name));
  });
  const evidence = tile('evidence');
  evidence.render(evidence);
  const skill = findSkill(name);
  announce(`Evidence for ${name}: ${LABEL[statusKey(skill)]}, ${skill.mentions} mentions.`);
  const box = evidence.el.getBoundingClientRect();
  if (box.top < 70 || box.bottom > window.innerHeight) {
    evidence.el.scrollIntoView({ block: 'center', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  }
  evidence.el.classList.remove('is-flash');
  void evidence.el.offsetWidth;          // restart the highlight animation
  evidence.el.classList.add('is-flash');
}

function setMethod(method, fromTile = false) {
  if (!(method in ctx.analysis.results) || method === ctx.method) return;
  ctx.method = method;
  $$('input[name="view-method"]').forEach((radio) => { radio.checked = radio.value === method; });
  renderAll();
  if (fromTile) $(`#bento .stat[data-method="${method}"]`)?.focus();
  announce(`Showing ${METHOD_NAME[method]} matching: ${Math.round(current().coverage_score)}% coverage.`);
}

const reviewKey = (name) => `${ctx.method}|${name}`;

function judge(skill, value) {
  const key = reviewKey(skill.skill);
  if (ctx.reviews.get(key)?.reviewer_judgement === value) ctx.reviews.delete(key);
  else {
    ctx.reviews.set(key, {
      skill: skill.skill, app_status: skill.status, reviewer_judgement: value, comment: '',
      role: current().role, method: ctx.method, timestamp: new Date().toISOString().replace(/\.\d+Z$/, 'Z'),
    });
  }
  const chosen = ctx.reviews.get(key)?.reviewer_judgement;
  $$('#bento .review-btns button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.judgement === chosen)));
  const link = $('#bento .review-dl');
  link.hidden = ctx.reviews.size === 0;
  link.textContent = `Download my review (${ctx.reviews.size})`;
  announce(chosen ? `Marked ${skill.skill} as ${chosen}.` : `Removed your answer for ${skill.skill}.`);
}

function rate(value) {
  ctx.rating = ctx.rating === value ? null : value;
  renderRating();
}

function renderRating() {
  $$('#rating button').forEach((b) => b.setAttribute('aria-pressed', String(Number(b.dataset.value) === ctx.rating)));
  $('#rating-thanks').hidden = !ctx.rating;
}

function openTable() {
  const details = $('#all-skills');
  details.open = true;
  details.scrollIntoView({ block: 'start', behavior: 'smooth' });
  $('summary', details).focus({ preventScroll: true });
}

// ---------------------------------------------------------------------------
// All skills table
// ---------------------------------------------------------------------------

function renderTable() {
  const skills = current().skills;
  $('#all-count').textContent = `(${skills.length})`;
  $('#skills-table tbody').replaceChildren(...skills.map((skill) => {
    const key = statusKey(skill);
    return h('tr', { class: key === 'gap' ? 'is-gap' : '' },
      h('th', { scope: 'row' }, skillButton(skill, 'table-skill', skill.skill)),
      h('td', {}, skill.category),
      h('td', { class: 'num' }, pct(skill.demand, 1)),
      h('td', {}, h('span', { 'aria-hidden': 'true' }, ICON[key]), ' ', LABEL[key]),
      h('td', { class: 'num' }, String(skill.mentions)));
  }));
}

// ---------------------------------------------------------------------------
// Downloads (CSV made in the browser; nothing is sent anywhere)
// ---------------------------------------------------------------------------

function downloadResults() {
  const r = current();
  const rows = r.skills.map((skill) => ({
    role: r.role, method: METHOD_NAME[ctx.method], skill: skill.skill, category: skill.category,
    skill_type: isSoft(skill) ? 'Soft skill' : 'Technical skill',
    demand_percent: (skill.demand * 100).toFixed(1), syllabus_status: LABEL[statusKey(skill)],
    mentions: skill.mentions, gap_score: (skill.gap_score * 100).toFixed(1),
    matched_terms: (skill.matched_terms || []).join('; '), evidence: skill.evidence || '',
    explanation: skill.explanation,
  }));
  download(`skillsgap_${slug(r.role)}_${METHOD_NAME[ctx.method].toLowerCase()}.csv`,
    toCsv(rows, Object.keys(rows[0] || { skill: '' })));
}

function downloadReview() {
  const columns = ['skill', 'app_status', 'reviewer_judgement', 'comment', 'role', 'method', 'timestamp'];
  const rows = [...ctx.reviews.values()].map((r) => ({ ...r, method: METHOD_NAME[r.method] }));
  download(`skillsgap_review_${slug(current().role)}.csv`, toCsv(rows, columns));
}

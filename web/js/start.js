// The start screen: 1. syllabus, 2. target job, 3. matching method, then Analyze.
//
// PRIVACY: the file is read in the browser and sent once to the server, which
// keeps it in memory only. Nothing is saved in the browser either.

import { $, $$, h, fileSize } from './dom.js';
import { analyzeSyllabus, ApiError } from './api.js';
import { formatMonth, readAsBase64 as readFile } from './shared.js';

const ALLOWED = ['.pdf', '.docx'];
const MIN_WORDS = 30;
const SLOW_MS = 4000;   // after this, explain that a sleeping server is waking up

let chosenFile = null;
let meta = null;

export function initStart(appMeta, onAnalyzed) {
  meta = appMeta;
  $('#max-mb').textContent = meta.max_file_mb;
  $('#paste').maxLength = meta.max_chars;
  renderRoles(meta.roles);
  renderSamples(meta.samples);
  renderTrust(meta);

  // Show the panel for the chosen source (Upload / Paste / Sample).
  $$('input[name="source"]').forEach((radio) => radio.addEventListener('change', showSourcePanel));

  // File: click to browse, or drag and drop onto the box.
  const drop = $('#drop');
  const input = $('#file');
  input.addEventListener('change', () => chooseFile(input.files[0]));
  ['dragenter', 'dragover'].forEach((type) =>
    drop.addEventListener(type, () => drop.classList.add('is-over')));
  ['dragleave', 'drop'].forEach((type) =>
    drop.addEventListener(type, () => drop.classList.remove('is-over')));
  $('#file-clear').addEventListener('click', () => {
    chooseFile(null);
    input.focus();
  });

  // Paste: live word count.
  $('#paste').addEventListener('input', updateWordCount);

  $('#analyze-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    await submit(onAnalyzed);
  });
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function renderRoles(roles) {
  const box = $('#role-chips');
  box.replaceChildren();
  if (!roles.length) {
    box.append(h('span', { class: 'hint' }, 'No roles available.'));
    return;
  }
  box.setAttribute('role', 'radiogroup');
  box.setAttribute('aria-label', 'Target job');
  for (const role of roles) {
    box.append(h('label', { class: 'chip', title: `${role.postings.toLocaleString('en-US')} job ads` },
      h('input', { type: 'radio', name: 'role', value: role.name }),
      h('span', {}, role.name)));
  }
}

function renderSamples(samples) {
  const box = $('#sample-list');
  box.replaceChildren(...samples.map((sample, i) =>
    h('label', { class: 'sample' },
      h('input', {
        type: 'radio', name: 'sample', value: sample.id, checked: i === 0,
        onchange: () => selectRole(sample.role),
      }),
      h('span', {}, sample.name, h('small', {}, `Suggested: ${sample.role}`)))));
}

function renderTrust(appMeta) {
  const src = appMeta.source;
  const month = formatMonth(src.date_range);
  const where = src.region === 'Global' ? 'mostly US' : src.region;
  const jobs = Number.isInteger(src.postings_used) ? src.postings_used.toLocaleString('en-US') : '';
  const items = [
    ['🔒', 'Never stored'],
    ['📊', [`${jobs} LinkedIn job ads`, month, where].filter(Boolean).join(' · ')],
    ['⚡', 'Results in seconds'],
  ];
  $('#trust').replaceChildren(...items.map(([icon, text]) =>
    h('li', {}, h('span', { 'aria-hidden': 'true' }, icon), ' ', text)));
}

// ---------------------------------------------------------------------------
// Inputs
// ---------------------------------------------------------------------------

const currentSource = () => $('input[name="source"]:checked').value;

function showSourcePanel() {
  const source = currentSource();
  $$('[data-panel]').forEach((panel) => { panel.hidden = panel.dataset.panel !== source; });
  if (source === 'sample') {
    const sample = meta.samples.find((s) => s.id === $('input[name="sample"]:checked')?.value);
    if (sample) selectRole(sample.role);
  }
  hideError();
}

function selectRole(name) {
  const radio = $$('input[name="role"]').find((r) => r.value === name);
  if (radio) radio.checked = true;
}

function chooseFile(file) {
  hideError();
  chosenFile = null;
  $('#file').value = '';
  $('#drop').hidden = false;
  $('#file-chosen').hidden = true;
  if (!file) return;

  const problem = checkFile(file);
  if (problem) {
    showError(problem);
    return;
  }
  chosenFile = file;
  $('#file-name').textContent = file.name;
  $('#file-size').textContent = fileSize(file.size);
  $('#file-type').textContent = file.name.toLowerCase().endsWith('.pdf') ? 'PDF' : 'DOCX';
  $('#drop').hidden = true;
  $('#file-chosen').hidden = false;
}

function checkFile(file) {
  const name = file.name.toLowerCase();
  if (!ALLOWED.some((ext) => name.endsWith(ext))) return 'Please choose a PDF or DOCX file.';
  if (file.size === 0) return 'This file is empty. Please choose another file.';
  if (file.size > meta.max_file_mb * 1024 * 1024) {
    return `This file is too large (${fileSize(file.size)}). The limit is ${meta.max_file_mb} MB.`;
  }
  return null;
}

function updateWordCount() {
  const words = $('#paste').value.trim().split(/\s+/).filter(Boolean).length;
  const enough = words >= MIN_WORDS;
  const counter = $('#word-count');
  counter.textContent = `${words.toLocaleString('en-US')} words${enough ? ' ✓' : ` · at least ${MIN_WORDS}`}`;
  counter.classList.toggle('is-ok', enough);
}

async function readAsBase64(file) {
  try {
    return await readFile(file);
  } catch (err) {
    throw new ApiError(err.message);
  }
}

// ---------------------------------------------------------------------------
// Submit
// ---------------------------------------------------------------------------

async function buildPayload() {
  const role = $('input[name="role"]:checked')?.value;
  if (!role) throw new ApiError('Please choose a target job.');
  const source = currentSource();
  const payload = { source, role };

  if (source === 'upload') {
    if (!chosenFile) throw new ApiError('Please choose a PDF or DOCX file, or paste the text instead.');
    payload.filename = chosenFile.name;
    payload.file_base64 = await readAsBase64(chosenFile);
  } else if (source === 'paste') {
    const text = $('#paste').value;
    const words = text.trim().split(/\s+/).filter(Boolean).length;
    if (words === 0) throw new ApiError('Please paste the syllabus text first.');
    if (words < MIN_WORDS) {
      throw new ApiError(`The text is too short (${words} words). Please paste at least ${MIN_WORDS} words.`);
    }
    payload.text = text;
  } else {
    payload.sample = $('input[name="sample"]:checked')?.value;
  }
  return payload;
}

async function submit(onAnalyzed) {
  hideError();
  const method = $('input[name="method"]:checked').value;
  setBusy(true);
  const slowTimer = setTimeout(() => {
    $('#busy-msg').textContent = 'Waking up the server. The first analysis can take up to a minute…';
  }, SLOW_MS);
  try {
    const payload = await buildPayload();
    const analysis = await analyzeSyllabus(payload);
    analysis.method = method;          // which result to show first
    onAnalyzed(analysis);
  } catch (err) {
    showError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.');
  } finally {
    clearTimeout(slowTimer);
    setBusy(false);
  }
}

function setBusy(busy) {
  const button = $('#analyze-btn');
  button.disabled = busy;
  button.setAttribute('aria-busy', String(busy));
  button.classList.toggle('is-busy', busy);
  $('#analyze-label').textContent = busy ? 'Analyzing…' : 'Analyze syllabus';
  $('#busy-msg').textContent = busy ? 'Comparing your syllabus with job ads…' : '';
}

function showError(message) {
  const box = $('#form-error');
  box.textContent = message;
  box.hidden = false;
}

function hideError() {
  $('#form-error').hidden = true;
}

// SkillsGap web page: loads the settings from the server, then switches
// between the views (Analyze, Results, Validate, About) using the address bar
// hash (#/, #/results, #/validate, #/about).
//
// Results live in memory only. Reloading the page clears them.

import { $, $$ } from './dom.js';
import { getMeta, ApiError } from './api.js';
import { initStart } from './start.js';
import { initResults, showResults } from './results.js';
import { showValidate } from './validate.js';
import { showAbout } from './about.js';

const state = { meta: null, analysis: null };

const VIEWS = {
  start: { section: '#view-start', heading: '#start-title', title: 'SkillsGap · Is your syllabus job-ready?' },
  results: { section: '#view-results', heading: '#results-title', title: 'Results · SkillsGap' },
  validate: { section: '#view-validate', heading: '#validate-title', title: 'Validate · SkillsGap' },
  about: { section: '#view-about', heading: '#about-title', title: 'About · SkillsGap' },
};

let firstRoute = true;

function route() {
  let name = location.hash.replace(/^#\/?/, '') || 'start';
  if (!VIEWS[name]) name = 'start';
  if (name === 'results' && !state.analysis) {
    location.replace('#/');
    return;
  }
  for (const [key, view] of Object.entries(VIEWS)) $(view.section).hidden = key !== name;
  if (name === 'validate') showValidate(state);

  // Highlight the current page in the menu ("Analyze" covers start and results).
  const navKey = name === 'results' ? 'start' : name;
  $$('.nav a').forEach((a) => {
    if (a.dataset.route === navKey) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });

  document.title = VIEWS[name].title;
  // Move keyboard / screen-reader focus to the new page's heading (not on first load).
  if (!firstRoute) {
    window.scrollTo({ top: 0 });
    $(VIEWS[name].heading)?.focus({ preventScroll: true });
  }
  firstRoute = false;
}

async function main() {
  window.addEventListener('hashchange', route);
  route();

  try {
    state.meta = await getMeta();
  } catch (err) {
    showBanner(err instanceof ApiError ? err.message : 'The page could not load. Please reload.');
    $('#analyze-btn').disabled = true;
    return;
  }
  if (state.meta.data_error) {
    showBanner(state.meta.data_error);
    $('#analyze-btn').disabled = true;
  }
  $('#attribution').textContent = state.meta.attribution;
  showAbout(state.meta);
  if (!$('#view-validate').hidden) showValidate(state);   // opened directly at #/validate

  initResults();
  initStart(state.meta, (analysis) => {
    state.analysis = analysis;
    // Show the results view first, so the dashboard can measure its width.
    location.hash = '#/results';
    route();
    showResults(analysis, state.meta);
  });

  $('#new-btn').addEventListener('click', () => { location.hash = '#/'; });
}

function showBanner(message) {
  const banner = $('#data-error');
  banner.textContent = message;
  banner.hidden = false;
}

main();

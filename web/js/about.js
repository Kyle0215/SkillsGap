// About page: how it works, the data, limitations, responsible use and the team.
// Short on purpose. Every number comes from the server (/api/meta).

import { $, h } from './dom.js';
import { formatMonth } from './shared.js';

export function showAbout(meta) {
  const src = meta.source;
  const month = formatMonth(src.date_range) || 'UNKNOWN';
  const region = src.region || 'UNKNOWN';
  const jobs = Number.isInteger(src.postings_used) ? src.postings_used.toLocaleString('en-US') : 'UNKNOWN';
  const threshold = Math.round(meta.gap_threshold * 100);
  const sourceName = src.name || 'UNKNOWN';
  const sourceLink = src.url && src.url.startsWith('https://')
    ? h('a', { href: src.url, rel: 'noopener noreferrer', target: '_blank' }, sourceName)
    : sourceName;

  const card = (title, ...content) => h('section', { class: 'card info-card', 'aria-label': title },
    h('h2', { class: 'kicker' }, title), ...content);
  const list = (items) => h('ul', { class: 'info-list' }, items.map((item) => h('li', {}, item)));

  $('#about-body').replaceChildren(
    card('How it works',
      h('ol', { class: 'info-steps' },
        h('li', {}, h('b', {}, 'Reads the syllabus'), ' text (PDF, Word or pasted).'),
        h('li', {}, h('b', {}, 'Looks for each skill'), ' as whole words. Exact: the name only. Smart: the name plus synonyms, for example “Splunk” for SIEM.'),
        h('li', {}, h('b', {}, 'Compares with job ads.'), ` Not found, and in ${threshold}% or more of ads, means a potential gap.`)),
      h('p', { class: 'hint' }, 'Dictionary-based matching, not AI. Scores use placeholder formulas.')),
    card('The data',
      h('dl', { class: 'facts' },
        fact('Source', sourceLink),
        fact('Licence', src.licence || 'UNKNOWN'),
        fact('Collected', src.collection_method || 'UNKNOWN'),
        fact('Dates', month),
        fact('Region', region === 'Global' ? 'Global · mostly US, no Malaysian postings' : region),
        fact('Job ads', jobs),
        fact('Roles', String(meta.roles.length)),
        fact('Skills', meta.skills_total ? String(meta.skills_total) : 'UNKNOWN'))),
    card('Limitations',
      list([
        'Misses skills taught without their name.',
        'Can count a word used in another sense.',
        'Can’t tell how deeply a topic is taught.',
        'Only finds skills in its dictionary.',
      ])),
    card('Responsible use',
      list([
        [h('b', {}, 'Never stored.'), ' Syllabi are processed in memory only.'],
        [h('b', {}, 'People decide.'), ' Results support a lecturer or committee; they don’t replace them.'],
        [h('b', {}, '“Not detected” ≠ “not taught”.'), ' It only means the words weren’t found.'],
        [h('b', {}, 'Job-ad data has limits.'), ` ${sourceName}, ${month}, region: ${region}.`],
      ])),
    card('Team',
      h('p', { class: 'team' }, h('b', {}, 'Team ArgonUT'), ' · HackSpire Lumina, UNITEN'),
      h('p', { class: 'hint' }, 'Prototype. Built with help from an AI coding assistant.')),
  );
}

function fact(label, value) {
  return [h('dt', {}, label), h('dd', {}, value)];
}

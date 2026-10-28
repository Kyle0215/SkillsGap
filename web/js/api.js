// Talking to the SkillsGap server (server.py). Every error becomes a short,
// friendly message; the page never shows technical details.

export class ApiError extends Error {}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(path, { ...options, cache: 'no-store' });
  } catch {
    throw new ApiError("Can't reach the SkillsGap server. Check your connection and try again.");
  }
  let body = null;
  try {
    body = await response.json();
  } catch {
    // Not JSON (for example a proxy error page): fall through to the message below.
  }
  if (!response.ok) {
    throw new ApiError((body && body.error) || 'Something went wrong. Please try again.');
  }
  return body;
}

// Roles, samples, data source and validation status.
export const getMeta = () => request('/api/meta');

// payload: {reference_base64, results: {level1, level2}}
// Returns {rows, blank, comparisons: {brief_on: {level1, level2}, brief_off: {level1, level2}}}.
export const validateReference = (payload) =>
  request('/api/validate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

// payload: {source: 'upload'|'paste'|'sample', role, text?, sample?, filename?, file_base64?}
// Returns {role, source_label, elapsed_seconds, results: {level1, level2}}.
export const analyzeSyllabus = (payload) =>
  request('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

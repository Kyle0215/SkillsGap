// Draggable tile grid: a plain-JavaScript version of the "Draggable Widget Grid"
// reference component (draggable-widget-grid-project).
//
// Each tile has a size: sm 1×1, wide 2×1, tall 1×2, lg 2×2 (columns × rows).
// The tiles are kept as an ordered list; an "exact tiler" turns that list
// into a gap-free layout for the current number of columns (4, 2 or 1).
//
//  - Mouse / pen: press on a tile (not on a button) and drag.
//  - Touch: press and hold, then drag (so the page can still scroll).
//  - Keyboard: focus a tile, hold Alt and press the arrow keys.
// Other tiles slide out of the way (FLIP animation). Reduced motion is respected.

const SPANS = { sm: [1, 1], wide: [2, 1], tall: [1, 2], lg: [2, 2] };
const ENTER = 0.18;          // fraction of a slot the dragged tile's centre must enter to take it
const SETTLE_MS = 40;        // minimum time between two reorders while dragging
const DRAG_START_PX = 5;     // mouse movement before a press becomes a drag (so clicks still work)
const LONG_PRESS_MS = 350;   // touch: hold time before a tile lifts
const PRESS_SLOP = 8;        // touch: movement allowed during the hold before it counts as a scroll
const NO_DRAG = 'button, a, input, select, textarea, summary, label, [data-no-drag]';

const reduceMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ---------------------------------------------------------------------------
// Layout (ported from the reference component)
// ---------------------------------------------------------------------------

function spanOf(item, columns) {
  const [w, h] = SPANS[item.size];
  return { w: Math.min(w, columns), h };
}

// Places every tile: exact tiling first (no gaps), otherwise a row packer.
export function layout(items, columns) {
  if (columns < 1 || items.length === 0) return [];
  return tile(items, columns) ?? pack(items, columns);
}

// Exact tiling: the first empty cell (in reading order) takes the earliest
// tile that fits there and still lets the rest be placed.
function tile(items, columns) {
  const spans = items.map((item) => spanOf(item, columns));
  const area = spans.reduce((n, s) => n + s.w * s.h, 0);
  const rows = Math.ceil(area / columns);
  const grid = new Array(rows * columns).fill(false);
  const used = new Array(items.length).fill(false);
  const out = [];
  let budget = 20000;

  const fits = (w, h, r, c) => {
    if (c + w > columns || r + h > rows) return false;
    for (let y = r; y < r + h; y++) for (let x = c; x < c + w; x++) if (grid[y * columns + x]) return false;
    return true;
  };
  const mark = (w, h, r, c, value) => {
    for (let y = r; y < r + h; y++) for (let x = c; x < c + w; x++) grid[y * columns + x] = value;
  };
  const place = (count) => {
    if (count === items.length) return true;
    if (--budget < 0) return false;
    const i = grid.indexOf(false);
    if (i < 0) return false;
    const r = Math.floor(i / columns);
    const c = i % columns;
    const tried = new Set();            // tiles of the same shape are interchangeable here
    for (let k = 0; k < items.length; k++) {
      if (used[k]) continue;
      const { w, h } = spans[k];
      const shape = `${w}x${h}`;
      if (tried.has(shape) || !fits(w, h, r, c)) continue;
      tried.add(shape);
      used[k] = true;
      mark(w, h, r, c, true);
      out.push({ id: items[k].id, col: c, row: r, w, h });
      if (place(count + 1)) return true;
      out.pop();
      mark(w, h, r, c, false);
      used[k] = false;
    }
    return false;
  };
  return place(0) ? out : null;
}

// Fallback: fill rows in order, then widen tiles to close each row.
function pack(items, columns) {
  const out = [];
  let row = 0;
  let queue = items.map((item) => ({ id: item.id, ...spanOf(item, columns) }));
  while (queue.length > 0) {
    const height = Math.max(...queue.slice(0, columns).map((q) => q.h));
    const cells = new Array(height * columns).fill(false);
    const band = [];
    const rest = [];
    for (const q of queue) {
      let spot = -1;
      for (let i = 0; i < cells.length && spot < 0; i++) {
        const r = Math.floor(i / columns);
        const c = i % columns;
        if (c + q.w > columns || r + q.h > height) continue;
        let free = true;
        for (let y = r; y < r + q.h && free; y++) for (let x = c; x < c + q.w && free; x++) if (cells[y * columns + x]) free = false;
        if (free) spot = i;
      }
      if (spot < 0 || rest.length > 0) { rest.push(q); continue; }
      const r = Math.floor(spot / columns);
      const c = spot % columns;
      for (let y = r; y < r + q.h; y++) for (let x = c; x < c + q.w; x++) cells[y * columns + x] = true;
      band.push({ id: q.id, col: c, row: r, w: q.w, h: q.h });
    }
    for (let i = 0; i < cells.length; i++) {
      if (cells[i]) continue;
      const r = Math.floor(i / columns);
      const c = i % columns;
      const left = band.find((p) => p.col + p.w === c && p.row <= r && p.row + p.h > r && p.h === 1);
      const above = band.find((p) => p.row + p.h === r && p.col === c && p.w === 1);
      const grow = left ?? above;
      if (!grow) continue;
      if (grow === left) grow.w += 1; else grow.h += 1;
      cells[i] = true;
    }
    out.push(...band.map((p) => ({ ...p, row: p.row + row })));
    row += height;
    queue = rest;
  }
  return out;
}

// Reorders `items` to match the reading order of their layout (if that keeps the layout).
function canonical(items, columns) {
  const places = layout(items, columns);
  if (places.length !== items.length) return items;
  const byId = new Map(items.map((item) => [item.id, item]));
  const sorted = [...places].sort((a, b) => a.row - b.row || a.col - b.col).map((p) => byId.get(p.id));
  if (sorted.every((item, i) => item === items[i])) return items;
  const at = new Map(places.map((p) => [p.id, p]));
  const same = layout(sorted, columns).every((p) => {
    const q = at.get(p.id);
    return q && q.col === p.col && q.row === p.row && q.w === p.w && q.h === p.h;
  });
  return same ? sorted : items;
}

function moveTo(items, id, index) {
  const from = items.findIndex((item) => item.id === id);
  if (from < 0 || from === index || index < 0 || index >= items.length) return items;
  const next = [...items];
  const [moved] = next.splice(from, 1);
  next.splice(index, 0, moved);
  return next;
}

const sameOrder = (a, b) => a.length === b.length && a.every((item, i) => item.id === b[i].id);

// ---------------------------------------------------------------------------
// Drop target selection (ported from the reference component)
//
// Every arrangement one move away is a "candidate". We pick the one whose slot
// for the dragged tile is nearest to the tile's centre, and only if it is
// nearer than where the tile already is. Every accepted move therefore strictly
// reduces that distance, so tiles can't flip back and forth.
// ---------------------------------------------------------------------------

const overlaps = (a, b) => a.col < b.col + b.w && b.col < a.col + a.w && a.row < b.row + b.h && b.row < a.row + a.h;
const contains = (outer, inner) => inner.col >= outer.col && inner.row >= outer.row
  && inner.col + inner.w <= outer.col + outer.w && inner.row + inner.h <= outer.row + outer.h;

function choose(home, candidates, cx, cy) {
  const distance = (slot, inset) => {
    const ix = (slot.right - slot.left) * inset;
    const iy = (slot.bottom - slot.top) * inset;
    const dx = Math.max(slot.left + ix - cx, 0, cx - (slot.right - ix));
    const dy = Math.max(slot.top + iy - cy, 0, cy - (slot.bottom - iy));
    return Math.hypot(dx, dy);
  };
  const toCentre = (slot) => Math.hypot((slot.left + slot.right) / 2 - cx, (slot.top + slot.bottom) / 2 - cy);
  let best = distance(home, 0);
  if (best === 0) return null;
  let pick = null;
  let bestCentre = Infinity;
  for (const { order, slot } of candidates) {
    const d = distance(slot, ENTER);
    const c = toCentre(slot);
    if (d < best || (d === best && pick && c < bestCentre)) {
      best = d;
      bestCentre = c;
      pick = order;
    }
  }
  return pick;
}

// Group swaps (a same-shaped area filled by smaller tiles trades places with the
// dragged tile) and sequence moves (the dragged tile takes another position).
function candidatesFor(items, id, columns, toSlot) {
  const places = layout(items, columns);
  const me = places.find((p) => p.id === id);
  if (!me) return [];
  const byId = new Map(items.map((item) => [item.id, item]));
  const rows = Math.max(...places.map((p) => p.row + p.h));
  const out = [];
  for (let row = 0; row + me.h <= rows; row++) {
    for (let col = 0; col + me.w <= columns; col++) {
      const area = { col, row, w: me.w, h: me.h };
      if (overlaps(area, me)) continue;
      const group = places.filter((p) => overlaps(p, area));
      if (group.length < 2 || !group.every((p) => contains(area, p))) continue;
      const moved = places.map((p) => (p.id === id ? { ...p, col, row }
        : group.includes(p) ? { ...p, col: p.col - col + me.col, row: p.row - row + me.row } : p));
      moved.sort((a, b) => a.row - b.row || a.col - b.col);
      out.push({ order: moved.map((p) => byId.get(p.id)), slot: toSlot(area) });
    }
  }
  const from = items.findIndex((item) => item.id === id);
  for (let i = 0; i < items.length; i++) {
    if (i === from) continue;
    const order = moveTo(items, id, i);
    const p = layout(order, columns).find((q) => q.id === id);
    if (p) out.push({ order, slot: toSlot(p) });
  }
  return out;
}

// ---------------------------------------------------------------------------
// The grid
// ---------------------------------------------------------------------------

export class DraggableGrid {
  /**
   * container: the element that holds the tiles.
   * tiles: [{id, size: 'sm'|'wide'|'tall'|'lg', label, el}] in their starting order.
   * options.describedBy: id of the element that explains how to move tiles.
   * options.announce(message): tells screen-reader users what happened.
   */
  constructor(container, tiles, { describedBy, announce } = {}) {
    this.el = container;
    this.items = tiles.map(({ id, size }) => ({ id, size }));
    this.initial = [...this.items];
    this.tiles = new Map(tiles.map((t) => [t.id, t]));
    this.announce = announce || (() => {});
    this.columns = 0;
    this.press = null;
    this.drag = null;

    this.el.setAttribute('role', 'list');
    for (const t of tiles) {
      t.el.setAttribute('role', 'listitem');
      t.el.tabIndex = 0;
      t.el.dataset.tileId = t.id;
      if (describedBy) t.el.setAttribute('aria-describedby', describedBy);
      t.el.addEventListener('pointerdown', (e) => this.onPointerDown(e, t.id));
      t.el.addEventListener('keydown', (e) => this.onKeyDown(e, t.id));
      // While a touch drag is active, stop the page from scrolling.
      t.el.addEventListener('touchmove', (e) => { if (this.drag) e.preventDefault(); }, { passive: false });
      this.el.append(t.el);
    }
    this.onMove = this.onMove.bind(this);
    this.onUp = this.onUp.bind(this);
    new ResizeObserver(() => this.measure()).observe(this.el);
    this.measure();
  }

  measure() {
    const width = this.el.clientWidth;
    if (width < 1) return;
    const columns = width >= 880 ? 4 : width >= 520 ? 2 : 1;
    if (columns === this.columns) return;
    this.columns = columns;
    this.el.dataset.cols = String(columns);
    this.el.style.gridTemplateColumns = `repeat(${columns}, minmax(0, 1fr))`;
    this.items = canonical(this.items, columns);
    this.apply(false);
    this.syncDomOrder();
  }

  // Puts every tile in its grid cell. With animate, tiles slide from where they were.
  apply(animate) {
    const before = animate && !reduceMotion()
      ? new Map([...this.tiles].map(([id, t]) => [id, { x: t.el.offsetLeft, y: t.el.offsetTop }]))
      : null;
    const placements = layout(this.items, this.columns);
    for (const p of placements) {
      const { el } = this.tiles.get(p.id);
      el.style.gridColumn = `${p.col + 1} / span ${p.w}`;
      el.style.gridRow = `${p.row + 1} / span ${p.h}`;
    }
    const order = [...placements].sort((a, b) => a.row - b.row || a.col - b.col);
    order.forEach((p, i) => {
      const { el } = this.tiles.get(p.id);
      el.setAttribute('aria-posinset', String(i + 1));
      el.setAttribute('aria-setsize', String(order.length));
    });
    if (!before) return;
    for (const [id, t] of this.tiles) {
      if (this.drag && this.drag.id === id) continue;
      const was = before.get(id);
      const dx = was.x - t.el.offsetLeft;
      const dy = was.y - t.el.offsetTop;
      if (dx || dy) {
        t.el.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: 'translate(0, 0)' }],
          { duration: 340, easing: 'cubic-bezier(0.2, 0.8, 0.2, 1)' });
      }
    }
  }

  // Keep the page (and Tab) order the same as the visual order.
  syncDomOrder() {
    const active = document.activeElement;
    const order = [...layout(this.items, this.columns)].sort((a, b) => a.row - b.row || a.col - b.col);
    const els = order.map((p) => this.tiles.get(p.id).el);
    if (els.every((el, i) => this.el.children[i] === el)) return;
    this.el.append(...els);
    if (active && this.el.contains(active)) active.focus({ preventScroll: true });
  }

  position(id) {
    const order = [...layout(this.items, this.columns)].sort((a, b) => a.row - b.row || a.col - b.col);
    return order.findIndex((p) => p.id === id) + 1;
  }

  reset() {
    this.items = canonical([...this.initial], this.columns);
    this.apply(true);
    this.syncDomOrder();
    this.announce('Layout reset.');
  }

  // ---------- Keyboard: Alt + arrow keys ----------
  onKeyDown(e, id) {
    if (!e.altKey) return;
    if (e.target !== this.tiles.get(id).el && e.target.closest('input, textarea, select')) return;
    const delta = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1
      : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0;
    if (!delta) return;
    e.preventDefault();
    const from = this.items.findIndex((item) => item.id === id);
    for (let to = from + delta; to >= 0 && to < this.items.length; to += delta) {
      const next = canonical(moveTo(this.items, id, to), this.columns);
      if (sameOrder(next, this.items)) continue;
      this.items = next;
      this.apply(true);
      this.syncDomOrder();
      this.tiles.get(id).el.focus({ preventScroll: true });
      this.announce(`${this.tiles.get(id).label} moved to position ${this.position(id)} of ${this.items.length}.`);
      return;
    }
  }

  // ---------- Pointer: mouse, pen and touch ----------
  onPointerDown(e, id) {
    if (e.button !== 0 || !e.isPrimary || this.drag) return;
    if (e.target.closest(NO_DRAG)) return;
    const el = this.tiles.get(id).el;
    this.press = { id, pointerId: e.pointerId, x: e.clientX, y: e.clientY, touch: e.pointerType === 'touch', timer: 0 };
    if (this.press.touch) {
      el.classList.add('is-holding');
      this.press.timer = window.setTimeout(() => this.startDrag(), LONG_PRESS_MS);
    }
    window.addEventListener('pointermove', this.onMove);
    window.addEventListener('pointerup', this.onUp);
    window.addEventListener('pointercancel', this.onUp);
  }

  onMove(e) {
    const press = this.press;
    if (!press || e.pointerId !== press.pointerId) return;
    const moved = Math.hypot(e.clientX - press.x, e.clientY - press.y);
    if (!this.drag) {
      if (press.touch) { if (moved > PRESS_SLOP) this.endPress(); return; }
      if (moved < DRAG_START_PX) return;
      this.startDrag();
    }
    e.preventDefault();
    this.dragTo(e.clientX, e.clientY);
  }

  startDrag() {
    const press = this.press;
    if (!press) return;
    window.clearTimeout(press.timer);
    const t = this.tiles.get(press.id);
    t.el.classList.remove('is-holding');
    t.el.classList.add('is-dragging');
    this.el.classList.add('is-dragging-any');
    if (press.touch) navigator.vibrate?.(10);
    this.drag = {
      id: press.id, el: t.el, startX: t.el.offsetLeft, startY: t.el.offsetTop,
      px: press.x, py: press.y, left: t.el.offsetLeft, top: t.el.offsetTop,
      lastMove: 0, retry: 0, startOrder: this.items,
    };
    this.placeDragged();
  }

  dragTo(x, y) {
    const d = this.drag;
    d.left = d.startX + (x - d.px);
    d.top = d.startY + (y - d.py);
    this.placeDragged();
    this.step();
  }

  // Picks the best arrangement for the dragged tile's current position.
  step(force = false) {
    const d = this.drag;
    if (!d) return;
    window.clearTimeout(d.retry);
    const now = performance.now();
    if (!force && now - d.lastMove < SETTLE_MS) {
      // Try again shortly, so a tile that is held still still settles.
      d.retry = window.setTimeout(() => this.step(), SETTLE_MS);
      return;
    }
    const me = layout(this.items, this.columns).find((p) => p.id === d.id);
    if (!me) return;
    const toSlot = this.slotMapper();
    const order = choose(toSlot(me), candidatesFor(this.items, d.id, this.columns, toSlot),
      d.left + d.el.offsetWidth / 2, d.top + d.el.offsetHeight / 2);
    if (!order) return;
    const next = canonical(order, this.columns);
    if (sameOrder(next, this.items)) return;
    d.lastMove = now;
    this.items = next;
    this.apply(true);
    this.placeDragged();
  }

  // Turns a grid box {col, row, w, h} into a rectangle in the grid's own pixels,
  // using the real column widths and row heights the browser computed.
  slotMapper() {
    const style = getComputedStyle(this.el);
    const colGap = parseFloat(style.columnGap) || 0;
    const rowGap = parseFloat(style.rowGap) || 0;
    const colWidth = (this.el.clientWidth - colGap * (this.columns - 1)) / this.columns;
    const rows = style.gridTemplateRows.split(' ').map(parseFloat).filter((n) => n > 0);
    const base = rows.length ? Math.min(...rows) : 196;
    const rowTop = (r) => {
      let top = 0;
      for (let i = 0; i < r; i++) top += (rows[i] ?? base) + rowGap;
      return top;
    };
    return (box) => {
      const left = box.col * (colWidth + colGap);
      const top = rowTop(box.row);
      return { left, top, right: left + box.w * colWidth + (box.w - 1) * colGap, bottom: rowTop(box.row + box.h) - rowGap };
    };
  }

  // Keeps the dragged tile under the pointer, wherever its grid cell is now.
  placeDragged() {
    const d = this.drag;
    d.el.style.transform = `translate(${d.left - d.el.offsetLeft}px, ${d.top - d.el.offsetTop}px) scale(1.03)`;
  }

  onUp(e) {
    if (!this.press || e.pointerId !== this.press.pointerId) return;
    if (this.drag) this.finishDrag();
    this.endPress();
  }

  endPress() {
    if (this.press) {
      window.clearTimeout(this.press.timer);
      this.tiles.get(this.press.id)?.el.classList.remove('is-holding');
    }
    this.press = null;
    window.removeEventListener('pointermove', this.onMove);
    window.removeEventListener('pointerup', this.onUp);
    window.removeEventListener('pointercancel', this.onUp);
  }

  finishDrag() {
    const d = this.drag;
    window.clearTimeout(d.retry);
    this.step(true);                      // settle on the final position first
    this.drag = null;
    const from = d.el.style.transform;
    d.el.style.transform = '';
    d.el.classList.remove('is-dragging');
    this.el.classList.remove('is-dragging-any');
    if (!reduceMotion()) {
      d.el.animate([{ transform: from }, { transform: 'translate(0, 0) scale(1)' }],
        { duration: 280, easing: 'cubic-bezier(0.2, 0.8, 0.2, 1)' });
    }
    d.el.classList.add('is-landed');
    window.setTimeout(() => d.el.classList.remove('is-landed'), 650);
    // The click that follows a drag (same event sequence as this pointerup) must
    // not press a button inside the tile. The guard is removed right after, so a
    // later, real click is never swallowed.
    const guard = (ev) => { ev.stopPropagation(); ev.preventDefault(); };
    window.addEventListener('click', guard, { capture: true, once: true });
    window.setTimeout(() => window.removeEventListener('click', guard, { capture: true }), 0);
    this.syncDomOrder();
    if (!sameOrder(d.startOrder, this.items)) {
      this.announce(`${this.tiles.get(d.id).label} moved to position ${this.position(d.id)} of ${this.items.length}.`);
    }
  }
}

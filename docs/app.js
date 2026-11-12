/* Manna: renders the day's edition (embedded as JSON in index.html) and runs the Bible tab. */
(function () {
  'use strict';
  var BOOKS = [["Genesis",50],["Exodus",40],["Leviticus",27],["Numbers",36],["Deuteronomy",34],["Joshua",24],["Judges",21],["Ruth",4],["1 Samuel",31],["2 Samuel",24],["1 Kings",22],["2 Kings",25],["1 Chronicles",29],["2 Chronicles",36],["Ezra",10],["Nehemiah",13],["Esther",10],["Job",42],["Psalm",150],["Proverbs",31],["Ecclesiastes",12],["Song of Solomon",8],["Isaiah",66],["Jeremiah",52],["Lamentations",5],["Ezekiel",48],["Daniel",12],["Hosea",14],["Joel",3],["Amos",9],["Obadiah",1],["Jonah",4],["Micah",7],["Nahum",3],["Habakkuk",3],["Zephaniah",3],["Haggai",2],["Zechariah",14],["Malachi",4],["Matthew",28],["Mark",16],["Luke",24],["John",21],["Acts",28],["Romans",16],["1 Corinthians",16],["2 Corinthians",13],["Galatians",6],["Ephesians",6],["Philippians",4],["Colossians",4],["1 Thessalonians",5],["2 Thessalonians",3],["1 Timothy",6],["2 Timothy",4],["Titus",3],["Philemon",1],["Hebrews",13],["James",5],["1 Peter",5],["2 Peter",3],["1 John",5],["2 John",1],["3 John",1],["Jude",1],["Revelation",22]];
  var NT_START = 39;
  var ALIAS = { gen:0, ge:0, gn:0, ex:1, exo:1, exod:1, lev:2, lv:2, num:3, nm:3, deut:4, dt:4, josh:5, jos:5, judg:6, jdg:6, ru:7, '1sam':8, '1sa':8, '2sam':9, '2sa':9, '1kgs':10, '1ki':10, '2kgs':11, '2ki':11, '1chr':12, '1ch':12, '2chr':13, '2ch':13, neh:15, est:16, esth:16, ps:18, psa:18, pss:18, psalms:18, prov:19, pr:19, prv:19, eccl:20, ecc:20, qoh:20, song:21, sos:21, songofsongs:21, canticles:21, isa:22, jer:23, lam:24, ezek:25, eze:25, dan:26, hos:27, obad:30, ob:30, mic:32, nah:33, hab:34, zeph:35, hag:36, zech:37, mal:38, matt:39, mt:39, mk:40, mrk:40, lk:41, luk:41, jn:42, jhn:42, rom:44, ro:44, '1cor':45, '2cor':46, gal:47, eph:48, phil:49, php:49, col:50, '1thess':51, '1th':51, '2thess':52, '2th':52, '1tim':53, '1ti':53, '2tim':54, '2ti':54, tit:55, phlm:56, philem:56, phm:56, heb:57, jas:58, jm:58, '1pet':59, '1pe':59, '2pet':60, '2pe':60, '1jn':61, '1jo':61, '2jn':62, '3jn':63, jude:64, rev:65, re:65, revelations:65 };
  var $ = function (id) { return document.getElementById(id); };
  var store = {
    get: function (k, d) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
  };
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function lordify(h) { return h.replace(/\b(LORD|GOD)\b/g, function (m) { return '<span class="sc">' + m.charAt(0) + m.slice(1).toLowerCase() + '</span>'; }); }
  function fmtText(s) { return lordify(esc(s)); }
  /* Prose from the edition: escape, then {{ref|label}} -> tappable reference, *word* -> italics, LORD -> small caps */
  function rich(s) {
    var h = esc(s);
    h = h.replace(/\{\{([^}|]+)(?:\|([^}]*))?\}\}/g, function (_, r, l) { return '<button class="ref" type="button" data-ref="' + r + '">' + (l || r) + '</button>'; });
    h = h.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
    return lordify(h);
  }
  var CHEV = '<svg class="chev" viewBox="0 0 8 13"><polyline points="1.5 1.5 6.5 6.5 1.5 11.5"/></svg>';
  var TICK = '<svg viewBox="0 0 24 24"><polyline points="5 12 10 17 19 7"/></svg>';

  /* ---------------------------------------------------------------- reference parsing */
  function norm(s) { return s.toLowerCase().replace(/\./g, '').trim().replace(/^(first|1st|i)\s+/, '1').replace(/^(second|2nd|ii)\s+/, '2').replace(/^(third|3rd|iii)\s+/, '3').replace(/\s+/g, ''); }
  var NAMEKEYS = BOOKS.map(function (b) { return norm(b[0]); });
  function findBook(raw) {
    var k = norm(raw);
    if (!k) return -1;
    if (Object.prototype.hasOwnProperty.call(ALIAS, k)) return ALIAS[k];
    var exact = NAMEKEYS.indexOf(k);
    if (exact > -1) return exact;
    if (k.length < 3) return -1;
    for (var i = 0; i < NAMEKEYS.length; i++) if (NAMEKEYS[i].indexOf(k) === 0) return i;
    return -1;
  }
  function parseRef(q) {
    var m = String(q).trim().match(/^((?:[1-3]|i{1,3}|first|second|third|1st|2nd|3rd)?\s*[a-z][a-z .]*?)\s*(\d+)?\s*(?:[:.]\s*(\d+)\s*(?:[-–—]\s*(\d+))?)?\s*$/i);
    if (!m) return null;
    var b = findBook(m[1]);
    if (b < 0) return null;
    var ch = m[2] ? +m[2] : 1, v1 = m[3] ? +m[3] : 0, v2 = m[4] ? +m[4] : 0;
    if (BOOKS[b][1] === 1 && m[2] && !m[3]) { v1 = ch; ch = 1; }
    if (ch < 1 || ch > BOOKS[b][1]) return null;
    return { b: b, c: ch, v1: v1, v2: v2 || v1 };
  }

  /* ---------------------------------------------------------------- tabs, nav bars */
  var screens = { today: $('s-today'), bible: $('s-bible') };
  function showTab(name) {
    $('tab-today').setAttribute('aria-selected', name === 'today');
    $('tab-bible').setAttribute('aria-selected', name === 'bible');
    screens.today.hidden = name !== 'today';
    screens.bible.hidden = name !== 'bible';
    screens[name].scrollTop = 0;  /* every screen opens at the top */
    syncNav(screens[name]);
  }
  function syncNav(sc) { sc.querySelectorAll('[data-nav]').forEach(function (n) { n.classList.toggle('solid', sc.scrollTop > 44); }); }
  Object.keys(screens).forEach(function (k) { screens[k].addEventListener('scroll', function () { syncNav(screens[k]); }, { passive: true }); });
  $('tab-today').addEventListener('click', function () { if (!screens.today.hidden) screens.today.scrollTo({ top: 0, behavior: 'smooth' }); showTab('today'); });
  $('tab-bible').addEventListener('click', function () { if (!screens.bible.hidden && !$('b-reader').hidden) { goHome(); return; } showTab('bible'); });

  /* ---------------------------------------------------------------- Today: render the edition */
  var E = {};
  try { E = JSON.parse($('edition').textContent); } catch (e) { E = {}; }

  function verseHTML(v) {
    var h = esc(v[1]);
    (E.glow || []).forEach(function (g) {
      var eg = esc(g);
      if (eg) h = h.split(eg).join('<span class="hesed">' + eg + '</span>');
    });
    return '<p class="verse"><sup>' + v[0] + '</sup><span>' + lordify(h) + '</span></p>';
  }
  function stepsMini() {
    var S = E.steps, rows = [['god', 'With God'], ['together', 'With each other'], ['others', 'Out in the world']];
    return rows.map(function (r) {
      return '<div class="mini"><button class="check" type="button" data-step="' + r[0] + '" aria-pressed="false" aria-label="Mark ' + r[1] + ' done">' + TICK + '</button><span><b>' + r[1] + '</b> ' + esc(S[r[0]].short) + '</span></div>';
    }).join('');
  }
  function stepsFull() {
    var S = E.steps, rows = [['god', 'With God'], ['together', 'With each other'], ['others', 'Out in the world']];
    return rows.map(function (r) {
      var s = S[r[0]];
      return '<div class="row"><button class="check" type="button" data-step="' + r[0] + '" aria-pressed="false" aria-label="Mark ' + r[1] + ' done">' + TICK + '</button><div><span class="who">' + r[1] + '</span><p>' + rich(s.full) + '</p>' + (s.why ? '<p class="why">' + rich(s.why) + '</p>' : '') + '</div></div>';
    }).join('');
  }
  function next(i, label) { return '<button class="next" type="button" data-go="' + i + '">' + label + ' <span aria-hidden="true">›</span></button>'; }

  function renderToday() {
    if (!E.date) { $('p0').innerHTML = '<div class="missing">Today\'s reading is on its way. Pull down or reopen Manna in a little while.</div>'; return; }
    $('t-date').textContent = E.weekday_line;
    var chips = (E.chips || []).map(function (c) { return '<span class="chip">' + esc(c.label) + ' <b>' + esc(c.when) + '</b></span>'; }).join('');
    var seriesLine = esc(E.series) + (E.series_day > 1 ? ' · Day ' + E.series_day : '');

    $('p0').innerHTML =
      '<div class="group hero">' +
        '<div class="sec-h" style="padding:0 0 10px"><span>' + seriesLine + '</span></div>' +
        '<h2>' + esc(E.title) + '</h2>' +
        '<div class="sub">' + esc(E.ref_display) + ' · about 5 minutes</div>' +
        (chips ? '<div class="chips">' + chips + '</div>' : '') +
        '<div class="prose"><p style="margin:0">' + rich(E.season_line) + '</p></div>' +
      '</div>' +
      (E.big_idea
        ? '<div class="sec"><div class="group big"><div class="lab">The big idea</div><p class="idea">' + rich(E.big_idea) + '</p><div class="prose"><p>' + rich(E.frame) + '</p></div></div></div>'
        : '<div class="sec"><div class="group pad prose">' + (E.in_a_minute || []).map(function (p) { return '<p>' + rich(p) + '</p>'; }).join('') + '</div></div>') +
      '<div class="sec"><div class="lit-card"><div class="lab">One thing to carry today</div>' +
        '<blockquote>“' + fmtText(E.carry.text) + '”</blockquote><div class="r">' + esc(E.carry.display) + '</div></div></div>' +
      '<div class="sec"><div class="sec-h"><span>Today\'s steps</span><button type="button" data-go="3">Details</button></div><div class="group">' + stepsMini() + '</div></div>' +
      '<div class="sec"><div class="sec-h"><span>Tonight, together</span></div><div class="group together"><p class="q">' + esc(E.tonight) + '</p></div></div>' +
      next(1, 'Start reading');

    $('p1').innerHTML =
      '<div class="sec-h" style="margin-top:6px"><span>At a glance</span></div><div class="group">' +
        E.glance.map(function (g) { return '<div class="ol"><span class="vv">' + esc(String(g.verses).replace('-', '–')) + '</span><span><b>' + esc(g.head) + '.</b> ' + rich(g.line) + '</span></div>'; }).join('') +
      '</div>' +
      '<div class="sec"><div class="sec-h"><span>' + esc(E.ref_display) + '</span><button type="button" data-ref="' + esc(E.ref) + '">Open in Bible</button></div></div>' +
      '<div class="group pad prose">' + E.verses.map(verseHTML).join('') + '</div>' +
      '<div class="foot-note">Berean Standard Bible (BSB) · public domain</div>' + next(2, 'Understand it');

    var word = E.word && E.word.term ? '<div class="word"><span class="heb">' + esc(E.word.term) + '</span><span class="gloss">' + (E.word.english ? '<b>“' + esc(E.word.english) + '.”</b> ' : '') + rich(E.word.gloss) + '</span></div>' : '';
    var paras = E.understand.map(function (p) { return '<p>' + rich(p) + '</p>'; });
    if (word) paras.splice(Math.min(2, paras.length), 0, word);
    var more = (E.more || []).length ? '<div class="sec"><div class="sec-h"><span>If you have five more minutes</span></div><div class="group">' +
      E.more.map(function (m) { return '<button class="li" type="button" data-ref="' + esc(m.ref) + '"><span class="m"><b>' + esc(m.display) + '</b><span>' + esc(m.line) + '</span></span>' + CHEV + '</button>'; }).join('') + '</div></div>' : '';
    $('p2').innerHTML = '<div class="group pad prose" style="margin-top:6px">' + paras.join('') + '</div>' + more + next(3, 'Live it');

    $('p3').innerHTML = '<div class="group" style="margin-top:6px">' + stepsFull() + '</div><div class="foot-note" id="tally"></div>' + next(4, 'Tonight');

    $('p4').innerHTML = '<div class="group together" style="margin-top:6px"><div class="sec-h" style="padding:0 0 6px"><span>Talk it over</span></div><p class="q">' + esc(E.tonight) + '</p></div>' +
      '<div class="foot-note" style="margin-top:14px">Tomorrow · ' + esc(E.tomorrow.display) + '</div>';

    document.title = 'Manna · ' + E.title;
    paintChecks();
  }

  /* steps checklist, remembered per day on this phone */
  function stepsKey() { return 'manna-steps-' + (E.date || ''); }
  function paintChecks() {
    var done = store.get(stepsKey(), {}), n = 0, seen = {};
    document.querySelectorAll('.check').forEach(function (b) {
      var on = !!done[b.dataset.step];
      b.setAttribute('aria-pressed', on);
      if (on && !seen[b.dataset.step]) { seen[b.dataset.step] = 1; n++; }
    });
    var t = $('tally'); if (t) t.textContent = n === 3 ? 'All 3 done today. Well done.' : n + ' of 3 done today';
  }
  document.addEventListener('click', function (e) {
    var c = e.target.closest('.check');
    if (!c) return;
    var done = store.get(stepsKey(), {});
    done[c.dataset.step] = !done[c.dataset.step];
    store.set(stepsKey(), done);
    paintChecks();
  });

  /* section pills + swipe */
  var pills = document.querySelectorAll('.pill'), panels = document.querySelectorAll('.panel'), curP = 0;
  function showPanel(i) {
    i = Math.max(0, Math.min(panels.length - 1, i)); curP = i;
    pills.forEach(function (p, k) { p.setAttribute('aria-selected', k === i); });
    panels.forEach(function (p, k) { p.hidden = k !== i; });
    var pill = pills[i]; if (pill && pill.scrollIntoView) pill.scrollIntoView({ block: 'nearest', inline: 'center' });
    screens.today.scrollTop = 0;
    syncNav(screens.today);
  }
  pills.forEach(function (p) { p.addEventListener('click', function () { showPanel(+p.dataset.p); }); });
  var sx = 0, sy = 0;
  $('panels').addEventListener('touchstart', function (e) { sx = e.touches[0].clientX; sy = e.touches[0].clientY; }, { passive: true });
  $('panels').addEventListener('touchend', function (e) {
    var dx = e.changedTouches[0].clientX - sx, dy = e.changedTouches[0].clientY - sy;
    if (Math.abs(dx) > 70 && Math.abs(dx) > Math.abs(dy) * 1.6) showPanel(curP + (dx < 0 ? 1 : -1));
  }, { passive: true });

  /* delegated: section jumps and scripture links anywhere on Today */
  document.addEventListener('click', function (e) {
    var g = e.target.closest('[data-go]');
    if (g) { showPanel(+g.dataset.go); return; }
    var r = e.target.closest('[data-ref]');
    if (r && !screens.today.hidden) { var ref = parseRef(r.dataset.ref); if (ref) openRef(ref, 'Today'); }
  });

  /* ---------------------------------------------------------------- Bible */
  var cache = {};
  function loadBook(i) {
    if (cache[i]) return cache[i];
    var n = String(i + 1).padStart(2, '0');
    cache[i] = fetch('bible/' + n + '.json').then(function (r) { if (!r.ok) throw new Error('load'); return r.json(); });
    cache[i].catch(function () { delete cache[i]; });
    return cache[i];
  }
  var testament = 'ot';
  function bookName(i) { return BOOKS[i][0] === 'Psalm' ? 'Psalms' : BOOKS[i][0]; }
  function renderBooks() {
    var from = testament === 'ot' ? 0 : NT_START, to = testament === 'ot' ? NT_START : BOOKS.length, h = '';
    for (var i = from; i < to; i++) h += '<button type="button" class="li" data-book="' + i + '"><span class="m"><b>' + esc(bookName(i)) + '</b></span><span class="n">' + BOOKS[i][1] + '</span>' + CHEV + '</button>';
    $('books').innerHTML = h;
  }
  $('books').addEventListener('click', function (e) {
    var b = e.target.closest('[data-book]'); if (!b) return;
    var i = +b.dataset.book;
    if (BOOKS[i][1] === 1) { openRef({ b: i, c: 1, v1: 0, v2: 0 }, 'Bible'); return; }
    openSheet(i);
  });
  function setSeg(t) { testament = t; $('seg-ot').setAttribute('aria-selected', t === 'ot'); $('seg-nt').setAttribute('aria-selected', t === 'nt'); renderBooks(); }
  $('seg-ot').addEventListener('click', function () { setSeg('ot'); });
  $('seg-nt').addEventListener('click', function () { setSeg('nt'); });

  function openSheet(i) {
    $('sheet-t').textContent = bookName(i);
    var h = ''; for (var c = 1; c <= BOOKS[i][1]; c++) h += '<button type="button" data-c="' + c + '">' + c + '</button>';
    var g = $('grid'); g.innerHTML = h; g.dataset.book = i; g.scrollTop = 0;
    $('scrim').classList.add('on'); $('sheet').classList.add('on');
  }
  function closeSheet() { $('scrim').classList.remove('on'); $('sheet').classList.remove('on'); }
  $('grid').addEventListener('click', function (e) {
    var b = e.target.closest('[data-c]'); if (!b) return;
    closeSheet(); openRef({ b: +$('grid').dataset.book, c: +b.dataset.c, v1: 0, v2: 0 }, 'Bible');
  });
  $('scrim').addEventListener('click', closeSheet);
  $('sheet-x').addEventListener('click', closeSheet);
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeSheet(); });

  function paintContinue() {
    var last = store.get('manna-last', null);
    $('continue-wrap').hidden = !last;
    if (last) $('continue-t').textContent = BOOKS[last.b][0] + ' ' + last.c;
  }
  $('continue').addEventListener('click', function () { var l = store.get('manna-last', null); if (l) openRef({ b: l.b, c: l.c, v1: 0, v2: 0 }, 'Bible'); });

  var at = null;
  function label(r) {
    var one = BOOKS[r.b][1] === 1, s = one ? BOOKS[r.b][0] : BOOKS[r.b][0] + ' ' + r.c;
    if (r.v1) s += (one ? ' ' : ':') + r.v1 + (r.v2 && r.v2 !== r.v1 ? '–' + r.v2 : '');
    return s;
  }
  function neighbor(r, d) {
    var b = r.b, c = r.c + d;
    if (c < 1) { b--; if (b < 0) return null; c = BOOKS[b][1]; }
    else if (c > BOOKS[b][1]) { b++; if (b >= BOOKS.length) return null; c = 1; }
    return { b: b, c: c, v1: 0, v2: 0 };
  }
  function openRef(r, backLabel) {
    at = r;
    showTab('bible');
    $('b-home').hidden = true; $('b-reader').hidden = false;
    $('back-t').textContent = backLabel || 'Bible';
    $('back').dataset.to = backLabel === 'Today' ? 'today' : 'home';
    var chName = BOOKS[r.b][1] === 1 ? BOOKS[r.b][0] : BOOKS[r.b][0] + ' ' + r.c;
    $('reader-t').textContent = chName; $('r-h').textContent = chName;
    $('r-meta').textContent = r.v1 ? 'Showing ' + label(r) : 'Berean Standard Bible';
    $('r-flow').innerHTML = '<span class="muted">Opening…</span>';
    var p = neighbor(r, -1), n = neighbor(r, 1);
    $('r-prev').disabled = !p; $('r-next').disabled = !n;
    $('r-prev-t').textContent = p ? BOOKS[p.b][0] + ' ' + p.c : '';
    $('r-next-t').textContent = n ? BOOKS[n.b][0] + ' ' + n.c : '';
    screens.bible.scrollTop = 0; syncNav(screens.bible);
    store.set('manna-last', { b: r.b, c: r.c });
    loadBook(r.b).then(function (book) {
      if (at !== r) return;
      var vs = book.c[r.c - 1] || [];
      $('r-flow').innerHTML = vs.map(function (v) {
        var lit = r.v1 && v[0] >= r.v1 && v[0] <= r.v2;
        return '<span class="v' + (lit ? ' lamp' : '') + '" id="v' + v[0] + '"><sup>' + v[0] + '</sup>' + fmtText(v[1]) + '</span> ';
      }).join('');
      if (r.v1) {
        var el = $('v' + r.v1);
        if (el) setTimeout(function () { screens.bible.scrollTo({ top: Math.max(0, el.getBoundingClientRect().top - screens.bible.getBoundingClientRect().top + screens.bible.scrollTop - 120), behavior: 'smooth' }); }, 60);
      }
    }).catch(function () { $('r-flow').innerHTML = '<span class="muted">This chapter could not be loaded. Check your connection and try again.</span>'; });
  }
  function goHome() { $('b-reader').hidden = true; $('b-home').hidden = false; paintContinue(); screens.bible.scrollTop = 0; syncNav(screens.bible); }
  $('back').addEventListener('click', function () { if (this.dataset.to === 'today') { goHome(); showTab('today'); } else goHome(); });
  $('r-prev').addEventListener('click', function () { var p = neighbor(at, -1); if (p) openRef(p, $('back-t').textContent); });
  $('r-next').addEventListener('click', function () { var n = neighbor(at, 1); if (n) openRef(n, $('back-t').textContent); });

  var q = $('q'), runId = 0;
  q.addEventListener('input', function () {
    $('clear').hidden = !q.value;
    if (!q.value.trim()) { $('results').hidden = true; $('browse').hidden = false; $('hint').hidden = false; }
  });
  $('clear').addEventListener('click', function () { q.value = ''; q.dispatchEvent(new Event('input')); q.focus(); });
  $('search-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var text = q.value.trim(); if (!text) return;
    var r = /\d/.test(text) || findBook(text) > -1 ? parseRef(text) : null;
    if (r) { q.blur(); openRef(r, 'Bible'); return; }
    wordSearch(text);
  });
  function wordSearch(term) {
    var id = ++runId, hits = [], LIMIT = 150, total = 0, loaded = 0;
    var pat = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    var rx = new RegExp('\\b' + pat, 'i'), rxAll = new RegExp('(\\b' + pat + '\\w*)', 'ig');
    $('browse').hidden = true; $('hint').hidden = true; $('results').hidden = false;
    screens.bible.scrollTop = 0; syncNav(screens.bible);
    $('results-h').textContent = 'Searching for “' + term + '”';
    $('results-list').innerHTML = '<div class="status">Looking through all 66 books…</div>';
    Promise.all(BOOKS.map(function (_, i) { return loadBook(i).then(function (b) { return [i, b]; }, function () { return [i, null]; }); })).then(function (all) {
      if (id !== runId) return;
      all.forEach(function (pair) {
        var book = pair[1]; if (!book) return; loaded++;
        book.c.forEach(function (ch, ci) { ch.forEach(function (v) {
          if (rx.test(v[1])) { total++; if (hits.length < LIMIT) hits.push({ b: pair[0], c: ci + 1, v: v[0], t: v[1] }); }
        }); });
      });
      $('results-h').textContent = total ? total.toLocaleString() + ' verse' + (total === 1 ? '' : 's') + ' with “' + term + '”' + (total > LIMIT ? ' · first ' + LIMIT : '') : 'No verses found';
      if (!loaded) { $('results-list').innerHTML = '<div class="status">The Bible text could not be loaded. Check your connection and try again.</div>'; return; }
      if (!total) { $('results-list').innerHTML = '<div class="status">Try a different word, or a reference like John 3:16.</div>'; return; }
      $('results-list').innerHTML = hits.map(function (h) {
        return '<button class="res" type="button" data-b="' + h.b + '" data-c="' + h.c + '" data-v="' + h.v + '"><b>' + esc(BOOKS[h.b][0]) + ' ' + h.c + ':' + h.v + '</b><span>' + fmtText(h.t).replace(rxAll, '<mark>$1</mark>') + '</span></button>';
      }).join('');
    });
  }
  $('results-list').addEventListener('click', function (e) {
    var b = e.target.closest('.res'); if (!b) return;
    openRef({ b: +b.dataset.b, c: +b.dataset.c, v1: +b.dataset.v, v2: +b.dataset.v }, 'Bible');
  });

  /* ---------------------------------------------------------------- freshness: a home-screen app can stay open for days */
  function checkFresh() {
    if (!window.fetch) return;
    fetch('latest.json?t=' + Date.now(), { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
      if (j && j.date && E.date && j.date > E.date) location.replace(location.pathname + '?d=' + j.date);
    }).catch(function () {});
  }
  document.addEventListener('visibilitychange', function () { if (!document.hidden) checkFresh(); });

  /* ---------------------------------------------------------------- the room: dust drifting in the window light */
  (function dust() {
    var cv = $('dust'), ctx = cv.getContext && cv.getContext('2d');
    if (!ctx) return;
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var W = 0, H = 0, dpr = Math.min(2, window.devicePixelRatio || 1), motes = [], running = true;
    function size() { W = cv.clientWidth; H = cv.clientHeight; cv.width = W * dpr; cv.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); }
    function inBeam(x, y) { var t = y / H, cx = W * (0.92 - 0.55 * t); return Math.abs(x - cx) < W * (0.12 + 0.18 * t); }
    function spawn() { var y = Math.random() * H * 0.85, t = y / H, cx = W * (0.92 - 0.55 * t); return { x: cx + (Math.random() - .5) * W * (0.24 + 0.3 * t), y: y, r: .5 + Math.random() * 1.3, vx: (Math.random() - .5) * .08, vy: -.04 - Math.random() * .08, ph: Math.random() * 6.3 }; }
    size(); for (var k = 0; k < 34; k++) motes.push(spawn());
    window.addEventListener('resize', size);
    function draw() {
      ctx.clearRect(0, 0, W, H);
      motes.forEach(function (m, i) {
        if (!reduce) { m.x += m.vx; m.y += m.vy; m.ph += .012; }
        if (m.y < -4 || !inBeam(m.x, Math.max(0, m.y))) { if (!reduce) motes[i] = spawn(); }
        var a = (.18 + .22 * Math.sin(m.ph)) * (1 - m.y / H);
        if (a <= 0) return;
        ctx.beginPath(); ctx.arc(m.x, m.y, m.r, 0, 6.283);
        ctx.fillStyle = 'rgba(196, 140, 58,' + a.toFixed(3) + ')'; ctx.fill();
      });
      if (!reduce && !document.hidden) requestAnimationFrame(draw); else running = false;
    }
    requestAnimationFrame(draw);
    document.addEventListener('visibilitychange', function () { if (!document.hidden && !reduce && !running) { running = true; requestAnimationFrame(draw); } });
  })();

  /* ---------------------------------------------------------------- first visit: how to add to the Home Screen */
  (function install() {
    var ua = navigator.userAgent || '';
    var isIOS = /iPhone|iPad|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    var isAndroid = /Android/.test(ua);
    var standalone = navigator.standalone === true || (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches);
    var forced = /[?&]install\b/.test(location.search);
    if (standalone && !forced) return;
    var card = $('install'), scrim = $('install-scrim'), link = $('install-link');
    if (isAndroid) { $('install-ios').hidden = true; $('install-android').hidden = false; $('install-note').textContent = 'If you opened this link inside another app, open it in Chrome first.'; }
    function open() { card.setAttribute('aria-hidden', 'false'); card.classList.add('on'); scrim.classList.add('on'); setTimeout(function () { $('install-ok').focus({ preventScroll: true }); }, 350); }
    function close() { card.setAttribute('aria-hidden', 'true'); card.classList.remove('on'); scrim.classList.remove('on'); store.set('manna-install-seen', true); }
    $('install-ok').addEventListener('click', close);
    scrim.addEventListener('click', close);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && card.classList.contains('on')) close(); });
    if (isIOS || isAndroid || forced) { link.hidden = false; link.addEventListener('click', open); }
    if (forced || ((isIOS || isAndroid) && !store.get('manna-install-seen', false))) setTimeout(open, 700);
  })();

  renderToday();
  renderBooks();
  paintContinue();
  checkFresh();
})();

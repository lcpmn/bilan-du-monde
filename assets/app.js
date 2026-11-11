/* Bilan du monde : thème, filtres par rubrique, copie de liens, recherche dans les archives.
   Le site reste entièrement lisible sans JavaScript. */
(function () {
  "use strict";
  var root = document.documentElement;
  var EN = root.lang === "en";
  var T = EN
    ? { copied: "Link copied", none: "No story matches this search.", one: " story found", many: " stories found",
        months: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"] }
    : { copied: "Lien copié", none: "Aucun sujet ne correspond à cette recherche.", one: " sujet trouvé", many: " sujets trouvés",
        months: ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."] };

  /* ---- langue : le choix du lecteur est mémorisé ---- */
  document.addEventListener("click", function (ev) {
    var a = ev.target.closest && ev.target.closest("a[data-lang]");
    if (a) { try { localStorage.setItem("lang", a.dataset.lang); } catch (e) {} }
  });

  /* ---- thème clair / sombre ---- */
  var themeBtn = document.getElementById("theme-btn");
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var dark = root.dataset.theme
        ? root.dataset.theme === "dark"
        : window.matchMedia("(prefers-color-scheme: dark)").matches;
      var next = dark ? "light" : "dark";
      root.dataset.theme = next;
      try { localStorage.setItem("theme", next); } catch (e) {}
    });
  }

  /* ---- filtres par rubrique ---- */
  var chips = Array.prototype.slice.call(document.querySelectorAll(".chip[data-filter]"));
  var sections = Array.prototype.slice.call(document.querySelectorAll(".rubrique[data-rub]"));
  function applyFilter(f) {
    chips.forEach(function (c) { c.setAttribute("aria-pressed", String(c.dataset.filter === f)); });
    sections.forEach(function (s) { s.hidden = f !== "tout" && s.dataset.rub !== f; });
  }
  chips.forEach(function (c) {
    c.addEventListener("click", function (ev) {
      ev.preventDefault();
      var f = c.dataset.filter;
      var already = c.getAttribute("aria-pressed") === "true";
      applyFilter(already && f !== "tout" ? "tout" : f);
      var nav = document.querySelector(".filters");
      var first = sections.filter(function (s) { return !s.hidden; })[0];
      if (first && nav && f !== "tout" && !already) {
        var y = first.getBoundingClientRect().top + window.scrollY - nav.offsetHeight - 8;
        window.scrollTo({ top: y, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
      }
    });
  });

  /* ---- partager un sujet ou l'édition : menu de partage du téléphone, sinon copie du lien ---- */
  var touch = window.matchMedia && matchMedia("(pointer: coarse)").matches;
  document.addEventListener("click", function (ev) {
    var b = ev.target.closest && ev.target.closest(".share[data-share]");
    if (!b) return;
    var url = b.dataset.share, title = b.dataset.title || document.title;
    if (touch && navigator.share) {
      navigator.share({ title: title, text: title, url: url }).catch(function () {});
      return;
    }
    function done(ok) {
      if (b.dataset.busy) return;
      b.dataset.busy = "1";
      var old = b.textContent;
      b.textContent = ok ? T.copied : url;
      b.classList.toggle("done", ok);
      setTimeout(function () { b.textContent = old; b.classList.remove("done"); delete b.dataset.busy; }, 1800);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(function () { done(true); }, function () { done(false); });
    } else { done(false); }
  });

  /* ---- recherche dans les archives ---- */
  var q = document.getElementById("q");
  if (!q) return;
  var results = document.getElementById("results");
  var listing = document.getElementById("ed-index");
  var base = q.dataset.root || "../";
  var data = null, loading = null;
  function norm(s) { return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }
  function load() {
    if (!loading) {
      loading = fetch(q.dataset.search).then(function (r) { return r.json(); })
        .then(function (rows) {
          data = rows.map(function (r) { r._n = norm(r.t + " " + r.s + " " + r.r); return r; });
        }).catch(function () { data = []; });
    }
    return loading;
  }
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function highlight(node, text, terms) {
    var nt = norm(text), marks = [];
    terms.forEach(function (t) { var i = nt.indexOf(t); if (i >= 0) marks.push([i, i + t.length]); });
    marks.sort(function (a, b) { return a[0] - b[0]; });
    var pos = 0;
    marks.forEach(function (m) {
      if (m[0] < pos) return;
      node.appendChild(document.createTextNode(text.slice(pos, m[0])));
      node.appendChild(el("mark", null, text.slice(m[0], m[1])));
      pos = m[1];
    });
    node.appendChild(document.createTextNode(text.slice(pos)));
    return node;
  }
  function fmt(d) {
    var p = d.split("-");
    return EN ? T.months[+p[1] - 1] + " " + (+p[2]) + ", " + p[0] : (+p[2]) + " " + T.months[+p[1] - 1] + " " + p[0];
  }
  function run() {
    var terms = norm(q.value).split(/\s+/).filter(Boolean);
    if (!terms.length) { results.hidden = true; listing.hidden = false; return; }
    load().then(function () {
      var hits = data.filter(function (r) { return terms.every(function (t) { return r._n.indexOf(t) >= 0; }); })
        .sort(function (a, b) { return a.d < b.d ? 1 : -1; });
      results.replaceChildren();
      results.appendChild(el("p", "count", hits.length ? hits.length + (hits.length > 1 ? T.many : T.one) : T.none));
      hits.slice(0, 60).forEach(function (r) {
        var a = el("a", "hit"); a.href = base + "edition/" + r.d + "/#" + r.a;
        a.style.setProperty("--rub", "var(--r-" + r.k + ")");
        var meta = el("span", "hit-meta"); meta.appendChild(el("span", "dot")); meta.appendChild(document.createTextNode(fmt(r.d) + " · " + r.r));
        a.appendChild(meta);
        a.appendChild(highlight(el("span", "hit-title"), r.t, terms));
        if (r.s) a.appendChild(highlight(el("span", "hit-sum"), r.s, terms));
        results.appendChild(a);
      });
      results.hidden = false; listing.hidden = true;
    });
  }
  var timer;
  q.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(run, 120); });
  q.addEventListener("focus", load, { once: true });
})();

/* SHEPHERD blog: TOC scrollspy. Highlights the section currently in view,
   matching the fixed left-margin table of contents. No dependencies. */
(function () {
  "use strict";
  var toc = document.getElementById("TOC");
  if (!toc) return;

  // mobile slide-up sheet: button toggles it; link / backdrop / Esc close it
  var fab = toc.querySelector(".toc-fab");
  var backdrop = toc.querySelector(".toc-backdrop");
  function setOpen(open) {
    toc.classList.toggle("open", open);
    if (fab) fab.setAttribute("aria-expanded", open ? "true" : "false");
  }
  if (fab) fab.addEventListener("click", function () { setOpen(!toc.classList.contains("open")); });
  if (backdrop) backdrop.addEventListener("click", function () { setOpen(false); });
  toc.querySelectorAll(".toc-panel a").forEach(function (a) {
    a.addEventListener("click", function () { setOpen(false); });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") setOpen(false);
  });

  var links = {};
  toc.querySelectorAll('a[href^="#"]').forEach(function (a) {
    links[decodeURIComponent(a.getAttribute("href").slice(1))] = a;
  });

  var heads = [].slice.call(
    document.querySelectorAll(".post-body h2, .post-body h3")
  ).filter(function (h) { return h.id && links[h.id]; });
  if (!heads.length) return;

  function clear() {
    Object.keys(links).forEach(function (k) { links[k].classList.remove("active"); });
  }

  if (!("IntersectionObserver" in window)) return;

  var visible = {};
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      visible[e.target.id] = e.isIntersecting;
    });
    // pick the first heading (document order) currently in the top band
    var current = null;
    for (var i = 0; i < heads.length; i++) {
      if (visible[heads[i].id]) { current = heads[i].id; break; }
    }
    if (current) { clear(); links[current].classList.add("active"); }
  }, { rootMargin: "-80px 0px -70% 0px", threshold: 0 });

  heads.forEach(function (h) { io.observe(h); });
})();

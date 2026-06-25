/* SHEPHERD landing — "execution becomes data" diagram with a scrubber.
   Plays the trace once (create -> observe -> edit -> intercept -> revert -> fork)
   and rests on the final frame. A reader can slide the line to stop at any step,
   or hit Replay (bottom right) to run it again. Vanilla JS. */
(function () {
  "use strict";

  // copy button on the terminal block
  document.querySelectorAll(".terminal__copy").forEach((btn) => {
    btn.addEventListener("click", () => {
      const code = btn.closest(".terminal").querySelector("code");
      if (code && navigator.clipboard) navigator.clipboard.writeText(code.innerText).catch(function () {});
      btn.classList.add("copied");
      setTimeout(() => btn.classList.remove("copied"), 1200);
    });
  });

  const anim = document.getElementById("anim");
  if (!anim) return;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const SEQ = ["create", "observe", "buggy", "intercept", "revert", "fork"];
  const LAST = SEQ.length - 1;
  const STEP_MS = 1150; // dwell per step while playing

  const track  = anim.querySelector(".scrub__track");
  const fill   = anim.querySelector(".scrub__fill");
  const handle = anim.querySelector(".scrub__handle");
  const replay = anim.querySelector(".anim__replay");
  const stops  = Array.prototype.slice.call(anim.querySelectorAll(".scrub__stop"));

  let cur = LAST;   // current step index; rests on the full picture by default
  let timer = null;

  function clearTimer() { if (timer) { clearTimeout(timer); timer = null; } }

  function applyReveal(i) {
    SEQ.forEach((step, idx) => {
      const on = idx <= i;
      anim.querySelectorAll('[data-step="' + step + '"]').forEach((el) => el.classList.toggle("in", on));
    });
    const imp = anim.querySelector(".cimport");
    if (imp) imp.classList.toggle("in", i >= 0);
  }

  function paint(i) {
    const pct = i < 0 ? 0 : (i / LAST) * 100;
    if (fill) fill.style.width = pct + "%";
    if (handle) handle.style.left = pct + "%";
    stops.forEach((s, idx) => {
      s.classList.toggle("done", idx <= i);
      s.classList.toggle("active", idx === i);
    });
    if (track) track.setAttribute("aria-valuenow", Math.max(0, i));
  }

  function setStep(i) {
    cur = Math.max(0, Math.min(LAST, i));
    applyReveal(cur);
    paint(cur);
  }

  // play once from the start, then stop on the final frame
  function play() {
    clearTimer();
    if (reduce) { setStep(LAST); return; }
    setStep(0);
    timer = setTimeout(function tick() {
      if (cur >= LAST) { clearTimer(); return; }
      setStep(cur + 1);
      if (cur < LAST) timer = setTimeout(tick, STEP_MS);
    }, STEP_MS);
  }

  if (replay) replay.addEventListener("click", play);

  // --- scrubber: drag / click / keyboard jumps to a step and stops playback ---
  function indexFromEvent(e) {
    const r = track.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width;
    return Math.max(0, Math.min(LAST, Math.round(x * LAST)));
  }

  let dragging = false;
  if (track) {
    track.addEventListener("pointerdown", (e) => {
      dragging = true;
      track.classList.add("dragging");
      if (track.setPointerCapture) track.setPointerCapture(e.pointerId);
      clearTimer();
      setStep(indexFromEvent(e));
      e.preventDefault();
    });
    track.addEventListener("pointermove", (e) => { if (dragging) setStep(indexFromEvent(e)); });
    const endDrag = () => { dragging = false; track.classList.remove("dragging"); };
    track.addEventListener("pointerup", endDrag);
    track.addEventListener("pointercancel", endDrag);
    track.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft" || e.key === "ArrowDown") { clearTimer(); setStep(cur - 1); e.preventDefault(); }
      else if (e.key === "ArrowRight" || e.key === "ArrowUp") { clearTimer(); setStep(cur + 1); e.preventDefault(); }
      else if (e.key === "Home") { clearTimer(); setStep(0); e.preventDefault(); }
      else if (e.key === "End") { clearTimer(); setStep(LAST); e.preventDefault(); }
    });
  }

  // --- initial: play once when scrolled into view, then rest on the last frame ---
  if (reduce) {
    setStep(LAST);
  } else {
    applyReveal(-1); paint(-1); // start blank so the first reveal reads as an animation
    if (!("IntersectionObserver" in window)) {
      play();
    } else {
      let started = false;
      const io = new IntersectionObserver((entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting && !started) { started = true; play(); io.disconnect(); }
        });
      }, { threshold: 0.35 });
      io.observe(anim);
    }
  }
})();

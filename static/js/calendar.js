(function () {
  var clock = document.getElementById('clock');
  function tick() {
    if (clock) clock.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  tick();
  setInterval(tick, 30000);

  // Click a day in the week grid to prefill the quick-add event date.
  var qa = document.getElementById('qa-date');
  var days = document.querySelectorAll('.day');
  days.forEach(function (el) {
    el.addEventListener('click', function (e) {
      if (!qa || e.target.closest('a')) return;
      qa.value = el.dataset.date;
      days.forEach(function (d) { d.classList.remove('sel'); });
      el.classList.add('sel');
      qa.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  });
})();

// Progressive enhancement only: reveals the Copy button and wires it to the
// paste box. Without JavaScript the box remains a selectable textarea.
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('[data-copy-target]').forEach(function (btn) {
    var ta = document.getElementById(btn.getAttribute('data-copy-target'));
    if (!ta) return;
    btn.hidden = false;
    function autosize() {
      ta.style.height = 'auto';
      ta.style.height = ta.scrollHeight + 'px';
    }
    autosize();
    window.addEventListener('resize', autosize);
    function done() {
      btn.textContent = 'Copied';
      setTimeout(function () { btn.textContent = 'Copy'; }, 2000);
    }
    function fallback() {
      ta.focus(); ta.select();
      try { document.execCommand('copy'); done(); } catch (e) {}
    }
    btn.addEventListener('click', function () {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(ta.value).then(done, fallback);
      } else { fallback(); }
    });
    ta.addEventListener('focus', function () { ta.select(); });
  });
});

/* UniFi MCP · Token Admin — progressive enhancements.
   Every page works without this file; it only adds conveniences. */
(function () {
  'use strict';

  /* Confirm destructive forms: <form data-confirm="Delete alice?"> */
  document.querySelectorAll('form[data-confirm]').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      if (!window.confirm(form.getAttribute('data-confirm'))) event.preventDefault();
    });
  });

  /* Copy a revealed token: <button data-copy="#new-token">.
     navigator.clipboard only exists on secure origins (HTTPS/localhost), so a
     plain-HTTP LAN deployment falls back to selecting the text and using the
     legacy execCommand copy. */
  function copyText(target) {
    var text = target.textContent.trim();
    if (navigator.clipboard) return navigator.clipboard.writeText(text);
    var range = document.createRange();
    range.selectNodeContents(target);
    var selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    selection.removeAllRanges();
    return ok ? Promise.resolve() : Promise.reject(new Error('copy failed'));
  }
  document.querySelectorAll('button[data-copy]').forEach(function (button) {
    var target = document.querySelector(button.getAttribute('data-copy'));
    if (!target) return;
    button.hidden = false;
    button.addEventListener('click', function () {
      var label = button.textContent;
      copyText(target).then(function () {
        button.textContent = 'Copied';
      }, function () {
        button.textContent = 'Select and copy manually';
      }).then(function () {
        window.setTimeout(function () { button.textContent = label; }, 1800);
      });
    });
  });

  /* Show the custom-date field only when "Custom date" is selected. */
  var preset = document.getElementById('expiry-preset');
  var custom = document.getElementById('custom-date-field');
  if (preset && custom) {
    var sync = function () {
      var isCustom = preset.value === 'custom';
      custom.hidden = !isCustom;
      var input = custom.querySelector('input');
      if (input) input.required = isCustom;
    };
    preset.addEventListener('change', sync);
    sync();
  }

  /* Usage filters: selects apply on change; text inputs still need Enter/Apply. */
  var filters = document.getElementById('usage-filters');
  if (filters) {
    document.querySelectorAll('select[form="usage-filters"]').forEach(function (select) {
      select.addEventListener('change', function () { filters.requestSubmit(); });
    });
  }
})();

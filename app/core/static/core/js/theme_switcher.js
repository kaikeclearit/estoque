// ============================================
// ClearIT - alternância de tema claro/escuro
// - Aplica o tema salvo (localStorage 'theme') em <html> como
//   data-theme (tema ClearIT) e data-bs-theme (modo escuro nativo do Bootstrap).
// - O <head> do base.html já aplica o tema antes da pintura (evita "piscar");
//   este script liga o botão #themeToggle e o cria se a página não tiver um.
// ============================================

(function () {
    'use strict';

    var STORAGE_KEY = 'theme';
    var root = document.documentElement;

    function readTheme() {
        try {
            return localStorage.getItem(STORAGE_KEY) === 'dark' ? 'dark' : 'light';
        } catch (e) {
            return 'light';
        }
    }

    function applyTheme(theme) {
        root.setAttribute('data-theme', theme);
        root.setAttribute('data-bs-theme', theme);
        var toggle = document.getElementById('themeToggle');
        if (toggle) {
            var dark = theme === 'dark';
            toggle.setAttribute('aria-pressed', dark ? 'true' : 'false');
            toggle.setAttribute('title', dark ? 'Usar tema claro' : 'Usar tema escuro');
        }
    }

    function toggleTheme() {
        var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        try { localStorage.setItem(STORAGE_KEY, next); } catch (e) { /* modo privado */ }
        applyTheme(next);
    }

    function ensureToggle() {
        var toggle = document.getElementById('themeToggle');
        if (!toggle) {
            var host = document.querySelector('.navbar-nav.ms-auto');
            if (!host) return null;
            toggle = document.createElement('button');
            toggle.type = 'button';
            toggle.id = 'themeToggle';
            toggle.className = 'btn btn-sm btn-theme';
            toggle.innerHTML = '<i class="bi bi-moon icon-light" aria-hidden="true"></i>' +
                               '<i class="bi bi-sun icon-dark" aria-hidden="true"></i>' +
                               '<span class="visually-hidden">Tema escuro</span>';
            host.insertBefore(toggle, host.firstChild);
        }
        return toggle;
    }

    applyTheme(readTheme());

    function init() {
        var toggle = ensureToggle();
        if (toggle && !toggle.dataset.bound) {
            toggle.dataset.bound = '1';
            toggle.addEventListener('click', toggleTheme);
        }
        applyTheme(readTheme());
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

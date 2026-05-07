// ============================================
// CLEARIT THEME SWITCHER - VERSÃO CORRIGIDA
// ============================================

(function() {
    'use strict';

    // Carregar tema salvo ou usar padrão (claro)
    const currentTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', currentTheme);

    // Função para criar o botão de toggle
    function createThemeToggle() {
        // Procurar o container do navbar
        const navbarNav = document.querySelector('.navbar-nav.ms-auto');
        
        if (!navbarNav) {
            console.warn('Navbar não encontrado, tentando novamente...');
            return false;
        }

        // Verificar se já existe
        if (document.getElementById('themeToggle')) {
            console.log('Toggle já existe');
            return true;
        }

        // Criar elemento do toggle
        const toggleWrapper = document.createElement('div');
        toggleWrapper.className = 'd-flex align-items-center me-3';
        toggleWrapper.innerHTML = `
            <div class="theme-toggle" id="themeToggle" title="Alternar tema" style="cursor: pointer;">
                <div class="theme-toggle-slider"></div>
            </div>
        `;

        // Inserir como primeiro elemento do navbar-nav
        navbarNav.insertBefore(toggleWrapper, navbarNav.firstChild);

        // Adicionar event listener
        const toggle = document.getElementById('themeToggle');
        if (toggle) {
            toggle.addEventListener('click', toggleTheme);
            console.log('✅ Theme toggle criado com sucesso!');
            return true;
        }

        return false;
    }

    // Função para alternar tema
    function toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        
        console.log(`Mudando tema de ${currentTheme} para ${newTheme}`);
        
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        
        // Animação suave
        document.body.style.transition = 'background-color 0.3s ease, color 0.3s ease';
    }

    // Tentar criar o toggle várias vezes (fallback)
    function tryCreateToggle(attempts = 0) {
        const maxAttempts = 10;
        
        if (attempts >= maxAttempts) {
            console.error('❌ Não foi possível criar o theme toggle após', maxAttempts, 'tentativas');
            return;
        }

        const success = createThemeToggle();
        
        if (!success) {
            setTimeout(() => tryCreateToggle(attempts + 1), 100);
        }
    }

    // Inicializar quando DOM estiver pronto
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => tryCreateToggle());
    } else {
        tryCreateToggle();
    }

})();
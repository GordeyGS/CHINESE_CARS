// Theme switcher: "apple" (light, default) or "dark". The choice is a per-browser
// convenience stored in localStorage; the page works without it.
(function () {
    var THEMES = ["apple", "dark"];
    var root = document.documentElement;

    function apply(theme) {
        root.dataset.theme = theme;
        document.querySelectorAll("[data-theme-choice]").forEach(function (button) {
            button.setAttribute("aria-pressed", String(button.dataset.themeChoice === theme));
        });
    }

    document.addEventListener("click", function (event) {
        var button = event.target.closest("[data-theme-choice]");
        if (!button || THEMES.indexOf(button.dataset.themeChoice) === -1) return;
        apply(button.dataset.themeChoice);
        try { localStorage.setItem("kb-theme", button.dataset.themeChoice); } catch (error) { /* storage blocked */ }
    });

    apply(THEMES.indexOf(root.dataset.theme) === -1 ? THEMES[0] : root.dataset.theme);
})();

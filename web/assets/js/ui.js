/* ==========================================================================
   Interacciones progresivas de interfaz (navegación móvil, filtros, pestañas)
   El contenido principal es HTML estático accesible sin depender de JS.
   ========================================================================== */
(function () {
  "use strict";

  // 1. Menú móvil accesible
  var navToggle = document.querySelector("[data-nav-toggle]");
  var siteNav = document.querySelector("[data-site-nav]");
  if (navToggle && siteNav) {
    navToggle.addEventListener("click", function () {
      var expanded = navToggle.getAttribute("aria-expanded") === "true";
      navToggle.setAttribute("aria-expanded", String(!expanded));
      siteNav.classList.toggle("is-open", !expanded);
    });
  }

  // 2. Filtros de catálogo (Proyectos / Atlas / Seguimiento / FAQ)
  function setupCatalogFilter(rootSelector) {
    var root = document.querySelector(rootSelector);
    if (!root) return;

    var searchInput = root.querySelector("[data-filter-search]");
    var selects = Array.prototype.slice.call(root.querySelectorAll("[data-filter-select]"));
    var resetBtn = root.querySelector("[data-filter-reset]");
    var cards = Array.prototype.slice.call(root.querySelectorAll("[data-filter-item]"));
    var countEl = root.querySelector("[data-filter-count]");
    var emptyEl = root.querySelector("[data-filter-empty]");

    function normalize(str) {
      return (str || "")
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "");
    }

    function applyFilters() {
      var q = normalize(searchInput ? searchInput.value : "");
      var visible = 0;

      cards.forEach(function (card) {
        var match = true;
        if (q) {
          var hay = normalize(card.getAttribute("data-search-text") || card.textContent);
          if (hay.indexOf(q) === -1) match = false;
        }
        selects.forEach(function (sel) {
          if (!match) return;
          var val = sel.value;
          if (!val || val === "all") return;
          var attrName = "data-" + sel.getAttribute("data-filter-select");
          var rawAttr = card.getAttribute(attrName) || "";
          var tokens = rawAttr.split("|");
          if (tokens.indexOf(val) === -1) {
            match = false;
          }
        });
        card.classList.toggle("hidden", !match);
        if (match) visible += 1;
      });

      if (countEl) {
        countEl.textContent = visible + " de " + cards.length + " registros mostrados";
      }
      if (emptyEl) {
        emptyEl.classList.toggle("hidden", visible > 0);
      }
    }

    if (searchInput) searchInput.addEventListener("input", applyFilters);
    selects.forEach(function (sel) {
      sel.addEventListener("change", applyFilters);
    });
    if (resetBtn) {
      resetBtn.addEventListener("click", function () {
        if (searchInput) searchInput.value = "";
        selects.forEach(function (sel) {
          sel.value = "all";
        });
        applyFilters();
      });
    }
    applyFilters();
  }

  setupCatalogFilter("[data-catalog-projects]");
  setupCatalogFilter("[data-catalog-atlas]");
  setupCatalogFilter("[data-catalog-progress]");
  setupCatalogFilter("[data-catalog-faq]");

  // 3. Pestañas de días en Agenda
  var dayTabs = Array.prototype.slice.call(document.querySelectorAll("[data-day-tab]"));
  var dayPanels = Array.prototype.slice.call(document.querySelectorAll("[data-day-panel]"));
  if (dayTabs.length && dayPanels.length) {
    dayTabs.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var target = btn.getAttribute("data-day-tab");
        dayTabs.forEach(function (b) {
          var active = b === btn;
          b.classList.toggle("is-active", active);
          b.setAttribute("aria-selected", String(active));
        });
        dayPanels.forEach(function (panel) {
          var show = target === "all" || panel.getAttribute("data-day-panel") === target;
          panel.classList.toggle("hidden", !show);
        });
      });
    });
  }

  // 4. Botones de copiar bloques de comandos
  var copyBtns = Array.prototype.slice.call(document.querySelectorAll("[data-copy-target]"));
  copyBtns.forEach(function (btn) {
    btn.addEventListener("click", function () {
      var id = btn.getAttribute("data-copy-target");
      var target = document.getElementById(id);
      if (!target || !navigator.clipboard) return;
      navigator.clipboard.writeText(target.textContent || "").then(function () {
        var prev = btn.textContent;
        btn.textContent = "Copiado";
        setTimeout(function () {
          btn.textContent = prev;
        }, 1800);
      });
    });
  });
})();

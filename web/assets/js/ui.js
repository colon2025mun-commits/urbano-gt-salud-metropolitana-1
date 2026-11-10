/* ==========================================================================
   Interacciones progresivas de interfaz (navegación móvil, filtros, pestañas,
   copiado de bloques y previsualizador local de logos institucionales)
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

  // 4. Botones de copiar bloques de comandos o prompts
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

  // 5. Previsualizador local de logo institucional (en /colaborar/#anadir-actualizar-logos)
  var logoPreviewRoot = document.querySelector("[data-logo-preview-helper]");
  if (logoPreviewRoot) {
    var fileInput = logoPreviewRoot.querySelector("[data-logo-file-input]");
    var nameInput = logoPreviewRoot.querySelector("[data-logo-inst-name]");
    var acrInput = logoPreviewRoot.querySelector("[data-logo-inst-acronym]");
    var roleInput = logoPreviewRoot.querySelector("[data-logo-inst-role]");
    var urlInput = logoPreviewRoot.querySelector("[data-logo-inst-url]");
    var orderInput = logoPreviewRoot.querySelector("[data-logo-inst-order]");
    var previewImg = logoPreviewRoot.querySelector("[data-logo-preview-img]");
    var previewBox = logoPreviewRoot.querySelector("[data-logo-preview-box]");
    var previewName = logoPreviewRoot.querySelector("[data-logo-preview-name]");
    var previewRole = logoPreviewRoot.querySelector("[data-logo-preview-role]");
    var previewAcr = logoPreviewRoot.querySelector("[data-logo-preview-acronym]");
    var jsonOutput = logoPreviewRoot.querySelector("[data-logo-json-output]");
    var downloadBtn = logoPreviewRoot.querySelector("[data-logo-download-json]");

    var currentFileName = "logo-institucion.png";
    var currentAspect = "horizontal";

    function slugify(text) {
      return (text || "institucion")
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "") || "institucion";
    }

    function updatePreviewAndSnippet() {
      var nm = (nameInput && nameInput.value.trim()) || "Nombre de la institución participante";
      var ac = (acrInput && acrInput.value.trim()) || "";
      var rl = (roleInput && roleInput.value.trim()) || "Institución participante";
      var ur = (urlInput && urlInput.value.trim()) || "";
      var ord = parseInt((orderInput && orderInput.value) || "2", 10) || 2;
      var idSlug = slugify(ac || nm);

      if (previewName) previewName.textContent = nm;
      if (previewRole) previewRole.textContent = rl;
      if (previewAcr) {
        previewAcr.textContent = ac || idSlug.toUpperCase();
        previewAcr.classList.toggle("hidden", !ac);
      }

      var entryObj = {
        id: idSlug,
        name: nm,
        acronym: ac || null,
        role: rl || null,
        logo_path: "branding/logos/" + currentFileName,
        alt_text: "Logo de " + nm + (ac ? " (" + ac + ")" : ""),
        url: ur && ur.indexOf("https://") === 0 ? ur : null,
        order: ord,
        aspect_hint: currentAspect
      };

      if (jsonOutput) {
        jsonOutput.textContent = JSON.stringify(entryObj, null, 2);
      }
    }

    if (fileInput) {
      fileInput.addEventListener("change", function () {
        var f = fileInput.files && fileInput.files[0];
        if (!f) return;
        currentFileName = f.name.replace(/[^A-Za-z0-9_.-]/g, "-");
        var reader = new FileReader();
        reader.onload = function (ev) {
          var dataUrl = ev.target && ev.target.result;
          if (previewImg && typeof dataUrl === "string") {
            previewImg.src = dataUrl;
            previewImg.classList.remove("hidden");
            var tempImg = new Image();
            tempImg.onload = function () {
              var ratio = tempImg.naturalWidth / Math.max(1, tempImg.naturalHeight);
              if (ratio > 1.35) currentAspect = "horizontal";
              else if (ratio < 0.85) currentAspect = "vertical";
              else currentAspect = "square";
              if (previewBox) {
                previewBox.classList.remove("is-horizontal", "is-vertical", "is-square");
                previewBox.classList.add("is-" + currentAspect);
              }
              updatePreviewAndSnippet();
            };
            tempImg.src = dataUrl;
          }
        };
        reader.readAsDataURL(f);
        updatePreviewAndSnippet();
      });
    }

    [nameInput, acrInput, roleInput, urlInput, orderInput].forEach(function (inp) {
      if (inp) inp.addEventListener("input", updatePreviewAndSnippet);
    });

    if (downloadBtn && jsonOutput) {
      downloadBtn.addEventListener("click", function () {
        var blob = new Blob([jsonOutput.textContent || "{}"], { type: "application/json;charset=utf-8" });
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "institucion-branding-entry.json";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      });
    }

    updatePreviewAndSnippet();
  }
})();

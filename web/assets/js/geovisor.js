/* ==========================================================================
   Controlador del Geovisor basado en GeoLibre / MapLibre GL JS
   - Soporta modo integrado (MapLibre GL JS), modo embebido (web.geolibre.app)
     y previsualización local de archivos GeoJSON sin subir datos a terceros.
   - También inicializa el mapa regional referencial en el Portal General.
   ========================================================================== */
(function () {
  "use strict";

  var BASEMAPS = {
    "carto-positron": {
      name: "Mapa Claro (OpenStreetMap / Humanitario)",
      styleUrl: "https://tiles.openfreemap.org/styles/positron",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      attribution: "&copy; OpenStreetMap contributors &copy; OpenFreeMap"
    },
    "osm-standard": {
      name: "OpenStreetMap Estándar",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      attribution: "&copy; OpenStreetMap contributors"
    },
    "carto-dark": {
      name: "Modo Oscuro Vectorial (OpenFreeMap)",
      styleUrl: "https://tiles.openfreemap.org/styles/dark",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      attribution: "&copy; OpenStreetMap contributors &copy; OpenFreeMap"
    },
    "esri-imagery": {
      name: "Imagen Satelital de Referencia",
      tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
      attribution: "Tiles &copy; Esri &mdash; Referencia visual orientativa"
    }
  };

  function makeStyle(basemapKey) {
    var bm = BASEMAPS[basemapKey] || BASEMAPS["osm-standard"];
    if (bm.styleUrl) {
      return bm.styleUrl;
    }
    return {
      version: 8,
      sources: {
        "base-tiles": {
          type: "raster",
          tiles: bm.tiles,
          tileSize: 256,
          attribution: bm.attribution
        }
      },
      layers: [
        {
          id: "base-tiles-layer",
          type: "raster",
          source: "base-tiles",
          minzoom: 0,
          maxzoom: 19
        }
      ]
    };
  }

  function createSafePopupElement(titleText, rows, badgeText) {
    var wrap = document.createElement("div");
    wrap.style.maxWidth = "270px";
    wrap.style.fontFamily = "system-ui, sans-serif";
    wrap.style.fontSize = "12.5px";

    if (badgeText) {
      var badge = document.createElement("div");
      badge.textContent = badgeText;
      badge.style.fontSize = "11px";
      badge.style.fontWeight = "700";
      badge.style.color = "#005F68";
      badge.style.marginBottom = "4px";
      wrap.appendChild(badge);
    }

    var h = document.createElement("strong");
    h.textContent = titleText;
    h.style.display = "block";
    h.style.color = "#14283F";
    h.style.marginBottom = "6px";
    wrap.appendChild(h);

    rows.forEach(function (pair) {
      var row = document.createElement("div");
      row.style.marginBottom = "3px";
      var k = document.createElement("span");
      k.style.fontWeight = "600";
      k.textContent = pair[0] + ": ";
      var v = document.createElement("span");
      v.textContent = pair[1];
      row.appendChild(k);
      row.appendChild(v);
      wrap.appendChild(row);
    });
    return wrap;
  }

  function computeGeoJsonBounds(geojson) {
    var bounds = [Infinity, Infinity, -Infinity, -Infinity];
    function visitCoords(coords) {
      if (!Array.isArray(coords) || coords.length === 0) return;
      if (typeof coords[0] === "number" && typeof coords[1] === "number") {
        var lon = coords[0];
        var lat = coords[1];
        if (lon < bounds[0]) bounds[0] = lon;
        if (lat < bounds[1]) bounds[1] = lat;
        if (lon > bounds[2]) bounds[2] = lon;
        if (lat > bounds[3]) bounds[3] = lat;
      } else {
        coords.forEach(visitCoords);
      }
    }
    function visitGeom(g) {
      if (!g) return;
      if (g.type === "GeometryCollection" && Array.isArray(g.geometries)) {
        g.geometries.forEach(visitGeom);
      } else if (g.coordinates) {
        visitCoords(g.coordinates);
      }
    }
    if (geojson.type === "FeatureCollection" && Array.isArray(geojson.features)) {
      geojson.features.forEach(function (f) {
        if (f && f.geometry) visitGeom(f.geometry);
      });
    } else if (geojson.type === "Feature" && geojson.geometry) {
      visitGeom(geojson.geometry);
    } else {
      visitGeom(geojson);
    }
    if (!isFinite(bounds[0])) return null;
    return [[bounds[0], bounds[1]], [bounds[2], bounds[3]]];
  }

  // =========================================================================
  // A. Inicializador del Geovisor de Proyecto (aplicacion/index.html)
  // =========================================================================
  function initProjectGeovisor() {
    var cfgScript = document.getElementById("geovisor-config-data");
    var canvas = document.getElementById("geovisor-map-canvas");
    if (!cfgScript || !canvas) return;

    var cfg;
    try {
      cfg = JSON.parse(cfgScript.textContent || "{}");
    } catch (err) {
      return;
    }

    var baseUrl = cfg.site_base_url || "./";
    var geolibreRelPath = (cfg.geolibre_integration && cfg.geolibre_integration.project_file) || "geovisor/proyecto.geolibre.json";
    var geolibreResolvedUrl = new URL(geolibreRelPath, window.location.origin + baseUrl).href;
    var isHttpsPublic = window.location.protocol === "https:";

    // Configurar enlace "Abrir en GeoLibre Studio"
    var studioBtn = document.getElementById("btn-open-geolibre-studio");
    if (studioBtn) {
      if (isHttpsPublic) {
        studioBtn.href = "https://web.geolibre.app/?url=" + encodeURIComponent(geolibreResolvedUrl);
      } else {
        studioBtn.href = "https://web.geolibre.app/";
      }
    }

    // Pestañas del panel lateral
    var tabs = Array.prototype.slice.call(document.querySelectorAll("[data-gv-tab]"));
    var panels = Array.prototype.slice.call(document.querySelectorAll("[data-gv-panel]"));
    var iframeEl = document.getElementById("geolibre-embed-iframe");
    var embedNoticeEl = document.getElementById("geolibre-embed-notice");

    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        var mode = tab.getAttribute("data-gv-tab");
        tabs.forEach(function (t) {
          t.classList.toggle("is-active", t === tab);
        });
        panels.forEach(function (p) {
          p.classList.toggle("is-active", p.getAttribute("data-gv-panel") === mode);
        });

        if (mode === "embed") {
          if (isHttpsPublic && iframeEl) {
            canvas.style.display = "none";
            iframeEl.style.display = "block";
            var embedSrc = "https://web.geolibre.app/?url=" + encodeURIComponent(geolibreResolvedUrl) + "&maponly";
            if (iframeEl.getAttribute("src") !== embedSrc) {
              iframeEl.setAttribute("src", embedSrc);
            }
            if (embedNoticeEl) embedNoticeEl.textContent = "Cargando proyecto .geolibre.json publicado con CORS sobre GeoLibre Web.";
          } else {
            canvas.style.display = "block";
            if (iframeEl) iframeEl.style.display = "none";
            if (embedNoticeEl) {
              embedNoticeEl.textContent = "Estás en modo local (" + window.location.protocol + "//" + window.location.host + "). Para embeber web.geolibre.app por parámetro ?url= se requiere que el sitio esté publicado en HTTPS (GitHub Pages). En local puedes usar el visor MapLibre integrado aquí a la derecha o descargar proyecto.geolibre.json y abrirlo en web.geolibre.app.";
            }
          }
        } else {
          canvas.style.display = "block";
          if (iframeEl) iframeEl.style.display = "none";
          if (mapInstance) mapInstance.resize();
        }
      });
    });

    if (typeof window.maplibregl === "undefined") {
      var fallback = document.createElement("div");
      fallback.className = "callout callout-warn";
      fallback.style.margin = "1rem";
      fallback.textContent = "No se pudo cargar la librería gráfica MapLibre GL JS (sin conexión a CDN). El catálogo de capas, metadatos y configuración .geolibre.json siguen disponibles en el panel lateral.";
      canvas.appendChild(fallback);
      return;
    }

    var center = (cfg.map_view && cfg.map_view.center) || [-84.0, 13.5];
    var zoom = (cfg.map_view && cfg.map_view.zoom) || 10;

    var mapInstance = new window.maplibregl.Map({
      container: canvas,
      style: makeStyle("carto-positron"),
      center: center,
      zoom: zoom,
      attributionControl: true
    });

    mapInstance.addControl(new window.maplibregl.NavigationControl(), "top-right");
    mapInstance.addControl(new window.maplibregl.ScaleControl({ maxWidth: 120, unit: "metric" }), "bottom-right");

    // Marcador de referencia declarado
    var refCentroid = (cfg.map_view && cfg.map_view.declared_centroid) || center;
    var popupNode = createSafePopupElement(
      cfg.title || cfg.project_id,
      [
        ["Coordenada referencial", refCentroid[1].toFixed(5) + ", " + refCentroid[0].toFixed(5)],
        ["Escala", (cfg.map_view && cfg.map_view.scale_label) || "Documentada en ficha"],
        ["Nota", (cfg.map_view && cfg.map_view.reference_note) || "Ubicación referencial"]
      ],
      "PUNTO DE REFERENCIA DEL PERFIL"
    );
    var refMarker = new window.maplibregl.Marker({ color: "#007F8B" })
      .setLngLat(refCentroid)
      .setPopup(new window.maplibregl.Popup({ offset: 24 }).setDOMContent(popupNode))
      .addTo(mapInstance);

    var toggleRefCheck = document.getElementById("gv-toggle-ref-marker");
    if (toggleRefCheck) {
      toggleRefCheck.addEventListener("change", function () {
        if (toggleRefCheck.checked) {
          refMarker.addTo(mapInstance);
        } else {
          refMarker.remove();
        }
      });
    }

    // Coordenadas dinámicas en barra inferior
    var coordsStatus = document.getElementById("gv-coords-readout");
    mapInstance.on("mousemove", function (e) {
      if (coordsStatus) {
        coordsStatus.textContent = "Lat: " + e.lngLat.lat.toFixed(5) + " · Lon: " + e.lngLat.lng.toFixed(5) + " · Zoom: " + mapInstance.getZoom().toFixed(1);
      }
    });

    // Botón restablecer vista
    var resetViewBtn = document.getElementById("gv-reset-view");
    if (resetViewBtn) {
      resetViewBtn.addEventListener("click", function () {
        mapInstance.flyTo({ center: center, zoom: zoom, essential: true });
      });
    }

    // Estado de capas activas (incluyendo vista previa local)
    var localGeoJsonCache = null;

    function addActiveProjectLayers() {
      var layers = Array.isArray(cfg.layers) ? cfg.layers : [];
      layers.forEach(function (lyr) {
        if (!lyr.source_path) return;
        if (lyr.status !== "publicado" && lyr.status !== "en_revision") return;

        var srcId = "src-" + lyr.id;
        var resolvedSource = /^https?:\/\//i.test(lyr.source_path)
          ? lyr.source_path
          : new URL(lyr.source_path, window.location.origin + baseUrl).href;

        if (lyr.format === "geojson") {
          mapInstance.addSource(srcId, { type: "geojson", data: resolvedSource });
          var fillColor = (lyr.style && lyr.style.fill_color) || "#007F8B";
          var fillOpacity = (lyr.style && lyr.style.fill_opacity) || 0.45;
          var strokeColor = (lyr.style && lyr.style.stroke_color) || "#14283F";

          mapInstance.addLayer({
            id: lyr.id + "-fill",
            type: "fill",
            source: srcId,
            paint: { "fill-color": fillColor, "fill-opacity": fillOpacity }
          });
          mapInstance.addLayer({
            id: lyr.id + "-line",
            type: "line",
            source: srcId,
            paint: { "line-color": strokeColor, "line-width": 1.6 }
          });

          // Control en árbol lateral
          var chk = document.querySelector('[data-layer-toggle="' + lyr.id + '"]');
          if (chk) {
            chk.disabled = false;
            chk.checked = true;
            chk.addEventListener("change", function () {
              var vis = chk.checked ? "visible" : "none";
              if (mapInstance.getLayer(lyr.id + "-fill")) mapInstance.setLayoutProperty(lyr.id + "-fill", "visibility", vis);
              if (mapInstance.getLayer(lyr.id + "-line")) mapInstance.setLayoutProperty(lyr.id + "-line", "visibility", vis);
            });
          }
          var slider = document.querySelector('[data-layer-opacity="' + lyr.id + '"]');
          if (slider) {
            slider.disabled = false;
            slider.addEventListener("input", function () {
              var op = parseFloat(slider.value);
              if (mapInstance.getLayer(lyr.id + "-fill")) {
                mapInstance.setPaintProperty(lyr.id + "-fill", "fill-opacity", op);
              }
            });
          }
        } else if (lyr.format === "xyz_or_cog" && resolvedSource.indexOf("{z}") !== -1) {
          mapInstance.addSource(srcId, { type: "raster", tiles: [resolvedSource], tileSize: 256 });
          mapInstance.addLayer({
            id: lyr.id + "-raster",
            type: "raster",
            source: srcId,
            paint: { "raster-opacity": 0.8 }
          });
        }
      });

      if (localGeoJsonCache) {
        renderLocalPreviewOnMap(localGeoJsonCache);
      }
    }

    function renderLocalPreviewOnMap(geojson) {
      ["local-preview-fill", "local-preview-line", "local-preview-circle"].forEach(function (lid) {
        if (mapInstance.getLayer(lid)) mapInstance.removeLayer(lid);
      });
      if (mapInstance.getSource("local-preview-src")) {
        mapInstance.removeSource("local-preview-src");
      }

      mapInstance.addSource("local-preview-src", { type: "geojson", data: geojson });
      mapInstance.addLayer({
        id: "local-preview-fill",
        type: "fill",
        source: "local-preview-src",
        filter: ["in", "$type", "Polygon"],
        paint: { "fill-color": "#007F8B", "fill-opacity": 0.42 }
      });
      mapInstance.addLayer({
        id: "local-preview-line",
        type: "line",
        source: "local-preview-src",
        paint: { "line-color": "#14283F", "line-width": 2.2 }
      });
      mapInstance.addLayer({
        id: "local-preview-circle",
        type: "circle",
        source: "local-preview-src",
        filter: ["in", "$type", "Point"],
        paint: { "circle-radius": 6, "circle-color": "#C9DA4D", "circle-stroke-color": "#14283F", "circle-stroke-width": 2 }
      });

      mapInstance.on("click", "local-preview-fill", function (e) {
        if (!e.features || !e.features.length) return;
        var props = e.features[0].properties || {};
        var rows = Object.keys(props).slice(0, 8).map(function (k) {
          return [k, String(props[k])];
        });
        if (!rows.length) rows.push(["Atributos", "Sin propiedades adicionales"]);
        var node = createSafePopupElement("Entidad en vista previa local", rows, "VISTA LOCAL TEMPORAL");
        new window.maplibregl.Popup().setLngLat(e.lngLat).setDOMContent(node).addTo(mapInstance);
      });
    }

    mapInstance.on("load", addActiveProjectLayers);

    // Selector de mapa base
    var basemapSelect = document.getElementById("gv-basemap-select");
    if (basemapSelect) {
      basemapSelect.addEventListener("change", function () {
        var chosen = basemapSelect.value;
        mapInstance.setStyle(makeStyle(chosen));
        mapInstance.once("styledata", function () {
          addActiveProjectLayers();
        });
      });
    }

    // Cargador local de prueba (.geojson)
    var fileInput = document.getElementById("gv-local-geojson-input");
    var dropzone = document.getElementById("gv-dropzone");
    var localStatus = document.getElementById("gv-local-status");
    var clearLocalBtn = document.getElementById("gv-clear-local");

    function handleLocalFile(file) {
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function () {
        try {
          var parsed = JSON.parse(String(reader.result || ""));
          if (!parsed || typeof parsed !== "object" || !parsed.type) {
            throw new Error("El archivo no tiene estructura GeoJSON válida.");
          }
          localGeoJsonCache = parsed;
          renderLocalPreviewOnMap(parsed);
          var bbox = computeGeoJsonBounds(parsed);
          if (bbox) {
            mapInstance.fitBounds(bbox, { padding: 48, maxZoom: 16 });
          }
          var count = parsed.type === "FeatureCollection" && Array.isArray(parsed.features) ? parsed.features.length : 1;
          if (localStatus) {
            localStatus.textContent = "Capa temporal cargada en tu navegador: " + file.name + " (" + count + " geometría(s)). Esta vista no modifica el repositorio hasta que la incorpores en geovisor/data/.";
          }
          if (clearLocalBtn) clearLocalBtn.classList.remove("hidden");
        } catch (err) {
          if (localStatus) {
            localStatus.textContent = "Error al leer GeoJSON: " + (err && err.message ? err.message : "formato inválido");
          }
        }
      };
      reader.readAsText(file, "utf-8");
    }

    if (fileInput) {
      fileInput.addEventListener("change", function () {
        if (fileInput.files && fileInput.files[0]) {
          handleLocalFile(fileInput.files[0]);
        }
      });
    }
    if (dropzone && fileInput) {
      dropzone.addEventListener("click", function () {
        fileInput.click();
      });
      dropzone.addEventListener("dragover", function (e) {
        e.preventDefault();
      });
      dropzone.addEventListener("drop", function (e) {
        e.preventDefault();
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
          handleLocalFile(e.dataTransfer.files[0]);
        }
      });
    }
    if (clearLocalBtn) {
      clearLocalBtn.addEventListener("click", function () {
        localGeoJsonCache = null;
        ["local-preview-fill", "local-preview-line", "local-preview-circle"].forEach(function (lid) {
          if (mapInstance.getLayer(lid)) mapInstance.removeLayer(lid);
        });
        if (mapInstance.getSource("local-preview-src")) mapInstance.removeSource("local-preview-src");
        clearLocalBtn.classList.add("hidden");
        if (localStatus) localStatus.textContent = "Vista previa local limpiada.";
      });
    }
  }

  // =========================================================================
  // B. Inicializador del Mapa Regional Referencial del Hub (index.html)
  // =========================================================================
  function initHubRegionalMap() {
    var dataScript = document.getElementById("hub-map-points");
    var container = document.getElementById("hub-regional-map");
    if (!dataScript || !container || typeof window.maplibregl === "undefined") return;

    var points;
    try {
      points = JSON.parse(dataScript.textContent || "[]");
    } catch (err) {
      return;
    }

    var map = new window.maplibregl.Map({
      container: container,
      style: makeStyle("carto-positron"),
      center: [-82.2, 14.1],
      zoom: 4.35,
      attributionControl: true
    });
    map.addControl(new window.maplibregl.NavigationControl(), "top-right");

    points.forEach(function (pt) {
      var wrap = createSafePopupElement(
        pt.country_name + " · " + pt.short_name,
        [
          ["Territorio", pt.territory_label],
          ["Institución", pt.institution],
          ["Aviso", "Ubicación referencial según el perfil (no representa polígono analítico)"]
        ],
        "INICIATIVA " + pt.country_code
      );
      if (pt.detail_url) {
        var link = document.createElement("a");
        link.href = pt.detail_url;
        link.textContent = "Ver ficha completa →";
        link.style.display = "inline-block";
        link.style.marginTop = "6px";
        link.style.fontWeight = "700";
        link.style.color = "#007F8B";
        wrap.appendChild(link);
      }

      new window.maplibregl.Marker({ color: "#14283F" })
        .setLngLat(pt.center)
        .setPopup(new window.maplibregl.Popup({ offset: 22 }).setDOMContent(wrap))
        .addTo(map);
    });
  }

  initProjectGeovisor();
  initHubRegionalMap();
})();

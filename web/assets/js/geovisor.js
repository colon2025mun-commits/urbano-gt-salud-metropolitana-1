/* ==========================================================================
   Controlador del Geovisor basado en GeoLibre / MapLibre GL JS
   - Soporta:
     1) Capas declaradas en geovisor/layers.json (activas con popups y opacidad).
     2) Opción "Cargar capa desde carpeta" (lee geovisor/capas/ del respectivo
        repositorio vía index.json estático + API pública de GitHub en vivo para
        detectar archivos subidos recientemente en formatos compatibles con GeoLibre).
     3) Vista previa local temporal (.geojson / .kml desde el equipo del usuario).
     4) Integración directa con GeoLibre Web (web.geolibre.app).
     5) Mapa regional referencial en el Portal Comunitario.
   ========================================================================== */
(function () {
  "use strict";

  var BASEMAPS = {
    "carto-positron": {
      name: "Mapa Claro Vectorial (OpenFreeMap)",
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

  var FOLDER_PALETTE = [
    "#007F8B",
    "#D95F02",
    "#7570B3",
    "#E7298A",
    "#66A61E",
    "#E6AB02",
    "#1F78B4"
  ];

  var GEOLIBRE_EXT_RE = /\.(geojson|json|kml|pmtiles|fgb|tif|tiff|parquet|geoparquet)$/i;

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
    wrap.style.maxWidth = "290px";
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
    if (!geojson) return null;
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

  function parseKmlToGeoJson(kmlText) {
    var parser = new DOMParser();
    var xml = parser.parseFromString(kmlText, "text/xml");
    var placemarks = Array.prototype.slice.call(xml.getElementsByTagName("Placemark"));
    var features = [];

    function parseCoordList(raw) {
      return (raw || "")
        .trim()
        .split(/\s+/)
        .filter(Boolean)
        .map(function (tok) {
          var p = tok.split(",");
          return [parseFloat(p[0]), parseFloat(p[1])];
        })
        .filter(function (pt) {
          return !isNaN(pt[0]) && !isNaN(pt[1]);
        });
    }

    placemarks.forEach(function (pm, idx) {
      var nameEl = pm.getElementsByTagName("name")[0];
      var descEl = pm.getElementsByTagName("description")[0];
      var props = {
        nombre: nameEl ? nameEl.textContent.trim() : "Elemento KML " + (idx + 1)
      };
      if (descEl && descEl.textContent.trim()) {
        props.descripcion = descEl.textContent.trim();
      }

      var poly = pm.getElementsByTagName("Polygon")[0];
      var line = pm.getElementsByTagName("LineString")[0];
      var point = pm.getElementsByTagName("Point")[0];

      if (poly) {
        var coordsEl = poly.getElementsByTagName("coordinates")[0];
        var ring = parseCoordList(coordsEl ? coordsEl.textContent : "");
        if (ring.length >= 3) {
          if (ring[0][0] !== ring[ring.length - 1][0] || ring[0][1] !== ring[ring.length - 1][1]) {
            ring.push([ring[0][0], ring[0][1]]);
          }
          features.push({ type: "Feature", properties: props, geometry: { type: "Polygon", coordinates: [ring] } });
        }
      } else if (line) {
        var lCoords = parseCoordList((line.getElementsByTagName("coordinates")[0] || {}).textContent);
        if (lCoords.length >= 2) {
          features.push({ type: "Feature", properties: props, geometry: { type: "LineString", coordinates: lCoords } });
        }
      } else if (point) {
        var pCoords = parseCoordList((point.getElementsByTagName("coordinates")[0] || {}).textContent);
        if (pCoords.length >= 1) {
          features.push({ type: "Feature", properties: props, geometry: { type: "Point", coordinates: pCoords[0] } });
        }
      }
    });

    return { type: "FeatureCollection", features: features };
  }

  function detectFormat(filename) {
    var lower = (filename || "").toLowerCase();
    if (lower.endsWith(".geolibre.json")) return "geolibre";
    if (lower.endsWith(".geojson") || lower.endsWith(".json")) return "geojson";
    if (lower.endsWith(".kml")) return "kml";
    if (lower.endsWith(".pmtiles")) return "pmtiles";
    if (lower.endsWith(".fgb")) return "flatgeobuf";
    if (lower.endsWith(".tif") || lower.endsWith(".tiff")) return "cog";
    if (lower.endsWith(".parquet") || lower.endsWith(".geoparquet")) return "geoparquet";
    return "otro";
  }

  function formatBytes(bytes) {
    if (!bytes || isNaN(bytes)) return "";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(2) + " MB";
  }

  function isWebGLSupported() {
    try {
      var testCanvas = document.createElement("canvas");
      return !!(
        window.WebGLRenderingContext &&
        (testCanvas.getContext("webgl2") || testCanvas.getContext("webgl") || testCanvas.getContext("experimental-webgl"))
      );
    } catch (e) {
      return false;
    }
  }

  function renderProjectWebGLFallback(canvas, cfg, baseUrl, geolibreResolvedUrl) {
    canvas.innerHTML = "";
    var box = document.createElement("div");
    box.className = "callout callout-warn";
    box.style.margin = "1.25rem";
    var center = (cfg.map_view && cfg.map_view.center) || [-84.0, 13.5];
    var h = document.createElement("strong");
    h.textContent = " aceleración gráfica WebGL no disponible en esta sesión del navegador";
    box.appendChild(h);
    var p = document.createElement("p");
    p.style.margin = "0.5rem 0";
    p.textContent =
      "El lienzo interactivo 2D/3D requiere WebGL habilitado. Aun sin aceleración gráfica, puedes consultar y descargar todas las capas activas del proyecto o abrir el archivo de proyecto GeoLibre:";
    box.appendChild(p);
    var meta = document.createElement("p");
    meta.style.fontSize = "0.85rem";
    meta.textContent =
      "Centroide referencial: Lat " + Number(center[1]).toFixed(4) + ", Lon " + Number(center[0]).toFixed(4) +
      " · Escala: " + ((cfg.map_view && cfg.map_view.scale_label) || "Documentada en ficha");
    box.appendChild(meta);

    var ul = document.createElement("ul");
    ul.style.margin = "0.5rem 0 0.75rem 1.2rem";
    (cfg.layers || []).forEach(function (lyr) {
      if (!lyr.source_path) return;
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = /^https?:\/\//i.test(lyr.source_path)
        ? lyr.source_path
        : new URL(lyr.source_path, window.location.origin + baseUrl).href;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = lyr.title + " (" + (lyr.format || "geojson") + ") ↗";
      li.appendChild(a);
      ul.appendChild(li);
    });
    box.appendChild(ul);

    var btn = document.createElement("a");
    btn.className = "btn btn-teal btn-xs";
    btn.href = geolibreResolvedUrl;
    btn.textContent = "Descargar proyecto.geolibre.json";
    box.appendChild(btn);
    canvas.appendChild(box);
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
    var repoSlug = cfg.repository_slug || null;
    var repoBranch = cfg.repository_branch || "main";
    var geolibreRelPath = (cfg.geolibre_integration && cfg.geolibre_integration.project_file) || "geovisor/proyecto.geolibre.json";
    var geolibreResolvedUrl = new URL(geolibreRelPath, window.location.origin + baseUrl).href;
    var isHttpsPublic = window.location.protocol === "https:";
    var isLocalhost = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";

    // Aislamiento estricto para forks y vistas previas:
    // Si estamos en <owner>.github.io/<repo>/, usar siempre <owner>/<repo> de la URL actual.
    // Si estamos en localhost, no consultar la API del repositorio canónico remoto para no mezclar capas.
    if (window.location.hostname.endsWith(".github.io")) {
      var hostOwner = window.location.hostname.replace(/\.github\.io$/i, "");
      var pathSeg = window.location.pathname.split("/").filter(Boolean)[0];
      if (hostOwner && pathSeg) {
        repoSlug = hostOwner + "/" + pathSeg;
      }
    } else if (isLocalhost) {
      repoSlug = null;
    }

    var studioBtn = document.getElementById("btn-open-geolibre-studio");
    if (studioBtn) {
      studioBtn.href = isHttpsPublic
        ? "https://web.geolibre.app/?url=" + encodeURIComponent(geolibreResolvedUrl)
        : "https://web.geolibre.app/";
    }

    var mapInstance = null;

    // Pestañas del panel lateral + acceso rápido desde barra superior
    var tabs = Array.prototype.slice.call(document.querySelectorAll("[data-gv-tab]"));
    var panels = Array.prototype.slice.call(document.querySelectorAll("[data-gv-panel]"));
    var iframeEl = document.getElementById("geolibre-embed-iframe");
    var embedNoticeEl = document.getElementById("geolibre-embed-notice");

    function activateTab(mode) {
      tabs.forEach(function (t) {
        t.classList.toggle("is-active", t.getAttribute("data-gv-tab") === mode);
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
          if (embedNoticeEl) embedNoticeEl.textContent = "Cargando proyecto .geolibre.json (v0.2.0) publicado con CORS sobre GeoLibre Studio.";
        } else {
          canvas.style.display = "block";
          if (iframeEl) iframeEl.style.display = "none";
          if (embedNoticeEl) {
            embedNoticeEl.textContent = "En modo local (" + window.location.host + "), usa el visor integrado o descarga proyecto.geolibre.json para abrirlo en web.geolibre.app. Al publicarse en HTTPS (GitHub Pages), la apertura directa con ?url= se activa automáticamente.";
          }
        }
      } else {
        canvas.style.display = "block";
        if (iframeEl) iframeEl.style.display = "none";
        if (mapInstance) mapInstance.resize();
      }
    }

    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        activateTab(tab.getAttribute("data-gv-tab"));
      });
    });

    var quickFolderBtn = document.getElementById("gv-open-folder-tab");
    if (quickFolderBtn) {
      quickFolderBtn.addEventListener("click", function () {
        activateTab("repo-folder");
        discoverRepositoryFolderLayers();
      });
    }

    var center = (cfg.map_view && cfg.map_view.center) || [-84.0, 13.5];
    var zoom = (cfg.map_view && cfg.map_view.zoom) || 10;

    if (typeof window.maplibregl === "undefined" || !isWebGLSupported()) {
      renderProjectWebGLFallback(canvas, cfg, baseUrl, geolibreResolvedUrl);
    } else {
      try {
        mapInstance = new window.maplibregl.Map({
          container: canvas,
          style: makeStyle("carto-positron"),
          center: center,
          zoom: zoom,
          attributionControl: true,
          canvasContextAttributes: { preserveDrawingBuffer: true }
        });
      } catch (err) {
        mapInstance = null;
        renderProjectWebGLFallback(canvas, cfg, baseUrl, geolibreResolvedUrl);
      }
    }

    if (mapInstance) {
      mapInstance.addControl(new window.maplibregl.NavigationControl(), "top-right");
      mapInstance.addControl(new window.maplibregl.ScaleControl({ maxWidth: 120, unit: "metric" }), "bottom-right");

      // Marcador de centroide referencial
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
          if (toggleRefCheck.checked) refMarker.addTo(mapInstance);
          else refMarker.remove();
        });
      }

      var coordsStatus = document.getElementById("gv-coords-readout");
      mapInstance.on("mousemove", function (e) {
        if (coordsStatus) {
          coordsStatus.textContent = "Lat: " + e.lngLat.lat.toFixed(5) + " · Lon: " + e.lngLat.lng.toFixed(5) + " · Zoom: " + mapInstance.getZoom().toFixed(1);
        }
      });

      var resetViewBtn = document.getElementById("gv-reset-view");
      if (resetViewBtn) {
        resetViewBtn.addEventListener("click", function () {
          mapInstance.flyTo({ center: center, zoom: zoom, essential: true });
        });
      }
    }

    // Registro de capas cargadas dinámicamente desde geovisor/capas/ o desde archivo local
    var dynamicFolderLayers = {}; // key: fileName -> { geojson, color, visible }
    var localGeoJsonCache = null;
    var initialBoundsFitted = false;

    function attachFeatureClickPopup(layerId, badgeTitle, defaultTitle) {
      mapInstance.on("click", layerId, function (e) {
        if (!e.features || !e.features.length) return;
        var props = e.features[0].properties || {};
        var nameVal = props.nombre || props.name || props.NAM || defaultTitle;
        var rows = [];
        Object.keys(props).forEach(function (k) {
          if (k === "nombre" || k === "name") return;
          if (props[k] !== null && props[k] !== undefined && String(props[k]).trim() !== "") {
            rows.push([k, String(props[k])]);
          }
        });
        if (!rows.length) rows.push(["Estado", "Capa vectorial cargada"]);
        var dom = createSafePopupElement(String(nameVal), rows.slice(0, 8), badgeTitle);
        new window.maplibregl.Popup({ maxWidth: "320px" }).setLngLat(e.lngLat).setDOMContent(dom).addTo(mapInstance);
      });
      mapInstance.on("mouseenter", layerId, function () {
        mapInstance.getCanvas().style.cursor = "pointer";
      });
      mapInstance.on("mouseleave", layerId, function () {
        mapInstance.getCanvas().style.cursor = "";
      });
    }

    function renderGeoJsonSourceLayers(srcId, prefixId, dataOrUrl, fillColor, fillOpacity, strokeColor, strokeWidth, badgeLabel, layerTitle) {
      if (mapInstance.getLayer(prefixId + "-fill")) mapInstance.removeLayer(prefixId + "-fill");
      if (mapInstance.getLayer(prefixId + "-line")) mapInstance.removeLayer(prefixId + "-line");
      if (mapInstance.getLayer(prefixId + "-pt")) mapInstance.removeLayer(prefixId + "-pt");
      if (mapInstance.getSource(srcId)) mapInstance.removeSource(srcId);

      mapInstance.addSource(srcId, { type: "geojson", data: dataOrUrl });
      mapInstance.addLayer({
        id: prefixId + "-fill",
        type: "fill",
        source: srcId,
        filter: ["==", ["geometry-type"], "Polygon"],
        paint: { "fill-color": fillColor, "fill-opacity": fillOpacity }
      });
      mapInstance.addLayer({
        id: prefixId + "-line",
        type: "line",
        source: srcId,
        paint: { "line-color": strokeColor, "line-width": strokeWidth }
      });
      mapInstance.addLayer({
        id: prefixId + "-pt",
        type: "circle",
        source: srcId,
        filter: ["==", ["geometry-type"], "Point"],
        paint: {
          "circle-radius": 6,
          "circle-color": fillColor,
          "circle-stroke-color": strokeColor,
          "circle-stroke-width": 2
        }
      });

      attachFeatureClickPopup(prefixId + "-fill", badgeLabel, layerTitle);
      attachFeatureClickPopup(prefixId + "-pt", badgeLabel, layerTitle);
    }

    function addActiveProjectLayers() {
      var layers = Array.isArray(cfg.layers) ? cfg.layers : [];
      var combinedBounds = null;

      layers.forEach(function (lyr) {
        if (!lyr.source_path) return;
        if (lyr.status !== "publicado" && lyr.status !== "en_revision") return;

        var srcId = "src-" + lyr.id;
        var resolvedSource = /^https?:\/\//i.test(lyr.source_path)
          ? lyr.source_path
          : new URL(lyr.source_path, window.location.origin + baseUrl).href;

        if (lyr.format === "geojson") {
          var fillColor = (lyr.style && lyr.style.fill_color) || "#007F8B";
          var fillOpacity = (lyr.style && lyr.style.fill_opacity) !== undefined ? lyr.style.fill_opacity : 0.22;
          var strokeColor = (lyr.style && lyr.style.stroke_color) || "#14283F";
          var strokeWidth = (lyr.style && lyr.style.stroke_width) || 2;

          fetch(resolvedSource)
            .then(function (r) {
              return r.ok ? r.json() : null;
            })
            .then(function (gj) {
              if (!gj) return;
              renderGeoJsonSourceLayers(
                srcId,
                lyr.id,
                gj,
                fillColor,
                fillOpacity,
                strokeColor,
                strokeWidth,
                "CAPA DEL PROYECTO · " + (lyr.status || "").toUpperCase(),
                lyr.title
              );
              if (!initialBoundsFitted) {
                var b = computeGeoJsonBounds(gj);
                if (b) {
                  if (!combinedBounds) {
                    combinedBounds = [[b[0][0], b[0][1]], [b[1][0], b[1][1]]];
                  } else {
                    combinedBounds[0][0] = Math.min(combinedBounds[0][0], b[0][0]);
                    combinedBounds[0][1] = Math.min(combinedBounds[0][1], b[0][1]);
                    combinedBounds[1][0] = Math.max(combinedBounds[1][0], b[1][0]);
                    combinedBounds[1][1] = Math.max(combinedBounds[1][1], b[1][1]);
                  }
                  mapInstance.fitBounds(combinedBounds, { padding: 42, maxZoom: 15.2, duration: 0 });
                }
              }
            })
            .catch(function (err) {
              if (window.console && console.warn) console.warn("Error al cargar capa del geovisor:", lyr.id, err);
            });

          var chk = document.querySelector('[data-layer-toggle="' + lyr.id + '"]');
          if (chk) {
            chk.disabled = false;
            chk.checked = true;
            chk.onchange = function () {
              var vis = chk.checked ? "visible" : "none";
              ["-fill", "-line", "-pt"].forEach(function (suf) {
                if (mapInstance.getLayer(lyr.id + suf)) {
                  mapInstance.setLayoutProperty(lyr.id + suf, "visibility", vis);
                }
              });
            };
          }
          var slider = document.querySelector('[data-layer-opacity="' + lyr.id + '"]');
          if (slider) {
            slider.disabled = false;
            slider.oninput = function () {
              var op = parseFloat(slider.value);
              if (mapInstance.getLayer(lyr.id + "-fill")) {
                mapInstance.setPaintProperty(lyr.id + "-fill", "fill-opacity", op);
              }
            };
          }
        } else if (lyr.format === "xyz_or_cog" && resolvedSource.indexOf("{z}") !== -1) {
          mapInstance.addSource(srcId, { type: "raster", tiles: [resolvedSource], tileSize: 256 });
          mapInstance.addLayer({ id: lyr.id + "-raster", type: "raster", source: srcId, paint: { "raster-opacity": 0.8 } });
        }
      });

      // Re-renderizar capas cargadas dinámicamente desde geovisor/capas/
      Object.keys(dynamicFolderLayers).forEach(function (fname) {
        var entry = dynamicFolderLayers[fname];
        if (entry && entry.visible && entry.geojson) {
          var safeId = "folder-" + fname.replace(/[^a-zA-Z0-9_-]/g, "_");
          renderGeoJsonSourceLayers(
            "src-" + safeId,
            safeId,
            entry.geojson,
            entry.color,
            0.38,
            "#14283F",
            2.2,
            "CARPETA REPOSITORIO (geovisor/capas/)",
            fname
          );
        }
      });

      if (localGeoJsonCache) {
        renderGeoJsonSourceLayers(
          "local-preview-src",
          "local-preview",
          localGeoJsonCache,
          "#007F8B",
          0.42,
          "#14283F",
          2.2,
          "VISTA PREVIA LOCAL TEMPORAL",
          "Archivo local"
        );
      }
    }

    if (mapInstance) {
      mapInstance.on("load", function () {
        addActiveProjectLayers();
        setTimeout(function () {
          initialBoundsFitted = true;
        }, 2500);
      });

      var basemapSelect = document.getElementById("gv-basemap-select");
      if (basemapSelect) {
        basemapSelect.addEventListener("change", function () {
          mapInstance.setStyle(makeStyle(basemapSelect.value));
          mapInstance.once("styledata", function () {
            addActiveProjectLayers();
          });
        });
      }
    }

    // =======================================================================
    // Opción: CARGAR CAPA DESDE CARPETA DEL REPOSITORIO (geovisor/capas/)
    // =======================================================================
    var folderListEl = document.getElementById("gv-repo-folder-list");
    var folderStatusEl = document.getElementById("gv-repo-folder-status");
    var refreshFolderBtn = document.getElementById("gv-refresh-repo-folder");

    // Pre-identificar archivos que ya están cargados por defecto desde layers.json
    var preloadedFiles = {};
    (cfg.layers || []).forEach(function (lyr) {
      if (lyr.source_path && (lyr.status === "publicado" || lyr.status === "en_revision")) {
        var baseName = lyr.source_path.split("/").pop();
        if (baseName) preloadedFiles[baseName] = lyr.id;
      }
    });

    function loadLayerFromRepoFolder(fileObj, colorIndex, btnEl) {
      var fname = fileObj.name;
      var fmt = detectFormat(fname);
      var safeId = "folder-" + fname.replace(/[^a-zA-Z0-9_-]/g, "_");

      // Formatos de proyecto GeoLibre (.geolibre.json) -> ?url=
      if (fmt === "geolibre") {
        window.open("https://web.geolibre.app/?url=" + encodeURIComponent(fileObj.url), "_blank", "noopener");
        return;
      }
      // Formatos cloud-native avanzados (PMTiles, COG, FlatGeobuf, GeoParquet) -> ?data=
      if (fmt === "pmtiles" || fmt === "cog" || fmt === "flatgeobuf" || fmt === "geoparquet") {
        if (folderStatusEl) {
          folderStatusEl.textContent = "Abriendo capa " + fname + " (" + fmt.toUpperCase() + ") en GeoLibre Studio mediante ?data=...";
        }
        window.open("https://web.geolibre.app/?data=" + encodeURIComponent(fileObj.url), "_blank", "noopener");
        return;
      }

      if (!mapInstance) {
        window.open("https://web.geolibre.app/?data=" + encodeURIComponent(fileObj.url), "_blank", "noopener");
        return;
      }

      // Si ya estaba activa dinámicamente, alternar visibilidad (quitar)
      if (dynamicFolderLayers[fname] && dynamicFolderLayers[fname].visible) {
        dynamicFolderLayers[fname].visible = false;
        ["-fill", "-line", "-pt"].forEach(function (suf) {
          if (mapInstance.getLayer(safeId + suf)) mapInstance.removeLayer(safeId + suf);
        });
        if (mapInstance.getSource("src-" + safeId)) mapInstance.removeSource("src-" + safeId);
        btnEl.textContent = "Cargar en mapa";
        btnEl.className = "btn btn-teal btn-xs";
        return;
      }

      btnEl.disabled = true;
      btnEl.textContent = "Cargando...";

      fetch(fileObj.url)
        .then(function (resp) {
          if (!resp.ok) throw new Error("HTTP " + resp.status);
          return resp.text();
        })
        .then(function (rawText) {
          var gj = fmt === "kml" ? parseKmlToGeoJson(rawText) : JSON.parse(rawText);
          if (!gj || !gj.type) throw new Error("Estructura geoespacial inválida");
          var chosenColor = FOLDER_PALETTE[colorIndex % FOLDER_PALETTE.length];
          dynamicFolderLayers[fname] = { geojson: gj, color: chosenColor, visible: true };

          renderGeoJsonSourceLayers(
            "src-" + safeId,
            safeId,
            gj,
            chosenColor,
            0.38,
            "#14283F",
            2.2,
            "CARPETA REPOSITORIO (geovisor/capas/)",
            fname
          );
          var bbox = computeGeoJsonBounds(gj);
          if (bbox) {
            mapInstance.fitBounds(bbox, { padding: 48, maxZoom: 15.5 });
          }
          btnEl.disabled = false;
          btnEl.textContent = "Quitar del mapa";
          btnEl.className = "btn btn-outline btn-xs";
          if (folderStatusEl) {
            folderStatusEl.textContent = "Capa cargada desde carpeta del repositorio: " + fname;
          }
        })
        .catch(function (err) {
          btnEl.disabled = false;
          btnEl.textContent = "Reintentar";
          if (folderStatusEl) {
            folderStatusEl.textContent = "No se pudo leer " + fname + ": " + (err.message || "error");
          }
        });
    }

    function renderFolderItems(filesList, sourceLabel) {
      if (!folderListEl) return;
      folderListEl.innerHTML = "";
      if (folderStatusEl) {
        folderStatusEl.textContent = filesList.length
          ? filesList.length + " archivo(s) compatibles en geovisor/capas/ (" + sourceLabel + ")."
          : "La carpeta geovisor/capas/ de esta vista aún no tiene capas adicionales. Sube archivos .geojson, .kml, .tif (COG), .pmtiles, .fgb o .geolibre.json.";
      }

      filesList.forEach(function (fileObj, idx) {
        var item = document.createElement("div");
        item.className = "layer-item";

        var head = document.createElement("div");
        head.className = "layer-item-head";

        var titleEl = document.createElement("div");
        titleEl.className = "layer-item-title";
        titleEl.style.minWidth = "0";
        titleEl.style.overflowWrap = "anywhere";
        titleEl.textContent = fileObj.name;

        var badge = document.createElement("span");
        var fmt = detectFormat(fileObj.name);
        badge.className = "badge badge-declarado";
        badge.style.flexShrink = "0";
        badge.textContent = fmt.toUpperCase();

        head.appendChild(titleEl);
        head.appendChild(badge);
        item.appendChild(head);

        var meta = document.createElement("div");
        meta.className = "layer-item-meta";
        var sizeTxt = formatBytes(fileObj.size_bytes);
        var whereTxt =
          fmt === "geolibre"
            ? "Proyecto GeoLibre Studio (?url=)"
            : fmt === "geojson" || fmt === "kml"
              ? "Visor integrado (MapLibre) + GeoLibre Studio"
              : "GeoLibre Studio cloud-native (?data=)";
        meta.textContent = "Ruta: geovisor/capas/" + fileObj.name + (sizeTxt ? " · " + sizeTxt : "") + " · " + whereTxt;
        item.appendChild(meta);

        var actions = document.createElement("div");
        actions.style.display = "flex";
        actions.style.flexWrap = "wrap";
        actions.style.gap = "0.4rem";
        actions.style.marginTop = "0.5rem";

        var isCloudNativeOnly = fmt === "pmtiles" || fmt === "cog" || fmt === "flatgeobuf" || fmt === "geoparquet";

        if (preloadedFiles[fileObj.name] && !isCloudNativeOnly && fmt !== "geolibre") {
          var alreadyBadge = document.createElement("span");
          alreadyBadge.className = "badge badge-ok";
          alreadyBadge.textContent = "Activa en pestaña Capas";
          actions.appendChild(alreadyBadge);

          if (mapInstance) {
            var zoomBtn = document.createElement("button");
            zoomBtn.type = "button";
            zoomBtn.className = "btn btn-outline btn-xs";
            zoomBtn.textContent = "Encuadrar capa";
            zoomBtn.addEventListener("click", function () {
              fetch(fileObj.url)
                .then(function (r) { return r.json(); })
                .then(function (gj) {
                  var b = computeGeoJsonBounds(gj);
                  if (b) mapInstance.fitBounds(b, { padding: 45, maxZoom: 15.5 });
                });
            });
            actions.appendChild(zoomBtn);
          }
        } else {
          var loadBtn = document.createElement("button");
          loadBtn.type = "button";
          var isLoaded = dynamicFolderLayers[fileObj.name] && dynamicFolderLayers[fileObj.name].visible;
          loadBtn.className = isLoaded ? "btn btn-outline btn-xs" : "btn btn-teal btn-xs";
          loadBtn.textContent =
            fmt === "geolibre"
              ? "Abrir proyecto en GeoLibre Studio ↗"
              : isCloudNativeOnly
                ? "Abrir capa en GeoLibre Studio ↗"
                : isLoaded
                  ? "Quitar del mapa"
                  : "Cargar en mapa";
          loadBtn.addEventListener("click", function () {
            loadLayerFromRepoFolder(fileObj, idx, loadBtn);
          });
          actions.appendChild(loadBtn);
        }

        if (fmt !== "geolibre" && !isCloudNativeOnly) {
          var openInStudioLink = document.createElement("a");
          openInStudioLink.className = "btn btn-outline btn-xs";
          openInStudioLink.href = "https://web.geolibre.app/?data=" + encodeURIComponent(fileObj.url);
          openInStudioLink.target = "_blank";
          openInStudioLink.rel = "noopener noreferrer";
          openInStudioLink.textContent = "GeoLibre Studio ↗";
          actions.appendChild(openInStudioLink);
        }

        var dlLink = document.createElement("a");
        dlLink.className = "btn btn-outline btn-xs";
        dlLink.href = fileObj.url;
        dlLink.target = "_blank";
        dlLink.rel = "noopener noreferrer";
        dlLink.textContent = "Ver archivo ↗";
        actions.appendChild(dlLink);

        item.appendChild(actions);
        folderListEl.appendChild(item);
      });
    }

    function discoverRepositoryFolderLayers() {
      if (folderStatusEl) {
        folderStatusEl.textContent = "Consultando carpeta geovisor/capas/ de esta vista...";
      }
      var indexUrl = new URL("geovisor/capas/index.json", window.location.origin + baseUrl).href;
      var byName = {};

      var localPromise = fetch(indexUrl, { cache: "no-store" })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (idxDoc) {
          if (!idxDoc || !Array.isArray(idxDoc.files)) return;
          idxDoc.files.forEach(function (f) {
            if (!f.name || f.name === "index.json" || !GEOLIBRE_EXT_RE.test(f.name)) return;
            byName[f.name] = {
              name: f.name,
              size_bytes: f.size_bytes || null,
              url: new URL("geovisor/capas/" + encodeURIComponent(f.name), window.location.origin + baseUrl).href
            };
          });
        })
        .catch(function () {});

      // Consulta complementaria en vivo a la API pública de GitHub SOLO del repositorio efectivo de esta vista
      // (nunca mezcla con el repositorio canónico si se está viendo desde un fork o desde localhost).
      var ghPromise = Promise.resolve();
      var sourceUsed = isLocalhost ? "índice local de trabajo (localhost)" : "índice publicado de esta vista";
      if (repoSlug) {
        var ghApiUrl = "https://api.github.com/repos/" + repoSlug + "/contents/geovisor/capas?ref=" + encodeURIComponent(repoBranch);
        ghPromise = fetch(ghApiUrl, { headers: { Accept: "application/vnd.github+json" } })
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (entries) {
            if (!Array.isArray(entries)) return;
            sourceUsed = "repositorio de esta vista (" + repoSlug + ")";
            entries.forEach(function (ent) {
              if (!ent || ent.type !== "file" || !ent.name) return;
              if (ent.name === "index.json" || !GEOLIBRE_EXT_RE.test(ent.name)) return;
              if (!byName[ent.name]) {
                byName[ent.name] = {
                  name: ent.name,
                  size_bytes: ent.size || null,
                  url: ent.download_url || ("https://raw.githubusercontent.com/" + repoSlug + "/" + repoBranch + "/geovisor/capas/" + encodeURIComponent(ent.name))
                };
              }
            });
          })
          .catch(function () {});
      }

      Promise.all([localPromise, ghPromise]).then(function () {
        var list = Object.keys(byName)
          .sort()
          .map(function (k) { return byName[k]; });
        renderFolderItems(list, sourceUsed);
      });
    }

    if (refreshFolderBtn) {
      refreshFolderBtn.addEventListener("click", discoverRepositoryFolderLayers);
    }
    discoverRepositoryFolderLayers();

    // =======================================================================
    // Cargador de prueba desde equipo local (.geojson / .kml)
    // =======================================================================
    var fileInput = document.getElementById("gv-local-geojson-input");
    var dropzone = document.getElementById("gv-dropzone");
    var localStatus = document.getElementById("gv-local-status");
    var clearLocalBtn = document.getElementById("gv-clear-local");

    function handleLocalFile(file) {
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function () {
        try {
          var raw = String(reader.result || "");
          var parsed = file.name.toLowerCase().endsWith(".kml") ? parseKmlToGeoJson(raw) : JSON.parse(raw);
          if (!parsed || typeof parsed !== "object" || !parsed.type) {
            throw new Error("El archivo no tiene estructura GeoJSON o KML válida.");
          }
          localGeoJsonCache = parsed;
          if (mapInstance) {
            renderGeoJsonSourceLayers(
              "local-preview-src",
              "local-preview",
              parsed,
              "#007F8B",
              0.42,
              "#14283F",
              2.2,
              "VISTA PREVIA LOCAL TEMPORAL",
              file.name
            );
            var bbox = computeGeoJsonBounds(parsed);
            if (bbox) {
              mapInstance.fitBounds(bbox, { padding: 48, maxZoom: 16 });
            }
          }
          var count = parsed.type === "FeatureCollection" && Array.isArray(parsed.features) ? parsed.features.length : 1;
          if (localStatus) {
            localStatus.textContent = "Capa temporal leída: " + file.name + " (" + count + " geometría(s)). Súbela a geovisor/capas/ en tu repositorio para compartirla.";
          }
          if (clearLocalBtn) clearLocalBtn.classList.remove("hidden");
        } catch (err) {
          if (localStatus) {
            localStatus.textContent = "Error al leer archivo: " + (err && err.message ? err.message : "formato inválido");
          }
        }
      };
      reader.readAsText(file, "utf-8");
    }

    if (fileInput) {
      fileInput.addEventListener("change", function () {
        if (fileInput.files && fileInput.files[0]) handleLocalFile(fileInput.files[0]);
      });
    }
    if (dropzone && fileInput) {
      dropzone.addEventListener("click", function () { fileInput.click(); });
      dropzone.addEventListener("dragover", function (e) { e.preventDefault(); });
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
        if (mapInstance) {
          ["local-preview-fill", "local-preview-line", "local-preview-pt"].forEach(function (lid) {
            if (mapInstance.getLayer(lid)) mapInstance.removeLayer(lid);
          });
          if (mapInstance.getSource("local-preview-src")) mapInstance.removeSource("local-preview-src");
        }
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
    if (!dataScript || !container) return;

    var points;
    try {
      points = JSON.parse(dataScript.textContent || "[]");
    } catch (err) {
      return;
    }

    function renderHubFallback() {
      container.innerHTML = "";
      var box = document.createElement("div");
      box.className = "callout callout-warn";
      box.style.margin = "1rem";
      var h = document.createElement("strong");
      h.textContent = "Vista accesible de ubicaciones referenciales (WebGL no activo en este navegador)";
      box.appendChild(h);
      var ul = document.createElement("ul");
      ul.style.marginTop = "0.5rem";
      points.forEach(function (pt) {
        var li = document.createElement("li");
        var a = document.createElement("a");
        a.href = pt.detail_url || "#";
        a.textContent = pt.country_name + " · " + pt.short_name + " (" + pt.territory_label + ")";
        li.appendChild(a);
        ul.appendChild(li);
      });
      box.appendChild(ul);
      container.appendChild(box);
    }

    if (typeof window.maplibregl === "undefined" || !isWebGLSupported()) {
      renderHubFallback();
      return;
    }

    var map;
    try {
      map = new window.maplibregl.Map({
        container: container,
        style: makeStyle("carto-positron"),
        center: [-82.2, 14.1],
        zoom: 4.35,
        attributionControl: true,
        canvasContextAttributes: { preserveDrawingBuffer: true }
      });
    } catch (err) {
      renderHubFallback();
      return;
    }
    map.addControl(new window.maplibregl.NavigationControl(), "top-right");

    points.forEach(function (pt) {
      var wrap = createSafePopupElement(
        pt.country_name + " · " + pt.short_name,
        [
          ["Territorio", pt.territory_label],
          ["Institución", pt.institution],
          ["Aviso", "Ubicación referencial según el perfil (cada sitio incluye sus capas en su Geovisor GeoLibre)"]
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

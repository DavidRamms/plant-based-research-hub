/* ============================================================
   Plant-Based Research Hub — main.js
   ============================================================ */

(function () {
  "use strict";

  /* ── Collapsible sections ────────────────────────────────── */
  function initCollapsibles() {
    document.querySelectorAll(".collapsible-section").forEach(function (section) {
      var btn = section.querySelector(".section-toggle");
      if (!btn) return;

      // Respect data-open attribute (default all expanded)
      var isOpen = section.getAttribute("data-open") !== "false";
      if (!isOpen) {
        section.classList.add("collapsed");
      }

      btn.addEventListener("click", function () {
        section.classList.toggle("collapsed");
      });
    });
  }

  /* ── Abstract expand/collapse ────────────────────────────── */
  function initAbstractToggles() {
    document.querySelectorAll(".abstract-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var targetId = btn.getAttribute("data-target");
        var content = document.getElementById(targetId);
        if (!content) return;

        var isHidden = content.style.display === "none" || content.style.display === "";
        content.style.display = isHidden ? "block" : "none";
        btn.textContent = isHidden ? "Hide Abstract" : "Show Abstract";
      });
    });
  }

  /* ── Database page ───────────────────────────────────────── */
  function initDatabasePage() {
    var tableBody = document.getElementById("study-table-body");
    if (!tableBody) return;

    var searchInput   = document.getElementById("db-search");
    var filterTopic   = document.getElementById("filter-topic");
    var filterType    = document.getElementById("filter-type");
    var filterYearMin = document.getElementById("filter-year-min");
    var filterYearMax = document.getElementById("filter-year-max");
    var filterTier    = document.getElementById("filter-tier");
    var clearBtn      = document.getElementById("clear-filters");
    var resultsCount  = document.getElementById("results-count");
    var table         = document.getElementById("study-table");

    var allRows = Array.from(tableBody.querySelectorAll("tr"));
    var totalCount = allRows.length;

    // ── Lunr.js search ──────────────────────────────────────
    var lunrIndex = null;
    var lunrDocMap = {};  // pmid → row element

    function buildLunrIndex() {
      if (typeof lunr === "undefined") return;

      var docs = allRows.map(function (row) {
        return {
          id:       row.dataset.pmid,
          title:    row.dataset.title    || "",
          abstract: row.dataset.abstract || "",
          authors:  row.dataset.authors  || "",
        };
      });

      docs.forEach(function (doc) {
        lunrDocMap[doc.id] = true;
      });

      lunrIndex = lunr(function () {
        this.ref("id");
        this.field("title",    { boost: 3 });
        this.field("abstract", { boost: 1 });
        this.field("authors",  { boost: 2 });
        docs.forEach(function (doc) { this.add(doc); }, this);
      });
    }

    function getLunrMatchIds(query) {
      if (!lunrIndex || !query.trim()) return null; // null = show all
      try {
        var results = lunrIndex.search(query);
        return new Set(results.map(function (r) { return r.ref; }));
      } catch (e) {
        // Lunr can throw on malformed queries — fall back to simple text match
        return null;
      }
    }

    // ── Filter logic ────────────────────────────────────────
    function getSelectedTopics() {
      if (!filterTopic) return [];
      return Array.from(filterTopic.selectedOptions).map(function (o) { return o.value; });
    }

    function applyFilters() {
      var query        = searchInput ? searchInput.value.toLowerCase().trim() : "";
      var selectedTopics = getSelectedTopics();
      var typeFilter   = filterType    ? filterType.value    : "";
      var tierFilter   = filterTier    ? filterTier.value    : "";
      var yearMin      = filterYearMin ? parseInt(filterYearMin.value, 10) || 0   : 0;
      var yearMax      = filterYearMax ? parseInt(filterYearMax.value, 10) || 9999 : 9999;

      var lunrMatches = null;
      if (query && lunrIndex) {
        lunrMatches = getLunrMatchIds(query);
      }

      var visibleCount = 0;

      allRows.forEach(function (row) {
        var pmid   = row.dataset.pmid   || "";
        var year   = parseInt(row.dataset.year, 10) || 0;
        var type   = row.dataset.type   || "";
        var tier   = row.dataset.tier   || "";
        var topics = row.dataset.topics || "";

        // Search filter
        var passSearch = true;
        if (query) {
          if (lunrMatches) {
            passSearch = lunrMatches.has(pmid);
          } else {
            // Fallback: plain text match
            var rowText = (row.dataset.title || "") + " " +
                          (row.dataset.abstract || "") + " " +
                          (row.dataset.authors  || "");
            passSearch = rowText.toLowerCase().includes(query);
          }
        }

        // Topic filter (AND: row must include ALL selected topics)
        var passTopics = true;
        if (selectedTopics.length > 0) {
          passTopics = selectedTopics.every(function (t) {
            return topics.split(",").map(function(s){return s.trim();}).includes(t);
          });
        }

        // Type filter
        var passType = !typeFilter || type === typeFilter;

        // Tier filter
        var passTier = !tierFilter || tier === tierFilter;

        // Year filter
        var passYear = (year === 0) || (year >= yearMin && year <= yearMax);

        var visible = passSearch && passTopics && passType && passTier && passYear;
        row.classList.toggle("hidden", !visible);
        if (visible) visibleCount++;
      });

      if (resultsCount) {
        resultsCount.textContent = "Showing " + visibleCount + " of " + totalCount + " studies";
      }
    }

    // ── Event listeners ──────────────────────────────────────
    if (searchInput)   searchInput.addEventListener("input",  applyFilters);
    if (filterTopic)   filterTopic.addEventListener("change", applyFilters);
    if (filterType)    filterType.addEventListener("change",  applyFilters);
    if (filterYearMin) filterYearMin.addEventListener("input", applyFilters);
    if (filterYearMax) filterYearMax.addEventListener("input", applyFilters);
    if (filterTier)    filterTier.addEventListener("change",  applyFilters);

    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        if (searchInput)   searchInput.value = "";
        if (filterType)    filterType.value  = "";
        if (filterTier)    filterTier.value  = "";
        if (filterYearMin) filterYearMin.value = "";
        if (filterYearMax) filterYearMax.value = "";
        if (filterTopic) {
          Array.from(filterTopic.options).forEach(function (o) { o.selected = false; });
        }
        applyFilters();
      });
    }

    // ── Sortable columns ─────────────────────────────────────
    var currentSortCol  = null;
    var currentSortDir  = "asc";

    if (table) {
      table.querySelectorAll("th.sortable").forEach(function (th) {
        th.addEventListener("click", function () {
          var col = th.dataset.sort;
          if (currentSortCol === col) {
            currentSortDir = currentSortDir === "asc" ? "desc" : "asc";
          } else {
            currentSortCol = col;
            currentSortDir = "asc";
          }

          // Update header classes
          table.querySelectorAll("th.sortable").forEach(function (h) {
            h.classList.remove("sort-asc", "sort-desc");
          });
          th.classList.add("sort-" + currentSortDir);

          // Sort rows
          var rows = Array.from(tableBody.querySelectorAll("tr"));
          rows.sort(function (a, b) {
            var av = getCellValue(a, col);
            var bv = getCellValue(b, col);

            // Numeric comparison for year, tier, n
            if (col === "year" || col === "tier" || col === "n") {
              var an = parseFloat(av) || 0;
              var bn = parseFloat(bv) || 0;
              return currentSortDir === "asc" ? an - bn : bn - an;
            }
            // String comparison
            var cmp = av.toLowerCase().localeCompare(bv.toLowerCase());
            return currentSortDir === "asc" ? cmp : -cmp;
          });

          rows.forEach(function (r) { tableBody.appendChild(r); });
        });
      });
    }

    function getCellValue(row, col) {
      switch (col) {
        case "pmid":   return row.dataset.pmid   || "";
        case "title":  return row.dataset.title  || "";
        case "year":   return row.dataset.year   || "0";
        case "type":   return row.dataset.type   || "";
        case "tier":   return row.dataset.tier   || "0";
        case "topics": return row.dataset.topics || "";
        case "n":      return row.dataset.n      || "0";
        default:       return "";
      }
    }

    // ── Load Lunr index from JSON ──────────────────────────
    var searchIndexUrl = window.SEARCH_INDEX_URL;
    if (searchIndexUrl && typeof lunr !== "undefined") {
      // Build index from in-page row data (avoids extra HTTP request)
      buildLunrIndex();
    } else if (typeof lunr !== "undefined") {
      buildLunrIndex();
    }

    // Initial count
    if (resultsCount) {
      resultsCount.textContent = "Showing " + totalCount + " of " + totalCount + " studies";
    }
  }

  /* ── Init ────────────────────────────────────────────────── */
  document.addEventListener("DOMContentLoaded", function () {
    initCollapsibles();
    initAbstractToggles();
    initDatabasePage();
  });

})();

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

  /* ── Generic sort helper ─────────────────────────────────── */
  function sortElements(elements, sortValue) {
    var parts = sortValue.split("-");
    var key = parts[0];           // year | tier | n | magnitude
    var dir = parts[1];           // asc | desc

    elements.sort(function (a, b) {
      var av = parseFloat(a.dataset[key]) || 0;
      var bv = parseFloat(b.dataset[key]) || 0;
      return dir === "asc" ? av - bv : bv - av;
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

    // ── Sort dropdown ────────────────────────────────────────
    var dbSort = document.getElementById("db-sort");
    function applyDbSort() {
      if (!dbSort) return;
      var rows = Array.from(tableBody.querySelectorAll("tr"));
      sortElements(rows, dbSort.value);
      rows.forEach(function (r) { tableBody.appendChild(r); });
    }
    if (dbSort) {
      dbSort.addEventListener("change", applyDbSort);
      applyDbSort(); // apply default on load
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

  /* ── Topic page study sort ───────────────────────────────── */
  function initTopicSort() {
    var sortSelect = document.getElementById("topic-sort");
    var container  = document.getElementById("topic-studies-list");
    if (!sortSelect || !container) return;

    function applyTopicSort() {
      var cards = Array.from(container.querySelectorAll(".study-card"));
      sortElements(cards, sortSelect.value);
      cards.forEach(function (c) { container.appendChild(c); });
    }

    sortSelect.addEventListener("change", applyTopicSort);
    applyTopicSort(); // apply default on load
  }

  /* ── Copy stat citation helper ──────────────────────────── */
  window.copyStatCitation = function (btn) {
    var sentence  = btn.getAttribute("data-copy-sentence")  || "";
    var authors   = btn.getAttribute("data-copy-authors")   || "";
    var year      = btn.getAttribute("data-copy-year")      || "";
    var studyType = btn.getAttribute("data-copy-study-type")|| "";
    var pmid      = btn.getAttribute("data-copy-pmid")      || "";

    var parts = ["“" + sentence + "”"];
    var credit = authors;
    if (year) credit += ", " + year;
    if (credit) parts.push("— " + credit + ".");
    if (studyType) parts.push(studyType + ".");
    if (pmid) parts.push("PMID: " + pmid + ". https://pubmed.ncbi.nlm.nih.gov/" + pmid + "/");

    var text = parts.join(" ");
    navigator.clipboard.writeText(text).then(function () {
      var orig = btn.textContent;
      btn.textContent = "✓ Copied!";
      setTimeout(function () { btn.textContent = orig; }, 2000);
    });
  };

  /* ── Stats page ──────────────────────────────────────────── */
  function initStatsPage() {
    var statsContainer = document.getElementById("stats-key-findings");
    if (!statsContainer) return;

    var filterTopic     = document.getElementById("stats-filter-topic");
    var filterDiet      = document.getElementById("stats-filter-diet");
    var filterDirection = document.getElementById("stats-filter-direction");
    var filterQuality   = document.getElementById("stats-filter-quality");
    var statsSort       = document.getElementById("stats-sort");
    var clearBtn        = document.getElementById("stats-clear-filters");
    var resultsCount    = document.getElementById("stats-results-count");

    // Gather all stat cards from both sections
    var allStatCards = Array.from(document.querySelectorAll(".stat-card[data-topic]"));
    var totalCount = allStatCards.length;

    function applyStatsFilters() {
      var topicVal     = filterTopic     ? filterTopic.value     : "";
      var dietVal      = filterDiet      ? filterDiet.value      : "";
      var directionVal = filterDirection ? filterDirection.value : "";
      var qualityVal   = filterQuality   ? filterQuality.value   : "";

      var visibleCount = 0;

      allStatCards.forEach(function (card) {
        var cardTopic     = card.dataset.topic     || "";
        var cardDiet      = card.dataset.diet      || "";
        var cardDirection = card.dataset.direction || "";
        var cardTier      = parseInt(card.dataset.tier, 10) || 99;

        var passTopic     = !topicVal     || cardTopic === topicVal;
        var passDiet      = !dietVal      || cardDiet === dietVal;
        var passDirection = !directionVal || cardDirection === directionVal;
        var passQuality   = true;
        if (qualityVal === "highonly") {
          passQuality = cardTier <= 2;
        }

        var visible = passTopic && passDiet && passDirection && passQuality;
        card.classList.toggle("hidden", !visible);
        if (visible) visibleCount++;
      });

      if (resultsCount) {
        resultsCount.textContent = "Showing " + visibleCount + " of " + totalCount + " statistics";
      }

      // Apply sort after filtering
      if (statsSort) {
        var container = document.getElementById("stats-key-findings");
        if (container) {
          var visible = Array.from(container.querySelectorAll(".stat-card:not(.hidden)"));
          sortElements(visible, statsSort.value);
          visible.forEach(function (c) { container.appendChild(c); });
        }
      }
    }

    if (filterTopic)     filterTopic.addEventListener("change",  applyStatsFilters);
    if (filterDiet)      filterDiet.addEventListener("change",   applyStatsFilters);
    if (filterDirection) filterDirection.addEventListener("change", applyStatsFilters);
    if (filterQuality)   filterQuality.addEventListener("change",   applyStatsFilters);
    if (statsSort)       statsSort.addEventListener("change",       applyStatsFilters);

    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        if (filterTopic)     filterTopic.value     = "";
        if (filterDiet)      filterDiet.value      = "";
        if (filterDirection) filterDirection.value = "";
        if (filterQuality)   filterQuality.value   = "";
        applyStatsFilters();
      });
    }

    // Apply default sort on load
    applyStatsFilters();
  }

  /* ── Contested Claims page ──────────────────────────────── */
  function initContestedPage() {
    var cardsList = document.getElementById("contested-cards-list");
    if (!cardsList) return;

    var filterTopic   = document.getElementById("contested-filter-topic");
    var filterType    = document.getElementById("contested-filter-type");
    var filterCounter = document.getElementById("contested-filter-counter");
    var clearBtn      = document.getElementById("contested-clear-filters");
    var resultsCount  = document.getElementById("contested-results-count");

    var allCards = Array.from(cardsList.querySelectorAll(".contested-card"));
    var totalCount = allCards.length;

    function applyContestedFilters() {
      var topicVal   = filterTopic   ? filterTopic.value   : "";
      var typeVal    = filterType    ? filterType.value    : "";
      var counterVal = filterCounter ? filterCounter.value : "";

      var visibleCount = 0;

      allCards.forEach(function (card) {
        var cardTopic   = card.dataset.topic      || "";
        var cardType    = card.dataset.claimType  || "";
        var cardCounter = card.dataset.hasCounter || "";

        var passTopic   = !topicVal   || cardTopic === topicVal;
        var passType    = !typeVal    || cardType === typeVal;
        var passCounter = !counterVal || cardCounter === counterVal;

        var visible = passTopic && passType && passCounter;
        card.classList.toggle("hidden", !visible);
        if (visible) visibleCount++;
      });

      if (resultsCount) {
        resultsCount.textContent = "Showing " + visibleCount + " of " + totalCount + " contested studies";
      }
    }

    if (filterTopic)   filterTopic.addEventListener("change",   applyContestedFilters);
    if (filterType)    filterType.addEventListener("change",    applyContestedFilters);
    if (filterCounter) filterCounter.addEventListener("change", applyContestedFilters);

    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        if (filterTopic)   filterTopic.value   = "";
        if (filterType)    filterType.value    = "";
        if (filterCounter) filterCounter.value = "";
        applyContestedFilters();
      });
    }

    // Apply on load to set initial count
    applyContestedFilters();
  }

  /* ── Init ────────────────────────────────────────────────── */
  document.addEventListener("DOMContentLoaded", function () {
    initCollapsibles();
    initAbstractToggles();
    initDatabasePage();
    initTopicSort();
    initStatsPage();
    initContestedPage();
  });

})();

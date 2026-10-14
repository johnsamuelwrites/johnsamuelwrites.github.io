/*
 * Teaching overview: pick an academic year or themes to focus the timeline,
 * the year summary and the course cards. Every string is in the generated
 * page (src/main/teaching_overview.py), in its own language; this script only
 * shows, hides and dims. The selected year is kept in the URL (#2020).
 */
(function () {
    "use strict";

    var root = document.querySelector(".teaching-overview");
    if (!root) {
        return;
    }
    var controls = root.querySelector(".timeline-controls");
    if (controls) {
        controls.hidden = false;
    }

    var year = "all";
    var themes = new Set();
    var hashYear = /^#(\d{4})$/.exec(window.location.hash);
    if (hashYear && root.querySelector('.year-summary[data-year="' + hashYear[1] + '"]')) {
        year = hashYear[1];
    }

    function matches(element) {
        var inYear = year === "all" || element.dataset.years.split(" ").indexOf(year) !== -1;
        var inTheme = themes.size === 0 || themes.has(element.dataset.theme);
        return inYear && inTheme;
    }

    function render() {
        root.querySelectorAll(".year-btn").forEach(function (button) {
            button.setAttribute("aria-pressed", String(button.dataset.selectYear === year));
        });
        root.querySelectorAll(".theme-btn").forEach(function (button) {
            button.setAttribute("aria-pressed", String(themes.has(button.dataset.theme)));
        });
        root.querySelectorAll(".year-summary").forEach(function (summary) {
            summary.hidden = summary.dataset.year !== year;
        });
        root.querySelectorAll(".year-col").forEach(function (column) {
            column.classList.toggle("is-selected", column.dataset.selectYear === year);
        });
        var visible = {};
        root.querySelectorAll(".lane[data-years], .course-card[data-years]").forEach(function (element) {
            var shown = matches(element);
            element.classList.toggle("is-dim", !shown);
            if (shown && element.classList.contains("lane")) {
                visible[element.dataset.id] = true;
            }
        });
        root.querySelectorAll(".theme-row").forEach(function (row) {
            row.classList.toggle("is-dim", themes.size > 0 && !themes.has(row.dataset.theme));
        });
        root.querySelectorAll(".lineage").forEach(function (path) {
            path.classList.toggle("is-dim", !(visible[path.dataset.from] && visible[path.dataset.to]));
        });
    }

    function selectYear(value) {
        year = year === value && value !== "all" ? "all" : value;
        var url = window.location.pathname + window.location.search + (year === "all" ? "" : "#" + year);
        window.history.replaceState(null, "", url);
        render();
    }

    root.addEventListener("click", function (event) {
        if (event.target.closest("a")) {
            return;
        }
        var yearTarget = event.target.closest("[data-select-year]");
        if (yearTarget) {
            selectYear(yearTarget.dataset.selectYear);
            return;
        }
        var themeTarget = event.target.closest(".theme-btn");
        if (themeTarget) {
            var theme = themeTarget.dataset.theme;
            if (themes.has(theme)) {
                themes.delete(theme);
            } else {
                themes.add(theme);
            }
            render();
        }
    });

    render();

    // On a narrow screen only the years scroll: start at the most recent
    // ones, once the layout (and its fonts) has settled.
    var scroller = root.querySelector(".timeline-scroll");
    function showLatest() {
        if (scroller && scroller.scrollWidth > scroller.clientWidth) {
            scroller.scrollLeft = scroller.scrollWidth - scroller.clientWidth;
        }
    }
    showLatest();
    window.addEventListener("load", showLatest);
})();

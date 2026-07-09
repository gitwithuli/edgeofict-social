document.addEventListener("DOMContentLoaded", () => {
    const bindSearch = ({ inputId, listId, emptyId, targets }) => {
        const input = document.getElementById(inputId);

        if (!input) {
            return null;
        }

        const targetList = targets || [{ listId, emptyId }];
        const boundTargets = targetList
            .map((target) => {
                const list = document.getElementById(target.listId);
                if (!list) {
                    return null;
                }

                return {
                    rows: Array.from(list.children).filter((row) => row.hasAttribute("data-search")),
                    empty: target.emptyId ? document.getElementById(target.emptyId) : null,
                };
            })
            .filter(Boolean);

        if (!boundTargets.length) {
            return null;
        }

        let activeSourceKey = "";

        const applyFilter = () => {
            const query = input.value.trim().toLowerCase();

            boundTargets.forEach(({ rows, empty }) => {
                let visibleCount = 0;

                rows.forEach((row) => {
                    const haystack = row.getAttribute("data-search") || "";
                    const rowSourceKey = row.getAttribute("data-source-key") || "";
                    const visible = activeSourceKey ? rowSourceKey === activeSourceKey : (!query || haystack.includes(query));
                    row.hidden = !visible;
                    if (visible) {
                        visibleCount += 1;
                    }
                });

                if (empty) {
                    empty.style.display = visibleCount === 0 ? "block" : "none";
                }
            });
        };

        input.addEventListener("input", () => {
            activeSourceKey = "";
            applyFilter();
        });
        applyFilter();

        return {
            applyFilter,
            setQuery(query) {
                activeSourceKey = "";
                input.value = query;
                applyFilter();
            },
            setSourceFilter(query, sourceKey) {
                activeSourceKey = sourceKey || "";
                input.value = query;
                applyFilter();
            },
            input,
        };
    };

    bindSearch({
        inputId: "document-search",
        listId: "document-list",
        emptyId: "document-no-results",
    });

    const quoteSearch = bindSearch({
        inputId: "quote-search",
        targets: [
            { listId: "quote-library-list", emptyId: "quote-no-results" },
            { listId: "pending-quote-list", emptyId: "pending-no-results" },
            { listId: "archive-quote-list", emptyId: "archive-no-results" },
        ],
    });

    const postedSearch = bindSearch({
        inputId: "posted-search",
        listId: "posted-feed-list",
        emptyId: "posted-no-results",
    });

    document.querySelectorAll(".js-source-filter").forEach((button) => {
        button.addEventListener("click", () => {
            const query = button.getAttribute("data-source-query") || "";
            const sourceKey = button.getAttribute("data-source-key") || "";
            if (!quoteSearch) {
                return;
            }

            quoteSearch.setSourceFilter(query, sourceKey);
            if (postedSearch) {
                postedSearch.setSourceFilter(query, sourceKey);
            }

            const firstMatch = document.querySelector(
                "#quote-library-list [data-search]:not([hidden]), #pending-quote-list [data-search]:not([hidden]), #archive-quote-list [data-search]:not([hidden]), #posted-feed-list [data-search]:not([hidden])"
            );
            const scrollTarget = firstMatch || quoteSearch.input;
            scrollTarget.scrollIntoView({ behavior: "smooth", block: "center" });
            quoteSearch.input.focus();
        });
    });
});

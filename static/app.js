document.addEventListener("DOMContentLoaded", () => {
    const bindSearch = ({ inputId, listId, emptyId }) => {
        const input = document.getElementById(inputId);
        const list = document.getElementById(listId);
        const empty = document.getElementById(emptyId);

        if (!input || !list) {
            return;
        }

        const rows = Array.from(list.children).filter((row) => row.hasAttribute("data-search"));

        const applyFilter = () => {
            const query = input.value.trim().toLowerCase();
            let visibleCount = 0;

            rows.forEach((row) => {
                const haystack = row.getAttribute("data-search") || "";
                const visible = !query || haystack.includes(query);
                row.hidden = !visible;
                if (visible) {
                    visibleCount += 1;
                }
            });

            if (empty) {
                empty.style.display = visibleCount === 0 ? "block" : "none";
            }
        };

        input.addEventListener("input", applyFilter);
        applyFilter();
    };

    bindSearch({
        inputId: "document-search",
        listId: "document-list",
        emptyId: "document-no-results",
    });

    bindSearch({
        inputId: "quote-search",
        listId: "quote-library-list",
        emptyId: "quote-no-results",
    });

    bindSearch({
        inputId: "posted-search",
        listId: "posted-feed-list",
        emptyId: "posted-no-results",
    });

    document.querySelectorAll(".js-source-filter").forEach((button) => {
        button.addEventListener("click", () => {
            const query = button.getAttribute("data-source-query") || "";
            const quoteSearch = document.getElementById("quote-search");
            if (!quoteSearch) {
                return;
            }

            quoteSearch.value = query;
            quoteSearch.dispatchEvent(new Event("input", { bubbles: true }));
            quoteSearch.scrollIntoView({ behavior: "smooth", block: "center" });
            quoteSearch.focus();
        });
    });
});

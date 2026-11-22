(() => {
    const debounceDelay = 250;
    const typeLabels = {
        brand: "марка",
        model: "модель",
        technology: "технология",
        article: "статья",
        correction: "исправление",
    };

    document.querySelectorAll("[data-search-autocomplete]").forEach((input, inputIndex) => {
        const form = input.closest("form");
        const list = document.createElement("div");
        const listId = `search-suggestions-${inputIndex}`;
        list.id = listId;
        list.className = "autocomplete-list list-group shadow";
        list.setAttribute("role", "listbox");
        list.hidden = true;
        input.setAttribute("aria-controls", listId);
        input.parentElement.classList.add("autocomplete-host");
        input.parentElement.appendChild(list);

        let timer;
        let controller;
        let activeIndex = -1;
        let suggestions = [];

        const close = () => {
            list.hidden = true;
            list.replaceChildren();
            input.setAttribute("aria-expanded", "false");
            input.removeAttribute("aria-activedescendant");
            activeIndex = -1;
            suggestions = [];
        };

        const select = (index) => {
            if (!suggestions[index]) return;
            input.value = suggestions[index].value;
            close();
            form.requestSubmit();
        };

        const setActive = (index) => {
            const options = list.querySelectorAll("[role=option]");
            options.forEach((option) => {
                option.classList.remove("active");
                option.setAttribute("aria-selected", "false");
            });
            if (!options.length) return;
            activeIndex = (index + options.length) % options.length;
            options[activeIndex].classList.add("active");
            options[activeIndex].setAttribute("aria-selected", "true");
            input.setAttribute("aria-activedescendant", options[activeIndex].id);
        };

        const render = (items) => {
            suggestions = items;
            list.replaceChildren();
            items.forEach((item, index) => {
                const option = document.createElement("button");
                option.type = "button";
                option.id = `${listId}-option-${index}`;
                option.className = "list-group-item list-group-item-action autocomplete-option";
                option.setAttribute("role", "option");
                option.innerHTML = `<span>${escapeText(item.label)}</span><small>${escapeText(typeLabels[item.type] || item.type)}</small>`;
                option.addEventListener("mousedown", (event) => event.preventDefault());
                option.addEventListener("click", () => select(index));
                list.appendChild(option);
            });
            list.hidden = !items.length;
            input.setAttribute("aria-expanded", items.length ? "true" : "false");
            activeIndex = -1;
        };

        const escapeText = (value) => {
            const node = document.createElement("span");
            node.textContent = value;
            return node.innerHTML;
        };

        input.addEventListener("input", () => {
            window.clearTimeout(timer);
            controller?.abort();
            const query = input.value.trim();
            if (query.length < 2) {
                close();
                return;
            }
            timer = window.setTimeout(async () => {
                controller = new AbortController();
                try {
                    const url = `${input.dataset.suggestUrl}?q=${encodeURIComponent(query)}`;
                    const response = await fetch(url, {signal: controller.signal, headers: {Accept: "application/json"}});
                    if (!response.ok) throw new Error("Suggestion request failed");
                    render((await response.json()).suggestions || []);
                } catch (error) {
                    if (error.name !== "AbortError") close();
                }
            }, debounceDelay);
        });

        input.addEventListener("keydown", (event) => {
            if (list.hidden) return;
            if (event.key === "ArrowDown") { event.preventDefault(); setActive(activeIndex + 1); }
            else if (event.key === "ArrowUp") { event.preventDefault(); setActive(activeIndex - 1); }
            else if (event.key === "Enter" && activeIndex >= 0) { event.preventDefault(); select(activeIndex); }
            else if (event.key === "Escape") close();
        });
        input.addEventListener("blur", () => window.setTimeout(close, 100));
        document.addEventListener("click", (event) => { if (!form.contains(event.target)) close(); });
    });
})();

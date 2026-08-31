// Load and render the public leaderboard with periodic refresh.
(() => {
    "use strict";

    const loading = document.getElementById("leaderboard-loading");
    const emptyState = document.getElementById("leaderboard-empty");
    const results = document.getElementById("leaderboard-results");
    const podium = document.getElementById("leaderboard-podium");
    const tablePanel = document.getElementById("leaderboard-table-panel");
    const tableBody = document.getElementById("leaderboard-body");
    const updated = document.getElementById("leaderboard-updated");
    const errorBar = document.getElementById("leaderboard-error");

    let requestInFlight = false;
    let hasSuccessfulData = false;
    let lastSuccessfulEntries = [];

    function setHidden(element, hidden) {
        element.hidden = Boolean(hidden);
    }

    function formatScore(value) {
        const numeric = Number(value ?? 0);
        if (!Number.isFinite(numeric)) return "0";
        return Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(1);
    }

    function normalizeEntries(payload) {
        if (!payload || !Array.isArray(payload.entries)) return [];
        return payload.entries.slice(0, 10).map((entry, index) => ({
            rank: Number(entry.rank) || index + 1,
            name: String(entry.avatar_name || entry.display_name || "Player"),
            score: formatScore(entry.total_score),
            completed: Number(entry.completed_question_count ?? entry.completed_questions ?? 0) || 0,
        }));
    }

    function createTextElement(tag, className, value) {
        const element = document.createElement(tag);
        element.className = className;
        element.textContent = String(value);
        return element;
    }

    function createPodiumCard(entry) {
        const card = document.createElement("article");
        card.className = `podium-card rank-${entry.rank}`;
        card.setAttribute("aria-label", `Rank ${entry.rank}: ${entry.name}`);
        card.append(
            createTextElement("span", "podium-rank", entry.rank),
            createTextElement("span", "podium-name", entry.name),
            createTextElement("span", "podium-score", entry.score),
            createTextElement("span", "podium-completed", `${entry.completed} attempted`),
        );
        return card;
    }

    function renderPodium(entries) {
        podium.replaceChildren();
        if (entries.length < 3) {
            setHidden(podium, true);
            return;
        }
        const byRank = new Map(entries.slice(0, 3).map(entry => [entry.rank, entry]));
        [2, 1, 3].forEach(rank => {
            const entry = byRank.get(rank);
            if (entry) podium.appendChild(createPodiumCard(entry));
        });
        setHidden(podium, false);
    }

    function renderTable(entries) {
        tableBody.replaceChildren();
        const rows = entries.length >= 3 ? entries.slice(3) : entries;
        if (rows.length === 0) {
            setHidden(tablePanel, true);
            return;
        }
        rows.forEach(entry => {
            const row = document.createElement("tr");
            row.append(
                createTextElement("td", "rank", entry.rank),
                createTextElement("td", "participant-name", entry.name),
                createTextElement("td", "number", entry.score),
                createTextElement("td", "number", entry.completed),
            );
            tableBody.appendChild(row);
        });
        setHidden(tablePanel, false);
    }

    function renderEntries(entries) {
        lastSuccessfulEntries = entries;
        results.classList.toggle("podium-only", entries.length === 3);
        if (entries.length === 0) {
            setHidden(results, true);
            setHidden(emptyState, false);
            return;
        }
        setHidden(emptyState, true);
        setHidden(results, false);
        renderPodium(entries);
        renderTable(entries);
    }

    function setLoading(active) {
        setHidden(loading, !active);
    }

    function setError(active) {
        setHidden(errorBar, !active);
    }

    function updateTimestamp(date) {
        const time = date.toLocaleTimeString("en-GB", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
        });
        updated.textContent = `Last updated: ${time}`;
    }

    async function refreshLeaderboard() {
        if (requestInFlight) return;
        requestInFlight = true;
        setLoading(true);

        try {
            const response = await fetch(`/api/leaderboard?_=${Date.now()}`, {
                cache: "no-store",
                headers: { "Accept": "application/json" },
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const payload = await response.json();
            const entries = normalizeEntries(payload);
            renderEntries(entries);
            hasSuccessfulData = true;
            updateTimestamp(new Date());
            setError(false);
        } catch (error) {
            setError(true);
            if (hasSuccessfulData) {
                renderEntries(lastSuccessfulEntries);
            }
        } finally {
            requestInFlight = false;
            setLoading(false);
        }
    }

    window.MedusaLeaderboard = Object.freeze({ refresh: refreshLeaderboard });
    refreshLeaderboard();
    window.setInterval(refreshLeaderboard, 30000);
})();

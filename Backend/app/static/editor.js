// Manage code editing, submission, and result rendering for the editor page.
(() => {
    "use strict";

    const shell = document.querySelector(".editor-shell");
    let attemptId = shell.dataset.attemptId;
    const editor = document.getElementById("source-code");
    const checkButton = document.getElementById("check-code");
    const submitButton = document.getElementById("run-submit");
    const resetButton = document.getElementById("reset-code");
    const status = document.getElementById("run-status");
    const title = document.getElementById("result-title");
    const message = document.getElementById("result-message");
    const score = document.getElementById("result-score");
    const scoreBreakdown = document.getElementById("score-breakdown");
    const testResults = document.getElementById("test-results");
    const errorOutput = document.getElementById("error-output");

    editor.addEventListener("keydown", event => {
        if (event.key !== "Tab") return;
        event.preventDefault();
        const start = editor.selectionStart;
        const end = editor.selectionEnd;
        editor.value = `${editor.value.slice(0, start)}    ${editor.value.slice(end)}`;
        editor.selectionStart = editor.selectionEnd = start + 4;
    });

    resetButton.addEventListener("click", () => {
        editor.value = window.SIMULATOR_STARTER_CODE;
        editor.focus();
        resetResults();
        status.textContent = "Starter code restored.";
    });

    checkButton.addEventListener("click", () => sendCode(false));
    submitButton.addEventListener("click", () => sendCode(true));

    async function sendCode(submit) {
        setBusy(true);
        status.textContent = submit ? "Submitting your answer..." : "Checking your answer...";

        try {
            const payload = { source_code: editor.value };
            if (submit) {
                payload.submission_id = globalThis.crypto?.randomUUID?.()
                    || `SUB-${Date.now()}-${Math.random().toString(16).slice(2)}`;
            }
            const endpoint = submit ? "run" : "check";
            const response = await fetch(`/api/attempt/${encodeURIComponent(attemptId)}/${endpoint}`, {
                method: "POST",
                headers: { "Content-Type": "application/json", "Accept": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || "Request failed.");

            if (submit && data.attempt_id && data.attempt_id !== attemptId) {
                attemptId = data.attempt_id;
                shell.dataset.attemptId = attemptId;
            }

            if (submit && data.redirect_url) {
                status.textContent = "Score saved. Opening your result...";
                window.location.assign(data.redirect_url);
                return;
            }

            renderResult(data);
            status.textContent = data.overall_correct
                ? "All checks passed. Submit your answer to save the score."
                : "Check complete. You can improve the code or submit this score.";
        } catch (error) {
            renderResult({
                status: "ERROR",
                score: 0,
                message: "The answer could not be checked.",
                error_message: String(error),
                visible_results: [],
                score_breakdown: [],
            });
            status.textContent = "Connection error. Please try again.";
        } finally {
            setBusy(false);
        }
    }

    function setBusy(active) {
        checkButton.disabled = active;
        submitButton.disabled = active;
        resetButton.disabled = active;
    }

    function resetResults() {
        title.textContent = "Your tests have not been checked yet.";
        message.innerHTML = "Use <strong>Check Answer</strong> for feedback, or <strong>Submit Answer</strong> to save a score.";
        score.hidden = true;
        scoreBreakdown.hidden = true;
        scoreBreakdown.replaceChildren();
        testResults.replaceChildren();
        errorOutput.hidden = true;
    }

    function renderResult(data) {
        const results = Array.isArray(data.visible_results) ? data.visible_results : [];
        const passed = results.filter(item => item.passed).length;
        const total = results.length;

        if (data.overall_correct) {
            title.textContent = "All checks passed!";
        } else if (data.status === "ERROR") {
            title.textContent = "The code needs a fix before it can run.";
        } else {
            title.textContent = `${passed} of ${total} checks passed`;
        }

        message.textContent = data.overall_correct
            ? "Great work. Submit the answer to save your score."
            : "Your answer is not fully correct yet. You can still submit it to save a score and play the actual result.";

        score.hidden = false;
        score.textContent = `${formatScore(data.score)} / 100`;
        renderBreakdown(data.score_breakdown || []);
        renderTests(results);

        if (data.error_message) {
            errorOutput.hidden = false;
            errorOutput.textContent = data.error_message;
        } else {
            errorOutput.hidden = true;
            errorOutput.textContent = "";
        }
    }

    function renderBreakdown(items) {
        scoreBreakdown.replaceChildren();
        if (!items.length) {
            scoreBreakdown.hidden = true;
            return;
        }
        for (const item of items) {
            const chip = document.createElement("span");
            chip.className = "score-chip";
            chip.textContent = `${item.label}: ${formatScore(item.points)} / ${formatScore(item.max_points)}`;
            scoreBreakdown.appendChild(chip);
        }
        scoreBreakdown.hidden = false;
    }

    function renderTests(items) {
        testResults.replaceChildren();
        for (const item of items) {
            const card = document.createElement("article");
            card.className = `test-result ${item.passed ? "pass" : "fail"}`;

            const icon = document.createElement("strong");
            icon.className = "test-icon";
            icon.textContent = item.passed ? "✓" : "×";

            const name = document.createElement("span");
            name.className = "test-name";
            name.textContent = item.name || "Test";

            const state = document.createElement("span");
            state.className = "test-state";
            state.textContent = item.passed ? "PASSED" : "NEEDS FIXING";

            const details = document.createElement("details");
            const summary = document.createElement("summary");
            summary.textContent = "View expected and actual result";
            const output = document.createElement("pre");
            output.textContent = `Expected:\n${formatValue(item.expected)}\n\nYour result:\n${formatValue(item.actual)}`;
            details.append(summary, output);
            card.append(icon, name, state, details);
            testResults.appendChild(card);
        }
    }

    function formatScore(value) {
        const numeric = Number(value ?? 0);
        if (!Number.isFinite(numeric)) return "0";
        return Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(1);
    }

    function formatValue(value) {
        if (value === null || value === undefined || value === "") return "—";
        if (typeof value === "object") {
            try { return JSON.stringify(value, null, 2); }
            catch (_) { return String(value); }
        }
        return String(value);
    }
})();

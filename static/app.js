document.addEventListener("DOMContentLoaded", () => {
    const refreshButton = document.getElementById("refresh-integrations");
    const setCardState = (key, payload) => {
        const card = document.querySelector(`[data-integration-card="${key}"]`);
        if (!card || !payload) {
            return;
        }

        card.classList.remove("state-ready", "state-ok", "state-error", "state-missing");
        card.classList.add(`state-${payload.state}`);

        const chip = card.querySelector(".status-chip");
        const live = card.querySelector(".integration-live");

        if (chip) {
            chip.textContent =
                payload.state === "ok"
                    ? "Verified"
                    : payload.state === "missing"
                      ? "Missing"
                      : "Error";
        }

        if (live) {
            live.textContent = payload.message;
        }
    };

    const verifyIntegrations = async () => {
        refreshButton.disabled = true;
        refreshButton.textContent = "Checking...";

        try {
            const response = await fetch("/api/integrations", {
                headers: {
                    "Accept": "application/json",
                },
            });

            if (!response.ok) {
                throw new Error("Failed to load integration status.");
            }

            const payload = await response.json();
            Object.entries(payload).forEach(([key, value]) => setCardState(key, value));
        } catch (error) {
            ["twitter", "facebook", "instagram", "cloudinary", "anthropic"].forEach((key) => {
                setCardState(key, {
                    state: "error",
                    message: error.message,
                });
            });
        } finally {
            refreshButton.disabled = false;
            refreshButton.textContent = "Verify Live";
        }
    };

    if (refreshButton) {
        refreshButton.addEventListener("click", verifyIntegrations);
        verifyIntegrations();
    }

    const stoicWorkbench = document.getElementById("stoic-workbench");
    if (!stoicWorkbench) {
        return;
    }

    const stoicReady = stoicWorkbench.dataset.stoicReady === "true";
    const stoicStatus = document.getElementById("stoic-status");
    const stoicResult = document.getElementById("stoic-result");
    const generateButton = document.getElementById("stoic-generate");
    const queueDraftButton = document.getElementById("stoic-queue-draft");
    const queueApprovedButton = document.getElementById("stoic-queue-approved");
    let stoicPayload = null;

    const escapeHtml = (value) =>
        String(value ?? "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");

    const setStoicStatus = (message, state = "info") => {
        if (!stoicStatus) {
            return;
        }

        stoicStatus.textContent = message;
        stoicStatus.style.borderColor =
            state === "error"
                ? "rgba(241, 125, 101, 0.35)"
                : state === "success"
                  ? "rgba(141, 217, 194, 0.35)"
                  : "rgba(241, 125, 101, 0.2)";
        stoicStatus.style.background =
            state === "error"
                ? "rgba(241, 125, 101, 0.08)"
                : state === "success"
                  ? "rgba(141, 217, 194, 0.08)"
                  : "rgba(241, 125, 101, 0.08)";
    };

    const renderStoicPayload = (payload) => {
        if (!stoicResult) {
            return;
        }

        const previewSource = payload.image_url || payload.image_data_uri || "";
        stoicResult.classList.remove("empty-state");
        stoicResult.innerHTML = `
            <div class="stoic-result-card">
                ${
                    previewSource
                        ? `<div class="stoic-preview-image"><img src="${escapeHtml(previewSource)}" alt="Stoic card preview"></div>`
                        : ""
                }
                <div class="stoic-topline">
                    <div>
                        <strong>${escapeHtml(payload.title)}</strong>
                        <div class="mono-line">${escapeHtml(payload.author)} - ${escapeHtml(payload.date || "")}</div>
                    </div>
                    <span class="pill">${escapeHtml(payload.key_takeaway)}</span>
                </div>
                <div class="stoic-pillars">
                    <article class="stoic-pillar">
                        <strong>${escapeHtml(payload.point1_title)}</strong>
                        <span>${escapeHtml(payload.point1_meaning)}</span>
                        <p>${escapeHtml(payload.point1_trading)}</p>
                    </article>
                    <article class="stoic-pillar">
                        <strong>${escapeHtml(payload.point2_title)}</strong>
                        <span>${escapeHtml(payload.point2_meaning)}</span>
                        <p>${escapeHtml(payload.point2_trading)}</p>
                    </article>
                    <article class="stoic-pillar">
                        <strong>${escapeHtml(payload.point3_title)}</strong>
                        <span>${escapeHtml(payload.point3_meaning)}</span>
                        <p>${escapeHtml(payload.point3_trading)}</p>
                    </article>
                </div>
                <article class="stoic-note">
                    <span class="eyebrow">Closing Wisdom</span>
                    <p>${escapeHtml(payload.closing_wisdom)}</p>
                </article>
                <article class="stoic-tweet">
                    <span class="eyebrow">Queue Preview</span>
                    <p>${escapeHtml(payload.tweet)}</p>
                    <div class="mono-line">${payload.tweet.length}/280 characters</div>
                </article>
            </div>
        `;
    };

    const queueStoic = async (status) => {
        if (!stoicPayload) {
            return;
        }

        queueDraftButton.disabled = true;
        queueApprovedButton.disabled = true;

        try {
            const response = await fetch("/api/stoic/queue", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                body: JSON.stringify({
                    tweet: stoicPayload.tweet,
                    status,
                    image_url: stoicPayload.image_url || null,
                    render_payload: stoicPayload,
                }),
            });

            const payload = await response.json();
            if (!response.ok || !payload.success) {
                throw new Error(payload.error || "Failed to queue Stoic post.");
            }

            setStoicStatus(`Queued Stoic post #${payload.post_id} as ${status}.`, "success");
        } catch (error) {
            setStoicStatus(error.message, "error");
        } finally {
            queueDraftButton.disabled = false;
            queueApprovedButton.disabled = false;
        }
    };

    if (!stoicReady) {
        return;
    }

    generateButton?.addEventListener("click", async () => {
        generateButton.disabled = true;
        queueDraftButton.disabled = true;
        queueApprovedButton.disabled = true;
        setStoicStatus("Generating Stoic trading angle...");

        try {
            const response = await fetch("/api/stoic/generate", {
                method: "POST",
                headers: {
                    "Accept": "application/json",
                },
            });

            const payload = await response.json();
            if (!response.ok || !payload.success) {
                throw new Error(payload.error || "Failed to generate Stoic content.");
            }

            stoicPayload = payload;
            renderStoicPayload(payload);
            queueDraftButton.disabled = false;
            queueApprovedButton.disabled = false;
            setStoicStatus("Stoic trading angle generated. Queue it when ready.", "success");
        } catch (error) {
            setStoicStatus(error.message, "error");
        } finally {
            generateButton.disabled = false;
        }
    });

    queueDraftButton?.addEventListener("click", () => queueStoic("pending"));
    queueApprovedButton?.addEventListener("click", () => queueStoic("approved"));
});

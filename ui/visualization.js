/* ==================== VISUALIZATION MANAGEMENT ==================== */

(function () {
  "use strict";

  console.log("Visualization.js loaded");

  const API_BASE = TMS_API.base;

  // Helper function for toast
  const toast =
    window.showToast ||
    function (msg, type) {
      console.log(`[${type}] ${msg}`);
      alert(msg);
    };

  // State
  let allJobs = [];
  let currentJob = null;
  let currentJobRoutes = [];
  let currentRoute = null;
  // Polling state
  let jobPollTimer = null;
  let jobPollAttempts = 0;
  const MAX_POLL_ATTEMPTS = 120; // ~10 minutes at 5s interval
  const POLL_INTERVAL_MS = 5000; // Poll every 5 seconds as requested

  // Enable/disable Print All based on job status and data availability
  function updatePrintAvailability() {
    const btn = document.getElementById("printAllRoutesBtn");
    if (!btn) return;
    const canPrint =
      !!currentJob &&
      (currentJob.status === "completed" || currentJob.status === "planned") &&
      currentJobRoutes?.length > 0;
    btn.disabled = !canPrint;
    btn.title = canPrint
      ? "Print all routes"
      : "Printing is available when the job is completed and routes are ready";
  }

  // Job state helpers
  function isJobFinished(status) {
    return (
      status === "completed" || status === "planned" || status === "failed"
    );
  }

  function autoSelectFirstRoute() {
    if (!currentJobRoutes || currentJobRoutes.length === 0) return;
    const targetRoute =
      (currentRoute &&
        currentJobRoutes.find((r) => r.id === currentRoute.id)) ||
      currentJobRoutes[0];
    if (!targetRoute) return;
    displayRouteDetails(targetRoute.id);
    // Highlight selection in list
    document.querySelectorAll(".route-item").forEach((el) => {
      const rid = parseInt(el.dataset.routeId);
      if (rid === targetRoute.id) el.classList.add("active");
      else el.classList.remove("active");
    });
  }

  function stopJobPolling() {
    if (jobPollTimer) {
      clearInterval(jobPollTimer);
      jobPollTimer = null;
    }
    jobPollAttempts = 0;
  }

  function rerenderJobsListAndKeepSelection(jobId) {
    renderJobsList();
    if (jobId != null) {
      const el = document.querySelector(`.job-item[data-job-id="${jobId}"]`);
      if (el) el.classList.add("active");
    }
  }

  function updateJobsListStatus(jobId, status, routeCount) {
    const idx = allJobs.findIndex((j) => j.id === jobId);
    if (idx !== -1) {
      allJobs[idx].status = status;
      if (typeof routeCount === "number") {
        allJobs[idx].route_count = routeCount;
      }
    }
    rerenderJobsListAndKeepSelection(jobId);
  }

  function startJobPolling(jobId) {
    stopJobPolling();
    if (!jobId) return;
    jobPollAttempts = 0;
    jobPollTimer = setInterval(async () => {
      try {
        // If user navigated away or switched job, stop polling
        if (!currentJob || currentJob.id !== jobId) {
          stopJobPolling();
          return;
        }

        jobPollAttempts++;
        if (jobPollAttempts > MAX_POLL_ATTEMPTS) {
          stopJobPolling();
          toast("Stopped auto-refresh after waiting for a while.", "warning");
          return;
        }

        const res = await fetch(`${API_BASE}/job/${jobId}`);
        if (!res.ok) return; // silent skip, try next tick
        const job = await res.json();

        // Update job details if status changed
        if (job.status !== currentJob.status) {
          currentJob = job;
          displayJobDetails();
          updateJobsListStatus(jobId, job.status, job.route_count);
        }

        if (isJobFinished(job.status)) {
          stopJobPolling();
          // Refresh routes when job finishes
          try {
            const routesRes = await fetch(`${API_BASE}/job/${jobId}/routes`);
            if (routesRes.ok) {
              currentJobRoutes = await routesRes.json();
            }
          } catch (e) {
            console.warn("Failed to refresh routes after completion", e);
          }

          displayRoutesList();
          updatePrintAvailability();
          // Auto-select first route to reveal stops/map without extra clicks
          autoSelectFirstRoute();

          if (job.status === "completed" || job.status === "planned") {
            toast("Job completed. Routes are ready.", "success");
          } else if (job.status === "failed") {
            toast("Job failed. Please check server logs.", "danger");
          }
        } else {
          // still running – keep UI responsive
          updatePrintAvailability();
        }
      } catch (err) {
        console.warn("Polling error:", err);
      }
    }, POLL_INTERVAL_MS);
  }

  // Helper: Get date string in YYYY-MM-DD format
  function formatDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  // Helper: Set default date range (last 7 days to today)
  function setDefaultDateRange() {
    const today = new Date();
    const lastWeek = new Date();
    lastWeek.setDate(today.getDate() - 7);

    const dateFromInput = document.getElementById("jobDateFrom");
    const dateToInput = document.getElementById("jobDateTo");

    if (dateFromInput) dateFromInput.value = formatDate(lastWeek);
    if (dateToInput) dateToInput.value = formatDate(today);
  }

  // Initialize on DOM ready
  document.addEventListener("DOMContentLoaded", () => {
    console.log("DOMContentLoaded - Setting up visualization tab");

    // Set default date range
    setDefaultDateRange();

    const visualizationTab = document.getElementById("visualization-tab");

    if (visualizationTab) {
      console.log("Found visualization tab button");
      visualizationTab.addEventListener("shown.bs.tab", async () => {
        console.log("Visualization tab activated");
        await loadJobs();

        // Check if there's a pending job to load
        if (window.pendingJobId) {
          const jobId = window.pendingJobId;
          window.pendingJobId = null; // Clear it

          // Wait for jobs to load, then select the job
          setTimeout(() => {
            loadJobDetails(jobId);
          }, 300);
        }
      });
      // Stop polling when leaving the tab
      visualizationTab.addEventListener("hidden.bs.tab", () => {
        stopJobPolling();
      });
    } else {
      console.error("Visualization tab button not found!");
    }

    // Check if visualization tab is already active on page load
    const visualizationPane = document.getElementById("visualization");
    if (visualizationPane?.classList.contains("active")) {
      console.log("Visualization tab already active on load");
      loadJobs();
    }

    // Refresh button
    const refreshBtn = document.getElementById("refreshJobsBtn");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", () => {
        console.log("Manual refresh jobs clicked");
        loadJobs();
        toast("Jobs refreshed", "success");
      });
    }

    // Job search filter
    const searchInput = document.getElementById("jobSearchInput");
    if (searchInput) {
      searchInput.addEventListener("input", renderJobsList);
    }

    // Date range filters
    const dateFromInput = document.getElementById("jobDateFrom");
    const dateToInput = document.getElementById("jobDateTo");
    if (dateFromInput) {
      dateFromInput.addEventListener("change", loadJobs);
    }
    if (dateToInput) {
      dateToInput.addEventListener("change", loadJobs);
    }

    // Print all routes button
    const printAllBtn = document.getElementById("printAllRoutesBtn");
    if (printAllBtn) {
      printAllBtn.addEventListener("click", printAllRoutes);
    }

    // Complete Delivery button
    const completeBtn = document.getElementById("completeDeliveryBtn");
    if (completeBtn) {
      completeBtn.addEventListener("click", async () => {
        if (!currentJob) return;

        if (
          !confirm(
            `Mark job "${currentJob.name}" as completed?\n\nThis will assign all orders to their respective routes and mark them as completed.`
          )
        ) {
          return;
        }

        try {
          completeBtn.disabled = true;
          completeBtn.innerHTML =
            '<i class="bi bi-hourglass-split"></i> Completing...';

          const res = await fetch(`${API_BASE}/job/${currentJob.id}/complete`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
          });

          if (!res.ok) {
            const error = await res.json();
            throw new Error(error.detail || "Failed to complete job");
          }

          const result = await res.json();
          toast(`Job completed successfully!`, "success");

          // Reload job details to reflect new status
          await loadJobDetails(currentJob.id);

          // Refresh jobs list
          await loadJobs();
        } catch (err) {
          toast(`Failed to complete job: ${err.message}`, "danger");
          completeBtn.disabled = false;
          completeBtn.innerHTML =
            '<i class="bi bi-check-circle"></i> Complete Delivery';
        }
      });
    }

    // Print modal buttons
    const printToDeviceBtn = document.getElementById("printToDeviceBtn");
    const saveToPdfBtn = document.getElementById("saveToPdfBtn");

    if (printToDeviceBtn) {
      printToDeviceBtn.addEventListener("click", () => {
        // Close modal
        const modal = bootstrap.Modal.getInstance(
          document.getElementById("printOptionsModal")
        );
        modal.hide();
        // Execute print
        executePrint();
        toast("Opening printer dialog...", "info");
      });
    }

    if (saveToPdfBtn) {
      saveToPdfBtn.addEventListener("click", () => {
        // Close modal
        const modal = bootstrap.Modal.getInstance(
          document.getElementById("printOptionsModal")
        );
        modal.hide();
        // Execute print (user can select "Save as PDF" in print dialog)
        executePrint();
        toast(
          "Opening print dialog... Select 'Save as PDF' as destination",
          "info"
        );
      });
    }
  });

  // === Clear all detail views ===
  function clearAllDetails() {
    console.log("Clearing all detail views");

    // Reset state
    currentJob = null;
    currentJobRoutes = [];
    currentRoute = null;

    // Hide all detail cards
    const jobDetailsCard = document.getElementById("jobDetailsCard");
    const routesCard = document.getElementById("routesCard");
    const stopsCard = document.getElementById("stopsCard");
    const mapCard = document.getElementById("mapCard");
    const placeholder = document.getElementById("visualizationPlaceholder");

    if (jobDetailsCard) jobDetailsCard.style.display = "none";
    if (routesCard) routesCard.style.display = "none";
    if (stopsCard) stopsCard.style.display = "none";
    if (mapCard) mapCard.style.display = "none";
    if (placeholder) placeholder.style.display = "block";

    // Clear content
    const routesList = document.getElementById("routesList");
    const stopsTableBody = document.querySelector("#stopsTable tbody");
    const mapContainer = document.getElementById("mapContainer");

    if (routesList) routesList.innerHTML = "";
    if (stopsTableBody) stopsTableBody.innerHTML = "";
    if (mapContainer) mapContainer.innerHTML = "";

    console.log("All details cleared");
  }

  // === Load all jobs ===
  async function loadJobs() {
    console.log("loadJobs called");

    // Clear all details when reloading jobs
    clearAllDetails();
    stopJobPolling();

    try {
      // Build query params from date filters
      const dateFromInput = document.getElementById("jobDateFrom");
      const dateToInput = document.getElementById("jobDateTo");

      const params = new URLSearchParams();
      if (dateFromInput?.value) {
        params.append("date_from", dateFromInput.value);
      }
      if (dateToInput?.value) {
        params.append("date_to", dateToInput.value);
      }

      const queryString = params.toString();
      const url = `${API_BASE}/job/${queryString ? "?" + queryString : ""}`;

      console.log("Fetching jobs from:", url);
      const res = await fetch(url);
      console.log("Jobs response status:", res.status);

      if (!res.ok) throw new Error("Failed to load jobs");

      allJobs = await res.json();
      console.log("Loaded jobs:", allJobs.length);

      renderJobsList();
    } catch (err) {
      console.error("Error loading jobs:", err);
      toast("Failed to load jobs: " + err.message, "danger");
    }
  }

  // === Render jobs list ===
  function renderJobsList() {
    console.log("renderJobsList called");
    const container = document.getElementById("jobsList");
    const noData = document.getElementById("noJobs");
    const searchInput = document.getElementById("jobSearchInput");

    if (!container) {
      console.error("Jobs list container not found!");
      return;
    }

    const searchTerm = searchInput?.value.toLowerCase() || "";
    const filtered = allJobs.filter((job) => {
      const name = (job.name || "").toLowerCase();
      const status = (job.status || "").toLowerCase();
      const day = (job.day || "").toString();
      return (
        name.includes(searchTerm) ||
        status.includes(searchTerm) ||
        day.includes(searchTerm)
      );
    });

    if (!filtered.length) {
      console.log("No jobs to display");
      if (noData) noData.style.display = "block";
      container.innerHTML = "";
      return;
    }

    if (noData) noData.style.display = "none";

    container.innerHTML = filtered
      .map((job) => {
        const statusClass =
          job.status === "completed" || job.status === "planned"
            ? "success"
            : job.status === "running"
            ? "primary"
            : job.status === "failed"
            ? "danger"
            : "secondary";

        return `
        <a
          href="#"
          class="list-group-item list-group-item-action job-item"
          data-job-id="${job.id}"
        >
          <div class="d-flex w-100 justify-content-between align-items-start">
            <div>
              <h6 class="mb-1">${job.name}</h6>
              <small class="text-muted">
                <i class="bi bi-calendar"></i> ${job.day}
                &nbsp;&nbsp;
                <i class="bi bi-truck"></i> ${job.route_count} routes
              </small>
            </div>
            <span class="badge bg-${statusClass}">${job.status}</span>
          </div>
        </a>
      `;
      })
      .join("");

    // Attach click listeners
    attachJobListeners();
  }

  // === Attach job click listeners ===
  function attachJobListeners() {
    document.querySelectorAll(".job-item").forEach((item) => {
      item.addEventListener("click", async (e) => {
        e.preventDefault();
        const jobId = parseInt(e.currentTarget.dataset.jobId);
        console.log("Job clicked:", jobId);

        // Highlight selected
        document.querySelectorAll(".job-item").forEach((el) => {
          el.classList.remove("active");
        });
        e.currentTarget.classList.add("active");

        await loadJobDetails(jobId);
      });
    });
  }

  // === Clear route details ===
  function clearRouteDetails() {
    console.log("Clearing route details");
    currentRoute = null;

    // Hide stops card
    const stopsCard = document.getElementById("stopsCard");
    if (stopsCard) stopsCard.style.display = "none";

    // Hide map card
    const mapCard = document.getElementById("mapCard");
    if (mapCard) mapCard.style.display = "none";

    // Clear stops table
    const tbody = document.querySelector("#stopsTable tbody");
    if (tbody) tbody.innerHTML = "";

    // Clear map container
    const mapContainer = document.getElementById("mapContainer");
    if (mapContainer) mapContainer.innerHTML = "";
  }

  // === Load job details and routes ===
  async function loadJobDetails(jobId) {
    console.log("loadJobDetails called for job:", jobId);

    // Clear previous route selection when switching jobs
    clearRouteDetails();
    stopJobPolling();

    // Highlight the selected job in the list
    document.querySelectorAll(".job-item").forEach((el) => {
      el.classList.remove("active");
      if (parseInt(el.dataset.jobId) === jobId) {
        el.classList.add("active");
      }
    });

    try {
      // Fetch job details
      const jobRes = await fetch(`${API_BASE}/job/${jobId}`);
      if (!jobRes.ok) throw new Error("Failed to load job details");
      currentJob = await jobRes.json();

      // Fetch all routes for this job
      const routesRes = await fetch(`${API_BASE}/job/${jobId}/routes`);
      if (!routesRes.ok) throw new Error("Failed to load routes");
      currentJobRoutes = await routesRes.json();

      console.log("Job details:", currentJob);
      console.log("Routes:", currentJobRoutes.length);

      displayJobDetails();
      displayRoutesList();
      updatePrintAvailability();

      // Hide placeholder
      document.getElementById("visualizationPlaceholder").style.display =
        "none";

      // If job is running, start polling for completion; if already finished, ensure routes and table show
      if (currentJob?.status === "running") {
        startJobPolling(jobId);
      } else if (isJobFinished(currentJob?.status)) {
        if (!currentJobRoutes || currentJobRoutes.length === 0) {
          try {
            const routesRes = await fetch(`${API_BASE}/job/${jobId}/routes`);
            if (routesRes.ok) currentJobRoutes = await routesRes.json();
          } catch (e) {
            console.warn("Failed to load routes for finished job", e);
          }
          displayRoutesList();
        }
        updatePrintAvailability();
        autoSelectFirstRoute();
      }
    } catch (err) {
      console.error("Error loading job details:", err);
      toast("Failed to load job details: " + err.message, "danger");
    }
  }

  // === Display job details card ===
  function displayJobDetails() {
    const card = document.getElementById("jobDetailsCard");
    const title = document.getElementById("jobDetailsTitle");
    const day = document.getElementById("jobDay");
    const status = document.getElementById("jobStatus");
    const routeCount = document.getElementById("jobRouteCount");
    const completeBtn = document.getElementById("completeDeliveryBtn");

    if (!card || !currentJob) return;

    title.textContent = currentJob.name;
    day.textContent = currentJob.day;
    status.innerHTML = `<span class="badge bg-${
      currentJob.status === "completed" || currentJob.status === "planned"
        ? "success"
        : currentJob.status === "running"
        ? "primary"
        : currentJob.status === "failed"
        ? "danger"
        : "secondary"
    }">${currentJob.status}</span>`;
    routeCount.textContent = `${currentJob.total_routes} routes, ${currentJob.total_stops} orders`;

    // Show Complete Delivery button only if status is "planned"
    // Reset button state and re-enable it
    if (completeBtn) {
      if (currentJob.status === "planned") {
        completeBtn.style.display = "inline-block";
        completeBtn.disabled = false;
        completeBtn.innerHTML =
          '<i class="bi bi-check-circle"></i> Complete Delivery';
      } else {
        completeBtn.style.display = "none";
      }
    }

    card.style.display = "block";
    updatePrintAvailability();
  }

  // === Display routes list ===
  function displayRoutesList() {
    const card = document.getElementById("routesCard");
    const container = document.getElementById("routesList");

    if (!container || !currentJobRoutes.length) {
      if (card) card.style.display = "none";
      return;
    }

    container.innerHTML = currentJobRoutes
      .map((route) => {
        return `
        <a
          href="#"
          class="list-group-item list-group-item-action route-item"
          data-route-id="${route.id}"
        >
          <div class="d-flex justify-content-between align-items-center">
            <div>
              <strong>${route.vehicle_name}</strong>
              <br>
              <small class="text-muted">
                ${route.stops.length} orders
                ${
                  route.total_distance
                    ? `&nbsp;|&nbsp; ${route.total_distance.toFixed(1)} km`
                    : ""
                }
                ${
                  route.total_time
                    ? `&nbsp;|&nbsp; ${route.total_time.toFixed(0)} min`
                    : ""
                }
              </small>
            </div>
            <i class="bi bi-chevron-right"></i>
          </div>
        </a>
      `;
      })
      .join("");

    card.style.display = "block";

    // Attach route click listeners
    attachRouteListeners();
  }

  // === Attach route click listeners ===
  function attachRouteListeners() {
    document.querySelectorAll(".route-item").forEach((item) => {
      item.addEventListener("click", async (e) => {
        e.preventDefault();
        const routeId = parseInt(e.currentTarget.dataset.routeId);
        console.log("Route clicked:", routeId);

        // Highlight selected
        document.querySelectorAll(".route-item").forEach((el) => {
          el.classList.remove("active");
        });
        e.currentTarget.classList.add("active");

        displayRouteDetails(routeId);
      });
    });
  }

  // === Display route details (stops table and map) ===
  function displayRouteDetails(routeId) {
    console.log("displayRouteDetails called for route:", routeId);
    currentRoute = currentJobRoutes.find((r) => r.id === routeId);

    if (!currentRoute) {
      console.error("Route not found in current job routes");
      return;
    }

    console.log("Current route:", currentRoute);

    displayStopsTable();
    displayRouteMap();
  }

  // === Display stops table ===
  function displayStopsTable() {
    const card = document.getElementById("stopsCard");
    const title = document.getElementById("stopsCardTitle");
    const tbody = document.querySelector("#stopsTable tbody");

    if (!card || !tbody || !currentRoute) return;

    title.textContent = `Route Stops - ${currentRoute.vehicle_name}`;

    tbody.innerHTML = currentRoute.stops
      .map(
        (stop) => `
      <tr>
        <td><strong>${stop.sequence}</strong></td>
        <td>${stop.shop_code}</td>
        <td>${stop.order_id || "-"}</td>
        <td>${stop.shop_location || "-"}</td>
        <td>${stop.shop_address || "-"}</td>
      </tr>
    `
      )
      .join("");

    card.style.display = "block";
  }

  // === Display route map (Folium HTML) ===
  function displayRouteMap() {
    const card = document.getElementById("mapCard");
    const container = document.getElementById("mapContainer");

    if (!card || !container || !currentRoute) return;

    if (!currentRoute.folium_html) {
      container.innerHTML = `
        <div class="text-center text-muted py-5">
          <i class="bi bi-map display-4"></i>
          <p class="mt-3">No map available for this route</p>
        </div>
      `;
      card.style.display = "block";
      return;
    }

    // Render Folium HTML in iframe
    container.innerHTML = `
      <iframe
        srcdoc="${currentRoute.folium_html
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#39;")}"
        style="width: 100%; height: 500px; border: none;"
        title="Route Map"
      ></iframe>
    `;

    card.style.display = "block";
  }

  // === Print all routes for the job ===
  function printAllRoutes() {
    if (!currentJob || !currentJobRoutes || currentJobRoutes.length === 0) {
      toast("Please select a job with routes first", "warning");
      return;
    }

    console.log("Printing all routes for job:", currentJob.name);

    // Show custom modal instead of confirm dialog
    const modal = new bootstrap.Modal(
      document.getElementById("printOptionsModal")
    );
    modal.show();
  }

  // === Execute print action for all routes ===
  function executePrint() {
    if (!currentJob || !currentJobRoutes || currentJobRoutes.length === 0) {
      toast("No routes to print", "warning");
      return;
    }

    console.log("Executing print for all routes in job:", currentJob.name);

    // Remove existing print iframe if any
    const existingIframe = document.getElementById("printIframe");
    if (existingIframe) {
      existingIframe.remove();
    }

    // Create hidden iframe for printing
    const iframe = document.createElement("iframe");
    iframe.id = "printIframe";
    iframe.style.position = "absolute";
    iframe.style.width = "0";
    iframe.style.height = "0";
    iframe.style.border = "none";
    document.body.appendChild(iframe);

    // Build print content
    const printContent = `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="UTF-8">
        <title>All Routes - ${currentJob.name}</title>
        <style>
          @page {
            size: A4;
            margin: 20mm;
          }
          * {
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
            color-adjust: exact !important;
          }
          body {
            font-family: Arial, Helvetica, sans-serif;
            margin: 0;
            padding: 20px;
            color: #333;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
          }
          .header {
            border-bottom: 3px solid #333;
            padding-bottom: 10px;
            margin-bottom: 30px;
          }
          .header h1 {
            margin: 0 0 5px 0;
            font-size: 26px;
            font-weight: bold;
          }
          .header p {
            margin: 3px 0;
            color: #666;
            font-size: 14px;
          }
          .route-section {
            page-break-inside: avoid;
            margin-bottom: 40px;
            border: 2px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            background: #fafafa;
          }
          .route-title {
            font-size: 20px;
            font-weight: bold;
            color: #0d6efd;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #0d6efd;
          }
          .route-info {
            background: #fff;
            padding: 15px;
            margin-bottom: 20px;
            border-radius: 5px;
            border: 1px solid #ddd;
          }
          .route-info p {
            margin: 5px 0;
            line-height: 1.4;
          }
          .route-info strong {
            display: inline-block;
            width: 150px;
            font-weight: bold;
          }
          table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            background: white;
          }
          th {
            background: #333;
            color: white;
            padding: 10px;
            text-align: left;
            font-weight: bold;
          }
          td {
            padding: 8px 10px;
            border-bottom: 1px solid #ddd;
            font-size: 13px;
          }
          tr:nth-child(even) {
            background: #f9f9f9;
          }
          .footer {
            margin-top: 30px;
            padding-top: 10px;
            border-top: 1px solid #ccc;
            text-align: center;
            font-size: 12px;
            color: #666;
          }
          .page-break {
            page-break-after: always;
          }
          @media print {
            body {
              padding: 0;
            }
            .no-print {
              display: none;
            }
            * {
              -webkit-print-color-adjust: exact !important;
              print-color-adjust: exact !important;
            }
          }
        </style>
      </head>
      <body>
        <div class="header">
          <h1>Vehicle Routes Plan</h1>
          <p><strong>Job:</strong> ${currentJob.name}</p>
          <p><strong>Date:</strong> ${currentJob.day}</p>
          <p><strong>Total Routes:</strong> ${currentJobRoutes.length}</p>
          <p><strong>Total Orders:</strong> ${currentJobRoutes.reduce(
            (sum, r) => sum + r.stops.length,
            0
          )}</p>
        </div>

        ${currentJobRoutes
          .map(
            (route, index) => `
          <div class="route-section ${
            index < currentJobRoutes.length - 1 ? "page-break" : ""
          }">
            <div class="route-title">
              Route ${index + 1}: ${route.vehicle_name}
            </div>

            <div class="route-info">
              <p><strong>Vehicle:</strong> ${route.vehicle_name}</p>
              <p><strong>Total Orders:</strong> ${route.stops.length}</p>
              ${
                route.total_distance
                  ? `<p><strong>Total Distance:</strong> ${route.total_distance.toFixed(
                      2
                    )} km</p>`
                  : ""
              }
              ${
                route.total_time
                  ? `<p><strong>Total Time:</strong> ${route.total_time.toFixed(
                      0
                    )} minutes</p>`
                  : ""
              }
            </div>

            <table>
              <thead>
                <tr>
                  <th style="width: 80px;">Sequence</th>
                  <th>Shop Code</th>
                  <th>Order ID</th>
                  <th>Location</th>
                  <th>Address</th>
                </tr>
              </thead>
              <tbody>
                ${route.stops
                  .map(
                    (stop) => `
                  <tr>
                    <td style="text-align: center;"><strong>${
                      stop.sequence
                    }</strong></td>
                    <td>${stop.shop_code}</td>
                    <td>${stop.order_id || "-"}</td>
                    <td>${stop.shop_location || "-"}</td>
                    <td>${stop.shop_address || "-"}</td>
                  </tr>
                `
                  )
                  .join("")}
              </tbody>
            </table>
          </div>
        `
          )
          .join("")}

        <div class="footer">
          <p>Generated on ${new Date().toLocaleString()} | Delivery Management System</p>
        </div>
      </body>
      </html>
    `;

    // Write content to iframe and print
    const iframeDoc = iframe.contentWindow.document;
    iframeDoc.open();
    iframeDoc.write(printContent);
    iframeDoc.close();

    // Wait for content to load, then print
    iframe.contentWindow.onload = function () {
      iframe.contentWindow.focus();
      iframe.contentWindow.print();

      // Remove iframe after printing (with delay to allow print dialog to open)
      setTimeout(() => {
        iframe.remove();
      }, 1000);
    };
  }

  // Expose loadJobDetails globally for navigation from other tabs
  window.loadVisualizationJob = loadJobDetails;

  // End of IIFE
})();

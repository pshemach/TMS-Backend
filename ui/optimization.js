/* ==================== OPTIMIZATION MANAGEMENT ==================== */

(function () {
  "use strict";

  console.log("Optimization.js loaded");

  // Helper function for toast (use global if available, otherwise fallback)
  const toast =
    window.showToast ||
    function (msg, type) {
      console.log(`[${type}] ${msg}`);
      alert(msg);
    };

  // Global state
  window.optimizationOrders = []; // Synced with processedOrders
  let allVehiclesForOptimization = [];
  let allPredefinedRoutes = [];
  let allDepotsForOptimization = [];
  let selectedVehiclesForOptimization = new Map(); // vehicle_id => { selected: bool, route_id: null|int }

  // Load vehicles when optimization tab is opened
  document.addEventListener("DOMContentLoaded", () => {
    console.log("DOMContentLoaded - Setting up optimization tab");
    const optimizationTab = document.getElementById("optimization-tab");

    if (optimizationTab) {
      console.log("Found optimization tab button");
      optimizationTab.addEventListener("shown.bs.tab", async () => {
        console.log("Optimization tab activated");
        await loadOptimizationData();
      });
    } else {
      console.error("Optimization tab button not found!");
    }

    // Check if optimization tab is already active on page load
    const optimizationPane = document.getElementById("optimization");
    if (optimizationPane?.classList.contains("active")) {
      console.log("Optimization tab already active on load");
      loadOptimizationData();
    }

    // Set default date to today
    const dateInput = document.getElementById("optimizationDate");
    if (dateInput) {
      dateInput.valueAsDate = new Date();
    } else {
      console.warn("optimizationDate input not found");
    }

    // Refresh orders button
    const refreshBtn = document.getElementById("refreshOptimizationOrders");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", () => {
        console.log("Manual refresh clicked");
        syncOptimizationOrders();
        toast("Orders refreshed", "success");
      });
    }

    // Clear orders button
    const clearBtn = document.getElementById("clearOptimizationOrders");
    if (clearBtn) {
      clearBtn.addEventListener("click", () => {
        if (
          confirm(
            "Clear all orders for optimization? This will remove all orders from both Order Constraint Management and Optimization Management."
          )
        ) {
          // Use the shared clear function if available
          if (typeof window.clearAllOrders === "function") {
            window.clearAllOrders();
          } else {
            // Fallback if function not available yet
            window.optimizationOrders = [];
            window.processedOrders = [];
            renderOptimizationOrders();

            if (typeof window.renderProcessedOrders === "function") {
              window.renderProcessedOrders();
            }
          }

          toast(
            "All orders cleared successfully from both sections",
            "success"
          );
        }
      });
    }
  });

  // Load vehicles and routes
  async function loadOptimizationData() {
    console.log("loadOptimizationData called");
    try {
      console.log("Fetching vehicles, routes, and depots...");
      const [vehiclesRes, routesRes, depotsRes] = await Promise.all([
        fetch(TMS_API.url("/vehicle")),
        fetch(TMS_API.url("/predefined-route")),
        fetch(TMS_API.url("/location/depot")),
      ]);

      console.log("Vehicle response status:", vehiclesRes.status);
      console.log("Routes response status:", routesRes.status);
      console.log("Depots response status:", depotsRes.status);

      if (!vehiclesRes.ok || !routesRes.ok || !depotsRes.ok)
        throw new Error("Failed to load data");

      allVehiclesForOptimization = await vehiclesRes.json();
      allPredefinedRoutes = await routesRes.json();
      allDepotsForOptimization = await depotsRes.json();

      console.log("Loaded vehicles:", allVehiclesForOptimization.length);
      console.log("Loaded routes:", allPredefinedRoutes.length);
      console.log("Loaded depots:", allDepotsForOptimization.length);

      renderVehiclesForOptimization();
      renderDepotsForOptimization();
      syncOptimizationOrders();
      renderOptimizationOrders();
    } catch (err) {
      console.error("Error loading optimization data:", err);
      toast("Failed to load optimization data: " + err.message, "danger");
    }
  }

  // Populate depot dropdown in optimization controls
  function renderDepotsForOptimization() {
    const depotSelect = document.getElementById("optimizationDepotSelect");
    if (!depotSelect) return;
    const options = ['<option value="">Select Depot</option>']
      .concat(
        allDepotsForOptimization.map(
          (d) =>
            `<option value="${d.id}">${d.depot_code} — ${d.location}</option>`
        )
      )
      .join("");
    depotSelect.innerHTML = options;
    // Auto-select first depot if available and none selected
    if (!depotSelect.value && allDepotsForOptimization.length > 0) {
      depotSelect.value = String(allDepotsForOptimization[0].id);
    }
  }

  // Render vehicles table with checkboxes and route dropdowns
  function renderVehiclesForOptimization() {
    console.log("renderVehiclesForOptimization called");
    const tbody = document.querySelector("#optimizationVehiclesTable tbody");
    const noData = document.getElementById("noVehiclesForOptimization");
    const searchInput = document.getElementById("optimizationVehicleSearch");

    // Helper: routes currently assigned to any vehicle
    const assignedRoutes = new Set(
      Array.from(selectedVehiclesForOptimization.values())
        .map((v) => v.route_id)
        .filter((rid) => rid != null)
    );

    console.log("tbody element:", tbody);
    console.log("noData element:", noData);
    console.log("Vehicles to render:", allVehiclesForOptimization.length);

    if (!tbody) {
      console.error("Vehicle table tbody not found!");
      return;
    }

    if (!allVehiclesForOptimization.length) {
      console.log("No vehicles, showing no data message");
      if (noData) noData.style.display = "block";
      tbody.innerHTML = "";
      return;
    }

    if (noData) noData.style.display = "none";

    // Get search filter
    const searchTerm = searchInput?.value.toLowerCase() || "";
    const filtered = allVehiclesForOptimization.filter((v) => {
      const name = (v.vehicle_name || "").toLowerCase();
      const type = (v.type || "").toLowerCase();
      return name.includes(searchTerm) || type.includes(searchTerm);
    });

    tbody.innerHTML = filtered
      .map((vehicle) => {
        const isSelected =
          selectedVehiclesForOptimization.get(vehicle.id)?.selected || false;
        const routeId =
          selectedVehiclesForOptimization.get(vehicle.id)?.route_id || null;

        const routeOptions = allPredefinedRoutes
          .map((r) => {
            const isAssignedElsewhere =
              assignedRoutes.has(r.id) && routeId !== r.id;
            const label = `${r.name}${
              isAssignedElsewhere ? " (assigned)" : ""
            }`;
            return `<option value="${r.id}" ${
              routeId === r.id ? "selected" : ""
            } ${isAssignedElsewhere ? "disabled" : ""}>${label}</option>`;
          })
          .join("");

        return `
        <tr>
          <td>
            <input
              type="checkbox"
              class="form-check-input vehicle-checkbox"
              data-vehicle-id="${vehicle.id}"
              ${isSelected ? "checked" : ""}
            >
          </td>
          <td>${vehicle.vehicle_name}</td>
          <td>${vehicle.type}</td>
          <td>
            <select
              class="form-select form-select-sm route-select"
              data-vehicle-id="${vehicle.id}"
              ${!isSelected ? "disabled" : ""}
            >
              <option value="">None</option>
              ${routeOptions}
            </select>
          </td>
        </tr>
      `;
      })
      .join("");

    // Attach event listeners
    attachVehicleListeners();
    updateOptimizationButton();
  }

  // Attach event listeners to checkboxes and dropdowns
  function attachVehicleListeners() {
    // Vehicle checkboxes
    document.querySelectorAll(".vehicle-checkbox").forEach((cb) => {
      cb.addEventListener("change", (e) => {
        const vehicleId = parseInt(e.target.dataset.vehicleId);
        const isChecked = e.target.checked;

        if (isChecked) {
          selectedVehiclesForOptimization.set(vehicleId, {
            selected: true,
            route_id: null,
          });
        } else {
          selectedVehiclesForOptimization.delete(vehicleId);
        }

        // Enable/disable route dropdown
        const routeSelect = document.querySelector(
          `.route-select[data-vehicle-id="${vehicleId}"]`
        );
        if (routeSelect) {
          routeSelect.disabled = !isChecked;
          if (!isChecked) routeSelect.value = "";
        }

        // Re-render to update disabled route options across all vehicles
        renderVehiclesForOptimization();
      });
    });

    // Route dropdowns
    document.querySelectorAll(".route-select").forEach((select) => {
      select.addEventListener("change", (e) => {
        const vehicleId = parseInt(e.target.dataset.vehicleId);
        const routeId = e.target.value ? parseInt(e.target.value) : null;

        const vehicleData = selectedVehiclesForOptimization.get(vehicleId);
        if (vehicleData) {
          vehicleData.route_id = routeId;
        }
        // Re-render to reflect unique route assignment disabling
        renderVehiclesForOptimization();
      });
    });

    // Select all vehicles
    const selectAllCheckbox = document.getElementById("selectAllVehicles");
    if (selectAllCheckbox) {
      selectAllCheckbox.addEventListener("change", (e) => {
        const isChecked = e.target.checked;
        document.querySelectorAll(".vehicle-checkbox").forEach((cb) => {
          cb.checked = isChecked;
          const vehicleId = parseInt(cb.dataset.vehicleId);

          if (isChecked) {
            selectedVehiclesForOptimization.set(vehicleId, {
              selected: true,
              route_id: null,
            });
          } else {
            selectedVehiclesForOptimization.delete(vehicleId);
          }

          const routeSelect = document.querySelector(
            `.route-select[data-vehicle-id="${vehicleId}"]`
          );
          if (routeSelect) {
            routeSelect.disabled = !isChecked;
          }
        });
        // Re-render to update disabled route options across all vehicles
        renderVehiclesForOptimization();
      });
    }

    // Search filter
    const searchInput = document.getElementById("optimizationVehicleSearch");
    if (searchInput) {
      searchInput.addEventListener("input", renderVehiclesForOptimization);
    }
  }

  // Sync optimization orders from processedOrders
  function syncOptimizationOrders() {
    console.log("syncOptimizationOrders called");
    console.log("window.processedOrders:", window.processedOrders);

    // Get orders from constraint tab
    window.optimizationOrders = [...(window.processedOrders || [])];

    console.log(
      "Synced optimizationOrders count:",
      window.optimizationOrders.length
    );

    renderOptimizationOrders();
    updateOptimizationButton();
  }

  // Render orders table
  function renderOptimizationOrders() {
    console.log("renderOptimizationOrders called");
    const tbody = document.querySelector("#optimizationOrdersTable tbody");
    const noData = document.getElementById("noOrdersForOptimization");
    const countBadge = document.getElementById("optimizationOrderCount");

    console.log("Orders tbody:", tbody);
    console.log("Orders to render:", window.optimizationOrders?.length);

    if (!tbody) {
      console.error("Orders table tbody not found!");
      return;
    }

    if (!window.optimizationOrders.length) {
      console.log("No orders, showing no data message");
      if (noData) noData.style.display = "block";
      tbody.innerHTML = "";
      if (countBadge) countBadge.textContent = "0 orders";
      return;
    }

    if (noData) noData.style.display = "none";
    if (countBadge)
      countBadge.textContent = `${window.optimizationOrders.length} orders`;

    tbody.innerHTML = window.optimizationOrders
      .map(
        (order) => `
      <tr>
        <td><strong>${order.order_id}</strong></td>
        <td>${order.shop?.shop_code || "-"}</td>
        <td>${order.shop?.location || "-"}</td>
        <td>${order.shop?.brand || "-"}</td>
        <td>${order.po_value?.toFixed(2) || "-"}</td>
        <td>
          <span class="badge bg-${
            order.priority === "high"
              ? "danger"
              : order.priority === "medium"
              ? "warning"
              : "secondary"
          }">
            ${order.priority || "none"}
          </span>
        </td>
      </tr>
    `
      )
      .join("");
  }

  // Update Run Optimization button state
  function updateOptimizationButton() {
    const btn = document.getElementById("runOptimizationBtn");
    const hasVehicles = selectedVehiclesForOptimization.size > 0;
    const hasOrders = window.optimizationOrders.length > 0;

    if (btn) {
      btn.disabled = !hasVehicles || !hasOrders;
    }
  }

  // Run optimization
  document
    .getElementById("runOptimizationBtn")
    ?.addEventListener("click", async () => {
      const btn = document.getElementById("runOptimizationBtn");
      const dateInput = document.getElementById("optimizationDate");
      // use_time_windows removed from UI; backend handles it
      const depotSelect = document.getElementById("optimizationDepotSelect");
      const depotId =
        depotSelect && depotSelect.value ? parseInt(depotSelect.value) : null;

      // Prepare payload
      const vehicles = Array.from(
        selectedVehiclesForOptimization.entries()
      ).map(([vehicle_id, data]) => ({
        vehicle_id,
        predefined_route_id: data.route_id,
      }));

      const selectedOrderIds = window.optimizationOrders.map((o) => o.id);

      const payload = {
        day: dateInput.value || null,
        vehicles,
        selected_orders: selectedOrderIds,
        // use_time_windows removed; backend default will be applied
        depot_id: depotId,
      };

      console.log("Running optimization with payload:", payload);

      try {
        btn.disabled = true;
        btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Running...';

        const res = await fetch(TMS_API.url("/optimize"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          const error = await res.json();
          throw new Error(error.detail || "Optimization failed");
        }

        const result = await res.json();
        toast(`Optimization completed! Job ID: ${result.job_id}`, "success");

        console.log("Optimization result:", result);

        // Navigate to Visualization tab and load the job
        navigateToVisualization(result.job_id);
      } catch (err) {
        toast("Optimization failed: " + err.message, "danger");
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-play-fill"></i> Run Optimization';
      }
    });

  // Helper function to navigate to Visualization tab and select job
  function navigateToVisualization(jobId) {
    console.log("Navigating to Visualization tab for job:", jobId);

    // Switch to Visualization tab
    const visualizationTab = document.getElementById("visualization-tab");
    if (visualizationTab) {
      const tab = new bootstrap.Tab(visualizationTab);
      tab.show();

      // Store the job ID to load after tab is shown
      window.pendingJobId = jobId;

      // Wait a moment for the tab to fully load, then trigger job selection
      setTimeout(() => {
        if (typeof window.loadVisualizationJob === "function") {
          window.loadVisualizationJob(jobId);
        }
      }, 500);
    }
  }

  // Listen for changes in processedOrders (from constraint tab)
  // This ensures optimization orders stay in sync
  if (typeof window.renderProcessedOrders !== "undefined") {
    const originalRender = window.renderProcessedOrders;
    window.renderProcessedOrders = function () {
      originalRender();
      syncOptimizationOrders();
    };
  }

  // Expose renderOptimizationOrders globally so it can be called from other modules
  window.renderOptimizationOrders = renderOptimizationOrders;
})(); // End of IIFE

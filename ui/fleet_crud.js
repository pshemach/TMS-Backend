// fleet_crud.js
// Basic fleet + vehicle CRUD for frontend
const FLEET_API_BASE = TMS_API.url("/fleet");
const VEHICLE_API_BASE = TMS_API.url("/vehicle");

let fleets = [];
let vehicles = [];
let selectedFleetId = null;

// Constraint API base
const VEHICLE_CONSTRAINT_API = TMS_API.url("/vehicle-constraint");

// DOM refs
const fleetsTableBody = document.querySelector("#fleetsTable tbody");
const vehiclesTableBody = document.querySelector("#vehiclesTable tbody");
const vehicleConstraintsTableBody = document.querySelector(
  "#vehicleConstraintsTable tbody"
);
const noFleets = document.getElementById("noFleets");
const noVehicles = document.getElementById("noVehicles");
const fleetSearchInput = document.getElementById("fleetSearchInput");
const vehicleSearchInput = document.getElementById("vehicleSearchInput");

// vehicle constraint modal refs
const vehicleConstraintForm = document.getElementById("vehicleConstraintForm");

// Helper to show toast if showToast exists
function toast(msg, type = "info") {
  if (typeof showToast === "function") return showToast(msg, type);
  console.log(type.toUpperCase() + ": " + msg);
}

async function loadFleets() {
  try {
    const res = await fetch(FLEET_API_BASE + "/", { cache: "no-store" });
    if (!res.ok) throw new Error("Failed to load fleets");
    fleets = await res.json();
    renderFleets(fleets);
    populateFleetSelect();
  } catch (err) {
    toast(err.message, "danger");
  }
}

function renderFleets(list) {
  if (!list || list.length === 0) {
    fleetsTableBody.innerHTML = "";
    noFleets.classList.remove("d-none");
    return;
  }
  noFleets.classList.add("d-none");
  fleetsTableBody.innerHTML = list
    .map(
      (f) => `
    <tr data-id="${f.id}">
      <td><strong>${f.id}</strong></td>
      <td>${f.fleet_name || f.name || "-"}</td>
      <td>${f.type || "-"}</td>
      <td>${f.region || "-"}</td>
      <td>${f.manager || "-"}</td>
      <td>${f.status || "-"}</td>
      <td>
        <button class="btn btn-sm btn-outline-primary me-1" onclick="editFleet(${
          f.id
        })" title="Edit"><i class="bi bi-pencil"></i></button>
        <button class="btn btn-sm btn-outline-secondary me-1" onclick="selectFleet(${
          f.id
        })" title="Select"><i class="bi bi-check2-square"></i></button>
        <button class="btn btn-sm btn-outline-danger" onclick="deleteFleet(${
          f.id
        })" title="Delete"><i class="bi bi-trash"></i></button>
      </td>
    </tr>
  `
    )
    .join("");
}

function populateFleetSelect() {
  const sel = document.getElementById("vehicleFleetSelect");
  if (!sel) return;
  sel.innerHTML = fleets
    .map(
      (f) =>
        `<option value="${f.id}">${
          f.fleet_name || f.name || "Fleet " + f.id
        }</option>`
    )
    .join("");
  const vf = document.getElementById("vehicleFleetFilter");
  if (vf) {
    const options = ['<option value="">All Fleets</option>'].concat(
      fleets.map(
        (f) =>
          `<option value="${f.id}">${
            f.fleet_name || f.name || "Fleet " + f.id
          }</option>`
      )
    );
    vf.innerHTML = options.join("");
    if (selectedFleetId) vf.value = selectedFleetId;
  }
}

function selectFleet(id) {
  selectedFleetId = id;
  document
    .querySelectorAll("#fleetsTable tbody tr")
    .forEach((r) => r.classList.remove("table-active"));
  const row = document.querySelector(`#fleetsTable tbody tr[data-id='${id}']`);
  if (row) row.classList.add("table-active");
  const vf = document.getElementById("vehicleFleetFilter");
  if (vf) vf.value = id;
  loadVehicles(id);
}

async function loadVehicles(fleet_id = null) {
  try {
    let url = VEHICLE_API_BASE + "/";
    if (fleet_id) url += `?fleet_id=${fleet_id}`;
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error("Failed to load vehicles");
    vehicles = await res.json();
    applyVehicleFilters();
  } catch (err) {
    toast(err.message, "danger");
  }
}

function applyVehicleFilters() {
  const statusVal = (
    document.getElementById("vehicleStatusFilter")?.value || ""
  ).toLowerCase();
  const q = (document.getElementById("vehicleSearchInput")?.value || "")
    .trim()
    .toLowerCase();
  let filtered = vehicles || [];
  if (statusVal)
    filtered = filtered.filter(
      (v) => (v.status || "").toLowerCase() === statusVal
    );
  if (q)
    filtered = filtered.filter((v) =>
      (
        (v.vehicle_name || v.name || "") +
        " " +
        (v.type || "") +
        " " +
        (v.location || "")
      )
        .toLowerCase()
        .includes(q)
    );
  renderVehicles(filtered);
  // also refresh constraints view (showing current state)
  renderVehicleConstraints(vehicles);
}

function renderVehicles(list) {
  if (!list || list.length === 0) {
    vehiclesTableBody.innerHTML = "";
    noVehicles.classList.remove("d-none");
    return;
  }
  noVehicles.classList.add("d-none");
  vehiclesTableBody.innerHTML = list
    .map(
      (v) => `
    <tr data-id="${v.id}">
      <td><strong>${v.id}</strong></td>
      <td>${v.vehicle_name || v.name || "-"}</td>
      <td>${v.type || "-"}</td>
      <td>${v.location || "-"}</td>
      <td>${v.status || "-"}</td>
      <td>
        <button class="btn btn-sm btn-outline-primary me-1" onclick="editVehicle(${
          v.id
        })" title="Edit"><i class="bi bi-pencil"></i></button>
        <button class="btn btn-sm btn-outline-danger" onclick="deleteVehicle(${
          v.id
        })" title="Delete"><i class="bi bi-trash"></i></button>
      </td>
    </tr>
  `
    )
    .join("");
}

function renderVehicleConstraints(list) {
  if (!vehicleConstraintsTableBody) return;
  if (!list || list.length === 0) {
    vehicleConstraintsTableBody.innerHTML = "";
    const el = document.getElementById("noVehicleConstraints");
    if (el) el.classList.remove("d-none");
    return;
  }
  const el = document.getElementById("noVehicleConstraints");
  if (el) el.classList.add("d-none");
  vehicleConstraintsTableBody.innerHTML = list
    .map((v) => {
      const c = v.constraint || {};
      return `
      <tr data-id="${v.id}">
        <td>${v.vehicle_name || v.name || "-"}</td>
        <td>${c.fleet || v.fleet_name || "-"}</td>
        <td>${v.type || "-"}</td>
        <td>${c.payload ?? "-"}</td>
        <td>${c.volume ?? "-"}</td>
        <td>${c.days ?? "-"}</td>
        <td>${c.time_window ?? "-"}</td>
        <td>${c.max_distance ?? "-"}</td>
        <td>${c.max_visits ?? "-"}</td>
        <td>
          <button class="btn btn-sm btn-outline-primary" onclick="openVehicleConstraintModal(${
            v.id
          })" title="Edit Constraint"><i class="bi bi-pencil"></i></button>
        </td>
      </tr>
    `;
    })
    .join("");
}

function openVehicleConstraintModal(vehicleId) {
  const v = (vehicles || []).find((x) => Number(x.id) === Number(vehicleId));
  if (!v) return toast("Vehicle not found", "danger");
  const c = v.constraint || {};
  document.getElementById("constraintVehicleId").value = v.id;
  document.getElementById("constraintDays").value = c.days ?? "";
  document.getElementById("constraintPayload").value = c.payload ?? "";
  document.getElementById("constraintVolume").value = c.volume ?? "";
  document.getElementById("constraintTimeWindow").value = c.time_window ?? "";
  document.getElementById("constraintMaxDistance").value = c.max_distance ?? "";
  document.getElementById("constraintMaxVisits").value = c.max_visits ?? "";
  document.getElementById(
    "vehicleConstraintModalTitle"
  ).textContent = `Edit Constraint - ${v.vehicle_name || v.name || v.id}`;
  new bootstrap.Modal(document.getElementById("vehicleConstraintModal")).show();
}

async function submitVehicleConstraintForm(e) {
  e.preventDefault();
  try {
    const vehicleId = document.getElementById("constraintVehicleId").value;
    if (!vehicleId) throw new Error("Vehicle id missing");
    const payload = {};
    const days = document.getElementById("constraintDays").value;
    const payloadVal = document.getElementById("constraintPayload").value;
    const volumeVal = document.getElementById("constraintVolume").value;
    const tw = document.getElementById("constraintTimeWindow").value.trim();
    const maxDistanceVal = document.getElementById(
      "constraintMaxDistance"
    ).value;
    const maxVisitsVal = document.getElementById("constraintMaxVisits").value;
    if (days !== "") payload.days = Number(days);
    if (payloadVal !== "") payload.payload = Number(payloadVal);
    if (volumeVal !== "") payload.volume = Number(volumeVal);
    if (tw) payload.time_window = tw;
    if (maxDistanceVal !== "") payload.max_distance = Number(maxDistanceVal);
    if (maxVisitsVal !== "") payload.max_visits = Number(maxVisitsVal);

    const res = await fetch(`${VEHICLE_CONSTRAINT_API}/${vehicleId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || "Constraint update failed");
    }
    const updated = await res.json();
    // update local vehicle entry
    vehicles = (vehicles || []).map((v) => {
      if (Number(v.id) === Number(vehicleId)) {
        return { ...v, constraint: updated };
      }
      return v;
    });
    applyVehicleFilters();
    renderVehicleConstraints(vehicles);
    toast("Constraint updated", "success");
    bootstrap.Modal.getInstance(
      document.getElementById("vehicleConstraintModal")
    ).hide();
  } catch (err) {
    toast(err.message, "danger");
  }
}

async function submitFleetForm(e) {
  e.preventDefault();
  try {
    const id = document.getElementById("fleetId").value;
    const fleet_name = document.getElementById("fleetName").value.trim();
    const type = document.getElementById("fleetType").value.trim();
    const region = document.getElementById("fleetRegion").value.trim();
    const manager = document.getElementById("fleetManager").value.trim();
    const status = document.getElementById("fleetStatus").value;
    if (!fleet_name) throw new Error("Fleet name is required");
    const payload = { fleet_name, type, region, manager, status };
    let res;
    if (id) {
      res = await fetch(`${FLEET_API_BASE}/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } else {
      res = await fetch(`${FLEET_API_BASE}/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    }
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || "Fleet save failed");
    }
    toast("Fleet saved", "success");
    bootstrap.Modal.getInstance(document.getElementById("fleetModal")).hide();
    document.getElementById("fleetForm").reset();
    await loadFleets();
  } catch (err) {
    toast(err.message, "danger");
  }
}

async function editFleet(id) {
  try {
    const res = await fetch(`${FLEET_API_BASE}/${id}`);
    if (!res.ok) throw new Error("Fleet not found");
    const f = await res.json();
    document.getElementById("fleetId").value = f.id;
    document.getElementById("fleetName").value = f.fleet_name || f.name || "";
    document.getElementById("fleetType").value = f.type || "";
    document.getElementById("fleetRegion").value = f.region || "";
    document.getElementById("fleetManager").value = f.manager || "";
    document.getElementById("fleetStatus").value = f.status || "active";
    document.getElementById("fleetModalTitle").textContent = "Edit Fleet";
    new bootstrap.Modal(document.getElementById("fleetModal")).show();
  } catch (err) {
    toast(err.message, "danger");
  }
}

// Delete Fleet
async function deleteFleet(id) {
  if (!confirm("Delete this fleet? All vehicles will also be deleted.")) return;

  try {
    const res = await fetch(`${FLEET_API_BASE}/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Delete failed");

    showToast("Fleet and all vehicles deleted!", "success");

    // === UI REFRESH FIX ===
    selectedFleetId = null; // Clear selection

    await loadFleets(); // Refresh fleets list

    // Clear active row highlight
    document
      .querySelectorAll("#fleetsTable tbody tr")
      .forEach((r) => r.classList.remove("table-active"));

    // Refresh vehicles list (show empty or all)
    await loadVehicles(); // null = show no filter

    // Reset filters
    const fleetFilter = document.getElementById("vehicleFleetFilter");
    if (fleetFilter) fleetFilter.value = "";
  } catch (err) {
    showToast(err.message, "danger");
  }
}

async function submitVehicleForm(e) {
  e.preventDefault();
  try {
    const id = document.getElementById("vehicleId").value;
    const fleet_id = Number(
      document.getElementById("vehicleFleetSelect").value
    );
    const vehicle_name = document.getElementById("vehicleName").value.trim();
    const type = document.getElementById("vehicleType").value.trim();
    const location = document.getElementById("vehicleLocation").value.trim();
    const status = document.getElementById("vehicleStatus").value;
    if (!fleet_id) throw new Error("Fleet must be selected");
    if (!vehicle_name) throw new Error("Vehicle name is required");
    const payload = {
      vehicle_name,
      type: type || undefined,
      location: location || undefined,
      status,
    };
    let res;
    if (id) {
      res = await fetch(`${VEHICLE_API_BASE}/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } else {
      res = await fetch(`${VEHICLE_API_BASE}/${fleet_id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    }
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || "Vehicle save failed");
    }
    toast("Vehicle saved", "success");
    bootstrap.Modal.getInstance(document.getElementById("vehicleModal")).hide();
    document.getElementById("vehicleForm").reset();
    if (selectedFleetId) loadVehicles(selectedFleetId);
    else loadVehicles();
  } catch (err) {
    toast(err.message, "danger");
  }
}

async function editVehicle(id) {
  try {
    const res = await fetch(`${VEHICLE_API_BASE}/${id}`);
    if (!res.ok) throw new Error("Vehicle not found");
    const v = await res.json();
    document.getElementById("vehicleId").value = v.id;
    document.getElementById("vehicleFleetSelect").value =
      v.fleet_id || v.fleet || "";
    document.getElementById("vehicleName").value =
      v.vehicle_name || v.name || "";
    document.getElementById("vehicleType").value = v.type || "";
    document.getElementById("vehicleLocation").value = v.location || "";
    document.getElementById("vehicleStatus").value = v.status || "active";
    document.getElementById("vehicleModalTitle").textContent = "Edit Vehicle";
    new bootstrap.Modal(document.getElementById("vehicleModal")).show();
  } catch (err) {
    toast(err.message, "danger");
  }
}

async function deleteVehicle(id) {
  if (!confirm("Delete this vehicle?")) return;
  try {
    const res = await fetch(`${VEHICLE_API_BASE}/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Delete failed");
    toast("Vehicle deleted", "success");
    // remove from local cache and re-render immediately
    vehicles = (vehicles || []).filter((v) => v.id !== id);
    applyVehicleFilters();
    // also refresh from server in background to keep in-sync
    if (selectedFleetId) loadVehicles(selectedFleetId);
    else loadVehicles();
  } catch (err) {
    toast(err.message, "danger");
  }
}

// Event listeners for filters
fleetSearchInput?.addEventListener("input", () => {
  const q = fleetSearchInput.value.trim().toLowerCase();
  const filtered = fleets.filter(
    (f) =>
      (f.fleet_name || f.name || "").toLowerCase().includes(q) ||
      (f.type || "").toLowerCase().includes(q) ||
      (f.region || "").toLowerCase().includes(q) ||
      (f.manager || "").toLowerCase().includes(q)
  );
  renderFleets(filtered);
});

vehicleSearchInput?.addEventListener("input", () => {
  applyVehicleFilters();
});

// Wire up forms and buttons on load
document.addEventListener("DOMContentLoaded", () => {
  // Forms
  const fleetForm = document.getElementById("fleetForm");
  if (fleetForm) fleetForm.addEventListener("submit", submitFleetForm);
  const vehicleForm = document.getElementById("vehicleForm");
  if (vehicleForm) vehicleForm.addEventListener("submit", submitVehicleForm);

  // Add Vehicle button
  const manageVehiclesBtn = document.getElementById("manageVehiclesBtn");
  if (manageVehiclesBtn) {
    manageVehiclesBtn.addEventListener("click", (e) => {
      e.preventDefault();
      const sel = document.getElementById("vehicleFleetSelect");
      if (sel) {
        if (selectedFleetId) sel.value = selectedFleetId;
        else if (sel.options.length > 0) sel.selectedIndex = 0;
      }
      document.getElementById("vehicleModalTitle").textContent = "Add Vehicle";
      new bootstrap.Modal(document.getElementById("vehicleModal")).show();
    });
  }

  // Filters
  const vehicleFleetFilter = document.getElementById("vehicleFleetFilter");
  const vehicleStatusFilter = document.getElementById("vehicleStatusFilter");
  if (vehicleFleetFilter)
    vehicleFleetFilter.addEventListener("change", () => {
      const fid = vehicleFleetFilter.value
        ? Number(vehicleFleetFilter.value)
        : null;
      if (fid) selectFleet(fid);
      else {
        selectedFleetId = null;
        loadVehicles(null);
      }
    });
  if (vehicleStatusFilter)
    vehicleStatusFilter.addEventListener("change", applyVehicleFilters);

  // vehicle constraint form
  const vcf = document.getElementById("vehicleConstraintForm");
  if (vcf) vcf.addEventListener("submit", submitVehicleConstraintForm);

  // Initial data load
  loadFleets();
  loadVehicles();
});

// Expose functions for onclick handlers
window.editFleet = editFleet;
window.deleteFleet = deleteFleet;
window.selectFleet = selectFleet;
window.editVehicle = editVehicle;
window.deleteVehicle = deleteVehicle;
window.openVehicleConstraintModal = openVehicleConstraintModal;

// depot_crud.js
// Relies on global API_BASE and showToast defined in customer_crud.js
let allDepots = [];

// DOM Elements
const depotTableBody = document.querySelector("#depotsTable tbody");
const noDepotData = document.getElementById("noDepotData");
const depotSearchInput = document.getElementById("depotSearchInput");
const depotDistrictFilter = document.getElementById("depotDistrictFilter");
const depotForm = document.getElementById("depotForm");

// Fetch all depots
async function loadDepots() {
  try {
    const res = await fetch(`${API_BASE}/depot`, {
      method: "GET",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
    });
    if (!res.ok) throw new Error("Failed to fetch depots");
    allDepots = await res.json();
    populateDepotFilters();
    renderDepotTable(allDepots);
  } catch (err) {
    console.error("Error loading depots:", err);
    if (typeof showToast === "function")
      showToast(`Failed to load depots: ${err.message}`, "danger");
  }
}

function populateDepotFilters() {
  const districts = [...new Set(allDepots.map((d) => d.district))].sort();
  depotDistrictFilter.innerHTML =
    '<option value="">All Districts</option>' +
    districts.map((d) => `<option value="${d}">${d}</option>`).join("");
}

function renderDepotTable(depots) {
  if (!depots || depots.length === 0) {
    depotTableBody.innerHTML = "";
    noDepotData.classList.remove("d-none");
    return;
  }
  noDepotData.classList.add("d-none");
  depotTableBody.innerHTML = depots
    .map(
      (depot) => `
      <tr>
        <td><strong>${depot.depot_code}</strong></td>
        <td>${depot.location}</td>
        <td>${depot.address || "-"}</td>
        <td>${depot.district}</td>
        <td><small>${Number(depot.latitude).toFixed(6)}, ${Number(
        depot.longitude
      ).toFixed(6)}</small></td>
        <td>
          <span class="badge bg-${
            depot.matrix_status === "updated" ? "success" : "warning"
          }">
            ${depot.matrix_status || "pending"}
          </span>
        </td>
        <td>
          <button class="btn btn-sm btn-outline-primary me-1" onclick="editDepot(${
            depot.id
          })" title="Edit">
            <i class="bi bi-pencil"></i>
          </button>
          <button class="btn btn-sm btn-outline-danger" onclick="deleteDepot(${
            depot.id
          })" title="Delete">
            <i class="bi bi-trash"></i>
          </button>
        </td>
      </tr>
    `
    )
    .join("");
}

function applyDepotFilters() {
  let filtered = allDepots;
  const search = depotSearchInput.value.trim().toLowerCase();
  if (search) {
    filtered = filtered.filter(
      (d) =>
        (d.depot_code || "").toLowerCase().includes(search) ||
        (d.location || "").toLowerCase().includes(search)
    );
  }
  const district = depotDistrictFilter.value;
  if (district) filtered = filtered.filter((d) => d.district === district);
  renderDepotTable(filtered);
}

// Create / Update Depot
if (depotForm) {
  depotForm.onsubmit = async (e) => {
    e.preventDefault();
    const id = document.getElementById("depotId").value;
    const data = {
      depot_code: document.getElementById("depotCode").value.trim(),
      location: document.getElementById("depotLocation").value.trim(),
      address: document.getElementById("depotAddress").value.trim(),
      district: document.getElementById("depotDistrict").value.trim(),
      latitude: parseFloat(document.getElementById("depotLatitude").value),
      longitude: parseFloat(document.getElementById("depotLongitude").value),
    };

    try {
      const method = id ? "PUT" : "POST";
      const url = id ? `${API_BASE}/depot/${id}` : `${API_BASE}/depot`;
      const res = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(data),
      });
      if (!res.ok) {
        const err = await res.text();
        throw new Error(err || "Failed to save depot");
      }
      await res.json();
      if (typeof showToast === "function")
        showToast(id ? "Depot updated!" : "Depot added!");
      bootstrap.Modal.getInstance(document.getElementById("depotModal")).hide();
      loadDepots();
    } catch (err) {
      if (typeof showToast === "function") showToast(err.message, "danger");
    }
  };
}

// Edit
window.editDepot = async (id) => {
  try {
    const res = await fetch(`${API_BASE}/depot/${id}`, {
      method: "GET",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
    });
    if (!res.ok) throw new Error("Depot not found");
    const depot = await res.json();

    document.getElementById("depotModalTitle").textContent = "Edit Depot";
    document.getElementById("depotId").value = depot.id;
    document.getElementById("depotCode").value = depot.depot_code;
    document.getElementById("depotLocation").value = depot.location;
    document.getElementById("depotAddress").value = depot.address || "";
    document.getElementById("depotDistrict").value = depot.district;
    document.getElementById("depotLatitude").value = depot.latitude;
    document.getElementById("depotLongitude").value = depot.longitude;

    new bootstrap.Modal(document.getElementById("depotModal")).show();
  } catch (err) {
    if (typeof showToast === "function") showToast(err.message, "danger");
  }
};

// Delete
window.deleteDepot = async (id) => {
  if (!confirm("Delete this depot?")) return;
  try {
    const res = await fetch(`${API_BASE}/depot/${id}`, {
      method: "DELETE",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
    });
    if (!res.ok) throw new Error("Failed to delete depot");
    if (typeof showToast === "function") showToast("Depot deleted!");
    loadDepots();
  } catch (err) {
    if (typeof showToast === "function") showToast(err.message, "danger");
  }
};

// Populate district dropdown in modal
function populateDepotDistrictDropdown() {
  const districtSelect = document.getElementById("depotDistrict");
  if (!districtSelect) return;
  // Use global sriLankanDistricts if available
  const districts =
    typeof sriLankanDistricts !== "undefined" &&
    Array.isArray(sriLankanDistricts)
      ? sriLankanDistricts
      : [
          "Ampara",
          "Anuradhapura",
          "Badulla",
          "Batticaloa",
          "Colombo",
          "Galle",
          "Gampaha",
          "Hambantota",
          "Jaffna",
          "Kalutara",
          "Kandy",
          "Kegalle",
          "Kilinochchi",
          "Kurunegala",
          "Mannar",
          "Matale",
          "Matara",
          "Monaragala",
          "Mullaitivu",
          "Nuwara Eliya",
          "Polonnaruwa",
          "Puttalam",
          "Ratnapura",
          "Trincomalee",
          "Vavuniya",
        ];
  districtSelect.innerHTML =
    '<option value="">Select District</option>' +
    districts.map((d) => `<option value="${d}">${d}</option>`).join("");
}

// Reset modal on hide
const depotModalEl = document.getElementById("depotModal");
if (depotModalEl) {
  depotModalEl.addEventListener("hidden.bs.modal", () => {
    depotForm.reset();
    document.getElementById("depotId").value = "";
    document.getElementById("depotModalTitle").textContent = "Add Depot";
  });
  depotModalEl.addEventListener("show.bs.modal", () => {
    populateDepotDistrictDropdown();
  });
}

// Event Listeners
if (depotSearchInput)
  depotSearchInput.addEventListener("input", applyDepotFilters);
if (depotDistrictFilter)
  depotDistrictFilter.addEventListener("change", applyDepotFilters);

// Init
document.addEventListener("DOMContentLoaded", () => {
  // Load depots when Shop tab is initially active
  const shopsTabPane = document.getElementById("shops");
  if (
    shopsTabPane &&
    shopsTabPane.classList.contains("show") &&
    shopsTabPane.classList.contains("active")
  ) {
    loadDepots();
  }
  // Also load when Shops tab is clicked (first time)
  const shopsTabBtn = document.getElementById("shops-tab");
  if (shopsTabBtn) {
    shopsTabBtn.addEventListener("shown.bs.tab", (e) => {
      // Only reload if we haven't loaded yet
      if (!allDepots || allDepots.length === 0) loadDepots();
    });
  }
});

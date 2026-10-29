// customer_crud.js
const API_BASE = TMS_API.url("/location");
let allShops = [];

// Sri Lankan Districts
const sriLankanDistricts = [
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

// DOM Elements
const tableBody = document.querySelector("#shopsTable tbody");
const noData = document.getElementById("noData");
const searchInput = document.getElementById("searchInput");
const brandFilter = document.getElementById("brandFilter");
const districtFilter = document.getElementById("districtFilter");
const shopForm = document.getElementById("shopForm");
const modalTitle = document.getElementById("modalTitle");
const submitBtn = document.getElementById("submitBtn");

// Toast
function showToast(message, type = "success") {
  const toast = document.createElement("div");
  toast.className = `toast align-items-center text-bg-${type} border-0`;
  toast.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">${message}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>
  `;
  document.querySelector(".toast-container").appendChild(toast);
  new bootstrap.Toast(toast).show();
  setTimeout(() => toast.remove(), 3000);
}

// Fetch all shops
async function loadShops() {
  try {
    console.log("Fetching shops from:", `${API_BASE}/customer`);
    const res = await fetch(`${API_BASE}/customer`, {
      method: "GET",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
    });
    console.log("Response status:", res.status);
    console.log("Response headers:", [...res.headers.entries()]);

    if (!res.ok) throw new Error("Failed to fetch shops");

    const data = await res.json();
    console.log("Received data:", data);

    allShops = data;
    populateFilters();
    renderTable(allShops);
  } catch (err) {
    console.error("Error loading shops:", err);
    showToast(`Failed to load customers: ${err.message}`, "danger");
  }
}

// Populate filter dropdowns
function populateFilters() {
  const brands = [...new Set(allShops.map((s) => s.brand))].sort();
  const districts = [...new Set(allShops.map((s) => s.district))].sort();

  brandFilter.innerHTML =
    '<option value="">All Brands</option>' +
    brands.map((b) => `<option value="${b}">${b}</option>`).join("");

  districtFilter.innerHTML =
    '<option value="">All Districts</option>' +
    districts.map((d) => `<option value="${d}">${d}</option>`).join("");
}

// Render table
function renderTable(shops) {
  console.log("Rendering shops:", shops);

  if (!shops || shops.length === 0) {
    console.log("No shops to display");
    tableBody.innerHTML = "";
    noData.classList.remove("d-none");
    return;
  }

  noData.classList.add("d-none");
  tableBody.innerHTML = shops
    .map(
      (shop) => `
    <tr>
      <td><strong>${shop.shop_code}</strong></td>
      <td>${shop.location}</td>
      <td>${shop.address || "-"}</td>
      <td><span class="badge bg-info">${shop.brand}</span></td>
      <td>${shop.district}</td>
      <td><small>${shop.latitude.toFixed(6)}, ${shop.longitude.toFixed(
        6
      )}</small></td>
      <td>
        <span class="badge bg-${
          shop.matrix_status === "updated" ? "success" : "warning"
        }">
          ${shop.matrix_status || "pending"}
        </span>
      </td>
      <td>
        <button class="btn btn-sm btn-outline-primary me-1" onclick="editShop(${
          shop.id
        })" title="Edit">
          <i class="bi bi-pencil"></i>
        </button>
        <button class="btn btn-sm btn-outline-danger" onclick="deleteShop(${
          shop.id
        })" title="Delete">
          <i class="bi bi-trash"></i>
        </button>
      </td>
    </tr>
  `
    )
    .join("");
}

// Filters
function applyFilters() {
  let filtered = allShops;

  const search = searchInput.value.trim().toLowerCase();
  if (search) {
    filtered = filtered.filter(
      (s) =>
        s.shop_code.toLowerCase().includes(search) ||
        s.location.toLowerCase().includes(search)
    );
  }

  const brand = brandFilter.value;
  if (brand) filtered = filtered.filter((s) => s.brand === brand);

  const district = districtFilter.value;
  if (district) filtered = filtered.filter((s) => s.district === district);

  renderTable(filtered);
}

// Add/Edit Customer
shopForm.onsubmit = async (e) => {
  e.preventDefault();
  const id = document.getElementById("shopId").value;
  const data = {
    shop_code: document.getElementById("shopCode").value.trim(),
    location: document.getElementById("location").value.trim(),
    address: document.getElementById("address").value.trim(),
    brand: document.getElementById("brand").value.trim(),
    district: document.getElementById("district").value.trim(),
    latitude: parseFloat(document.getElementById("latitude").value),
    longitude: parseFloat(document.getElementById("longitude").value),
  };

  try {
    const method = id ? "PUT" : "POST";
    const url = id ? `${API_BASE}/customer/${id}` : `${API_BASE}/customer`;
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
      throw new Error(err || "Failed to save");
    }

    const result = await res.json();
    showToast(id ? "Customer updated!" : "Customer added!");
    bootstrap.Modal.getInstance(document.getElementById("shopModal")).hide();
    loadShops();
  } catch (err) {
    showToast(err.message, "danger");
  }
};

// Edit
window.editShop = async (id) => {
  try {
    const res = await fetch(`${API_BASE}/customer/${id}`, {
      method: "GET",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
      },
      mode: "cors",
      credentials: "same-origin",
    });
    if (!res.ok) throw new Error("Customer not found");
    const shop = await res.json();

    document.getElementById("modalTitle").textContent = "Edit Customer";
    document.getElementById("shopId").value = shop.id;
    document.getElementById("shopCode").value = shop.shop_code;
    document.getElementById("location").value = shop.location;
    document.getElementById("address").value = shop.address || "";
    document.getElementById("brand").value = shop.brand;
    document.getElementById("district").value = shop.district;
    document.getElementById("latitude").value = shop.latitude;
    document.getElementById("longitude").value = shop.longitude;

    new bootstrap.Modal(document.getElementById("shopModal")).show();
  } catch (err) {
    showToast(err.message, "danger");
  }
};

// Delete
window.deleteShop = async (id) => {
  if (!confirm("Delete this customer?")) return;

  try {
    const res = await fetch(`${API_BASE}/customer/${id}`, {
      method: "DELETE",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
      },
      mode: "cors",
      credentials: "same-origin",
    });
    if (!res.ok) throw new Error("Failed to delete");
    showToast("Customer deleted!");
    loadShops();
  } catch (err) {
    showToast(err.message, "danger");
  }
};

// Populate district dropdown in modal
function populateDistrictDropdown() {
  const districtSelect = document.getElementById("district");
  districtSelect.innerHTML =
    '<option value="">Select District</option>' +
    sriLankanDistricts
      .map((district) => `<option value="${district}">${district}</option>`)
      .join("");
}

// Reset modal
document.getElementById("shopModal").addEventListener("hidden.bs.modal", () => {
  shopForm.reset();
  document.getElementById("shopId").value = "";
  document.getElementById("modalTitle").textContent = "Add Customer";
});

// Initialize district dropdown when modal opens
document.getElementById("shopModal").addEventListener("show.bs.modal", () => {
  populateDistrictDropdown();
});

// Event Listeners
searchInput.addEventListener("input", applyFilters);
brandFilter.addEventListener("change", applyFilters);
districtFilter.addEventListener("change", applyFilters);

// Init
document.addEventListener("DOMContentLoaded", loadShops);

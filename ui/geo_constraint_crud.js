/* ==================== GEO CONSTRAINT CRUD ==================== */
let geoShops = [];
let geoVehicles = [];
let selectedStartShop = null;
let selectedEndShop = null;
let selectedVehicle = null;

// Load shops & vehicles
async function loadGeoConstraintData() {
  try {
    const [shopsRes, vehiclesRes] = await Promise.all([
      fetch(TMS_API.url("/master/shop")),
      fetch(TMS_API.url("/vehicle")),
    ]);

    if (!shopsRes.ok || !vehiclesRes.ok) throw new Error("Failed to load data");

    geoShops = await shopsRes.json();
    geoVehicles = await vehiclesRes.json();

    console.log("Loaded shops for geo constraint:", geoShops.length);
    console.log("Loaded vehicles for geo constraint:", geoVehicles.length);

    setupGeoShopAutocomplete();
    setupGeoVehicleAutocomplete();
  } catch (err) {
    showToast("Failed to load shops/vehicles: " + err.message, "danger");
  }
}

// Setup shop autocomplete (similar to order management)
function setupGeoShopAutocomplete() {
  const startInput = document.getElementById("startShopInput");
  const endInput = document.getElementById("endShopInput");
  const startList = document.getElementById("startShopList");
  const endList = document.getElementById("endShopList");

  if (!startInput || !endInput || !startList || !endList) return;

  console.log("Setting up shop autocomplete with", geoShops.length, "shops");

  // Populate datalists with ALL shops initially
  const shopOptions = geoShops
    .map(
      (s) => `
    <option value="${s.shop_code}">${s.location || ""} - ${s.address || ""} (${
        s.district || ""
      })</option>
  `
    )
    .join("");

  startList.innerHTML = shopOptions;
  endList.innerHTML = shopOptions;

  // Remove existing listeners by cloning and replacing
  const newStartInput = startInput.cloneNode(true);
  newStartInput.setAttribute("list", "startShopList"); // Ensure list attribute is set
  startInput.parentNode.replaceChild(newStartInput, startInput);

  const newEndInput = endInput.cloneNode(true);
  newEndInput.setAttribute("list", "endShopList"); // Ensure list attribute is set
  endInput.parentNode.replaceChild(newEndInput, endInput);

  // Start shop input handler
  newStartInput.addEventListener("input", () => {
    const val = newStartInput.value.toLowerCase();
    const filtered = geoShops.filter(
      (s) =>
        s.shop_code.toLowerCase().includes(val) ||
        (s.location && s.location.toLowerCase().includes(val)) ||
        (s.address && s.address.toLowerCase().includes(val))
    );

    startList.innerHTML = filtered
      .map(
        (s) => `
      <option value="${s.shop_code}">${s.location || ""} - ${
          s.address || ""
        } (${s.district || ""})</option>
    `
      )
      .join("");

    validateStartShop(newStartInput.value);
  });

  // End shop input handler
  newEndInput.addEventListener("input", () => {
    const val = newEndInput.value.toLowerCase();
    const filtered = geoShops.filter(
      (s) =>
        s.shop_code.toLowerCase().includes(val) ||
        (s.location && s.location.toLowerCase().includes(val)) ||
        (s.address && s.address.toLowerCase().includes(val))
    );

    endList.innerHTML = filtered
      .map(
        (s) => `
      <option value="${s.shop_code}">${s.location || ""} - ${
          s.address || ""
        } (${s.district || ""})</option>
    `
      )
      .join("");

    validateEndShop(newEndInput.value);
  });

  // Validate on blur
  newStartInput.addEventListener("blur", () =>
    validateStartShop(newStartInput.value)
  );
  newEndInput.addEventListener("blur", () =>
    validateEndShop(newEndInput.value)
  );
}

// Validate start shop
function validateStartShop(code) {
  const shop = geoShops.find((s) => s.shop_code === code);
  const detailsEl = document.getElementById("startShopDetails");

  if (shop) {
    selectedStartShop = shop;
    detailsEl.innerHTML = `<small class="text-success"><i class="bi bi-check-circle-fill"></i> ${
      shop.location || ""
    } - ${shop.address || ""} (${shop.latitude}, ${shop.longitude})</small>`;
    return true;
  } else {
    selectedStartShop = null;
    if (code.trim()) {
      detailsEl.innerHTML = `<small class="text-danger"><i class="bi bi-exclamation-circle-fill"></i> Shop not found</small>`;
    } else {
      detailsEl.innerHTML = "";
    }
    return false;
  }
}

// Validate end shop
function validateEndShop(code) {
  const shop = geoShops.find((s) => s.shop_code === code);
  const detailsEl = document.getElementById("endShopDetails");

  if (shop) {
    selectedEndShop = shop;
    detailsEl.innerHTML = `<small class="text-success"><i class="bi bi-check-circle-fill"></i> ${
      shop.location || ""
    } - ${shop.address || ""} (${shop.latitude}, ${shop.longitude})</small>`;
    return true;
  } else {
    selectedEndShop = null;
    if (code.trim()) {
      detailsEl.innerHTML = `<small class="text-danger"><i class="bi bi-exclamation-circle-fill"></i> Shop not found</small>`;
    } else {
      detailsEl.innerHTML = "";
    }
    return false;
  }
}

// Setup vehicle autocomplete
function setupGeoVehicleAutocomplete() {
  const input = document.getElementById("vehicleSelect");
  const list = document.getElementById("vehicleList");

  if (!input || !list) return;

  console.log(
    "Setting up vehicle autocomplete with",
    geoVehicles.length,
    "vehicles"
  );

  // Populate datalist with ALL vehicles initially
  const vehicleOptions = geoVehicles
    .map(
      (v) => `
    <option value="${v.vehicle_name || v.name || v.id}">${
        v.vehicle_name || v.name || v.id
      } - ${v.type || ""} (Fleet ID: ${v.fleet_id || "N/A"})</option>
  `
    )
    .join("");

  list.innerHTML = vehicleOptions;

  // Remove existing listener by cloning and replacing
  const newInput = input.cloneNode(true);
  newInput.setAttribute("list", "vehicleList"); // Ensure list attribute is set
  input.parentNode.replaceChild(newInput, input);

  // Input handler
  newInput.addEventListener("input", () => {
    const val = newInput.value.toLowerCase();
    const filtered = geoVehicles.filter((v) => {
      const vehicleName = (v.vehicle_name || v.name || v.id).toLowerCase();
      const vehicleType = (v.type || "").toLowerCase();
      return vehicleName.includes(val) || vehicleType.includes(val);
    });

    list.innerHTML = filtered
      .map(
        (v) => `
      <option value="${v.vehicle_name || v.name || v.id}">${
          v.vehicle_name || v.name || v.id
        } - ${v.type || ""} (Fleet ID: ${v.fleet_id || "N/A"})</option>
    `
      )
      .join("");

    validateVehicle(newInput.value);
  });

  // Validate on blur
  newInput.addEventListener("blur", () => validateVehicle(newInput.value));
}

// Validate vehicle
function validateVehicle(vehicleName) {
  const vehicle = geoVehicles.find(
    (v) => (v.vehicle_name || v.name || v.id) === vehicleName
  );
  const detailsEl = document.getElementById("vehicleDetails");

  if (vehicle) {
    selectedVehicle = vehicle;
    detailsEl.innerHTML = `<small class="text-success"><i class="bi bi-check-circle-fill"></i> ${
      vehicle.type || ""
    } - Fleet ID: ${vehicle.fleet_id || "N/A"}</small>`;
    return true;
  } else {
    selectedVehicle = null;
    if (vehicleName.trim()) {
      detailsEl.innerHTML = `<small class="text-warning"><i class="bi bi-exclamation-circle-fill"></i> Vehicle not found (optional)</small>`;
    } else {
      detailsEl.innerHTML = "";
    }
    return true; // Vehicle is optional
  }
}

// Fetch & render
async function fetchGeoConstraints() {
  try {
    const res = await fetch(TMS_API.url("/geo-constraint"));
    if (!res.ok) throw new Error("Failed");
    const data = await res.json();

    // Enrich shop data with location and brand info
    const enrichedData = await Promise.all(
      data.map(async (constraint) => {
        try {
          // Fetch full shop details for start and end shops
          const [startShopRes, endShopRes] = await Promise.all([
            fetch(
              TMS_API.url(`/master/shop/shop_code/${constraint.start_shop.shop_code}`)
            ),
            fetch(
              TMS_API.url(`/master/shop/shop_code/${constraint.end_shop.shop_code}`)
            ),
          ]);

          if (startShopRes.ok && endShopRes.ok) {
            const startShopFull = await startShopRes.json();
            const endShopFull = await endShopRes.json();

            return {
              ...constraint,
              start_shop: { ...constraint.start_shop, ...startShopFull },
              end_shop: { ...constraint.end_shop, ...endShopFull },
            };
          }
        } catch (err) {
          console.error("Failed to enrich shop data:", err);
        }
        return constraint; // Return original if enrichment fails
      })
    );

    renderGeoConstraints(enrichedData);
  } catch (err) {
    showToast(err.message, "danger");
  }
}

function renderGeoConstraints(constraints) {
  const container = document.getElementById("geoConstraintsList");
  const noData = document.getElementById("noGeoConstraints");

  if (!constraints.length) {
    noData.style.display = "block";
    container.innerHTML = "";
    return;
  }
  noData.style.display = "none";

  container.innerHTML = constraints
    .map(
      (c) => `
    <div class="border p-3 mb-2 rounded bg-light d-flex justify-content-between align-items-center">
      <div>
        <div class="mb-1">
          <strong>${c.start_shop.shop_code}</strong> 
          <span class="text-primary">${c.start_shop.location || ""}</span>
          <span class="badge bg-secondary">${c.start_shop.brand || ""}</span>
        </div>
        <div class="mb-1">
          <i class="bi bi-arrow-down"></i>
        </div>
        <div class="mb-2">
          <strong>${c.end_shop.shop_code}</strong> 
          <span class="text-primary">${c.end_shop.location || ""}</span>
          <span class="badge bg-secondary">${c.end_shop.brand || ""}</span>
        </div>
        <div class="small text-muted">
          (${c.start_shop.latitude}, ${c.start_shop.longitude}) → (${
        c.end_shop.latitude
      }, ${c.end_shop.longitude})
        </div>
        ${
          c.vehicle
            ? `<span class="badge bg-info mt-1">Vehicle: ${c.vehicle.vehicle_name} (${c.vehicle.type})</span>`
            : '<span class="badge bg-light text-muted mt-1">No vehicle assigned</span>'
        }
      </div>
      <div>
        <button class="btn btn-sm btn-outline-primary me-1 edit-geo" data-id="${
          c.id
        }">Edit</button>
        <button class="btn btn-sm btn-outline-danger delete-geo" data-id="${
          c.id
        }">Delete</button>
      </div>
    </div>
  `
    )
    .join("");
}

// Create / Update
document
  .getElementById("geoConstraintForm")
  .addEventListener("submit", async (e) => {
    e.preventDefault();

    const id = document.getElementById("geoConstraintId").value;
    const startCode = document.getElementById("startShopInput").value.trim();
    const endCode = document.getElementById("endShopInput").value.trim();
    const vehicleName = document.getElementById("vehicleSelect").value.trim();

    // Validate shops
    if (!validateStartShop(startCode)) {
      return showToast("Invalid start shop", "danger");
    }
    if (!validateEndShop(endCode)) {
      return showToast("Invalid end shop", "danger");
    }
    if (startCode === endCode) {
      return showToast("Start and end shops must be different", "danger");
    }

    // Validate vehicle (optional)
    if (vehicleName) {
      validateVehicle(vehicleName);
    }

    const payload = {
      start_shop_id: selectedStartShop.id,
      end_shop_id: selectedEndShop.id,
      vehicle_id: selectedVehicle ? selectedVehicle.id : null,
    };

    try {
      const method = id ? "PUT" : "POST";
      const url = id
        ? TMS_API.url(`/geo-constraint/${id}`)
        : TMS_API.url("/geo-constraint");
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Failed");
      }

      showToast(id ? "Updated!" : "Created!", "success");

      // Close modal
      const modalElement = document.getElementById("geoConstraintModal");
      const modalInstance = bootstrap.Modal.getInstance(modalElement);
      if (modalInstance) {
        modalInstance.hide();
      }

      // Refresh list
      fetchGeoConstraints();
    } catch (err) {
      showToast(err.message, "danger");
    }
  });

// Edit
document
  .getElementById("geoConstraintsList")
  .addEventListener("click", async (e) => {
    const btn = e.target.closest(".edit-geo");
    if (!btn) return;

    const id = btn.dataset.id;
    try {
      // Load data first to ensure shops/vehicles are available
      await loadGeoConstraintData();

      const res = await fetch(TMS_API.url(`/geo-constraint/${id}`));
      if (!res.ok) throw new Error("Failed to load constraint");
      const geo = await res.json();

      document.getElementById("geoConstraintId").value = geo.id;
      document.getElementById("startShopInput").value =
        geo.start_shop.shop_code;
      document.getElementById("endShopInput").value = geo.end_shop.shop_code;
      document.getElementById("vehicleSelect").value =
        geo.vehicle?.vehicle_name || geo.vehicle?.name || "";

      // Validate to show details
      validateStartShop(geo.start_shop.shop_code);
      validateEndShop(geo.end_shop.shop_code);
      if (geo.vehicle) {
        validateVehicle(geo.vehicle.vehicle_name || geo.vehicle.name);
      }

      document.getElementById("geoModalTitle").textContent =
        "Edit Geo Constraint";

      new bootstrap.Modal(document.getElementById("geoConstraintModal")).show();
    } catch (err) {
      showToast("Failed to load constraint: " + err.message, "danger");
    }
  });

// Delete
document
  .getElementById("geoConstraintsList")
  .addEventListener("click", async (e) => {
    const btn = e.target.closest(".delete-geo");
    if (!btn) return;
    if (!confirm("Delete this constraint?")) return;

    const id = btn.dataset.id;
    try {
      const res = await fetch(TMS_API.url(`/geo-constraint/${id}`), {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Delete failed");
      showToast("Deleted", "success");
      fetchGeoConstraints();
    } catch (err) {
      showToast(err.message, "danger");
    }
  });

// Reset modal
document
  .getElementById("geoConstraintModal")
  .addEventListener("hidden.bs.modal", () => {
    document.getElementById("geoConstraintForm").reset();
    document.getElementById("geoConstraintId").value = "";
    document.getElementById("geoModalTitle").textContent = "Add Geo Constraint";
    document.getElementById("startShopDetails").innerHTML = "";
    document.getElementById("endShopDetails").innerHTML = "";
    document.getElementById("vehicleDetails").innerHTML = "";
    selectedStartShop = null;
    selectedEndShop = null;
    selectedVehicle = null;
  });

// Load data when modal opens
document
  .getElementById("geoConstraintModal")
  ?.addEventListener("show.bs.modal", async () => {
    console.log("Geo Constraint modal opening, loading data...");

    // Always reload data to ensure it's fresh
    await loadGeoConstraintData();

    // Log to verify data is loaded
    console.log(
      "Data loaded - Shops:",
      geoShops.length,
      "Vehicles:",
      geoVehicles.length
    );
  });

// Load when tab opens
let geoConstraintDataLoaded = false;

document.addEventListener("DOMContentLoaded", () => {
  // Try to find the tab button using its id
  const geoConstraintTabBtn = document.getElementById("geo-constraint-tab");

  console.log("Setting up Geo Constraint tab listener", geoConstraintTabBtn);

  if (geoConstraintTabBtn) {
    geoConstraintTabBtn.addEventListener("shown.bs.tab", async () => {
      console.log("Geo Constraint tab activated via tab click");
      if (!geoConstraintDataLoaded) {
        await loadGeoConstraintData();
        geoConstraintDataLoaded = true;
      }
      await fetchGeoConstraints();
    });
  }

  // Also check if the tab is already active on load
  const geoConstraintPane = document.getElementById("geo-constraint");
  if (geoConstraintPane?.classList.contains("active")) {
    console.log("Geo Constraint tab already active on load");
    loadGeoConstraintData().then(() => {
      geoConstraintDataLoaded = true;
      fetchGeoConstraints();
    });
  }
});

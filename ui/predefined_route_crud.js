/* ==================== PRE-DEFINED ROUTE CRUD ==================== */
let routeShops = [];
let selectedRouteShops = []; // [{shop_id, shop_code, location, address, latitude, longitude}]

async function loadRouteShops() {
  // Always load fresh data to ensure it's up-to-date
  try {
    const res = await fetch(TMS_API.url("/location/customer"));
    if (!res.ok) throw new Error("Failed to load shops");
    routeShops = await res.json();
    console.log("Loaded shops for routes:", routeShops.length);
    setupRouteShopAutocomplete();
  } catch (err) {
    showToast("Failed to load shops: " + err.message, "danger");
  }
}

function setupRouteShopAutocomplete() {
  const input = document.getElementById("routeShopSearch");
  const list = document.getElementById("routeShopList");
  if (!input || !list) {
    console.log("Route shop input or list not found");
    return;
  }

  console.log(
    "Setting up route shop autocomplete with",
    routeShops.length,
    "shops"
  );

  // Populate datalist with ALL shops initially
  const options = routeShops
    .map(
      (s) => `
      <option value="${s.shop_code}">${s.location || ""} - ${
        s.address || ""
      } (${s.district || ""})</option>
    `
    )
    .join("");
  list.innerHTML = options;

  // Remove existing listener by cloning and replacing
  const newInput = input.cloneNode(true);
  input.parentNode.replaceChild(newInput, input);

  newInput.addEventListener("input", () => {
    const val = newInput.value.toLowerCase();
    const filtered = routeShops.filter(
      (s) =>
        s.shop_code.toLowerCase().includes(val) ||
        (s.location && s.location.toLowerCase().includes(val)) ||
        (s.address && s.address.toLowerCase().includes(val))
    );
    list.innerHTML = filtered
      .map(
        (s) => `
        <option value="${s.shop_code}">${s.location || ""} - ${
          s.address || ""
        } (${s.district || ""})</option>
      `
      )
      .join("");
    validateRouteShop(newInput.value);
  });

  newInput.addEventListener("blur", () => validateRouteShop(newInput.value));

  // Update the add button listener to use the new input
  const addBtn = document.getElementById("addShopToRouteBtn");
  if (addBtn) {
    // Remove old listener
    const newBtn = addBtn.cloneNode(true);
    addBtn.parentNode.replaceChild(newBtn, addBtn);

    // Add new listener
    newBtn.addEventListener("click", () => {
      const code = newInput.value.trim();
      const shop = validateRouteShop(code);
      if (shop) {
        addShopToRouteList(shop);
        newInput.value = "";
        document.getElementById("routeShopDetails").innerHTML = "";

        // Repopulate datalist with ALL shops after adding
        list.innerHTML = routeShops
          .map(
            (s) => `
            <option value="${s.shop_code}">${s.location || ""} - ${
              s.address || ""
            } (${s.district || ""})</option>
          `
          )
          .join("");
      }
    });
  }
}

function validateRouteShop(code) {
  const shop = routeShops.find((s) => s.shop_code === code);
  const details = document.getElementById("routeShopDetails");
  if (shop) {
    details.innerHTML = `<small class="text-success"><i class="bi bi-check-circle-fill"></i> ${shop.location} - ${shop.address}</small>`;
    return shop;
  } else {
    if (code.trim()) {
      details.innerHTML = `<small class="text-danger"><i class="bi bi-exclamation-circle-fill"></i> Shop not found</small>`;
    } else {
      details.innerHTML = "";
    }
    return null;
  }
}

function addShopToRouteList(shop) {
  if (selectedRouteShops.some((s) => s.shop_id === shop.id)) {
    showToast("Shop already added", "warning");
    return;
  }
  selectedRouteShops.push({
    shop_id: shop.id,
    shop_code: shop.shop_code,
    location: shop.location || "",
    address: shop.address || "",
    latitude: shop.latitude,
    longitude: shop.longitude,
  });
  renderRouteShopList();
}

function renderRouteShopList() {
  const container = document.getElementById("routeShopListContainer");
  if (selectedRouteShops.length === 0) {
    container.innerHTML = '<em class="text-muted">No shops added</em>';
    return;
  }
  container.innerHTML = selectedRouteShops
    .map(
      (s, i) => `
    <li class="list-group-item d-flex justify-content-between align-items-center" draggable="true" data-index="${i}">
      <span><strong>${s.shop_code}</strong> - ${s.location} (${s.latitude}, ${s.longitude})</span>
      <button type="button" class="btn btn-sm btn-danger remove-shop" data-index="${i}">×</button>
    </li>
  `
    )
    .join("");

  // Drag & drop
  container.querySelectorAll("[draggable]").forEach((el) => {
    el.addEventListener("dragstart", (e) => {
      e.dataTransfer.setData("text/plain", el.dataset.index);
      el.classList.add("dragging");
    });
    el.addEventListener("dragend", () => el.classList.remove("dragging"));
  });
  container.addEventListener("dragover", (e) => e.preventDefault());
  container.addEventListener("drop", (e) => {
    e.preventDefault();
    const from = e.dataTransfer.getData("text/plain");
    const to = e.target.closest("li")?.dataset.index;
    if (to !== undefined && from !== to) {
      const [moved] = selectedRouteShops.splice(from, 1);
      selectedRouteShops.splice(to, 0, moved);
      renderRouteShopList();
    }
  });

  // Remove
  container.querySelectorAll(".remove-shop").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = btn.dataset.index;
      selectedRouteShops.splice(idx, 1);
      renderRouteShopList();
    });
  });
}

// Open modal
async function openPredefinedRouteModal(route = null) {
  console.log("Opening predefined route modal...");

  // Ensure shops are loaded before opening modal
  await loadRouteShops();

  console.log("Shops loaded:", routeShops.length);

  selectedRouteShops = [];

  // Reset form
  const form = document.getElementById("predefinedRouteForm");
  form.reset();
  document.getElementById("predefinedRouteId").value = "";
  document.getElementById("predefinedRouteModalTitle").textContent =
    "Add Route";
  document.getElementById("routeShopDetails").innerHTML = "";

  if (route) {
    document.getElementById("predefinedRouteId").value = route.id;
    document.getElementById("routeNameInput").value = route.name;
    document.getElementById("predefinedRouteModalTitle").textContent =
      "Edit Route";
    selectedRouteShops = route.shops.map((s) => ({
      shop_id: s.shop_id,
      shop_code: s.shop.shop_code,
      location: s.shop.location || "",
      address: s.shop.address || "",
      latitude: s.shop.latitude,
      longitude: s.shop.longitude,
    }));
  }

  renderRouteShopList();

  // Show modal - get existing instance or create new one
  const modalElement = document.getElementById("predefinedRouteModal");
  let modal = bootstrap.Modal.getInstance(modalElement);
  if (!modal) {
    modal = new bootstrap.Modal(modalElement);
  }
  modal.show();
}

// NOTE: Add button listener is now in setupRouteShopAutocomplete()

// Form submit
document
  .getElementById("predefinedRouteForm")
  .addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = document.getElementById("predefinedRouteId").value;
    const name = document.getElementById("routeNameInput").value.trim();
    if (!name) return showToast("Route name required", "danger");
    if (selectedRouteShops.length < 2)
      return showToast("Add at least 2 shops", "danger");

    const payload = {
      name,
      shops: selectedRouteShops.map((s) => ({ shop_id: s.shop_id })),
    };

    try {
      const method = id ? "PUT" : "POST";
      const url = id
        ? TMS_API.url(`/predefined-route/${id}`)
        : TMS_API.url("/predefined-route");

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed");
      }

      showToast(id ? "Updated!" : "Created!", "success");

      // Close modal (hidden.bs.modal event will handle cleanup and refresh)
      const modalElement = document.getElementById("predefinedRouteModal");
      const modalInstance = bootstrap.Modal.getInstance(modalElement);
      if (modalInstance) {
        modalInstance.hide();
      }
    } catch (err) {
      showToast(err.message, "danger");
    }
  });

// Fetch & render
async function fetchPredefinedRoutes() {
  try {
    const res = await fetch(TMS_API.url("/predefined-route"));
    if (!res.ok) throw new Error("Failed");
    const routes = await res.json();

    // Enrich shop data with location, brand, and address info
    const enrichedRoutes = await Promise.all(
      routes.map(async (route) => {
        try {
          const enrichedShops = await Promise.all(
            route.shops.map(async (shopEntry) => {
              try {
                const shopRes = await fetch(
                  TMS_API.url(`/location/customer/code/${shopEntry.shop.shop_code}`)
                );
                if (shopRes.ok) {
                  const fullShopData = await shopRes.json();
                  return {
                    ...shopEntry,
                    shop: { ...shopEntry.shop, ...fullShopData },
                  };
                }
              } catch (err) {
                console.error(
                  "Failed to enrich shop:",
                  shopEntry.shop.shop_code,
                  err
                );
              }
              return shopEntry; // Return original if enrichment fails
            })
          );

          return {
            ...route,
            shops: enrichedShops,
          };
        } catch (err) {
          console.error("Failed to enrich route:", err);
        }
        return route; // Return original if enrichment fails
      })
    );

    renderPredefinedRoutes(enrichedRoutes);
  } catch (err) {
    showToast(err.message, "danger");
  }
}

function renderPredefinedRoutes(routes) {
  const container = document.getElementById("predefinedRoutesList");
  const noData = document.getElementById("noPredefinedRoutes");

  if (!routes.length) {
    noData.style.display = "block";
    container.innerHTML = "";
    return;
  }
  noData.style.display = "none";

  container.innerHTML = routes
    .map(
      (r) => `
    <div class="border p-3 mb-2 rounded bg-light">
      <div class="d-flex justify-content-between align-items-start">
        <div class="flex-grow-1">
          <strong class="fs-5">${r.name}</strong>
          <ol class="mt-2 mb-0 ps-4">
            ${r.shops
              .map(
                (s) => `
              <li class="mb-2">
                <strong>${s.shop.shop_code}</strong> - 
                <span class="text-primary">${s.shop.location || ""}</span>
                <span class="badge bg-secondary ms-1">${
                  s.shop.brand || ""
                }</span>
                <br>
                <small class="text-muted">📍 ${s.shop.address || ""} (${
                  s.shop.latitude
                }, ${s.shop.longitude})</small>
              </li>
            `
              )
              .join("")}
          </ol>
        </div>
        <div class="ms-3">
          <button class="btn btn-sm btn-outline-primary me-1 edit-route" data-id="${
            r.id
          }">Edit</button>
          <button class="btn btn-sm btn-outline-danger delete-route" data-id="${
            r.id
          }">Delete</button>
        </div>
      </div>
    </div>
  `
    )
    .join("");

  // Edit
  container.querySelectorAll(".edit-route").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.id;
      try {
        const res = await fetch(TMS_API.url(`/predefined-route/${id}`));
        if (!res.ok) throw new Error("Failed to load route");
        const route = await res.json();
        await openPredefinedRouteModal(route);
      } catch (err) {
        showToast("Failed to load route: " + err.message, "danger");
      }
    });
  });

  // Delete
  container.querySelectorAll(".delete-route").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!confirm("Delete this route?")) return;
      const id = btn.dataset.id;
      try {
        const res = await fetch(
          TMS_API.url(`/predefined-route/${id}`),
          { method: "DELETE" }
        );
        if (!res.ok) throw new Error("Delete failed");
        showToast("Deleted", "success");
        fetchPredefinedRoutes();
      } catch (err) {
        showToast(err.message, "danger");
      }
    });
  });
}

// Load data when modal opens (in addition to tab)
document
  .getElementById("predefinedRouteModal")
  ?.addEventListener("show.bs.modal", async () => {
    console.log("Predefined route modal opening, loading shops...");
    await loadRouteShops();
  });

// Reset modal when closed (Cancel button or X button)
document
  .getElementById("predefinedRouteModal")
  ?.addEventListener("hidden.bs.modal", () => {
    console.log("Predefined route modal closed, resetting...");

    // Remove any stuck backdrops
    const backdrops = document.querySelectorAll(".modal-backdrop");
    backdrops.forEach((backdrop) => backdrop.remove());
    document.body.classList.remove("modal-open");
    document.body.style.overflow = "";
    document.body.style.paddingRight = "";

    // Small timeout to ensure modal is fully hidden before cleanup
    setTimeout(() => {
      // Reset form
      const form = document.getElementById("predefinedRouteForm");
      if (form) form.reset();

      // Clear all fields explicitly
      const routeIdField = document.getElementById("predefinedRouteId");
      const routeNameField = document.getElementById("routeNameInput");
      const shopSearchField = document.getElementById("routeShopSearch");
      const shopDetailsField = document.getElementById("routeShopDetails");
      const modalTitle = document.getElementById("predefinedRouteModalTitle");

      if (routeIdField) routeIdField.value = "";
      if (routeNameField) routeNameField.value = "";
      if (shopSearchField) shopSearchField.value = "";
      if (shopDetailsField) shopDetailsField.innerHTML = "";
      if (modalTitle) modalTitle.textContent = "Add Route";

      // Clear selected shops
      selectedRouteShops = [];
      renderRouteShopList();

      // Refresh the routes list to show newly created/updated routes
      fetchPredefinedRoutes();

      console.log("Form reset complete");
    }, 100);
  });

// Load on tab show
document.addEventListener("DOMContentLoaded", () => {
  const tabBtn = document.getElementById("routes-constraint-tab");
  if (tabBtn) {
    tabBtn.addEventListener("shown.bs.tab", async () => {
      console.log("Routes tab activated");
      await loadRouteShops();
      await fetchPredefinedRoutes();
    });
  }

  // If already active
  if (
    document.getElementById("routes-constraint")?.classList.contains("show")
  ) {
    console.log("Routes tab already active on load");
    loadRouteShops().then(fetchPredefinedRoutes);
  }
});

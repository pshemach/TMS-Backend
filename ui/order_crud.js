// order_crud.js
const ORDER_API_BASE = TMS_API.url("/order");
let allOrders = [];

// DOM Elements
const orderTableBody = document.querySelector("#ordersTable tbody");
const noOrders = document.getElementById("noOrders");
const orderSearchInput = document.getElementById("orderSearchInput");
const orderStatusFilter = document.getElementById("orderStatusFilter");
const selectAllCheckbox = document.getElementById("selectAllOrders");
const exportOrdersBtn = document.getElementById("exportOrdersBtn");

// Track selected orders
const selectedOrders = new Set();
const dateFromFilter = document.getElementById("dateFromFilter");
const dateToFilter = document.getElementById("dateToFilter");
const orderForm = document.getElementById("orderForm");

// Helper: format date as YYYY-MM-DD
function formatDate(date) {
  const year = date.getFullYear();
  const month = (date.getMonth() + 1).toString().padStart(2, "0");
  const day = date.getDate().toString().padStart(2, "0");
  return `${year}-${month}-${day}`;
}

// Generate next order_id: YYMMDD### (e.g., 251029004)
function generateOrderId(poDate) {
  const date = poDate ? new Date(poDate) : new Date();
  const year = date.getFullYear().toString().slice(-2);
  const month = (date.getMonth() + 1).toString().padStart(2, "0");
  const day = date.getDate().toString().padStart(2, "0");
  const prefix = `${year}${month}${day}`;

  const sameDayOrders = allOrders
    .filter((o) => o.order_id.startsWith(prefix))
    .map((o) => parseInt(o.order_id.slice(-3)))
    .sort((a, b) => b - a);

  const nextSeq = sameDayOrders.length > 0 ? sameDayOrders[0] + 1 : 1;
  return `${prefix}${nextSeq.toString().padStart(3, "0")}`;
}

// Load Orders
async function loadOrders() {
  try {
    let url = TMS_API.url("/order");
    const params = new URLSearchParams();

    if (orderStatusFilter.value)
      params.append("status", orderStatusFilter.value);
    if (dateFromFilter.value) params.append("date_from", dateFromFilter.value);
    if (dateToFilter.value) params.append("date_to", dateToFilter.value);

    if (params.toString()) url += "?" + params.toString();

    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to fetch orders");

    allOrders = await res.json();
    await renderOrderTable(allOrders);
  } catch (err) {
    console.error("Error loading orders:", err);
    showToast(err.message, "danger");
  }
}

// Fetch shop details by shop_code
async function fetchShopDetails(shop_code) {
  try {
    const res = await fetch(
      TMS_API.url(`/location/customer/code/${shop_code}`)
    );
    if (!res.ok) throw new Error("Shop not found");
    return await res.json();
  } catch (err) {
    return null;
  }
}

// Render Orders Table
async function renderOrderTable(orders) {
  if (!orders || orders.length === 0) {
    orderTableBody.innerHTML = "";
    noOrders.classList.remove("d-none");
    return;
  }

  noOrders.classList.add("d-none");

  // Reset select-all when list changes
  if (selectAllCheckbox) selectAllCheckbox.checked = false;
  updateExportButton();

  const shopDetailsPromises = orders.map((o) =>
    fetchShopDetails(o.shop.shop_code)
  );
  const shopDetails = await Promise.all(shopDetailsPromises);

  const shopMap = {};
  orders.forEach((o, i) => {
    shopMap[o.shop.shop_code] = shopDetails[i];
  });

  orderTableBody.innerHTML = orders
    .map((order, i) => {
      const shop = shopMap[order.shop.shop_code] || {};
      const checked = selectedOrders.has(order.order_id) ? "checked" : "";
      return `
      <tr>
        <td>
          <input type="checkbox" class="form-check-input order-select-checkbox" 
                 data-order-id="${order.order_id}" ${checked}>
        </td>
        <td><strong>${order.order_id}</strong></td>
        <td>${order.shop.shop_code}</td>
        <td>${shop.location || "-"}</td>
        <td>${shop.address || "-"}</td>
        <td>${order.po_value?.toFixed(2) || "-"}</td>
        <td>${order.volume?.toFixed(2) || "-"}</td>
        <td>${order.po_date}</td>
        <td><span class="badge bg-${getStatusColor(order.status)}">${
        order.status
      }</span></td>
        <td>
          <button class="btn btn-sm btn-outline-primary me-1" onclick="editOrder(${
            order.id
          })" title="Edit">
            <i class="bi bi-pencil"></i>
          </button>
          <button class="btn btn-sm btn-outline-danger" onclick="deleteOrder(${
            order.id
          })" title="Delete">
            <i class="bi bi-trash"></i>
          </button>
        </td>
      </tr>`;
    })
    .join("");
}

function getStatusColor(status) {
  switch (status?.toLowerCase()) {
    case "pending":
      return "warning";
    case "active":
      return "primary";
    case "completed":
      return "success";
    default:
      return "secondary";
  }
}

// Filter Orders (search by order_id, shop_code, location, or address)
function filterOrders() {
  const search = orderSearchInput.value.trim().toLowerCase();
  let filtered = allOrders;

  if (search) {
    filtered = filtered.filter(
      (o) =>
        o.order_id.toLowerCase().includes(search) ||
        o.shop.shop_code.toLowerCase().includes(search) ||
        (o.shop.location && o.shop.location.toLowerCase().includes(search)) ||
        (o.shop.address && o.shop.address.toLowerCase().includes(search))
    );
  }

  renderOrderTable(filtered);
}

// === EXCEL UPLOAD: FULLY FIXED FOR REPEATED UPLOADS ===
async function handleExcelUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  showToast("Reading Excel file...", "info");

  try {
    const workbook = await readExcelFile(file);

    // Step 1: Parse raw rows (no order_id yet)
    const rawRows = parseExcelRows(workbook);

    if (rawRows.length === 0) throw new Error("No valid rows in Excel");

    // Step 2: Fetch latest orders from DB to avoid duplicates
    await loadOrders(); // Ensure allOrders is up-to-date

    // Step 3: Generate unique order_id using current DB state
    const ordersToUpload = generateUniqueOrderIds(rawRows);

    showToast(`Uploading ${ordersToUpload.length} orders...`, "info");

    let success = 0;
    const errors = [];

    for (const order of ordersToUpload) {
      try {
        await createOrder(order);
        success++;
      } catch (err) {
        errors.push(`${order.order_id}: ${err.message}`);
      }
    }

    if (success > 0) {
      showToast(`${success} orders uploaded successfully!`, "success");
      await loadOrders(); // Refresh
    }
    if (errors.length > 0) {
      const msg =
        errors.length <= 3
          ? errors.join("; ")
          : `${errors.slice(0, 3).join("; ")}... (+${errors.length - 3} more)`;
      showToast(`Upload errors: ${msg}`, "danger");
    }

    // Reset file input
    event.target.value = "";
  } catch (err) {
    showToast(err.message, "danger");
  }
}

// === PARSE RAW ROWS (no order_id) ===
function parseExcelRows(workbook) {
  const sheet = workbook.Sheets[workbook.SheetNames[0]];
  const rows = XLSX.utils.sheet_to_json(sheet);

  if (rows.length === 0) throw new Error("Excel file is empty");

  return rows.map((row, index) => {
    const shop_code = row.shop_code ? String(row.shop_code).trim() : null;
    if (!shop_code) {
      throw new Error(`Row ${index + 2}: shop_code is required`);
    }

    const po_date = row.po_date
      ? formatDate(new Date(row.po_date))
      : formatDate(new Date());

    return {
      shop_code,
      order_id: row.order_id ? String(row.order_id).trim() : null, // may be custom
      po_value: row.po_value ? parseFloat(row.po_value) : null,
      volume: row.volume ? parseFloat(row.volume) : null,
      po_date,
    };
  });
}

// === GENERATE UNIQUE ORDER_ID USING CURRENT DB STATE ===
function generateUniqueOrderIds(rows) {
  const dateGroups = {};

  // Group by po_date
  rows.forEach((row) => {
    const key = row.po_date;
    if (!dateGroups[key]) dateGroups[key] = [];
    dateGroups[key].push(row);
  });

  const result = [];

  for (const [po_date, orders] of Object.entries(dateGroups)) {
    const prefix =
      po_date.slice(2, 4) + po_date.slice(5, 7) + po_date.slice(8, 10);

    // Get existing sequences from DB
    const existingSeqs = allOrders
      .filter((o) => o.order_id.startsWith(prefix))
      .map((o) => parseInt(o.order_id.slice(-3)))
      .sort((a, b) => a - b);

    let nextSeq = existingSeqs.length > 0 ? Math.max(...existingSeqs) + 1 : 1;

    for (const order of orders) {
      if (order.order_id) {
        // Custom order_id → use it (assume unique)
        result.push(order);
      } else {
        // Auto-generate
        while (existingSeqs.includes(nextSeq)) {
          nextSeq++;
        }
        order.order_id = `${prefix}${nextSeq.toString().padStart(3, "0")}`;
        existingSeqs.push(nextSeq);
        nextSeq++;
        result.push(order);
      }
    }
  }

  return result;
}

async function readExcelFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target.result);
        const workbook = XLSX.read(data, { type: "array" });
        resolve(workbook);
      } catch (err) {
        reject(new Error("Cannot read Excel file"));
      }
    };
    reader.readAsArrayBuffer(file);
  });
}

// Global shops cache
let allShopsList = [];

// Fetch all shops
async function fetchAllShops() {
  try {
    const res = await fetch(TMS_API.url("/location/customer"));
    if (!res.ok) throw new Error("Failed to load shops");
    allShopsList = await res.json();
    setupShopAutocomplete();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

function setupShopAutocomplete() {
  const input = document.getElementById("shopSelect");
  const list = document.getElementById("shopSearchList");

  list.innerHTML = allShopsList
    .map(
      (s) => `
    <option value="${s.shop_code}">${s.location} - ${s.address || ""}</option>
  `
    )
    .join("");

  input.addEventListener("input", () => {
    const val = input.value.toLowerCase();
    const filtered = allShopsList.filter(
      (s) =>
        s.shop_code.toLowerCase().includes(val) ||
        s.location.toLowerCase().includes(val) ||
        (s.address && s.address.toLowerCase().includes(val))
    );
    list.innerHTML = filtered
      .map(
        (s) => `
      <option value="${s.shop_code}">${s.location} - ${s.address || ""}</option>
    `
      )
      .join("");
  });
}

// Create Order (from form or Excel)
async function createOrder(data) {
  let payload = { ...data };

  // Resolve shop_id
  if (payload.shop_code && !payload.shop_id) {
    const shop = allShopsList.find((s) => s.shop_code === payload.shop_code);
    if (shop) payload.shop_id = shop.id;
    else throw new Error(`Shop "${payload.shop_code}" not found`);
  }

  if (!payload.shop_id) throw new Error("Shop not found");

  // Generate order_id if missing
  if (!payload.order_id) {
    payload.order_id = generateOrderId(payload.po_date);
  }

  delete payload.shop_code;

  const res = await fetch(TMS_API.url("/order"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || "Failed to create order");
  }

  return await res.json();
}

// Edit Order
async function editOrder(id) {
  try {
    const res = await fetch(`${ORDER_API_BASE}/${id}`);
    if (!res.ok) throw new Error("Order not found");
    const order = await res.json();

    document.getElementById("orderId").value = order.id;
    document.getElementById("orderCode").value = order.order_id;
    document.getElementById("shopSelect").value = order.shop.shop_code;
    document.getElementById("poValue").value = order.po_value || "";
    document.getElementById("volume").value = order.volume || "";
    document.getElementById("poDate").value = order.po_date;

    const statusField = document.getElementById("statusField");
    const statusSelect = document.getElementById("status");
    if (statusField && statusSelect) {
      statusField.style.display = "block";
      statusSelect.value = order.status || "pending";
    }

    document.getElementById("orderModalTitle").textContent = "Edit Order";
    new bootstrap.Modal(document.getElementById("orderModal")).show();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

// Delete Order
async function deleteOrder(id) {
  if (!confirm("Delete order?")) return;
  try {
    const res = await fetch(`${ORDER_API_BASE}/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Delete failed");
    showToast("Order deleted");
    loadOrders();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

// Event Listeners
orderSearchInput.addEventListener("input", filterOrders);
orderStatusFilter.addEventListener("change", loadOrders);
dateFromFilter.addEventListener("change", loadOrders);
dateToFilter.addEventListener("change", loadOrders);
document
  .getElementById("excelUpload")
  .addEventListener("change", handleExcelUpload);

// Validate shop code
async function validateShopCode(code) {
  const shop = allShopsList.find((s) => s.shop_code === code);
  if (shop) {
    updateShopDetails(shop);
    return shop;
  }

  const res = await fetch(
    TMS_API.url(`/location/customer/code/${code}`)
  );
  if (!res.ok) {
    updateShopDetails(null);
    return null;
  }
  const details = await res.json();
  updateShopDetails(details);
  return details;
}

function updateShopDetails(shop) {
  const el = document.getElementById("shopDetails");
  if (shop) {
    el.innerHTML = `<small class="text-success"><i class="bi bi-check-circle-fill"></i> ${
      shop.location
    } - ${shop.address || "No address"} (${shop.district})</small>`;
  } else {
    el.innerHTML = `<small class="text-danger"><i class="bi bi-exclamation-circle-fill"></i> Shop not found</small>`;
  }
}

// Form Submit (Add / Edit)
document.getElementById("orderForm").addEventListener("submit", async (e) => {
  e.preventDefault();

  const orderId = document.getElementById("orderId").value;
  const shopCode = document.getElementById("shopSelect").value.trim();
  const po_value = document.getElementById("poValue").value;
  const volume = document.getElementById("volume").value;
  const po_date =
    document.getElementById("poDate").value || formatDate(new Date());

  if (!shopCode) return showToast("Shop code is required", "danger");

  const shop = await validateShopCode(shopCode);
  if (!shop) return showToast("Invalid shop code", "danger");

  const payload = {
    shop_id: shop.id,
    po_value: po_value ? parseFloat(po_value) : null,
    volume: volume ? parseFloat(volume) : null,
    po_date,
  };

  // Only include order_id for NEW orders
  if (!orderId) {
    const inputOrderId = document.getElementById("orderCode").value.trim();
    payload.order_id = inputOrderId || generateOrderId(po_date);
  }

  // Include status on edit
  const statusSelect = document.getElementById("status");
  if (orderId && statusSelect && statusSelect.value) {
    payload.status = statusSelect.value;
  }

  const method = orderId ? "PUT" : "POST";
  const url = orderId ? `${ORDER_API_BASE}/${orderId}` : TMS_API.url("/order");

  try {
    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || "Save failed");
    }

    showToast(orderId ? "Order updated!" : "Order created!");
    bootstrap.Modal.getInstance(document.getElementById("orderModal")).hide();
    loadOrders();
  } catch (err) {
    showToast(err.message, "danger");
  }
});

// Reset modal
document
  .getElementById("orderModal")
  .addEventListener("hidden.bs.modal", () => {
    const statusField = document.getElementById("statusField");
    if (statusField) statusField.style.display = "none";
    document.getElementById("orderForm").reset();
    document.getElementById("orderId").value = "";
    document.getElementById("orderModalTitle").textContent = "Add Order";
  });

// Set default PO date to today when opening modal for ADD (not edit)
document
  .getElementById("orderModal")
  .addEventListener("show.bs.modal", function (event) {
    const orderId = document.getElementById("orderId").value;
    if (!orderId) {
      document.getElementById("poDate").value = formatDate(new Date());
    }
  });

// Init
// Handle checkbox events
function setupCheckboxHandlers() {
  // Select All checkbox
  selectAllCheckbox?.addEventListener("change", (e) => {
    const checkboxes = document.querySelectorAll(".order-select-checkbox");
    checkboxes.forEach((cb) => {
      cb.checked = e.target.checked;
      const orderId = cb.getAttribute("data-order-id");
      if (e.target.checked) {
        selectedOrders.add(orderId);
      } else {
        selectedOrders.delete(orderId);
      }
    });
    updateExportButton();
  });

  // Individual checkboxes
  orderTableBody.addEventListener("change", (e) => {
    if (e.target.matches(".order-select-checkbox")) {
      const orderId = e.target.getAttribute("data-order-id");
      if (e.target.checked) {
        selectedOrders.add(orderId);
      } else {
        selectedOrders.delete(orderId);
        selectAllCheckbox.checked = false;
      }
      updateExportButton();
    }
  });
}

function updateExportButton() {
  if (exportOrdersBtn) {
    exportOrdersBtn.disabled = selectedOrders.size === 0;
  }
}

// Get selected order details for constraint tab
function getSelectedOrderDetails() {
  return allOrders.filter((order) => selectedOrders.has(order.order_id));
}

// Convert {start: "09:00:00", end: "17:00:00"} → "09:00-17:00"
function formatTimeWindow(tw) {
  if (!tw || !tw.start || !tw.end) return null;
  const s = tw.start.slice(0, 5);
  const e = tw.end.slice(0, 5);
  return `${s}-${e}`;
}

// Export selected orders to constraints tab
async function exportSelectedOrders() {
  const freshOrders = await window.getSelectedOrderDetails();
  // Filter out orders with status 'completed'
  const filteredOrders = freshOrders.filter(
    (order) => order.status?.toLowerCase() !== "completed"
  );
  if (!filteredOrders?.length) {
    showToast("No eligible orders selected (excluding completed)", "warning");
    return;
  }

  // Instead of replacing, merge new orders with existing ones
  filteredOrders.forEach((fresh) => {
    // Check if order already exists in processedOrders
    const existingIndex = window.processedOrders.findIndex(
      (c) => c.order_id === fresh.order_id
    );

    if (existingIndex >= 0) {
      // Order already exists, update it while preserving constraints
      const existing = window.processedOrders[existingIndex];
      window.processedOrders[existingIndex] = {
        ...fresh,
        priority: existing.priority ?? fresh.priority,
        time_window:
          existing.time_window ??
          (fresh.time_window ? formatTimeWindow(fresh.time_window) : null),
        group_name: existing.group_name ?? fresh.group_name,
        group_id: existing.group_id ?? fresh.group_id,
      };
    } else {
      // New order, add it to the list
      window.processedOrders.push({
        ...fresh,
        priority: fresh.priority || "",
        time_window: fresh.time_window
          ? formatTimeWindow(fresh.time_window)
          : null,
        group_name: fresh.group_name || "",
        group_id: fresh.group_id || null,
      });
    }
  });

  // Switch tabs
  const constraintsTab = document.querySelector("#constraints-tab");
  const orderConstraintTab = document.querySelector("#order-constraint-tab");
  if (constraintsTab && orderConstraintTab) {
    new bootstrap.Tab(constraintsTab).show();
    setTimeout(() => {
      new bootstrap.Tab(orderConstraintTab).show();
      // REFRESH GROUPS AFTER TAB SWITCH
      setTimeout(fetchOrderGroups, 200);
    }, 100);
  }

  // Clear selections after export
  selectedOrders.clear();

  // Uncheck all checkboxes in the order table
  document.querySelectorAll(".order-select-checkbox").forEach((cb) => {
    cb.checked = false;
  });

  // Uncheck select-all checkbox
  if (selectAllCheckbox) {
    selectAllCheckbox.checked = false;
  }

  // Update export button state
  updateExportButton();

  window.renderProcessedOrders();
  showToast(`Added ${freshOrders.length} order(s) to constraints`, "success");
}

// Hook up export button click handler
exportOrdersBtn?.addEventListener("click", exportSelectedOrders);

// Return enriched data (used by constraint tab)
window.getSelectedOrderDetails = async function () {
  // Only return selected orders that are NOT completed
  const orders = allOrders.filter(
    (o) =>
      selectedOrders.has(o.order_id) && o.status?.toLowerCase() !== "completed"
  );
  if (!orders.length) return [];

  const shopPromises = orders.map((o) =>
    fetchShopDetails(o.shop.shop_code).catch(() => ({}))
  );
  const shops = await Promise.all(shopPromises);

  return orders.map((order, i) => {
    const enriched = {
      ...order,
      shop: { ...order.shop, ...shops[i] },
    };

    // === TIME WINDOW: Convert DB fields → string ===
    // Handle both object format {start, end} and separate fields
    if (
      order.time_window &&
      typeof order.time_window === "object" &&
      order.time_window.start &&
      order.time_window.end
    ) {
      const start = order.time_window.start.slice(0, 5);
      const end = order.time_window.end.slice(0, 5);
      enriched.time_window = `${start}-${end}`;
    } else if (order.time_window_start && order.time_window_end) {
      const start = order.time_window_start.slice(0, 5);
      const end = order.time_window_end.slice(0, 5);
      enriched.time_window = `${start}-${end}`;
    } else {
      enriched.time_window = null;
    }

    // === GROUP INFO ===
    if (order.group) {
      enriched.group_name = order.group.name;
      enriched.group_id = order.group.id;
    }

    return enriched;
  });
};

// === RE-ATTACH AUTOCOMPLETE ON MODAL OPEN ===
document.getElementById("orderModal").addEventListener("show.bs.modal", () => {
  setupShopAutocomplete();
});

// Optional: Clean up on close
document
  .getElementById("orderModal")
  .addEventListener("hidden.bs.modal", () => {
    const input = document.getElementById("shopSelect");
    const list = document.getElementById("shopSearchList");
    if (input) input.value = "";
    if (list) list.innerHTML = "";
  });

document.addEventListener("DOMContentLoaded", () => {
  const today = new Date();
  const past = new Date(today);
  past.setDate(today.getDate() - 30);

  dateFromFilter.value = formatDate(past);
  dateToFilter.value = formatDate(today);

  setupCheckboxHandlers();
  fetchAllShops();
  loadOrders();

  // Refresh orders when the Orders tab becomes active (e.g., after switching tabs)
  const ordersTabBtn = document.getElementById("orders-tab");
  if (ordersTabBtn) {
    ordersTabBtn.addEventListener("shown.bs.tab", () => {
      loadOrders();
    });
  }

  // Also refresh when the window regains focus while Orders tab is active
  window.addEventListener("focus", () => {
    const ordersPane = document.getElementById("orders");
    if (ordersPane && ordersPane.classList.contains("active")) {
      loadOrders();
    }
  });

  // If returning to the page (tab becomes visible) and Orders is active, refresh
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      const ordersPane = document.getElementById("orders");
      if (ordersPane && ordersPane.classList.contains("active")) {
        loadOrders();
      }
    }
  });

  // Expose a simple global trigger so other modules can refresh orders when needed
  window.refreshOrders = loadOrders;
});

/* ==============================================================
   constraint_crud.js
   ============================================================== */
let orderGroups = [];

/* ------------------- GLOBAL STATE ------------------- */
window.processedOrders = []; // ← ONLY source of truth (order_crud.js writes here)

// Auto-fetch groups when constraint tab loads
document.addEventListener("DOMContentLoaded", () => {
  const observer = new MutationObserver((mutations, obs) => {
    if (
      document
        .querySelector("#order-constraint-tab")
        ?.classList.contains("active")
    ) {
      fetchOrderGroups();
      obs.disconnect();
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
});

/* ------------------- TIME OPTIONS (once) ------------------- */
const timeOptionsHTML = Array.from({ length: 48 }, (_, i) => {
  const h = String(Math.floor(i / 2)).padStart(2, "0");
  const m = i % 2 === 0 ? "00" : "30";
  return `<option value="${h}:${m}">${h}:${m}</option>`;
}).join("");

/* ------------------- HELPERS ------------------- */
function formatTimeWindow(tw) {
  if (!tw || !tw.start || !tw.end) return null;
  return `${tw.start.slice(0, 5)}-${tw.end.slice(0, 5)}`;
}

function normalizeOrder(order) {
  if (order.time_window && typeof order.time_window === "object") {
    order.time_window = formatTimeWindow(order.time_window);
  }
  return order;
}

/* ------------------- RENDER TABLE ------------------- */
window.renderProcessedOrders = function () {
  const tbody = document.querySelector("#processedOrdersTable tbody");
  const noData = document.getElementById("noProcessedOrders");
  const addBtn = document.getElementById("addGroupBtn");

  if (!window.processedOrders?.length) {
    noData.style.display = "block";
    addBtn.disabled = true;
    tbody.innerHTML = "";
    return;
  }

  noData.style.display = "none";
  addBtn.disabled = false;

  tbody.innerHTML = window.processedOrders
    .map((o) => {
      const order = normalizeOrder({ ...o });
      return `
    <tr data-order-id="${order.order_id}">
      <td><input type="checkbox" class="form-check-input order-in-constraint"></td>
      <td>${order.order_id}</td>
      <td>${order.shop?.shop_code || "-"}</td>
      <td>${order.shop?.location || "-"}</td>
      <td>${order.shop?.address || "-"}</td>
      <td>${order.po_value?.toFixed(2) || "-"}</td>
      <td>${order.volume?.toFixed(2) || "-"}</td>
      <td>${order.po_date || "-"}</td>
      <td>
        <span class="time-window-display">${order.time_window || "-"}</span>
        <button class="btn btn-sm btn-outline-secondary ms-2 set-time-window" title="Set Time Window">
          <i class="bi bi-clock"></i>
        </button>
      </td>
      <td>
        <select class="form-select form-select-sm priority-select">
          
          <option value="low"    ${
            order.priority === "low" ? "selected" : ""
          }>Low</option>
          <option value="medium" ${
            order.priority === "medium" ? "selected" : ""
          }>Medium</option>
          <option value="high"   ${
            order.priority === "high" ? "selected" : ""
          }>High</option>
        </select>
      </td>
      <td><span class="group-name-display">${
        order.group_name || "-"
      }</span></td>
      <td>
        <button class="btn btn-sm btn-outline-danger remove-order" title="Remove">
          <i class="bi bi-x"></i>
        </button>
      </td>
    </tr>`;
    })
    .join("");

  // Select All
  document.getElementById("selectAllInConstraint").onclick = (e) => {
    document
      .querySelectorAll(".order-in-constraint")
      .forEach((cb) => (cb.checked = e.target.checked));
  };
};

/* ------------------- TIME WINDOW – OPEN MODAL (DROPDOWNS WORK) ------------------- */
document
  .querySelector("#processedOrdersTable tbody")
  ?.addEventListener("click", (e) => {
    if (!e.target.closest(".set-time-window")) return;

    const row = e.target.closest("tr");
    const orderId = row.dataset.orderId;
    const order = window.processedOrders.find((o) => o.order_id === orderId);
    const [start = "", end = ""] = (order?.time_window || "").split("-");

    const modalEl = document.getElementById("timeWindowModal");
    const startSel = document.getElementById("startTimeSelect");
    const endSel = document.getElementById("endTimeSelect");

    // Inject options ONCE per modal open
    if (!startSel.options.length) {
      const opts = `<option value="">-- none --</option>${timeOptionsHTML}`;
      startSel.innerHTML = opts;
      endSel.innerHTML = opts;
    }

    document.getElementById("timeWindowOrderId").value = orderId;
    startSel.value = start;
    endSel.value = end;

    new bootstrap.Modal(modalEl).show();
  });

/* ------------------- TIME WINDOW – SAVE ------------------- */
document
  .getElementById("timeWindowForm")
  ?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const orderId = document.getElementById("timeWindowOrderId").value;
    const start = document.getElementById("startTimeSelect").value;
    const end = document.getElementById("endTimeSelect").value;

    const payload = { time_window: start && end ? { start, end } : null };

    try {
      const res = await fetch(
        `http://localhost:8000/order/order_id/${orderId}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );
      if (!res.ok) throw new Error((await res.json()).detail || "Failed");

      const order = window.processedOrders.find((o) => o.order_id === orderId);
      if (order) order.time_window = start && end ? `${start}-${end}` : null;

      window.renderProcessedOrders();
      showToast("Time window saved!", "success");
    } catch (err) {
      showToast(err.message, "danger");
    } finally {
      bootstrap.Modal.getInstance(
        document.getElementById("timeWindowModal")
      ).hide();
    }
  });

/* ------------------- PRIORITY (FIXED: use window.processedOrders) ------------------- */
document
  .querySelector("#processedOrdersTable tbody")
  ?.addEventListener("change", async (e) => {
    if (!e.target.matches(".priority-select")) return;

    const orderId = e.target.closest("tr").dataset.orderId;
    const priority = e.target.value;

    try {
      const res = await fetch(
        `http://localhost:8000/order/order_id/${orderId}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ priority: priority || null }),
        }
      );
      if (!res.ok) throw new Error((await res.json()).detail || "Failed");

      const order = window.processedOrders.find((o) => o.order_id === orderId);
      if (order) order.priority = priority;

      showToast("Priority updated!", "success");
    } catch (err) {
      showToast(err.message, "danger");
      e.target.value =
        window.processedOrders.find((o) => o.order_id === orderId)?.priority ||
        "";
    }
  });

/* ------------------- REMOVE ORDER ------------------- */
document
  .querySelector("#processedOrdersTable tbody")
  ?.addEventListener("click", (e) => {
    if (!e.target.closest(".remove-order")) return;

    const orderId = e.target.closest("tr").dataset.orderId;
    window.processedOrders = window.processedOrders.filter(
      (o) => o.order_id !== orderId
    );
    window.renderProcessedOrders();
  });

/* ------------------- GROUP MANAGEMENT ------------------- */
async function createGroup(payload) {
  const res = await fetch("http://localhost:8000/order-group", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Failed to create group");
  }
  return await res.json();
}

async function deleteGroup(groupId) {
  const res = await fetch(`http://localhost:8000/order-group/${groupId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete group");
}

/* ------------------- FETCH GROUPS FROM DB ------------------- */
async function fetchOrderGroups() {
  try {
    // Fetch both groups and all orders (not just active)
    const [groupsRes, ordersRes] = await Promise.all([
      fetch("http://localhost:8000/order-group"),
      fetch("http://localhost:8000/order"), // Fetch ALL orders
    ]);

    if (!groupsRes.ok) throw new Error("Failed to fetch groups");
    if (!ordersRes.ok) throw new Error("Failed to fetch orders");

    const groups = await groupsRes.json();
    const allOrders = await ordersRes.json();

    // Normalize: extract group_name for each order
    orderGroups = groups.map((g) => ({
      id: g.id,
      name: g.name,
      orders: g.orders.map((o) => o.order_id),
    }));

    // If processedOrders is empty (on page reload), populate it from all orders
    if (window.processedOrders.length === 0) {
      // Filter orders that have constraints (time_window or priority) or are in groups
      const ordersWithConstraints = allOrders.filter((order) => {
        const hasTimeWindow =
          (order.time_window &&
            typeof order.time_window === "object" &&
            order.time_window.start &&
            order.time_window.end) ||
          (order.time_window_start && order.time_window_end);
        const hasPriority = order.priority && order.priority !== "";
        const inGroup = groups.some((g) =>
          g.orders.some((o) => o.order_id === order.order_id)
        );
        return hasTimeWindow || hasPriority || inGroup;
      });

      window.processedOrders = ordersWithConstraints.map((order) => {
        // Find group if exists
        const group = groups.find((g) =>
          g.orders.some((o) => o.order_id === order.order_id)
        );

        // Format time_window
        let timeWindow = null;
        if (
          order.time_window &&
          typeof order.time_window === "object" &&
          order.time_window.start &&
          order.time_window.end
        ) {
          const start = order.time_window.start.slice(0, 5);
          const end = order.time_window.end.slice(0, 5);
          timeWindow = `${start}-${end}`;
        } else if (order.time_window_start && order.time_window_end) {
          const start = order.time_window_start.slice(0, 5);
          const end = order.time_window_end.slice(0, 5);
          timeWindow = `${start}-${end}`;
        }

        return {
          ...order,
          time_window: timeWindow,
          group_name: group ? group.name : "",
          group_id: group ? group.id : null,
          priority: order.priority || "",
        };
      });
    } else {
      // Update existing processedOrders with group_name AND constraints from DB
      window.processedOrders.forEach((order) => {
        const group = orderGroups.find((g) =>
          g.orders.includes(order.order_id)
        );
        order.group_name = group ? group.name : "";
        order.group_id = group ? group.id : null;

        // Find the full order data from groups or all orders to get time_window and priority
        let fullOrder = null;
        if (group) {
          const fullGroup = groups.find((g) => g.id === group.id);
          fullOrder = fullGroup?.orders.find(
            (o) => o.order_id === order.order_id
          );
        }
        if (!fullOrder) {
          fullOrder = allOrders.find((o) => o.order_id === order.order_id);
        }

        if (fullOrder) {
          // Update time_window from DB if exists
          if (
            fullOrder.time_window &&
            typeof fullOrder.time_window === "object" &&
            fullOrder.time_window.start &&
            fullOrder.time_window.end
          ) {
            const start = fullOrder.time_window.start.slice(0, 5);
            const end = fullOrder.time_window.end.slice(0, 5);
            order.time_window = `${start}-${end}`;
          } else if (fullOrder.time_window_start && fullOrder.time_window_end) {
            const start = fullOrder.time_window_start.slice(0, 5);
            const end = fullOrder.time_window_end.slice(0, 5);
            order.time_window = `${start}-${end}`;
          }

          // Update priority from DB if exists
          if (fullOrder.priority) {
            order.priority = fullOrder.priority;
          }
        }
      });
    }

    renderOrderGroups();
    window.renderProcessedOrders();
  } catch (err) {
    showToast(err.message, "danger");
  }
}

/* ------------------- RENDER GROUPS (under table) ------------------- */
function renderOrderGroups() {
  const container = document.getElementById("constraintGroupsList");
  const section = document.getElementById("constraintOrderGroups");

  if (!orderGroups.length) {
    section.style.display = "none";
    return;
  }
  section.style.display = "block";

  container.innerHTML = orderGroups
    .map(
      (g) => `
    <div class="border p-2 mb-2 rounded bg-light d-flex justify-content-between align-items-center">
      <div>
        <strong>${g.name}</strong>
        <div class="mt-1">
          ${g.orders
            .map((id) => `<span class="badge bg-primary me-1">${id}</span>`)
            .join("")}
        </div>
      </div>
      <button class="btn btn-sm btn-outline-danger delete-group" data-id="${
        g.id
      }" title="Delete Group">
        <i class="bi bi-trash"></i>
      </button>
    </div>
  `
    )
    .join("");
}

// Add Group
document.getElementById("addGroupBtn")?.addEventListener("click", () => {
  const checked = Array.from(
    document.querySelectorAll(".order-in-constraint:checked")
  ).map((cb) => cb.closest("tr").dataset.orderId);
  if (!checked.length) return showToast("Select at least one order", "warning");

  document.getElementById("groupAppendOrderIds").value = checked.join(",");
  new bootstrap.Modal(document.getElementById("constraintGroupModal")).show();
});

// Create Group
document
  .getElementById("constraintGroupForm")
  ?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const orderIds = document
      .getElementById("groupAppendOrderIds")
      .value.split(",")
      .filter(Boolean);
    const name = document.getElementById("groupNameInput").value.trim();
    if (!name) return showToast("Group name required", "danger");

    try {
      const group = await createGroup({ name, order_ids: orderIds });
      await fetchOrderGroups(); // ← REFRESH FROM DB
      showToast(`Group "${name}" created!`, "success");
      bootstrap.Modal.getInstance(
        document.getElementById("constraintGroupModal")
      ).hide();
    } catch (err) {
      showToast(err.message, "danger");
    }
  });

// Delete Group
document
  .getElementById("constraintGroupsList")
  ?.addEventListener("click", async (e) => {
    if (!e.target.closest(".delete-group")) return;

    const groupId = parseInt(e.target.closest(".delete-group").dataset.id);
    if (!confirm("Delete this group?")) return;

    try {
      await deleteGroup(groupId);
      await fetchOrderGroups(); // ← REFRESH FROM DB
      showToast("Group deleted", "success");
    } catch (err) {
      showToast(err.message, "danger");
    }
  });

/* ------------------- CLEAR BUTTONS ------------------- */
// Shared function to clear all orders from both sections
window.clearAllOrders = function () {
  // Clear both processed orders and optimization orders
  window.processedOrders = [];
  window.optimizationOrders = [];
  orderGroups = [];

  // Update constraint management view
  window.renderProcessedOrders();
  renderOrderGroups();

  // Update optimization view if it exists
  if (typeof window.renderOptimizationOrders === "function") {
    window.renderOptimizationOrders();
  }
};

document
  .getElementById("clearProcessedOrders")
  ?.addEventListener("click", () => {
    if (
      confirm(
        "Clear all processed orders? This will remove all orders from both Order Constraint Management and Optimization Management."
      )
    ) {
      window.clearAllOrders();
    }
  });

// Also attach to the new button ID
document
  .getElementById("clearProcessedOrdersBtn")
  ?.addEventListener("click", () => {
    if (
      confirm(
        "Clear all exported orders from the table? This will remove all orders from both Order Constraint Management and Optimization Management."
      )
    ) {
      window.clearAllOrders();

      showToast(
        "All orders cleared successfully from both sections",
        "success"
      );
    }
  });

document
  .getElementById("clearOrderConstraints")
  ?.addEventListener("click", () => {
    if (confirm("Clear all time windows, priorities, and groups?")) {
      window.processedOrders.forEach((o) => {
        o.time_window = null;
        o.priority = "";
        o.group_name = "";
        o.group_id = null;
      });
      window.renderProcessedOrders();
    }
  });

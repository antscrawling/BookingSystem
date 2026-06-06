const form = document.getElementById("bookingForm");
const formTitle = document.getElementById("formTitle");
const formMessage = document.getElementById("formMessage");
const listMessage = document.getElementById("listMessage");
const bookingsBody = document.getElementById("bookingsBody");
const costPreview = document.getElementById("costPreview");
const saveBtn = document.getElementById("saveBtn");
const cancelEditBtn = document.getElementById("cancelEditBtn");

const customerNameInput = document.getElementById("customerName");
const courtNumberInput = document.getElementById("courtNumber");
const bookingDateInput = document.getElementById("bookingDate");
const startHourInput = document.getElementById("startHour");
const durationHoursInput = document.getElementById("durationHours");

const apiBaseInput = document.getElementById("apiBase");
const refreshBtn = document.getElementById("refreshBtn");
const applyFiltersBtn = document.getElementById("applyFiltersBtn");
const clearFiltersBtn = document.getElementById("clearFiltersBtn");
const filterDateInput = document.getElementById("filterDate");
const filterCourtInput = document.getElementById("filterCourt");
const rulePrice = document.getElementById("rulePrice");
const ruleOpen = document.getElementById("ruleOpen");
const ruleClose = document.getElementById("ruleClose");
const ruleCourts = document.getElementById("ruleCourts");

let editingBookingId = null;
let bookingRules = {
  pricePerHour: 12,
  openingHour: 8,
  closingHour: 22,
  totalCourts: 10,
};

function apiBase() {
  return (apiBaseInput.value || "http://127.0.0.1:8000").replace(/\/$/, "");
}

function setMessage(element, text, type = "") {
  element.textContent = text;
  element.className = "message";
  if (type) {
    element.classList.add(type);
  }
}

function estimatedCost() {
  const duration = Number(durationHoursInput.value || 0);
  const cost = duration * bookingRules.pricePerHour;
  costPreview.textContent = `Estimated Cost: $${cost}`;
}

function formatHour(hour) {
  return `${String(hour).padStart(2, "0")}:00`;
}

function applyServerRules(data) {
  const price = Number(data.price_per_hour);
  const opening = Number(data.opening_hour);
  const closing = Number(data.closing_hour);
  const courts = Number(data.total_courts);

  if (!Number.isNaN(price)) {
    bookingRules.pricePerHour = price;
  }
  if (!Number.isNaN(opening)) {
    bookingRules.openingHour = opening;
  }
  if (!Number.isNaN(closing)) {
    bookingRules.closingHour = closing;
  }
  if (!Number.isNaN(courts)) {
    bookingRules.totalCourts = courts;
  }

  const latestStartHour = Math.max(bookingRules.openingHour, bookingRules.closingHour - 1);
  const maxDuration = Math.max(1, bookingRules.closingHour - bookingRules.openingHour);

  courtNumberInput.max = String(bookingRules.totalCourts);
  filterCourtInput.max = String(bookingRules.totalCourts);
  startHourInput.min = String(bookingRules.openingHour);
  startHourInput.max = String(latestStartHour);
  durationHoursInput.max = String(maxDuration);

  rulePrice.textContent = `$${bookingRules.pricePerHour}/hour`;
  ruleOpen.textContent = formatHour(bookingRules.openingHour);
  ruleClose.textContent = formatHour(bookingRules.closingHour);
  ruleCourts.textContent = `${bookingRules.totalCourts} courts`;

  estimatedCost();
}

function resetForm() {
  form.reset();
  editingBookingId = null;
  formTitle.textContent = "Create Booking";
  saveBtn.textContent = "Save Booking";
  cancelEditBtn.hidden = true;
  setMessage(formMessage, "");
  estimatedCost();
}

function toPayload() {
  return {
    customer_name: customerNameInput.value.trim(),
    court_number: Number(courtNumberInput.value),
    booking_date: bookingDateInput.value,
    start_hour: Number(startHourInput.value),
    duration_hours: Number(durationHoursInput.value),
  };
}

function toTimeRange(booking) {
  const endHour = booking.end_hour ?? booking.start_hour + booking.duration_hours;
  return `${String(booking.start_hour).padStart(2, "0")}:00 - ${String(endHour).padStart(2, "0")}:00`;
}

async function http(path, options = {}) {
  const response = await fetch(`${apiBase()}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    let detail = "Request failed";
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      detail = await response.text();
    }
    throw new Error(detail || "Request failed");
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

function rowActions(booking) {
  const actionsCell = document.createElement("td");

  const editBtn = document.createElement("button");
  editBtn.className = "ghost";
  editBtn.textContent = "Edit";
  editBtn.addEventListener("click", () => {
    editingBookingId = booking.id;
    formTitle.textContent = `Edit Booking #${booking.id}`;
    saveBtn.textContent = "Update Booking";
    cancelEditBtn.hidden = false;

    customerNameInput.value = booking.customer_name;
    courtNumberInput.value = booking.court_number;
    bookingDateInput.value = booking.booking_date;
    startHourInput.value = booking.start_hour;
    durationHoursInput.value = booking.duration_hours;
    estimatedCost();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  const deleteBtn = document.createElement("button");
  deleteBtn.textContent = "Delete";
  deleteBtn.addEventListener("click", async () => {
    const shouldDelete = window.confirm(`Delete booking #${booking.id}?`);
    if (!shouldDelete) {
      return;
    }

    try {
      await http(`/bookings/${booking.id}`, { method: "DELETE" });
      setMessage(listMessage, `Deleted booking #${booking.id}.`, "ok");
      if (editingBookingId === booking.id) {
        resetForm();
      }
      await loadBookings();
    } catch (error) {
      setMessage(listMessage, error.message, "error");
    }
  });

  actionsCell.append(editBtn, document.createTextNode(" "), deleteBtn);
  return actionsCell;
}

function renderBookings(bookings) {
  bookingsBody.innerHTML = "";

  if (!bookings.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 8;
    cell.textContent = "No bookings found.";
    row.appendChild(cell);
    bookingsBody.appendChild(row);
    return;
  }

  for (const booking of bookings) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${booking.id}</td>
      <td>${booking.customer_name}</td>
      <td>${booking.court_number}</td>
      <td>${booking.booking_date}</td>
      <td>${toTimeRange(booking)}</td>
      <td>${booking.duration_hours} hr</td>
      <td>$${booking.total_cost}</td>
    `;
    row.appendChild(rowActions(booking));
    bookingsBody.appendChild(row);
  }
}

function listQuery() {
  const params = new URLSearchParams();
  if (filterDateInput.value) {
    params.set("booking_date", filterDateInput.value);
  }
  if (filterCourtInput.value) {
    params.set("court_number", filterCourtInput.value);
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

async function loadBookings() {
  setMessage(listMessage, "Loading...");
  try {
    const bookings = await http(`/bookings${listQuery()}`);
    renderBookings(bookings);
    setMessage(listMessage, `Loaded ${bookings.length} booking(s).`, "ok");
  } catch (error) {
    renderBookings([]);
    setMessage(listMessage, error.message, "error");
  }
}

async function loadServerRules() {
  try {
    const rules = await http("/");
    applyServerRules(rules);
  } catch (error) {
    setMessage(listMessage, `Could not load pricing rules: ${error.message}`, "error");
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = toPayload();

  try {
    if (editingBookingId === null) {
      const booking = await http("/bookings", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setMessage(formMessage, `Created booking #${booking.id}.`, "ok");
    } else {
      const booking = await http(`/bookings/${editingBookingId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      setMessage(formMessage, `Updated booking #${booking.id}.`, "ok");
    }

    resetForm();
    await loadBookings();
  } catch (error) {
    setMessage(formMessage, error.message, "error");
  }
});

cancelEditBtn.addEventListener("click", () => {
  resetForm();
});

refreshBtn.addEventListener("click", () => {
  loadBookings();
});

applyFiltersBtn.addEventListener("click", () => {
  loadBookings();
});

clearFiltersBtn.addEventListener("click", () => {
  filterDateInput.value = "";
  filterCourtInput.value = "";
  loadBookings();
});

durationHoursInput.addEventListener("input", estimatedCost);
apiBaseInput.addEventListener("change", async () => {
  await loadServerRules();
  await loadBookings();
});

async function initialize() {
  estimatedCost();
  await loadServerRules();
  await loadBookings();
}

initialize();

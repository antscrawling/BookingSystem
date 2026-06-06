const STORAGE_TOKEN_KEY = "booking_access_token";

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

const authMessage = document.getElementById("authMessage");
const sessionInfo = document.getElementById("sessionInfo");
const registerForm = document.getElementById("registerForm");
const loginForm = document.getElementById("loginForm");
const registerNameInput = document.getElementById("registerName");
const registerEmailInput = document.getElementById("registerEmail");
const registerPasswordInput = document.getElementById("registerPassword");
const loginEmailInput = document.getElementById("loginEmail");
const loginPasswordInput = document.getElementById("loginPassword");
const logoutBtn = document.getElementById("logoutBtn");

const paymentForm = document.getElementById("paymentForm");
const paymentMessage = document.getElementById("paymentMessage");
const payBookingIdInput = document.getElementById("payBookingId");
const payCardholderInput = document.getElementById("payCardholder");
const payCardNumberInput = document.getElementById("payCardNumber");
const payExpMonthInput = document.getElementById("payExpMonth");
const payExpYearInput = document.getElementById("payExpYear");
const payCvvInput = document.getElementById("payCvv");

const adminCard = document.getElementById("adminCard");
const adminSettingsForm = document.getElementById("adminSettingsForm");
const adminPriceInput = document.getElementById("adminPrice");
const adminOpenInput = document.getElementById("adminOpen");
const adminCloseInput = document.getElementById("adminClose");
const adminCourtsInput = document.getElementById("adminCourts");
const adminMessage = document.getElementById("adminMessage");
const adminCustomersRefreshBtn = document.getElementById("adminCustomersRefreshBtn");
const adminCustomersBody = document.getElementById("adminCustomersBody");
const adminCustomersMessage = document.getElementById("adminCustomersMessage");

let editingBookingId = null;
let authToken = localStorage.getItem(STORAGE_TOKEN_KEY) || "";
let currentUser = null;
let bookingRules = {
  pricePerHour: 12,
  openingHour: 8,
  closingHour: 22,
  totalCourts: 10,
  paymentWindowMinutes: 10,
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

function setAuthToken(token) {
  authToken = token || "";
  if (authToken) {
    localStorage.setItem(STORAGE_TOKEN_KEY, authToken);
  } else {
    localStorage.removeItem(STORAGE_TOKEN_KEY);
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

function formatDateTime(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString();
}

function normalizeStatusLabel(statusValue) {
  return String(statusValue || "-")
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function applyServerRules(data) {
  const price = Number(data.price_per_hour);
  const opening = Number(data.opening_hour);
  const closing = Number(data.closing_hour);
  const courts = Number(data.total_courts);
  const paymentWindowMinutes = Number(data.payment_window_minutes);

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
  if (!Number.isNaN(paymentWindowMinutes)) {
    bookingRules.paymentWindowMinutes = paymentWindowMinutes;
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

  adminPriceInput.value = String(bookingRules.pricePerHour);
  adminOpenInput.value = String(bookingRules.openingHour);
  adminCloseInput.value = String(bookingRules.closingHour);
  adminCourtsInput.value = String(bookingRules.totalCourts);

  estimatedCost();
}

function resetForm() {
  form.reset();
  editingBookingId = null;
  formTitle.textContent = "Create Booking";
  saveBtn.textContent = "Save Booking";
  cancelEditBtn.hidden = true;
  setMessage(formMessage, "");

  if (currentUser?.full_name) {
    customerNameInput.value = currentUser.full_name;
  }
  estimatedCost();
}

function toPayload() {
  const customerName = customerNameInput.value.trim();
  return {
    customer_name: customerName || null,
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
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }

  const response = await fetch(`${apiBase()}${path}`, {
    headers,
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

function isLoggedIn() {
  return Boolean(authToken);
}

function updateAuthUI() {
  const loggedIn = isLoggedIn();

  form.querySelectorAll("input, button").forEach((el) => {
    el.disabled = !loggedIn;
  });
  paymentForm.querySelectorAll("input, button").forEach((el) => {
    el.disabled = !loggedIn;
  });
  refreshBtn.disabled = !loggedIn;
  applyFiltersBtn.disabled = !loggedIn;
  clearFiltersBtn.disabled = !loggedIn;

  logoutBtn.hidden = !loggedIn;

  if (!loggedIn) {
    currentUser = null;
    sessionInfo.textContent = "Not logged in.";
    adminCard.classList.add("hidden");
    adminCustomersBody.innerHTML = "";
    setMessage(adminCustomersMessage, "");
    setMessage(listMessage, "Login to view bookings.");
    bookingsBody.innerHTML = "";
    return;
  }

  const roleLabel = currentUser?.role || "customer";
  const fullName = currentUser?.full_name || "User";
  sessionInfo.textContent = `Logged in as ${fullName} (${roleLabel}).`;

  if (currentUser?.full_name) {
    customerNameInput.value = currentUser.full_name;
  }

  if (currentUser?.role === "admin") {
    adminCard.classList.remove("hidden");
  } else {
    adminCard.classList.add("hidden");
    adminCustomersBody.innerHTML = "";
    setMessage(adminCustomersMessage, "");
  }
}

function renderAdminCustomers(customers) {
  adminCustomersBody.innerHTML = "";

  if (!customers.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 5;
    cell.textContent = "No customers found.";
    row.appendChild(cell);
    adminCustomersBody.appendChild(row);
    return;
  }

  for (const customer of customers) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${customer.id}</td>
      <td>${customer.full_name}</td>
      <td>${customer.email}</td>
      <td>${normalizeStatusLabel(customer.role)}</td>
      <td>${formatDateTime(customer.created_at)}</td>
    `;
    adminCustomersBody.appendChild(row);
  }
}

async function loadAdminCustomers() {
  if (!isLoggedIn() || currentUser?.role !== "admin") {
    return;
  }

  setMessage(adminCustomersMessage, "Loading customers...");
  try {
    const customers = await http("/admin/customers");
    renderAdminCustomers(customers);
    setMessage(adminCustomersMessage, `Loaded ${customers.length} user(s).`, "ok");
  } catch (error) {
    renderAdminCustomers([]);
    setMessage(adminCustomersMessage, error.message, "error");
  }
}

async function loadProfile() {
  if (!isLoggedIn()) {
    updateAuthUI();
    return;
  }

  try {
    const profile = await http("/auth/me");
    currentUser = profile;
    setMessage(authMessage, "Authenticated session restored.", "ok");
  } catch (error) {
    setAuthToken("");
    currentUser = null;
    setMessage(authMessage, error.message, "error");
  }
  updateAuthUI();
}

function createActionButton(label, className, handler) {
  const button = document.createElement("button");
  if (className) {
    button.className = className;
  }
  button.textContent = label;
  button.addEventListener("click", handler);
  return button;
}

function rowActions(booking) {
  const actionsCell = document.createElement("td");

  const editBtn = createActionButton("Edit", "ghost", () => {
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

  if (booking.status !== "pending_payment") {
    editBtn.disabled = true;
  }

  const deleteBtn = createActionButton("Delete", "", async () => {
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

  const payBtn = createActionButton("Pay", "ghost", () => {
    payBookingIdInput.value = String(booking.id);
    payCardholderInput.value = booking.customer_name;
    window.scrollTo({ top: 0, behavior: "smooth" });
    setMessage(paymentMessage, `Ready to pay booking #${booking.id}.`);
  });
  if (booking.status !== "pending_payment") {
    payBtn.disabled = true;
  }

  const refundBtn = createActionButton("Refund", "ghost", async () => {
    const shouldRefund = window.confirm(`Refund booking #${booking.id}?`);
    if (!shouldRefund) {
      return;
    }

    try {
      const result = await http(`/bookings/${booking.id}/refund`, { method: "POST" });
      setMessage(listMessage, `Refund completed (${result.provider_reference}).`, "ok");
      await loadBookings();
    } catch (error) {
      setMessage(listMessage, error.message, "error");
    }
  });
  if (booking.status !== "paid") {
    refundBtn.disabled = true;
  }

  actionsCell.append(
    editBtn,
    document.createTextNode(" "),
    payBtn,
    document.createTextNode(" "),
    refundBtn,
    document.createTextNode(" "),
    deleteBtn,
  );
  return actionsCell;
}

function renderBookings(bookings) {
  bookingsBody.innerHTML = "";

  if (!bookings.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 10;
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
      <td>${normalizeStatusLabel(booking.status)}</td>
      <td>${formatDateTime(booking.payment_due_at)}</td>
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
  if (!isLoggedIn()) {
    updateAuthUI();
    return;
  }

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

async function loadAdminSettings() {
  if (!isLoggedIn() || currentUser?.role !== "admin") {
    return;
  }

  try {
    const settings = await http("/admin/settings");
    adminPriceInput.value = String(settings.price_per_hour);
    adminOpenInput.value = String(settings.opening_hour);
    adminCloseInput.value = String(settings.closing_hour);
    adminCourtsInput.value = String(settings.total_courts);
    setMessage(adminMessage, "Admin settings loaded.", "ok");
  } catch (error) {
    setMessage(adminMessage, error.message, "error");
  }
}

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  try {
    await http("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        full_name: registerNameInput.value.trim(),
        email: registerEmailInput.value.trim(),
        password: registerPasswordInput.value,
      }),
    });
    setMessage(authMessage, "Registration successful. You can login now.", "ok");
    registerForm.reset();
  } catch (error) {
    setMessage(authMessage, error.message, "error");
  }
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  try {
    const data = await http("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: loginEmailInput.value.trim(),
        password: loginPasswordInput.value,
      }),
    });

    setAuthToken(data.access_token);
    currentUser = data.user;
    setMessage(authMessage, "Login successful.", "ok");
    loginForm.reset();
    updateAuthUI();
    resetForm();
    await loadServerRules();
    await loadAdminSettings();
    await loadAdminCustomers();
    await loadBookings();
  } catch (error) {
    setMessage(authMessage, error.message, "error");
  }
});

logoutBtn.addEventListener("click", () => {
  setAuthToken("");
  currentUser = null;
  setMessage(authMessage, "Logged out.");
  updateAuthUI();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = toPayload();

  try {
    if (editingBookingId === null) {
      const booking = await http("/bookings", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setMessage(
        formMessage,
        `Created booking #${booking.id}. Complete payment in ${bookingRules.paymentWindowMinutes} minute(s).`,
        "ok",
      );
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

paymentForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const bookingId = Number(payBookingIdInput.value);
  if (!bookingId) {
    setMessage(paymentMessage, "Booking ID is required.", "error");
    return;
  }

  try {
    const result = await http(`/bookings/${bookingId}/pay`, {
      method: "POST",
      body: JSON.stringify({
        card_holder_name: payCardholderInput.value.trim(),
        card_number: payCardNumberInput.value.trim(),
        exp_month: Number(payExpMonthInput.value),
        exp_year: Number(payExpYearInput.value),
        cvv: payCvvInput.value.trim(),
      }),
    });
    setMessage(paymentMessage, `${result.status}: ${result.message} (${result.provider_reference})`, "ok");
    paymentForm.reset();
    await loadBookings();
  } catch (error) {
    setMessage(paymentMessage, error.message, "error");
  }
});

adminSettingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  try {
    const updated = await http("/admin/settings", {
      method: "PUT",
      body: JSON.stringify({
        price_per_hour: Number(adminPriceInput.value),
        opening_hour: Number(adminOpenInput.value),
        closing_hour: Number(adminCloseInput.value),
        total_courts: Number(adminCourtsInput.value),
      }),
    });
    applyServerRules(updated);
    setMessage(adminMessage, "Admin settings saved.", "ok");
    await loadBookings();
  } catch (error) {
    setMessage(adminMessage, error.message, "error");
  }
});

adminCustomersRefreshBtn.addEventListener("click", async () => {
  await loadAdminCustomers();
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
  await loadProfile();
  await loadAdminSettings();
  await loadAdminCustomers();
  await loadBookings();
});

async function initialize() {
  estimatedCost();
  await loadServerRules();
  await loadProfile();
  resetForm();
  await loadAdminSettings();
  await loadAdminCustomers();
  await loadBookings();
}

initialize();

const showAjaxMessage = (message, type = "success") => {
  const alert = document.createElement("div");
  alert.className = `alert alert-${type} alert-dismissible shadow position-fixed`;
  alert.style.cssText = "top:1rem;right:1rem;z-index:2000;max-width:420px";

  const text = document.createElement("span");
  text.textContent = message;
  const close = document.createElement("button");
  close.type = "button";
  close.className = "btn-close";
  close.dataset.bsDismiss = "alert";

  alert.append(text, close);
  document.body.appendChild(alert);
  window.setTimeout(() => alert.remove(), 4000);
};

const readJsonResponse = async response => {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    throw new Error("Phiên làm việc đã hết hạn hoặc máy chủ trả về dữ liệu không hợp lệ.");
  }
  return response.json();
};

const refreshPageContent = async () => {
  const response = await fetch(window.location.href, {
    headers: { "X-Requested-With": "XMLHttpRequest" },
    cache: "no-store"
  });
  if (!response.ok) throw new Error("Không thể tải lại nội dung trang.");

  const html = await response.text();
  const nextDocument = new DOMParser().parseFromString(html, "text/html");
  const currentContent = document.querySelector(".app-content .container-fluid");
  const nextContent = nextDocument.querySelector(".app-content .container-fluid");
  if (!currentContent || !nextContent) throw new Error("Không tìm thấy vùng nội dung cần cập nhật.");

  currentContent.innerHTML = nextContent.innerHTML;
  initializeApp(currentContent);
};

const setFormLoading = (form, loading) => {
  const button = form.querySelector('button[type="submit"], button:not([type])');
  if (!button) return;

  if (loading) {
    button.dataset.originalHtml = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Đang xử lý';
  } else {
    button.disabled = false;
    button.innerHTML = button.dataset.originalHtml || "Lưu";
  }
};

const closeContainingModal = async form => {
  const modalElement = form.closest(".modal");
  if (!modalElement || !window.bootstrap) return;
  if (!modalElement.classList.contains("show")) return;
  await new Promise(resolve => {
    modalElement.addEventListener("hidden.bs.modal", resolve, { once: true });
    bootstrap.Modal.getOrCreateInstance(modalElement).hide();
  });
};

const initializeTableSearch = root => {
  root.querySelectorAll("[data-table-search]").forEach(search => {
    if (search.dataset.ajaxBound) return;
    search.dataset.ajaxBound = "true";
    search.addEventListener("input", () => {
      const keyword = search.value.trim().toLowerCase();
      root.querySelectorAll("[data-search-row]").forEach(row => {
        row.style.display = row.innerText.toLowerCase().includes(keyword) ? "" : "none";
      });
    });
  });
};

const initializeRoomFilters = root => {
  root.querySelectorAll("[data-room-filter]").forEach(button => {
    if (button.dataset.ajaxBound) return;
    button.dataset.ajaxBound = "true";
    button.addEventListener("click", () => {
      root.querySelectorAll("[data-room-filter]").forEach(item => item.classList.remove("active"));
      button.classList.add("active");
      const filter = button.dataset.roomFilter;
      root.querySelectorAll("[data-room-status]").forEach(card => {
        card.style.display = filter === "all" || card.dataset.roomStatus === filter ? "" : "none";
      });
    });
  });
};

const initializeContractForms = root => {
  root.querySelectorAll("[data-contract-form]").forEach(form => {
    if (form.dataset.priceBound) return;
    form.dataset.priceBound = "true";

    const roomSelect = form.querySelector('select[name="room_id"]');
    const priceInput = form.querySelector('input[name="monthly_price"]');
    if (!roomSelect || !priceInput) return;

    const updatePrice = () => {
      const selectedRoom = roomSelect.options[roomSelect.selectedIndex];
      if (selectedRoom?.dataset.price) priceInput.value = selectedRoom.dataset.price;
    };

    roomSelect.addEventListener("change", updatePrice);
    if (!priceInput.value) updatePrice();
  });
};

const initializeAjaxForms = root => {
  root.querySelectorAll("form[data-ajax-form]").forEach(form => {
    if (form.dataset.ajaxBound) return;
    form.dataset.ajaxBound = "true";

    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) return;

      setFormLoading(form, true);
      try {
        const targetUrl = form.getAttribute("action") || window.location.href;
        const response = await fetch(targetUrl, {
          method: (form.method || "POST").toUpperCase(),
          body: new FormData(form),
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json"
          }
        });
        const result = await readJsonResponse(response);
        if (!response.ok || !result.success) {
          throw new Error(result.message || "Không thể thực hiện thao tác.");
        }

        await closeContainingModal(form);
        if (result.refresh) await refreshPageContent();
        showAjaxMessage(result.message, result.type || "success");
      } catch (error) {
        showAjaxMessage(error.message, "danger");
      } finally {
        setFormLoading(form, false);
      }
    });
  });
};

const initializeRoomStatusAjax = root => {
  root.querySelectorAll("[data-ajax-room-status]").forEach(form => {
    if (form.dataset.ajaxBound) return;
    form.dataset.ajaxBound = "true";

    form.addEventListener("submit", async event => {
      event.preventDefault();
      const select = form.querySelector('select[name="status"]');
      const button = form.querySelector('button[type="submit"], button:not([type])');
      const card = form.closest("[data-room-status]");
      const badge = card?.querySelector("[data-room-status-badge]");
      const originalValue = select.dataset.originalValue;

      const payload = new FormData(form);
      select.disabled = true;
      button.disabled = true;
      button.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

      try {
        const response = await fetch(form.getAttribute("action"), {
          method: "POST",
          body: payload,
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json"
          }
        });
        const result = await readJsonResponse(response);
        if (!response.ok || !result.success) {
          throw new Error(result.message || "Không thể cập nhật.");
        }

        const data = result.data;
        select.dataset.originalValue = data.status;
        card.dataset.roomStatus = data.status;
        if (badge) {
          badge.classList.remove("status-empty", "status-rented", "status-repair");
          badge.classList.add(data.status_class);
          badge.textContent = data.status_label;
        }
        showAjaxMessage(result.message);

        const activeFilter = root.querySelector("[data-room-filter].active");
        if (activeFilter && activeFilter.dataset.roomFilter !== "all") activeFilter.click();
      } catch (error) {
        select.value = originalValue;
        showAjaxMessage(error.message, "danger");
      } finally {
        select.disabled = false;
        button.disabled = false;
        button.innerHTML = '<i class="bi bi-check-lg"></i>';
      }
    });
  });
};

const initializeTraditionalConfirmations = root => {
  root.querySelectorAll("form[data-confirm]:not([data-ajax-form])").forEach(form => {
    if (form.dataset.confirmBound) return;
    form.dataset.confirmBound = "true";
    form.addEventListener("submit", event => {
      if (!window.confirm(form.dataset.confirm || "Bạn có chắc muốn thực hiện?")) {
        event.preventDefault();
      }
    });
  });
};

function initializeApp(root = document) {
  initializeTableSearch(root);
  initializeRoomFilters(root);
  initializeContractForms(root);
  initializeAjaxForms(root);
  initializeRoomStatusAjax(root);
  initializeTraditionalConfirmations(root);
}

document.addEventListener("DOMContentLoaded", () => initializeApp());

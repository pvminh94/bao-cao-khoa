/* JS cho form nhập liệu: tính tổng tự động + lưu qua fetch */

function calcFormula(formula, rowValues) {
  // thay key bằng số; công thức dạng 'hs+tq+te+khac'
  var expr = String(formula).replace(/[a-zA-Z_][a-zA-Z0-9_]*/g, function (k) {
    var v = rowValues[k];
    return String(typeof v === "number" && isFinite(v) ? v : 0);
  });
  if (!/^[0-9+\-*/().\s]+$/.test(expr)) return 0;
  try {
    // eslint-disable-next-line no-new-func
    return Function('"use strict"; return (' + expr + ")")();
  } catch (e) {
    return 0;
  }
}

function readRowValues(rowId) {
  var vals = {};
  document.querySelectorAll('.cell-input[data-row="' + rowId + '"]').forEach(function (inp) {
    var v = parseFloat(inp.value);
    vals[inp.dataset.col] = isFinite(v) ? v : 0;
  });
  return vals;
}

function refreshRow(rowId) {
  var vals = readRowValues(rowId);
  document.querySelectorAll('.calc-cell[data-row="' + rowId + '"]').forEach(function (td) {
    var out = calcFormula(td.dataset.formula, vals);
    td.textContent = Number.isInteger(out) ? out : Math.round(out * 10) / 10;
    td.dataset.value = out;
    // ghi đè vào vals để công thức sau (vd: tong = bhyt_tong + dich_vu) dùng được
    if (td.dataset.outCol) vals[td.dataset.outCol] = out;
  });
  refreshTotals();
}

function refreshTotals() {
  recalcFooter();
}

function recalcFooter() {
  var footCells = document.querySelectorAll("tfoot [data-sum-col]");
  if (!footCells.length) return;
  footCells.forEach(function (td) {
    var col = td.dataset.sumCol;
    var sum = 0;
    var inputs = document.querySelectorAll('.cell-input[data-col="' + col + '"]');
    if (inputs.length) {
      inputs.forEach(function (inp) {
        var v = parseFloat(inp.value);
        sum += isFinite(v) ? v : 0;
      });
      td.textContent = Number.isInteger(sum) ? sum : Math.round(sum * 10) / 10;
      return;
    }
    // cột tính: tìm calc-cell mà formula không chứa col khác ngoài input hợp lệ —
    // cách đơn giản demo: cộng mọi calc-cell có data-formula tương ứng col_key hiển thị
    // Chúng ta gán data-out-col khi khởi tạo:
    document.querySelectorAll('.calc-cell[data-out-col="' + col + '"]').forEach(function (cell) {
      var v = parseFloat(cell.dataset.value);
      sum += isFinite(v) ? v : 0;
    });
    td.textContent = Number.isInteger(sum) ? sum : Math.round(sum * 10) / 10;
  });
}

function initEntryGrid() {
  // gán data-out-col cho calc cell theo thứ tự cột calc trong table
  var calcCellsByRow = {};
  document.querySelectorAll(".calc-cell").forEach(function (td) {
    var row = td.dataset.row;
    calcCellsByRow[row] = calcCellsByRow[row] || [];
    calcCellsByRow[row].push(td);
  });
  // thứ tự col_key của calc trong footer đã có sẵn: đọc thead hàng 2
  var calcColKeys = [];
  document.querySelectorAll("thead tr:nth-child(2) th.num.calc, thead tr:nth-child(2) th.calc").forEach(function () {});
  // fallback: suy ra từ structure đã render trong thead — đánh số calc header
  var theadCalc = Array.from(document.querySelectorAll("thead th")).filter(function (th) {
    return th.classList.contains("calc");
  });
  // Gắn out-col: công thức tính ra col_key nào?
  // Trong template: bhyt_tong = hs+tq+te+khac ; tong = bhyt_tong+dich_vu
  // col_key xuất hiện trong footer data-sum-col đúng thứ tự với thead calc.
  var footCalcKeys = Array.from(document.querySelectorAll("tfoot [data-sum-col]")).map(function (td) {
    return td.dataset.sumCol;
  });
  var allKeys = Array.from(document.querySelectorAll("tfoot [data-sum-col]")).map(function (td) {
    return td.dataset.sumCol;
  });
  // input keys từ input elements unique
  var inputKeys = [];
  document.querySelectorAll(".cell-input").forEach(function (inp) {
    if (inputKeys.indexOf(inp.dataset.col) === -1) inputKeys.push(inp.dataset.col);
  });
  var calcKeys = allKeys.filter(function (k) {
    return inputKeys.indexOf(k) === -1;
  });

  Object.keys(calcCellsByRow).forEach(function (rowId) {
    calcCellsByRow[rowId].forEach(function (td, idx) {
      if (calcKeys[idx]) td.dataset.outCol = calcKeys[idx];
    });
  });

  document.querySelectorAll(".cell-input").forEach(function (inp) {
    inp.addEventListener("input", function () {
      refreshRow(inp.dataset.row);
    });
    inp.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        var all = Array.from(document.querySelectorAll(".cell-input"));
        var i = all.indexOf(inp);
        if (i > -1 && all[i + 1]) all[i + 1].focus();
      }
    });
  });

  document.querySelectorAll("tr[data-row]").forEach(function (tr) {
    refreshRow(tr.dataset.row);
  });

  var form = document.getElementById("entryForm");
  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var payload = {};
      document.querySelectorAll(".cell-input").forEach(function (inp) {
        var r = inp.dataset.row;
        payload[r] = payload[r] || {};
        payload[r][inp.dataset.col] = parseFloat(inp.value) || 0;
      });
      var status = document.getElementById("saveStatus");
      status.textContent = "Đang lưu...";
      var body = new URLSearchParams(new FormData(form));
      body.set("payload", JSON.stringify(payload));
      fetch("/nhap", { method: "POST", body: body })
        .then(function (r) {
          if (!r.ok) throw new Error("HTTP " + r.status);
          return r.json();
        })
        .then(function (data) {
          status.innerHTML =
            '<span style="color:var(--ok);font-weight:700">✓ Đã lưu ' +
            data.saved +
            " ô nhập lúc " +
            new Date().toLocaleTimeString("vi-VN") +
            "</span>";
        })
        .catch(function (err) {
          status.innerHTML = '<span style="color:var(--danger);font-weight:700">Lỗi: ' + err + "</span>";
        });
    });
  }
}

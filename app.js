import { initializeApp } from "https://www.gstatic.com/firebasejs/10.14.1/firebase-app.js";
import {
  getFirestore,
  collection,
  doc,
  onSnapshot,
  setDoc,
} from "https://www.gstatic.com/firebasejs/10.14.1/firebase-firestore.js";
import { firebaseConfig } from "./firebase-config.js";

const app = initializeApp(firebaseConfig);
const db = getFirestore(app);

const weekSelect = document.getElementById("weekSelect");
const dateLabel = document.getElementById("dateLabel");
const prevBtn = document.getElementById("prevBtn");
const nextBtn = document.getElementById("nextBtn");
const todayBtn = document.getElementById("todayBtn");
const listEl = document.getElementById("list");
const progressFill = document.getElementById("progressFill");
const progressText = document.getElementById("progressText");
const statusMsg = document.getElementById("statusMsg");
const checklistSection = document.getElementById("checklistSection");
const progressSection = document.getElementById("progressSection");
const statsBtn = document.getElementById("statsBtn");
const backBtn = document.getElementById("backBtn");
const statsList = document.getElementById("statsList");

let plan = [];
let currentIndex = 0;
let unsubscribe = null;
let statsUnsubscribe = null;

function todayId() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function findDefaultIndex() {
  const today = todayId();
  const exact = plan.findIndex((d) => d.id === today);
  if (exact !== -1) return exact;
  let lastBefore = -1;
  for (let i = 0; i < plan.length; i++) {
    if (plan[i].id < today) lastBefore = i;
  }
  return lastBefore !== -1 ? lastBefore : 0;
}

function populateWeekSelect() {
  const weeks = [...new Set(plan.map((d) => d.week))].sort((a, b) => a - b);
  weekSelect.innerHTML = weeks.map((w) => `<option value="${w}">${w}주차</option>`).join("");
}

function renderHeader(day) {
  weekSelect.value = String(day.week);
  dateLabel.textContent = `${day.month}월 ${day.day}일 (${day.weekday})`;
  prevBtn.disabled = currentIndex <= 0;
  nextBtn.disabled = currentIndex >= plan.length - 1;
  todayBtn.hidden = day.id === todayId();
}

function countVerses(day) {
  return day.items.filter((it) => it.type === "verse").length;
}

function renderList(day, checkedMap) {
  listEl.innerHTML = "";
  let verseIdx = 0;
  let total = 0;
  let done = 0;

  for (const item of day.items) {
    if (item.type === "note") {
      const el = document.createElement("div");
      el.className = "note-row";
      el.textContent = item.text;
      listEl.appendChild(el);
      continue;
    }

    const idx = verseIdx++;
    total++;
    const isChecked = !!checkedMap[String(idx)];
    if (isChecked) done++;

    const row = document.createElement("div");
    row.className = "verse-row" + (isChecked ? " checked" : "");

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = isChecked;
    checkbox.addEventListener("change", () => toggleVerse(day.id, idx, checkbox.checked));

    const textWrap = document.createElement("div");
    textWrap.className = "verse-text";

    const ref = document.createElement("div");
    ref.className = "verse-ref";
    ref.textContent = item.ref;
    textWrap.appendChild(ref);

    if (item.note) {
      const note = document.createElement("div");
      note.className = "verse-note";
      note.textContent = item.note;
      textWrap.appendChild(note);
    }

    row.appendChild(checkbox);
    row.appendChild(textWrap);
    row.addEventListener("click", (e) => {
      if (e.target !== checkbox) {
        checkbox.checked = !checkbox.checked;
        checkbox.dispatchEvent(new Event("change"));
      }
    });

    listEl.appendChild(row);
  }

  progressText.textContent = `${done} / ${total}`;
  progressFill.style.width = total ? `${(done / total) * 100}%` : "0%";

  if (total === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-msg";
    empty.textContent = "이 날은 등록된 말씀이 없습니다.";
    listEl.appendChild(empty);
  }
}

function toggleVerse(dayId, idx, value) {
  setDoc(doc(db, "progress", dayId), { checked: { [String(idx)]: value } }, { merge: true }).catch(
    (err) => {
      statusMsg.hidden = false;
      statusMsg.textContent = "저장 실패 — 인터넷 연결을 확인하세요.";
      console.error(err);
    }
  );
}

function showDay(index) {
  currentIndex = index;
  const day = plan[currentIndex];
  renderHeader(day);

  if (unsubscribe) unsubscribe();
  statusMsg.hidden = true;

  unsubscribe = onSnapshot(
    doc(db, "progress", day.id),
    (snap) => {
      const data = snap.exists() ? snap.data() : {};
      renderList(day, data.checked || {});
    },
    (err) => {
      console.error(err);
      statusMsg.hidden = false;
      statusMsg.textContent = "데이터를 불러올 수 없습니다.";
      renderList(day, {});
    }
  );
}

function renderProgressView(progressMap) {
  statsList.innerHTML = "";

  const weeks = [...new Set(plan.map((d) => d.week))].sort((a, b) => a - b);
  for (const week of weeks) {
    const daysInWeek = plan.filter((d) => d.week === week);
    let weekTotal = 0;
    let weekDone = 0;

    const dayRows = daysInWeek.map((day) => {
      const total = countVerses(day);
      const checked = progressMap[day.id] || {};
      const done = Object.values(checked).filter(Boolean).length;
      weekTotal += total;
      weekDone += done;

      const row = document.createElement("div");
      row.className = "stats-day-row";
      row.innerHTML = `
        <div class="stats-day-label">${day.month}월 ${day.day}일 (${day.weekday})</div>
        <div class="stats-mini-bar"><div class="stats-mini-fill" style="width:${total ? (done / total) * 100 : 0}%"></div></div>
        <div class="stats-day-count">${done}/${total}</div>
      `;
      row.addEventListener("click", () => {
        const idx = plan.findIndex((d) => d.id === day.id);
        if (idx !== -1) {
          showDay(idx);
          hideProgressView();
        }
      });
      return row;
    });

    const weekHeader = document.createElement("div");
    weekHeader.className = "stats-week-header";
    weekHeader.innerHTML = `
      <span>${week}주차</span>
      <span class="stats-week-count">${weekDone} / ${weekTotal}</span>
    `;

    const weekWrap = document.createElement("div");
    weekWrap.className = "stats-week";
    weekWrap.appendChild(weekHeader);
    dayRows.forEach((r) => weekWrap.appendChild(r));
    statsList.appendChild(weekWrap);
  }
}

function showProgressView() {
  checklistSection.hidden = true;
  progressSection.hidden = false;

  if (statsUnsubscribe) statsUnsubscribe();
  statsUnsubscribe = onSnapshot(collection(db, "progress"), (snap) => {
    const map = {};
    snap.forEach((d) => {
      map[d.id] = d.data().checked || {};
    });
    renderProgressView(map);
  });
}

function hideProgressView() {
  progressSection.hidden = true;
  checklistSection.hidden = false;
  if (statsUnsubscribe) {
    statsUnsubscribe();
    statsUnsubscribe = null;
  }
}

statsBtn.addEventListener("click", showProgressView);
backBtn.addEventListener("click", hideProgressView);

prevBtn.addEventListener("click", () => {
  if (currentIndex > 0) showDay(currentIndex - 1);
});
nextBtn.addEventListener("click", () => {
  if (currentIndex < plan.length - 1) showDay(currentIndex + 1);
});
todayBtn.addEventListener("click", () => showDay(findDefaultIndex()));
weekSelect.addEventListener("change", () => {
  const week = Number(weekSelect.value);
  const idx = plan.findIndex((d) => d.week === week);
  if (idx !== -1) showDay(idx);
});

fetch("data/plan.json")
  .then((res) => res.json())
  .then((data) => {
    plan = data.slice().sort((a, b) => (a.id < b.id ? -1 : 1));
    populateWeekSelect();
    showDay(findDefaultIndex());
  })
  .catch((err) => {
    console.error(err);
    statusMsg.hidden = false;
    statusMsg.textContent = "읽기 계획을 불러올 수 없습니다.";
  });

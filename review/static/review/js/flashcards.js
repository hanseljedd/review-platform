(function () {
  var root = document.getElementById("flashcards-app");
  if (!root) return;
  var cfg = {
    topic: root.getAttribute("data-topic-slug") || "",
    subject: root.getAttribute("data-subject-slug") || "",
    isPremium: (root.getAttribute("data-is-premium") || "false").toLowerCase() === "true",
    featureRandom: (root.getAttribute("data-random-enabled") || "false").toLowerCase() === "true",
    premiumLoginRequired: (root.getAttribute("data-premium-login-required") || "false").toLowerCase() === "true"
  };

  var el = {
    modeSelect: document.getElementById("mode-select"),
    progressCurrent: document.getElementById("progress-current"),
    progressTotal: document.getElementById("progress-total"),
    stateLoading: document.getElementById("state-loading"),
    stateError: document.getElementById("state-error"),
    stateEmpty: document.getElementById("state-empty"),
    stateUpgrade: document.getElementById("state-upgrade"),
    content: document.getElementById("fc-content"),
    questionPrompt: document.getElementById("question-prompt"),
    questionChoices: document.getElementById("question-choices"),
    questionAnswer: document.getElementById("question-answer"),
    revealBtn: document.getElementById("reveal-btn"),
    prevBtn: document.getElementById("prev-btn"),
    nextBtn: document.getElementById("next-btn"),
    retryBtn: document.getElementById("retry-btn"),
    downgradeBtn: document.getElementById("downgrade-btn"),
    flipInner: document.getElementById("flip-inner"),
    flashcardCard: document.getElementById("flashcard-card")
  };

  var defaultPageSizeAttr = root.getAttribute("data-page-size");
  var defaultPageSize = defaultPageSizeAttr ? parseInt(defaultPageSizeAttr, 10) || 200 : 200;
  var state = { mode: "ordered", page: 1, pageSize: defaultPageSize, index: 0, offset: 0, items: [], revealed: false, selected: null };

  function qs(name) {
    var params = new URLSearchParams(window.location.search);
    return params.get(name);
  }
  function applyInitial() {
    // Always start in ordered mode so it matches the table list
    state.mode = "ordered";
    el.modeSelect.value = "ordered";
  }
  function showOnly(target) {
    el.stateLoading.style.display = "none";
    el.stateError.style.display = "none";
    el.stateEmpty.style.display = "none";
    el.stateUpgrade.style.display = "none";
    el.content.style.display = "none";
    target.style.display = target === el.stateLoading ? "flex" : "block";
    if (target === el.content) el.content.style.display = "block";
  }
  function upgradeRequired() {
    var wantsRandom = state.mode === "random";
    if (!wantsRandom) return false;
    // Force random mode to work for logged-in users regardless of server flags
    if (cfg.isPremium) return false;
    // Otherwise fallback to original checks
    if (!cfg.featureRandom) return true;
    if (cfg.premiumLoginRequired && !cfg.isPremium) return true;
    return false;
  }
  function buildUrl() {
    var base = "/api/v1/flashcards/";
    var u = new URL(base, window.location.origin);
    if (cfg.topic) u.searchParams.set("topic", cfg.topic);
    if (cfg.subject) u.searchParams.set("subject", cfg.subject);
    var m = state.mode === "random" && !upgradeRequired() ? "random" : "ordered";
    u.searchParams.set("mode", m);
    u.searchParams.set("page", String(state.page));
    u.searchParams.set("page_size", String(state.pageSize));
    return u.toString();
  }

  function fetchData() {
    showOnly(el.stateLoading);
    fetch(buildUrl(), { credentials: "include" })
      .then(function (r) { if (!r.ok) throw new Error("Bad status: " + r.status); return r.json(); })
      .then(function (json) {
        var results = Array.isArray(json.results) ? json.results : [];
        if (results.length === 0) {
          // Fallback to server-rendered SEO questions if API returns none
          try {
            var seoRaw = document.getElementById('seo-questions');
            if (seoRaw) {
              var seo = JSON.parse(seoRaw.textContent || '[]');
              var fallback = seo.map(function(item){ return { order: item.index, prompt: item.prompt, answer: item.answer_text, choices: [] }; });
              if (fallback.length > 0) {
                state.items = fallback;
                state.index = 0;
                el.progressTotal.textContent = String(fallback.length);
                renderCard();
                showOnly(el.content);
                return;
              }
            }
          } catch(e) {}
          showOnly(el.stateEmpty); return;
        }
        state.items = results.slice();
        // Server handles randomization if mode=random, so no client-side shuffle needed.
        state.index = 0;
        el.progressTotal.textContent = String(json.count || state.items.length); // Use server count if available
        renderCard();
        showOnly(el.content);
      })
      .catch(function () { showOnly(el.stateError); });
  }

  function renderChoices(item) {
    el.questionChoices.innerHTML = "";
    var c = Array.isArray(item.choices) ? item.choices : [];
    c.forEach(function (choice, idx) {
      var row = document.createElement("div"); row.className = "choice";
      var letter = document.createElement("span"); letter.className = "choice-letter";
      // Handle both object {key, text} and simple string formats
      var text = "";
      var key = String.fromCharCode(65 + idx);
      if (typeof choice === "object" && choice !== null) {
          text = choice.text || "";
          key = choice.key || key;
      } else {
          text = String(choice);
      }
      
      letter.textContent = key;
      var label = document.createElement("div"); label.className = "choice-label"; label.textContent = text;
      row.appendChild(letter); row.appendChild(label);
      row.addEventListener("click", function () { if (!state.revealed) { setSelected(idx); } });
      el.questionChoices.appendChild(row);
    });
    if (state.selected !== null) { setSelected(state.selected); }
  }

  function setSelected(idx) {
    state.selected = idx;
    var item = state.items[state.index] || {};
    var choices = Array.isArray(item.choices) ? item.choices : [];
    
    // Find correct index by comparing answer to choice text OR key
    var correctIdx = choices.findIndex(function (v, i) {
        // Determine effective key and text for this choice
        var cText = "";
        var cKey = String.fromCharCode(65 + i); // Default key A, B, C... based on index
        
        if (typeof v === "object" && v !== null) {
            cText = v.text || "";
            if (v.key) cKey = v.key;
        } else {
            cText = String(v);
        }
        
        var ans = String(item.answer || "").trim();
        var txt = String(cText).trim();
        var k = String(cKey).trim();

        // Check if answer matches Text OR Key (case-insensitive for key)
        return (txt === ans) || (k.toLowerCase() === ans.toLowerCase());
    });
    
    var rows = el.questionChoices ? el.questionChoices.children : [];
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      r.classList.remove("choice-selected", "choice-correct", "choice-wrong");
      if (i === idx) {
          // Highlight selected
          if (state.revealed) {
              if (i === correctIdx) r.classList.add("choice-correct");
              else r.classList.add("choice-wrong");
          } else {
              r.classList.add("choice-selected");
          }
      } else if (state.revealed && i === correctIdx) {
          // Always show correct answer when revealed
          r.classList.add("choice-correct");
      }
    }
  }

  function renderCard() {
    var item = state.items[state.index];
    el.questionPrompt.textContent = item && item.prompt ? item.prompt : "";
    renderChoices(item || {});
    el.questionAnswer.textContent = item && item.answer ? String(item.answer) : "";
    if (el.flipInner) el.flipInner.classList.toggle("is-revealed", !!state.revealed);
    var total = parseInt(el.progressTotal.textContent || "0", 10);
    var globalIndex = state.offset + state.index + 1;
    el.progressCurrent.textContent = String(globalIndex);
    el.prevBtn.disabled = (state.offset + state.index) === 0;
    // Keep Next enabled when there are more cards on the server
    var moreOnServer = (state.offset + state.items.length) < total;
    el.nextBtn.disabled = !moreOnServer && state.index >= state.items.length - 1;
    el.revealBtn.disabled = state.revealed;
  }

  function handleNavigation(newIndex) {
    if (state.revealed && el.flipInner) {
      el.flipInner.style.transition = "none";
      el.flipInner.classList.remove("is-revealed");
      state.revealed = false;
      void el.flipInner.offsetHeight;
      state.index = newIndex;
      state.selected = null;
      renderCard();
      requestAnimationFrame(function(){ el.flipInner.style.transition = ""; });
    } else {
      state.index = newIndex; state.revealed = false; state.selected = null; renderCard();
    }
  }
  function next() {
    var total = parseInt(el.progressTotal.textContent || "0", 10);
    if (state.index < state.items.length - 1) {
      handleNavigation(state.index + 1);
    } else if (state.offset + state.items.length < total) {
      // We reached the end of the currently loaded page but server says there are more.
      state.page += 1;
      state.offset += state.items.length;
      state.index = 0;
      state.items = [];
      fetchData();
    }
  }
  function prev() { if (state.index > 0) handleNavigation(state.index - 1); }
  function reveal() {
    state.revealed = !state.revealed; renderCard();
    if (state.revealed && state.selected !== null) { setSelected(state.selected); }
  }

  function bindEvents() {
    el.modeSelect.addEventListener("change", function () {
      state.mode = el.modeSelect.value;
      state.page = 1;
      state.offset = 0;
      state.items = [];
      state.index = 0;
      if (upgradeRequired()) { showOnly(el.stateUpgrade); return; }
      fetchData();
    });
    el.retryBtn && el.retryBtn.addEventListener("click", function () { fetchData(); });
    el.downgradeBtn && el.downgradeBtn.addEventListener("click", function () { state.mode = "ordered"; el.modeSelect.value = "ordered"; fetchData(); });
    el.prevBtn.addEventListener("click", prev);
    el.nextBtn.addEventListener("click", next);
    el.revealBtn.addEventListener("click", reveal);
    document.addEventListener("keydown", function (e) {
      if (e.key === "ArrowRight") next();
      else if (e.key === "ArrowLeft") prev();
      else if (e.key.toLowerCase() === "r") reveal();
      else if (e.key === "ArrowDown") { if (!state.revealed) { var n = (state.selected==null?0:Math.min(state.selected+1,(el.questionChoices.children.length||1)-1)); setSelected(n); } }
      else if (e.key === "ArrowUp") { if (!state.revealed) { var p = (state.selected==null?0:Math.max(state.selected-1,0)); setSelected(p); } }
      else if (e.key === "Enter" || e.key === " ") { reveal(); }
      else if (/^[1-9]$/.test(e.key)) { if (!state.revealed) { var idx = Math.min(parseInt(e.key,10)-1,(el.questionChoices.children.length||1)-1); setSelected(idx); } }
    });
    if (el.flashcardCard) {
      el.flashcardCard.addEventListener("click", function (e) {
        var ignore = e.target.closest("button") || e.target.closest("input") || e.target.closest("select") || e.target.closest("a");
        if (ignore) return;
        reveal();
      });
    }
  }

  (function boot(){ applyInitial(); bindEvents(); if (upgradeRequired()) { showOnly(el.stateUpgrade); } else { fetchData(); } })();
})();

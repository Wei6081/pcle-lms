document.addEventListener("DOMContentLoaded", () => {
  const takeQuizBtn = document.getElementById("takeQuizBtn");
  const chooseStyleBtn = document.getElementById("chooseStyleBtn");
  const varkForm = document.getElementById("varkForm");
  const selectStyle = document.getElementById("selectStyle");
  const resultBox = document.getElementById("result");
  const optionBox = document.querySelector(".option-box");

  if (!resultBox) return;

  const backBtn = document.createElement("button");
  backBtn.textContent = "Back to Main Options";
  backBtn.classList.add("btn", "hidden");
  backBtn.style.marginTop = "15px";
  resultBox.after(backBtn);

  const styleMap = {
    "Visual": "V",
    "Auditory": "A",
    "Reading/Writing": "R",
    "Kinesthetic": "K",
    "V": "V",
    "A": "A",
    "R": "R",
    "K": "K"
  };

  function showMainOptions() {
    if (varkForm) varkForm.classList.add("hidden");
    if (selectStyle) selectStyle.classList.add("hidden");
    resultBox.innerHTML = "";
    backBtn.classList.add("hidden");
    if (optionBox) optionBox.classList.remove("hidden");
  }

  function showBackButton() {
    backBtn.classList.remove("hidden");
  }

  if (takeQuizBtn) {
    takeQuizBtn.addEventListener("click", () => {
      if (varkForm) varkForm.classList.remove("hidden");
      if (selectStyle) selectStyle.classList.add("hidden");
      if (optionBox) optionBox.classList.add("hidden");
      resultBox.innerHTML = "";
    });
  }

  if (chooseStyleBtn) {
    chooseStyleBtn.addEventListener("click", () => {
      if (selectStyle) selectStyle.classList.remove("hidden");
      if (varkForm) varkForm.classList.add("hidden");
      if (optionBox) optionBox.classList.add("hidden");
      resultBox.innerHTML = "";
    });
  }

  backBtn.addEventListener("click", showMainOptions);

  if (varkForm) {
    varkForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const formData = new FormData(varkForm);
      const counts = {
        Visual: 0,
        Auditory: 0,
        "Reading/Writing": 0,
        Kinesthetic: 0
      };

      for (let value of formData.values()) {
        if (counts.hasOwnProperty(value)) {
          counts[value]++;
        }
      }

      const maxScore = Math.max(...Object.values(counts));
      const topStyles = Object.keys(counts).filter(style => counts[style] === maxScore);

      varkForm.classList.add("hidden");
      showBackButton();

      if (topStyles.length === 1) {
        const finalStyle = topStyles[0];
        resultBox.innerHTML = `✅ Your dominant learning style is <strong>${finalStyle}</strong>.`;
        await saveLearningStyleAndRedirect(styleMap[finalStyle]);
      } else {
        showTieSelection(topStyles);
      }
    });
  }

  const submitStyleBtn = document.getElementById("submitStyle");
  if (submitStyleBtn) {
    submitStyleBtn.addEventListener("click", async () => {
      const style = document.getElementById("styleDropdown").value;

      if (!style) {
        alert("Please select a learning style first.");
        return;
      }

      resultBox.innerHTML = `🎯 You selected <strong>${style}</strong> as your learning style.`;
      if (selectStyle) selectStyle.classList.add("hidden");
      showBackButton();

      await saveLearningStyleAndRedirect(styleMap[style]);
    });
  }

  function showTieSelection(topStyles) {
    let buttonsHtml = "";

    topStyles.forEach(style => {
      buttonsHtml += `
        <button type="button" class="btn tie-btn" data-style="${style}" style="margin:8px;">
          ${style}
        </button>
      `;
    });

    resultBox.innerHTML = `
      <div>
        <p><strong>You have mixed preferences:</strong> ${topStyles.join(" and ")}</p>
        <p>Please choose the learning style that best matches how you prefer to learn.</p>
        <div style="margin-top: 15px;">
          ${buttonsHtml}
        </div>
      </div>
    `;

    const tieButtons = document.querySelectorAll(".tie-btn");
    tieButtons.forEach(button => {
      button.addEventListener("click", async () => {
        const chosenStyle = button.dataset.style;
        resultBox.innerHTML = `
          ✅ You have mixed preferences, and you selected
          <strong>${chosenStyle}</strong> as your learning style.
        `;
        await saveLearningStyleAndRedirect(styleMap[chosenStyle]);
      });
    });
  }

  async function saveLearningStyleAndRedirect(abbrevStyle) {
    try {
      const res = await fetch("/save_learning_style", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          learningStyle: abbrevStyle
        })
      });

      const json = await res.json();

      if (!res.ok) {
        throw new Error(json.message || "Unable to save learning style.");
      }

      setTimeout(() => {
        window.location.href = "/content";
      }, 1200);

    } catch (err) {
      console.error("Error saving learning style:", err);
      alert(err.message || "Unable to save learning style. Please try again.");
    }
  }
});
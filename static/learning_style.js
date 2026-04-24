document.addEventListener("DOMContentLoaded", () => {
  const takeQuizBtn = document.getElementById("takeQuizBtn");
  const chooseStyleBtn = document.getElementById("chooseStyleBtn");
  const varkForm = document.getElementById("varkForm");
  const selectStyle = document.getElementById("selectStyle");
  const resultBox = document.getElementById("result");
  const optionBox = document.querySelector(".option-box");

  if (!resultBox) return;

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

  const styleInfo = {
    "Visual": {
      icon: "👁️",
      title: "Visual Learner",
      description: "You usually learn better through diagrams, charts, images, and visual examples.",
      preferred: "Visual materials such as slide notes, diagrams and illustrated content"
    },
    "Auditory": {
      icon: "🎧",
      title: "Auditory Learner",
      description: "You usually learn better through listening, discussion, and spoken explanation.",
      preferred: "Audio or video-based learning materials"
    },
    "Reading/Writing": {
      icon: "📘",
      title: "Reading/Writing Learner",
      description: "You usually learn better through reading and writing, such as notes, text explanations, and guides.",
      preferred: "Text-rich materials such as notes, articles and written explanations"
    },
    "Kinesthetic": {
      icon: "🛠️",
      title: "Kinesthetic Learner",
      description: "You usually learn better through practice, hands-on activities, and learning by doing.",
      preferred: "Practical tasks, activities and interactive learning content"
    }
  };



  function showResultCard(styleName) {
    const info = styleInfo[styleName];
    resultBox.innerHTML = `
      <div class="result-box" style="display:block;">
        <div style="font-size:3rem; margin-bottom:10px;">${info.icon}</div>
        <h3 style="margin-bottom:10px;">Your Learning Style Result</h3>
        <h2 style="margin-top:0; margin-bottom:15px;">${info.title}</h2>
        <p style="margin-bottom:12px;">${info.description}</p>
        <p style="margin-bottom:18px;"><strong>Preferred content format:</strong> ${info.preferred}</p>
        <button type="button" class="btn" id="continueToContentBtn">Continue to Learning Content</button>
      </div>
    `;

    document.getElementById("continueToContentBtn").addEventListener("click", () => {
      window.location.href = "/content";
    });
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
  

      if (topStyles.length === 1) {
        const finalStyle = topStyles[0];
        await saveLearningStyle(styleMap[finalStyle]);
        showResultCard(finalStyle);
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

      if (selectStyle) selectStyle.classList.add("hidden");
  

      await saveLearningStyle(styleMap[style]);
      showResultCard(style);
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
        <div style="margin-top:15px;">
          ${buttonsHtml}
        </div>
      </div>
    `;

    const tieButtons = document.querySelectorAll(".tie-btn");
    tieButtons.forEach(button => {
      button.addEventListener("click", async () => {
        const chosenStyle = button.dataset.style;
        await saveLearningStyle(styleMap[chosenStyle]);
        showResultCard(chosenStyle);
      });
    });
  }

  async function saveLearningStyle(abbrevStyle) {
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
  }
});
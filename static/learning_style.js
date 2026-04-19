// Get all elements
const takeQuizBtn = document.getElementById("takeQuizBtn");
const chooseStyleBtn = document.getElementById("chooseStyleBtn");
const varkForm = document.getElementById("varkForm");
const selectStyle = document.getElementById("selectStyle");
const resultBox = document.getElementById("result");
const optionBox = document.querySelector(".option-box");

// back button (created once)
const backBtn = document.createElement("button");
backBtn.textContent = "Back to Main Options";
backBtn.classList.add("btn");
backBtn.style.marginTop = "15px";
backBtn.classList.add("hidden");
resultBox.after(backBtn);

// Mapping full names to abbreviations
const styleMap = {
  "Visual":"V",
  "Auditory":"A",
  "Reading/Writing":"R",
  "Kinesthetic":"K",
  "V":"V",
  "A":"A",
  "R":"R",
  "K":"K"
};

// helper: show main choice buttons
function showMainOptions() {
  varkForm.classList.add("hidden");
  selectStyle.classList.add("hidden");
  resultBox.innerHTML = "";
  backBtn.classList.add("hidden");
  optionBox.classList.remove("hidden");
}

// Show back button
function showBackButton() {
  backBtn.classList.remove("hidden");
}

// Event listeners for main buttons
takeQuizBtn.addEventListener("click", () => {
  varkForm.classList.remove("hidden");
  selectStyle.classList.add("hidden");
  optionBox.classList.add("hidden");
  resultBox.innerHTML = "";
});

chooseStyleBtn.addEventListener("click", () => {
  selectStyle.classList.remove("hidden");
  varkForm.classList.add("hidden");
  optionBox.classList.add("hidden");
  resultBox.innerHTML = "";
});

// Back button
backBtn.addEventListener("click", showMainOptions);

// --- VARK quiz submit ---
varkForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  // Count answers
  const formData = new FormData(e.target);
  const counts = { Visual:0, Auditory:0, "Reading/Writing":0, Kinesthetic:0 };

  for (let value of formData.values()) {
    if (counts.hasOwnProperty(value)) counts[value]++;
  }

  // Determine dominant style
  const predicted = Object.keys(counts).reduce((a,b)=> counts[a]>=counts[b]?a:b);
  const abbrevStyle = styleMap[predicted];

  // Show result
  resultBox.innerHTML = `✅ Your predicted learning style is <strong>${predicted}</strong>`;
  varkForm.classList.add("hidden");
  showBackButton();

  // Save locally
  localStorage.setItem("learningStyle", abbrevStyle);

  // Save to backend and redirect
  await saveLearningStyleAndRedirect(abbrevStyle);
});

// --- Direct selection (dropdown) ---
document.getElementById("submitStyle").addEventListener("click", async () => {
  const style = document.getElementById("styleDropdown").value;
  if (!style) return alert("Please select a learning style first.");

  const abbrevStyle = styleMap[style];
  resultBox.innerHTML = `🎯 You selected your learning style as <strong>${style}</strong>`;
  selectStyle.classList.add("hidden");
  showBackButton();

  localStorage.setItem("learningStyle", abbrevStyle);
  await saveLearningStyleAndRedirect(abbrevStyle);
});

// --- Save to backend & redirect ---
async function saveLearningStyleAndRedirect(abbrevStyle) {
  try {
    const studentName = localStorage.getItem("studentName") || "";

    const res = await fetch("/save_learning_style", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ studentName: studentName, learningStyle: abbrevStyle })
    });

    const json = await res.json();
    console.log(json.message || "Learning style saved.");

    // Redirect to Flask route (not file name)
    window.location.href = "/content";
  } catch (err) {
    console.error("Error saving learning style:", err);
    alert("Unable to save learning style — please try again.");
  }
}

document.addEventListener("DOMContentLoaded", () => {

  // Proceed to final assessment
  const finalBtn = document.getElementById("finalBtn");

  if (finalBtn) {
    finalBtn.addEventListener("click", () => {

      const moduleName = encodeURIComponent(MODULE_NAME);

      window.location.href = `/final_assessment/${moduleName}`;
    });
  }

});
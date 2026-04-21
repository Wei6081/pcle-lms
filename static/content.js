document.addEventListener("DOMContentLoaded", () => {
  const finalBtn = document.getElementById("finalBtn");

  if (finalBtn) {
    finalBtn.addEventListener("click", async () => {
      try {
        const res = await fetch("/mark_content_complete", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          }
        });

        const data = await res.json();
        console.log(data.message);

        const moduleName = encodeURIComponent(MODULE_NAME);
        window.location.href = `/final_assessment/${moduleName}`;
      } catch (err) {
        console.error("Error marking content complete:", err);
        alert("Unable to continue. Please try again.");
      }
    });
  }
});
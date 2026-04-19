document.getElementById("studentForm")?.addEventListener("submit", async function (event) {
  event.preventDefault();

  const studentId = document.getElementById("studentId").value.trim();
  const studentName = document.getElementById("studentName").value.trim();

  if (!studentId || !studentName) {
    alert("Please enter your student ID and name.");
    return;
  }

  localStorage.setItem("studentId", studentId);
  localStorage.setItem("studentName", studentName);

  window.location.href = "/login";
});

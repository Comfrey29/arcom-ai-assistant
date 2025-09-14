document.addEventListener("DOMContentLoaded", () => {
  const sendBtn = document.getElementById("sendBtn");
  const userInput = document.getElementById("userInput");
  const chatMessages = document.getElementById("chatMessages");

  async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;

    // Mostra el missatge de l’usuari
    appendMessage(message, "user");
    userInput.value = "";
    sendBtn.disabled = true;

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          user_id: "default",
          message: message
        })
      });
      const data = await response.json();

      if (data.respuesta) {
        appendMessage(data.respuesta, "bot");
      } else {
        appendMessage("⚠️ Error: no se recibió respuesta.", "bot");
      }
    } catch (error) {
      appendMessage("⚠️ Error en la conexión con el servidor.", "bot");
    }

    sendBtn.disabled = false;
  }

  function appendMessage(text, sender) {
    const msg = document.createElement("div");
    msg.classList.add("message", sender);
    msg.textContent = text;
    chatMessages.appendChild(msg);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  sendBtn.addEventListener("click", sendMessage);
  userInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
      sendMessage();
    }
  });
});

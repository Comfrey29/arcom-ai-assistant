async function askQuestion() {
    const question = document.getElementById("question").value;
    const answerEl = document.getElementById("answer");

    // Mostrem que està carregant
    answerEl.textContent = "Pensant...";

    try {
        const response = await fetch("/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ prompt: question })
        });

        const data = await response.json();
        answerEl.textContent = data.output || "[ERROR]";
    } catch (err) {
        answerEl.textContent = "[ERROR] " + err.message;
    }
}

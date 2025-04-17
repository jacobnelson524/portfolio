document.addEventListener("DOMContentLoaded", function () {
    const partyId = document.getElementById("party-id").value;
    const resultContainer = document.getElementById("movie-result");
    
    async function fetchSelectedMovie() {
        try {
            const response = await fetch(`/users/watchparty/${partyId}/choose/`);
            const data = await response.json();
            
            if (data.selected_movie) {
                resultContainer.innerHTML = `
                    <p><strong>Genre:</strong> ${data.selected_movie.genre}</p>
                    <p><strong>Director:</strong> ${data.selected_movie.director || "N/A"}</p>
                    <p><strong>Age Rating:</strong> ${data.selected_movie.age_rating || "N/A"}</p>
                `;
            } else {
                resultContainer.innerHTML = "<p>No movies selected yet.</p>";
            }
        } catch (error) {
            console.error("Error fetching selected movie:", error);
        }
    }

    // Poll the server every 5 seconds for updates
    setInterval(fetchSelectedMovie, 5000);
});

document.addEventListener('DOMContentLoaded', function() {
    const applyFiltersButton = document.getElementById('apply_filters');
    const loadingIndicator = document.getElementById('loading');
    const errorMessageDiv = document.getElementById('error_message');
    const excludeGenresSelect = document.getElementById('exclude_genres');

    // Function to fetch data and update charts
    function fetchDataAndUpdateCharts() {
        loadingIndicator.style.display = 'block'; // Show loading
        errorMessageDiv.textContent = ''; // Clear previous errors

        // Get filter values
        const startDate = document.getElementById('start_date').value;
        const endDate = document.getElementById('end_date').value;
        const timeOfDay = document.getElementById('time_of_day').value;

        // Get selected genres to exclude
        const selectedExcludeOptions = Array.from(excludeGenresSelect.selectedOptions).map(opt => opt.value);
        const excludeGenres = selectedExcludeOptions.join(',');

        // Construct API URL with query parameters
        const params = new URLSearchParams({
            start_date: startDate,
            end_date: endDate,
            time_of_day: timeOfDay,
            exclude_genres: excludeGenres
        });
        const apiUrl = `/api/listening_history?${params.toString()}`;

        fetch(apiUrl)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                loadingIndicator.style.display = 'none'; // Hide loading

                if (data.error) {
                   errorMessageDiv.textContent = `Error: ${data.error}`;
                   // Clear charts maybe?
                   clearCharts();
                   return;
                }
                if (data.message){
                     errorMessageDiv.textContent = data.message; // e.g., "No data matches filters"
                     clearCharts(); // Clear charts if no data
                }

                // Populate genre filter ONLY the first time or if needed
                updateGenreFilter(data.available_genres || []);

                // Update charts with the received data
                updateCharts(data);

            })
            .catch(error => {
                loadingIndicator.style.display = 'none'; // Hide loading
                errorMessageDiv.textContent = `Workspace error: ${error.message}`;
                console.error('Error fetching history data:', error);
                clearCharts();
            });
    }

    let genresPopulated = false; // Flag to prevent repopulating genre list unnecessarily
    function updateGenreFilter(availableGenres) {
        if (genresPopulated && excludeGenresSelect.options.length > 0) return; // Only populate once unless empty

        // Remember currently selected values
         const previouslySelected = new Set(Array.from(excludeGenresSelect.selectedOptions).map(opt => opt.value));

        excludeGenresSelect.innerHTML = ''; // Clear existing options
        availableGenres.forEach(genre => {
            const option = document.createElement('option');
            option.value = genre;
            option.textContent = genre;
            if (previouslySelected.has(genre)) {
                option.selected = true; // Re-select if it was selected before
            }
            excludeGenresSelect.appendChild(option);
        });
         genresPopulated = availableGenres.length > 0; // Set flag if genres were added
    }


    function updateCharts(data) {
        // --- Top Artists Chart (Plotly Example) ---
        const topArtists = data.top_artists || [];
        const artistNames = topArtists.map(a => a.artist);
        const artistCounts = topArtists.map(a => a.count);

        const artistTrace = {
            x: artistNames,
            y: artistCounts,
            type: 'bar',
            marker: { color: '#1DB954' } // Spotify green
        };
        const artistLayout = {
            title: 'Top Artists (Filtered)',
            xaxis: { title: 'Artist' },
            yaxis: { title: 'Play Count' },
            margin: { l: 50, r: 30, b: 100, t: 50 } // Adjust margins
        };
         if(artistNames.length > 0){
            Plotly.newPlot('top_artists_chart', [artistTrace], artistLayout);
        } else {
             document.getElementById('top_artists_chart').innerHTML = '<p>No artist data for this selection.</p>';
        }


        // --- Top Tracks Chart (Plotly Example) ---
        const topTracks = data.top_tracks || [];
        // Combine track and artist for unique labels if needed
        const trackLabels = topTracks.map(t => `${t.track_name} - ${t.artist_name}`);
        const trackCounts = topTracks.map(t => t.count);

        const trackTrace = {
            x: trackLabels,
            y: trackCounts,
            type: 'bar',
             marker: { color: '#17A2B8' } // A different color
        };
        const trackLayout = {
            title: 'Top Tracks (Filtered)',
            xaxis: { title: 'Track' },
            yaxis: { title: 'Play Count' },
             margin: { l: 50, r: 30, b: 150, t: 50 } // Adjust margins for long labels
        };

        if(trackLabels.length > 0){
            Plotly.newPlot('top_tracks_chart', [trackTrace], trackLayout);
         } else {
             document.getElementById('top_tracks_chart').innerHTML = '<p>No track data for this selection.</p>';
         }

        // --- Add more chart updates here ---
    }

     function clearCharts() {
         document.getElementById('top_artists_chart').innerHTML = '';
         document.getElementById('top_tracks_chart').innerHTML = '';
         // Clear other charts if added
     }

    // Add event listener to the button
    if (applyFiltersButton) {
        applyFiltersButton.addEventListener('click', fetchDataAndUpdateCharts);
    }

    // Initial data load when the page loads (optional, or wait for first filter click)
     fetchDataAndUpdateCharts();

});
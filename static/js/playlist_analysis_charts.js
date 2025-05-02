// static/js/playlist_analysis_charts.js

console.log("playlist_analysis_charts.js script started");

document.addEventListener('DOMContentLoaded', function() {
    console.log("Playlist Analysis Page: DOM Content Loaded");

    // Check if the data object specific to this page exists
    // Note the variable name matches the one embedded in playlist_analysis.html
    if (typeof playlistAnalysisVizData !== 'undefined' && playlistAnalysisVizData) {
        console.log("playlistAnalysisVizData found:", JSON.stringify(playlistAnalysisVizData, null, 2));
        try {
            renderPlaylistAnalysisCharts(playlistAnalysisVizData);
            // --- NEW: Scatter Plot Setup ---
            const scatterData = playlistAnalysisVizData.scatter_plot_data;
            const xAxisSelect = document.getElementById('scatter-x-axis');
            const yAxisSelect = document.getElementById('scatter-y-axis');

            // Function to render/update the scatter plot
            function updateScatterPlot() {
                const xFeature = xAxisSelect.value;
                const yFeature = yAxisSelect.value;
                console.log(`Updating scatter plot: X=${xFeature}, Y=${yFeature}`);

                if (!scatterData || scatterData.length === 0) {
                    document.getElementById('playlist_scatter_plot').innerHTML = '<p>No track data for scatter plot.</p>';
                    return;
                }

                // Extract data, handling potential null/undefined values
                const xValues = scatterData.map(track => track[xFeature] ?? null); // Use nullish coalescing
                const yValues = scatterData.map(track => track[yFeature] ?? null);
                const hoverTexts = scatterData.map(track =>
                    `Track: ${track.name || 'N/A'}<br>Artist: ${Array.isArray(track.artists) ? track.artists.join(', ') : 'N/A'}<br>${xFeature}: ${track[xFeature] ?? 'N/A'}<br>${yFeature}: ${track[yFeature] ?? 'N/A'}`
                );

                const trace = {
                    x: xValues,
                    y: yValues,
                    mode: 'markers',
                    type: 'scatter',
                    text: hoverTexts,
                    hoverinfo: 'text',
                    marker: {
                        size: 8,
                        color: yValues, // Color points by Y value (e.g., popularity)
                        colorscale: 'Viridis', // Choose a colorscale
                        opacity: 0.7,
                        colorbar: {
                        title: yFeature.charAt(0).toUpperCase() + yFeature.slice(1) // Capitalize Y feature name
                        }
                    }
                };

                // Capitalize feature names for axis titles
                const formatAxisTitle = (feature) => feature.charAt(0).toUpperCase() + feature.slice(1);

                const layout = {
                    xaxis: { title: formatAxisTitle(xFeature), automargin: true },
                    yaxis: { title: formatAxisTitle(yFeature), automargin: true },
                    margin: { l: 60, r: 30, b: 50, t: 40 },
                    hovermode: 'closest', // Improve hover interaction
                    hoverlabel: { bgcolor: "#FFF", font: { color: "#000", size: 12 }, bordercolor: '#ccc' }
                };

                Plotly.newPlot('playlist_scatter_plot', [trace], layout, {responsive: true});
                console.log("Scatter plot updated.");
            }

            // Add event listeners to dropdowns
            xAxisSelect.addEventListener('change', updateScatterPlot);
            yAxisSelect.addEventListener('change', updateScatterPlot);

            // Initial render with default selections
            updateScatterPlot();
            console.log("renderPlaylistAnalysisCharts function finished.");
        } catch (error) {
            console.error("Error calling renderPlaylistAnalysisCharts:", error);
        }
    } else {
        console.warn("playlistAnalysisVizData is undefined or null. Cannot render charts.");
         const playlistChartDivs = ['playlist_top_artists_chart', 'playlist_top_genres_chart'];
         playlistChartDivs.forEach(divId => {
             const element = document.getElementById(divId);
             // Add message only if div exists and is empty (and no error message already shown)
             if (element && element.innerHTML.trim() === '' && !document.querySelector('.error-message')) {
                  element.innerHTML = '<p>Chart data not available for this playlist.</p>';
             }
         });
    }
});

/**
 * Renders charts specific to the Playlist Analysis page.
 * @param {object} data - The visualization data object for the analyzed playlist.
 * Expected structure:
 * {
 * top_artists: [ { artist: 'Artist Name', count: N }, ... ],
 * top_genres: [ { genre: 'Genre Name', count: N }, ... ],
 * // total_tracks, unique_artists, unique_genres also present but not used here
 * }
 */
function renderPlaylistAnalysisCharts(data) {
    console.log("Inside renderPlaylistAnalysisCharts function.");

     // --- Most Followed Artists Chart ---
    try {
        const artists = data.top_followed_artists || [];
        if (artists.length > 0) {
            const artistNames = artists.map(a => a.name);
            const artistFollowers = artists.map(a => a.followers);
            const trace = {
                y: artistNames.reverse(),
                x: artistFollowers.reverse(),
                text: artistFollowers.map(f => `${f.toLocaleString()} followers`),
                hoverinfo: 'text+y',
                type: 'bar', orientation: 'h', marker: { color: '#0d6efd' } // Blue
            };
             const layout = { /* ... similar layout ... */
                 xaxis: { title: 'Total Followers', automargin: true },
                 yaxis: { automargin: true },
                 margin: { l: 150, r: 30, b: 50, t: 30 }
             };
            Plotly.newPlot('playlist_most_followed_artists_chart', [trace], layout, {responsive: true});
        } else { document.getElementById('playlist_most_followed_artists_chart').innerHTML = '<p>No data</p>';}
    } catch(e) { console.error("Error rendering most followed artists chart:", e); }

     // --- Least Followed Artists Chart ---
    try {
        const artists = data.bottom_followed_artists || [];
        if (artists.length > 0) {
             const artistNames = artists.map(a => a.name);
            const artistFollowers = artists.map(a => a.followers);
            const trace = {
                y: artistNames.reverse(),
                x: artistFollowers.reverse(), // Already sorted ascending, reverse for plot
                text: artistFollowers.map(f => `${f.toLocaleString()} followers`),
                hoverinfo: 'text+y',
                type: 'bar', orientation: 'h', marker: { color: '#6c757d' } // Grey
            };
             const layout = { /* ... similar layout ... */
                xaxis: { title: 'Total Followers', automargin: true },
                 yaxis: { automargin: true },
                 margin: { l: 150, r: 30, b: 50, t: 30 }
             };
            Plotly.newPlot('playlist_least_followed_artists_chart', [trace], layout, {responsive: true});
        } else { document.getElementById('playlist_least_followed_artists_chart').innerHTML = '<p>No data</p>';}
    } catch(e) { console.error("Error rendering least followed artists chart:", e); }

    // --- Top 10 Artists Chart (Playlist) ---
    try {
        console.log("Processing playlist artists chart...");
        const topArtists = data.top_artists || [];

        if (topArtists.length > 0) {
             console.log("Playlist artists data (first item):", topArtists[0]);
            const artistNames = topArtists.map(a => a.artist);
            const artistCounts = topArtists.map(a => a.count); // Count of tracks in playlist

            const artistTrace = {
                x: artistNames,
                y: artistCounts,
                text: artistCounts.map(c => `${c} track(s)`),
                hoverinfo: 'x+text',
                type: 'bar',
                orientation: 'v',
                marker: { color: '#1DB954' } // Use consistent colors
            };
            const artistLayout = {
                yaxis: { title: 'Number of Tracks in Playlist', automargin: true },
                xaxis: { tickangle: -30, automargin: true },
                margin: { l: 60, r: 30, b: 100, t: 40 },
                 hoverlabel: { bgcolor: "#FFF", font: { color: "#000" } }
            };

            console.log("Plotting playlist artists chart...");
            // Use the unique div ID from playlist_analysis.html
            Plotly.newPlot('playlist_top_artists_chart', [artistTrace], artistLayout, {responsive: true});
            console.log("Playlist artists chart plotted.");
        } else {
             console.log("No top artists data to plot for playlist.");
            document.getElementById('playlist_top_artists_chart').innerHTML = '<p>No top artists data available for this playlist.</p>';
        }
    } catch(error) {
        console.error("Error rendering playlist artists chart:", error);
         document.getElementById('playlist_top_artists_chart').innerHTML = '<p>Error displaying playlist artists chart.</p>';
    }

    // --- Top 10 Genres Chart (Playlist) ---
    try {
         console.log("Processing playlist genres chart...");
        const topGenres = data.top_genres || [];

        if (topGenres.length > 0) {
            console.log("Playlist genres data (first item):", topGenres[0]);
            const genreNames = topGenres.map(g => g.genre);
            const genreCounts = topGenres.map(g => g.count); // Count of tracks in playlist

            const genreTrace = {
                x: genreNames,
                y: genreCounts,
                 text: genreCounts.map(c => `${c} track(s)`),
                hoverinfo: 'x+text',
                type: 'bar',
                orientation: 'v',
                marker: { color: '#FFC107' } // Use consistent colors
            };
            const genreLayout = {
                yaxis: { title: 'Number of Tracks in Playlist', automargin: true },
                 xaxis: { tickangle: -30, automargin: true },
                margin: { l: 60, r: 30, b: 100, t: 40 },
                 hoverlabel: { bgcolor: "#FFF", font: { color: "#000" } }
            };

            console.log("Plotting playlist genres chart...");
             // Use the unique div ID from playlist_analysis.html
            Plotly.newPlot('playlist_top_genres_chart', [genreTrace], genreLayout, {responsive: true});
            console.log("Playlist genres chart plotted.");
        } else {
             console.log("No top genres data to plot for playlist.");
            document.getElementById('playlist_top_genres_chart').innerHTML = '<p>No top genres data available for this playlist.</p>';
        }
    } catch (error) {
         console.error("Error rendering playlist genres chart:", error);
         document.getElementById('playlist_top_genres_chart').innerHTML = '<p>Error displaying playlist genres chart.</p>';
    }
}
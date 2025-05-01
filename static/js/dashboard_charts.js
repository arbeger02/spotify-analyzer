// static/js/dashboard_charts.js

console.log("dashboard_charts.js script started"); // Log: Script execution begins

document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM Content Loaded event fired"); // Log: DOM is ready

    // Check if the main data object exists (it's created in the HTML script tag)
    if (typeof dashboardVizData !== 'undefined' && dashboardVizData) {
        // Log the received data structure for verification
        console.log("dashboardVizData found:", JSON.stringify(dashboardVizData, null, 2)); // Pretty print JSON for readability

        try {
            // Call the main function to render all charts
            renderDashboardCharts(dashboardVizData);
            console.log("renderDashboardCharts function finished successfully."); // Log: Chart rendering attempted
        } catch (error) {
            // Catch any unexpected errors during the chart rendering process
            console.error("Error calling renderDashboardCharts:", error);
        }
    } else {
        // Log a warning if the data object is missing
        console.warn("dashboardVizData is undefined, null, or empty. Cannot render charts.");

        // Optionally display a message in the chart divs if data is missing
        const chartDivIds = ['top_artists_chart', 'top_tracks_chart', 'top_genres_chart'];
        chartDivIds.forEach(divId => {
            const element = document.getElementById(divId);
            // Add message only if the element exists and doesn't already have specific content
            if (element && element.innerHTML.trim() === '') {
                 element.innerHTML = '<p>Could not load chart data. Data object missing.</p>';
            }
        });
    }
});

/**
 * Renders the Top Artists, Top Tracks, and Top Genres charts using Plotly.
 * @param {object} data - The visualization data object passed from the backend.
 * Expected structure:
 * {
 * artists_chart: [ { name: 'Artist Name', track_count: N, ... }, ... ],
 * tracks_chart: [ { name: 'Track Name', artists: ['Artist'], rank: N, ... }, ... ],
 * genres_chart: [ ['Genre Name', count], ... ],
 * // artists_raw and tracks_raw are also present but not used directly here
 * }
 */
function renderDashboardCharts(data) {
    console.log("Inside renderDashboardCharts function."); // Log: Function entry

    // --- Top Genres Chart ---
    try {
        console.log("Processing genres chart...");
        // Use the 'genres_chart' key which holds [ ['genre_name', count], ... ]
        const topGenres = data.genres_chart || [];

        if (topGenres.length > 0) {
            console.log("Genre chart data (first item):", topGenres[0]); // Log sample data point
            const genreNames = topGenres.map(g => g[0]); // g[0] is genre name
            const genreCounts = topGenres.map(g => g[1]); // g[1] is count

            const genreTrace = {
                x: genreNames,
                y: genreCounts,
                text: genreCounts.map(c => `${c} tracks`), // Show count on hover
                hoverinfo: 'x+text',
                type: 'bar',
                orientation: 'v',
                marker: {
                    color: '#FFC107', // Amber/Yellow
                     line: {
                       color: '#d39e00',
                       width: 1
                   }
                 }
            };
            const genreLayout = {
                yaxis: {
                    title: 'Frequency in Top Artists',
                    automargin: true
                 },
                 xaxis: {
                    tickangle: -45, // Angle labels
                    automargin: true
                 },
                margin: { l: 50, r: 30, b: 120, t: 40 }, // Adjust bottom margin
                 hoverlabel: { bgcolor: "#FFF", font: { color: "#000" } }
            };

            console.log("Plotting genres chart...");
            Plotly.newPlot('top_genres_chart', [genreTrace], genreLayout, {responsive: true});
            console.log("Genre chart plotted.");
         } else {
             console.log("No genre data to plot.");
             document.getElementById('top_genres_chart').innerHTML = '<p>No top genres data derived from top artists for this period.</p>';
         }
    } catch (error) {
        console.error("Error rendering genres chart:", error);
         document.getElementById('top_genres_chart').innerHTML = '<p>Error displaying genres chart.</p>';
    }
}
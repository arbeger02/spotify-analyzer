// static/js/liked_songs_charts.js

console.log("liked_songs_charts.js script started");

document.addEventListener('DOMContentLoaded', function() {
    console.log("Liked Songs Page: DOM Content Loaded");

    // Check if the data object specific to this page exists
    if (typeof likedSongsVizData !== 'undefined' && likedSongsVizData) {
        console.log("likedSongsVizData found:", JSON.stringify(likedSongsVizData, null, 2));
        try {
            renderLikedSongsCharts(likedSongsVizData);
            console.log("renderLikedSongsCharts function finished.");
        } catch (error) {
            console.error("Error calling renderLikedSongsCharts:", error);
        }
    } else {
        console.warn("likedSongsVizData is undefined or null. Cannot render charts.");
        // Optional: display message in chart divs if needed
         const likedChartDivs = ['liked_top_artists_chart', 'liked_top_genres_chart'];
         likedChartDivs.forEach(divId => {
             const element = document.getElementById(divId);
             if (element && element.innerHTML.trim() === '') {
                  element.innerHTML = '<p>Could not load chart data for liked songs.</p>';
             }
         });
    }
});

/**
 * Renders charts specific to the Liked Songs page.
 * @param {object} data - The visualization data object for liked songs.
 * Expected structure:
 * {
 * top_artists: [ { artist: 'Artist Name', count: N }, ... ],
 * top_genres: [ { genre: 'Genre Name', count: N }, ... ]
 * }
 */
function renderLikedSongsCharts(data) {
    console.log("Inside renderLikedSongsCharts function.");

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
            Plotly.newPlot('liked_most_followed_artists_chart', [trace], layout, {responsive: true});
        } else { document.getElementById('liked_most_followed_artists_chart').innerHTML = '<p>No data</p>';}
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
            Plotly.newPlot('liked_least_followed_artists_chart', [trace], layout, {responsive: true});
        } else { document.getElementById('liked_least_followed_artists_chart').innerHTML = '<p>No data</p>';}
    } catch(e) { console.error("Error rendering least followed artists chart:", e); }

    // --- Top 10 Artists Chart (Liked Songs) ---
    try {
        console.log("Processing liked artists chart...");
        const topArtists = data.top_artists || [];

        if (topArtists.length > 0) {
             console.log("Liked artists data (first item):", topArtists[0]);
            const artistNames = topArtists.map(a => a.artist);
            const artistCounts = topArtists.map(a => a.count);

            const artistTrace = {
                x: artistNames,
                y: artistCounts,
                text: artistCounts.map(c => `${c} tracks(s)`),
                hoverinfo: 'x+text',
                type: 'bar',
                orientation: 'v',
                marker: { color: '#1DB954' } // Use consistent color or choose another
            };
            const artistLayout = {
                yaxis: { title: 'Number of Liked Songs', automargin: true },
                xaxis: { tickangle: -30, automargin: true }, // Less angle if fewer items
                margin: { l: 60, r: 30, b: 100, t: 40 },
                 hoverlabel: { bgcolor: "#FFF", font: { color: "#000" } }
            };

            console.log("Plotting liked artists chart...");
            Plotly.newPlot('liked_top_artists_chart', [artistTrace], artistLayout, {responsive: true});
            console.log("Liked artists chart plotted.");
        } else {
             console.log("No liked artists data to plot.");
            document.getElementById('liked_top_artists_chart').innerHTML = '<p>No top artists data available for liked songs.</p>';
        }
    } catch(error) {
        console.error("Error rendering liked artists chart:", error);
         document.getElementById('liked_top_artists_chart').innerHTML = '<p>Error displaying liked artists chart.</p>';
    }


    // --- Top 10 Genres Chart (Liked Songs) ---
    try {
         console.log("Processing liked genres chart...");
        const topGenres = data.top_genres || [];

        if (topGenres.length > 0) {
            console.log("Liked genres data (first item):", topGenres[0]);
            const genreNames = topGenres.map(g => g.genre);
            const genreCounts = topGenres.map(g => g.count);

            const genreTrace = {
                x: genreNames,
                y: genreCounts,
                 text: genreCounts.map(c => `${c} track(s)`),
                hoverinfo: 'x+text',
                type: 'bar',
                orientation: 'v',
                marker: { color: '#FFC107' } // Use consistent color or choose another
            };
            const genreLayout = {
                yaxis: { title: 'Number of Liked Songs', automargin: true },
                 xaxis: { tickangle: -30, automargin: true }, // Less angle if fewer items
                margin: { l: 60, r: 30, b: 100, t: 40 },
                 hoverlabel: { bgcolor: "#FFF", font: { color: "#000" } }
            };

            console.log("Plotting liked genres chart...");
            Plotly.newPlot('liked_top_genres_chart', [genreTrace], genreLayout, {responsive: true});
            console.log("Liked genres chart plotted.");
        } else {
             console.log("No liked genres data to plot.");
            document.getElementById('liked_top_genres_chart').innerHTML = '<p>No top genres data available for liked songs.</p>';
        }
    } catch (error) {
         console.error("Error rendering liked genres chart:", error);
         document.getElementById('liked_top_genres_chart').innerHTML = '<p>Error displaying liked genres chart.</p>';
    }
}
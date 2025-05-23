# Spotify Analyzer 🎧📊

Spotify Analyzer is a web application that provides insights into your Spotify listening habits. Connect your Spotify account to explore your top artists and tracks, analyze your liked songs, and dive deep into the characteristics of any playlist.

## Features ✨

* **Dashboard Overview**:
    * View your top artists and tracks across different time periods (last 4 weeks, last 6 months, last 12 months).
    * See raw data tables for your top artists and tracks.
    * Discover your top genres based on your listening history.
* **Liked Songs Analysis**:
    * Get a summary of your liked songs, including total tracks, unique artists, and unique genres.
    * View charts of your top 10 artists and top 10 genres from your liked songs.
    * See tables of your most and least popular liked tracks.
    * Discover the most and least followed artists among those you've liked.
* **Playlist Analysis**:
    * Enter any Spotify playlist URL or ID to get a detailed analysis.
    * View overall statistics like total tracks, unique artists, and unique genres in the playlist.
    * See the average popularity of tracks in the playlist.
    * Explore charts for the top 10 artists and genres within the playlist.
    * Identify the most and least popular tracks in the playlist.
    * See the most and least followed artists featured in the playlist.
* **Secure Authentication**: Uses Spotify OAuth 2.0 for secure access to your data.

## Getting Started 🚀

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

* Python 3.x
* A Spotify Developer account and API credentials (Client ID, Client Secret). You can create an app at the [Spotify Developer Dashboard](http://googleusercontent.com/spotify.com/dashboard/applications).

### Installation & Setup

1.  **Clone the repository (or download the files):**
    ```bash
    git clone <your-repository-link>
    cd spotify-analyzer
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    The project uses several Python libraries, listed in `requirements.txt`.
    ```bash
    pip install -r requirements.txt
    ```
    Key dependencies include:
    * Flask (for the web framework)
    * Spotipy (Python client for the Spotify Web API)
    * Flask-Session (for server-side sessions)
    * python-dotenv (for managing environment variables)
    * Pandas & NumPy (for data manipulation, though direct audio feature analysis has been removed)

4.  **Set up Environment Variables:**
    Create a `.env` file in the root directory of the project. Add your Spotify API credentials and a secret key for Flask sessions:
    ```env
    SPOTIPY_CLIENT_ID='YOUR_SPOTIFY_CLIENT_ID'
    SPOTIPY_CLIENT_SECRET='YOUR_SPOTIFY_CLIENT_SECRET'
    SPOTIPY_REDIRECT_URI='http://localhost:5000/callback' # Or your configured redirect URI
    FLASK_SECRET_KEY='YOUR_FLASK_SECRET_KEY' # A strong, random string
    ```
    * **Important**: Ensure your `SPOTIPY_REDIRECT_URI` in the `.env` file matches the Redirect URI you set in your Spotify Developer Dashboard application settings. For local development, `http://localhost:5000/callback` is common.

5.  **Run the application:**
    ```bash
    python app.py
    ```
    The application will typically be available at `http://localhost:5000`.

## Project Structure 📁
```
spotify-analyzer/
├── app.py                     # Main Flask application logic
├── requirements.txt           # Python package dependencies
├── .env                       # (You create this) Environment variables (API keys, secret key)
├── static/
│   ├── css/
│   │   └── style.css          # Main stylesheet for the application
│   └── js/
│       ├── dashboard_charts.js # JavaScript for Dashboard charts
│       ├── liked_songs_charts.js # JavaScript for Liked Songs charts
│       ├── playlist_analysis_charts.js # JavaScript for Playlist Analysis charts
│       └── main.js            # (Potentially general client-side JS, though content was for history page)
└── templates/
├── base.html              # Base HTML template with header and footer
├── dashboard.html         # HTML template for the main dashboard
├── liked_songs.html       # HTML template for liked songs analysis
├── login.html             # HTML template for the login page
└── playlist_analysis.html # HTML template for playlist analysis
```
## How to Use 🧭

1.  **Navigate to the application** in your web browser (e.g., `http://localhost:5000`).
2.  You will be redirected to the **Login Page**. Click the "Login with Spotify" button.
3.  You'll be taken to Spotify to authorize the application. Grant the requested permissions.
4.  After successful authorization, you'll be redirected to the **Dashboard**.
    * Here, you can see your top artists and tracks for different time ranges.
    * Use the time range buttons ("Last 4 Weeks", "Last 6 Months", "Last 12 Months") to filter the data.
5.  Navigate to **Liked Songs** using the header navigation to see an analysis of all your saved/liked tracks on Spotify.
6.  Navigate to **Playlist Analysis** to analyze any Spotify playlist.
    * Enter the URL or ID of a Spotify playlist into the input field and click "Analyze Playlist".
    * The page will display statistics and charts related to that playlist.
7.  **Logout** using the button in the header when you're done.

## Future Enhancements (Ideas) 💡

* Historical listening trends (if Spotify API allows easy access to more granular history).
* Deeper genre analysis and exploration.
* Recommendations based on listening habits.
* Ability to compare multiple playlists.
* More interactive visualizations.

## Contributing 🤝

Contributions are welcome! If you have ideas for improvements or find any bugs, please feel free to open an issue or submit a pull request.

---

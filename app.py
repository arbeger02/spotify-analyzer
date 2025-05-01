import os
import re
import time
import pandas as pd
from flask import Flask, request, redirect, session, url_for, render_template, jsonify
from flask_session import Session 
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from datetime import datetime, timedelta, time as dt_time
import pytz 
from collections import Counter
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
# Configure server-side session (safer than client-side for tokens)
app.config['SESSION_TYPE'] = 'filesystem' # Or use redis, memcached, etc.
app.config['SESSION_PERMANENT'] = False # Session expires when browser closes
Session(app)

# Spotify API Scopes (Permissions your app needs)
# Adjust scopes based on the data you need
SCOPES = 'user-read-recently-played user-library-read user-top-read'

# --- Authentication Routes ---

def get_spotify_oauth():
    """Creates and returns a SpotifyOAuth object."""
    return SpotifyOAuth(
        client_id=os.getenv('SPOTIPY_CLIENT_ID'),
        client_secret=os.getenv('SPOTIPY_CLIENT_SECRET'),
        redirect_uri=os.getenv('SPOTIPY_REDIRECT_URI'),
        scope=SCOPES,
        cache_path=None # Don't use file cache with web sessions
    )

def get_token_info():
    """Retrieves token info from the session."""
    return session.get('token_info', None)

def set_token_info(token_info):
    """Saves token info to the session."""
    session['token_info'] = token_info
    session.modified = True # Ensure session is saved

def create_spotify_client():
    """Creates a Spotipy client with the current user's token."""
    token_info = get_token_info()
    if not token_info:
        logging.warning("No token info found in session.")
        return None # Or raise an exception/redirect to login

    # Check if token is expired and refresh if needed
    now = int(time.time())
    is_expired = token_info.get('expires_at', 0) - now < 60 # Refresh if expires in < 60 secs

    if is_expired:
        logging.info("Token expired, attempting refresh.")
        sp_oauth = get_spotify_oauth()
        try:
            token_info = sp_oauth.refresh_access_token(token_info.get('refresh_token'))
            set_token_info(token_info)
            logging.info("Token refreshed successfully.")
        except Exception as e:
            logging.error(f"Error refreshing token: {e}")
            # Clear potentially invalid token and force re-login
            session.pop('token_info', None)
            return None

    return spotipy.Spotify(auth=token_info.get('access_token'))

@app.route('/')
def home():
    token_info = get_token_info()
    if not token_info:
        # <<< If not logged in, show the login page >>>
        return redirect(url_for('login_page'))
    # User is logged in, redirect to dashboard
    return redirect(url_for('dashboard'))

# --- Route to display the actual login page ---
@app.route('/login_page')
def login_page():
    # Get potential messages from query parameters (e.g., after logout or error)
    message = request.args.get('message')
    error = request.args.get('error')
    # Render the login template
    return render_template('login.html', message=message, error=error)

@app.route('/login')
def login():
    sp_oauth = get_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    logging.info(f"Redirecting to Spotify auth URL: {auth_url}")
    return redirect(auth_url)

@app.route('/callback')
def callback():
    sp_oauth = get_spotify_oauth()
    session.clear()
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        logging.error(f"Spotify authorization failed with error: {error}")
        return redirect(url_for('login', error=f"Authorization failed: {error}"))
    if not code:
        logging.error("Callback received no code.")
        return redirect(url_for('login', error='Authorization failed (no code)'))
    try:
        # Request token using the auth code
        token_info = sp_oauth.get_access_token(code, check_cache=False)
        if not token_info:
             raise Exception("Failed to retrieve token info.")

        set_token_info(token_info)
        logging.info("Token obtained and stored in session.")
        return redirect(url_for('dashboard'))
    except Exception as e:
        logging.error(f"Error getting or storing token: {e}")
        # Log the full exception for debugging if needed
        # logging.exception("Detailed token error:")
        return redirect(url_for('login', error=f'Could not get token: {e}'))

@app.route('/logout')
def logout():
    session.clear() # Clear the user's session data (including tokens)
    logging.info("User logged out, session cleared.")
    # <<< Redirect to the login page with a confirmation message >>>
    return redirect(url_for('login_page', message="You have been successfully logged out."))

# --- UPDATED Dashboard Route ---
@app.route('/dashboard')
def dashboard():
    sp = create_spotify_client()
    if not sp:
        return redirect(url_for('login'))

    # Get selected time range from query param, default to medium_term
    time_range = request.args.get('time_range', 'medium_term')
    # Validate time_range
    if time_range not in ['short_term', 'medium_term', 'long_term']:
        time_range = 'medium_term' # Default to medium if invalid value passed

    try:
        user_info = sp.current_user()
        username = user_info.get('display_name', 'User')

        # --- Fetch Top Data from Spotify ---
        limit = 50 # How many top items to fetch (adjust as needed)

        # Fetch Top Artists
        top_artists_results = sp.current_user_top_artists(time_range=time_range, limit=limit)
        top_artists_raw = top_artists_results.get('items', [])

        # Fetch Top Tracks
        top_tracks_results = sp.current_user_top_tracks(time_range=time_range, limit=limit)
        top_tracks_raw = top_tracks_results.get('items', [])

                # --- Calculate Artist Counts from Top Tracks ---
        artist_track_counts = Counter()
        if top_tracks_raw:
            for track in top_tracks_raw:
                if track and track.get('artists'):
                    # Count based on the primary artist of the track
                    primary_artist_id = track['artists'][0]['id']
                    if primary_artist_id:
                        artist_track_counts[primary_artist_id] += 1

        # --- Prepare Top Artists data for Chart ---
        # Use artists from the top_artists list, but add their count from top_tracks
        top_artists_for_chart = []
        displayed_artist_ids = set() # Avoid duplicates if limit > 50 somehow allows it
        if top_artists_raw:
            for artist in top_artists_raw:
                if artist and artist.get('id') and artist['id'] not in displayed_artist_ids:
                    artist_id = artist['id']
                    top_artists_for_chart.append({
                        'id': artist_id,
                        'name': artist.get('name', 'N/A'),
                        'track_count': artist_track_counts.get(artist_id, 0),
                        'image_url': artist['images'][0]['url'] if artist.get('images') else None,
                        'genres': artist.get('genres', [])
                    })
                    displayed_artist_ids.add(artist_id)

        # Sort artists for chart by track_count (descending) and take top 10
        top_artists_for_chart.sort(key=lambda x: x['track_count'], reverse=True)
        top_artists_for_chart = top_artists_for_chart[:10] # <<< LIMIT TO 10 HERE

        # --- Prepare Top Tracks data for List (Limit to Top 10) ---
        top_tracks_for_list = [] # Renamed variable for clarity
        if top_tracks_raw:
            for i, track in enumerate(top_tracks_raw[:10]): # <<< LIMIT TO 10 HERE
                if track:
                    primary_artist_names = [a.get('name', 'N/A') for a in track.get('artists', [])]
                    album_images = track.get('album', {}).get('images', [])
                    image_url = album_images[0]['url'] if album_images else None # Get largest image URL

                    top_tracks_for_list.append({ # Renamed variable
                        'id': track.get('id'),
                        'name': track.get('name', 'N/A'),
                        'artists': primary_artist_names, # List of artist names
                        'album': track.get('album', {}).get('name', 'N/A'),
                        'image_url': image_url # <<< Ensure image URL is included
                    })

        # --- Derive Top Genres from Top Artists ---
        genre_counts = Counter()
        if top_artists_raw:
            for artist in top_artists_raw:
                genres = artist.get('genres', [])
                if genres:
                    for genre in genres:
                        if genre:
                            genre_counts[genre] += 1

        # Get the top N genres (e.g., top 10)
        top_genres = genre_counts.most_common(10)

        # --- Final Data for Template ---
        viz_data = {
            "artists_chart": top_artists_for_chart, # Data specifically for artist chart
            "tracks_chart": top_tracks_for_list,    # Data specifically for track list
            "genres_chart": top_genres,             # Data for genre chart
            "artists_raw": top_artists_raw,         # Full raw artist list for table
            "tracks_raw": top_tracks_raw            # Full raw track list for table
        }

        return render_template('dashboard.html',
                               username=username,
                               viz_data=viz_data,
                               selected_time_range=time_range) # Pass range back to template

    except spotipy.SpotifyException as e:
        logging.error(f"Spotify API Error on /dashboard: {e}")
        # If unauthorized, clear token and force login
        if e.http_status == 401:
            session.pop('token_info', None)
            return redirect(url_for('login', error='Your session expired or permissions changed. Please login again.'))
        # Show error on dashboard page for other API errors
        return render_template('dashboard.html', username=username, error=f"Could not fetch data from Spotify: {e.msg}", selected_time_range=time_range)
    except Exception as e:
        logging.exception("Unexpected error on /dashboard:") # Log the full traceback
        return render_template('dashboard.html', username=username, error="An unexpected error occurred.", selected_time_range=time_range)
    
# --- Helper function to get artist genres ---
memoized_genres = {} # Simple in-memory cache for genres

def get_artist_genres(sp, artist_ids):
    """Fetches genres for a list of artist IDs, using a simple cache."""
    genres_map = {}
    ids_to_fetch = [aid for aid in artist_ids if aid not in memoized_genres]

    # Fetch in batches of 50 (API limit)
    for i in range(0, len(ids_to_fetch), 50):
        batch_ids = ids_to_fetch[i:i+50]
        try:
            artists_info = sp.artists(batch_ids)
            for artist in artists_info['artists']:
                if artist: # Check if artist info was found
                    memoized_genres[artist['id']] = artist.get('genres', [])
        except Exception as e:
            logging.error(f"Error fetching artist batch {batch_ids}: {e}")
            # Assign empty genre list on error for these IDs to avoid re-fetching constantly
            for aid in batch_ids:
                 memoized_genres[aid] = []


    for artist_id in artist_ids:
         genres_map[artist_id] = memoized_genres.get(artist_id, []) # Use cached or fetched

    return genres_map

# --- Route and Logic for Liked Songs Page ---
@app.route('/liked_songs')
def liked_songs_page():
    sp = create_spotify_client()
    if not sp:
        return redirect(url_for('login'))
    try:
        user_info = sp.current_user()
        username = user_info.get('display_name', 'User')

        # Fetch ALL liked songs (handles pagination)
        all_tracks_items = []
        limit = 50
        offset = 0
        logging.info("Starting fetch for all liked songs...")
        while True:
            try:
                results = sp.current_user_saved_tracks(limit=limit, offset=offset)
                items = results.get('items', [])
                if not items:
                    logging.info("No more liked songs found.")
                    break # No more tracks
                all_tracks_items.extend(items)
                logging.info(f"Fetched {len(items)} liked songs, total so far: {len(all_tracks_items)}")
                offset += len(items)
                if len(items) < limit: # Optimization: break if last page fetched
                    break
                # Optional: Add a small delay to avoid hitting rate limits too hard on many pages
                # time.sleep(0.1)
            except spotipy.SpotifyException as e:
                 logging.error(f"Spotify API Error fetching saved tracks (offset {offset}): {e}")
                 # Decide how to handle partial failure - maybe return partial data or an error
                 return render_template('liked_songs.html', username=username, error=f"Failed to fetch all liked songs: {e.msg}")
            except Exception as e:
                 logging.error(f"Non-Spotify Error fetching saved tracks (offset {offset}): {e}")
                 return render_template('liked_songs.html', username=username, error="An unexpected error occurred while fetching liked songs.")

        logging.info(f"Total liked songs fetched: {len(all_tracks_items)}")
        num_liked_tracks = len(all_tracks_items)

        if not all_tracks_items:
             return render_template('liked_songs.html', username=username, message="No liked songs found.")

        # --- Process Liked Songs Data ---
        data = []
        liked_artist_ids = set()
        for item in all_tracks_items:
            track = item.get('track')
            added_at_str = item.get('added_at')
            if not track or not track.get('id'): continue # Skip if track data or ID is missing

            primary_artist = track['artists'][0] if track.get('artists') else None
            artist_id = primary_artist['id'] if primary_artist and primary_artist.get('id') else None
            artist_name = primary_artist['name'] if primary_artist else 'N/A'

            if artist_id: # Only collect valid artist IDs
                liked_artist_ids.add(artist_id)

            data.append({
                # 'added_at': datetime.fromisoformat(added_at_str.replace('Z', '+00:00')) if added_at_str else None, # Parsing date if needed
                'track_name': track.get('name', 'N/A'),
                'track_id': track.get('id'),
                'artist_name': artist_name,
                'artist_id': artist_id, # Store ID for genre fetching
                'album_name': track.get('album', {}).get('name', 'N/A'),
                'album_image_url': track.get('album', {}).get('images', [{}])[0].get('url') if track.get('album', {}).get('images') else None
            })

        df_liked = pd.DataFrame(data)

        num_unique_artists = len(liked_artist_ids)

        # --- Calculate Top 10 Artists by Liked Songs ---
        top_artists_liked = df_liked['artist_name'].value_counts().head(10).reset_index()
        top_artists_liked.columns = ['artist', 'count']
        # Get image for top artists (requires matching back to original data or another call - simplified here)

        # --- Get Genres for Liked Artists & Calculate Top 5 Genres ---
        logging.info(f"Fetching genres for {len(liked_artist_ids)} unique artists in liked songs...")
        liked_artist_genres_map = get_artist_genres(sp, list(liked_artist_ids))
        logging.info("Genre fetching complete.")

        # Add genres to the DataFrame (using the primary artist's genres)
        df_liked['genres'] = df_liked['artist_id'].map(liked_artist_genres_map)

        # Explode the DataFrame to have one row per genre per track
        # Filter out rows where genres might be missing or artist_id was None
        df_genres_exploded = df_liked.dropna(subset=['genres', 'artist_id']).explode('genres')

        top_genres_liked = pd.Series(dtype=int) # Initialize empty Series
        num_unique_genres = 0
        if not df_genres_exploded.empty:
            # Calculate unique genres *before* getting the top 10 counts
            num_unique_genres = df_genres_exploded['genres'].nunique()
            top_genres_liked = df_genres_exploded['genres'].value_counts().head(10).reset_index()
            top_genres_liked.columns = ['genre', 'count']
        else:
             top_genres_liked = pd.DataFrame(columns=['genre', 'count'])
             logging.warning("No genres found to calculate stats/top genres for liked songs.")

        # --- Prepare Data for Template ---
        viz_data = {
            # Convert to dict records for easy JSON serialization
            "top_artists": top_artists_liked.to_dict(orient='records'),
            "top_genres": top_genres_liked.to_dict(orient='records'),
            "total_liked_tracks": num_liked_tracks,
            "unique_liked_artists": num_unique_artists,
            "unique_liked_genres": num_unique_genres
        }

        return render_template('liked_songs.html',
                               username=username,
                               viz_data=viz_data)

    except spotipy.SpotifyException as e:
        logging.error(f"Spotify API Error on /liked_songs: {e}")
        if e.http_status == 401:
            session.pop('token_info', None)
            return redirect(url_for('login', error='Session expired. Please login again.'))
        return render_template('liked_songs.html', username=username, error=f"Could not fetch data from Spotify: {e.msg}")
    except Exception as e:
        logging.exception("Unexpected error on /liked_songs:")
        return render_template('liked_songs.html', username=username, error="An unexpected error occurred on the liked songs page.")

# --- Helper function to extract Playlist ID from URL/ID ---
def extract_playlist_id(playlist_input):
    """Extracts Spotify Playlist ID from URL or potentially just ID string."""
    # Regex to find playlist ID in various Spotify URL formats
    match = re.search(r'playlist[/:]([a-zA-Z0-9]+)', playlist_input)
    if match:
        return match.group(1)
    # Basic check if the input itself might be a valid ID (alphanumeric, typically 22 chars)
    elif re.match(r'^[a-zA-Z0-9]{22}$', playlist_input):
        return playlist_input
    return None # Return None if no valid ID found


# --- NEW: Route for Playlist Analysis ---
@app.route('/playlist_analysis', methods=['GET', 'POST'])
def playlist_analysis():
    sp = create_spotify_client()
    if not sp:
        return redirect(url_for('login'))

    playlist_id_input = None
    playlist_info = None
    viz_data = None
    error_message = None
    message = None

    if request.method == 'POST':
        playlist_id_input = request.form.get('playlist_id_input')
    elif request.method == 'GET':
        # Allow ID via query param as well e.g. /playlist_analysis?id=...
        playlist_id_input = request.args.get('id') or request.args.get('playlist_id')


    if playlist_id_input:
        playlist_id = extract_playlist_id(playlist_id_input)

        if not playlist_id:
            error_message = "Invalid Spotify Playlist URL or ID provided."
        else:
            logging.info(f"Attempting to analyze playlist ID: {playlist_id}")
            try:
                # 1. Get Playlist Metadata
                logging.info("Fetching playlist metadata...")
                playlist_data = sp.playlist(playlist_id)
                playlist_info = {
                    'name': playlist_data.get('name', 'N/A'),
                    'owner': playlist_data.get('owner', {}).get('display_name', 'N/A'),
                    'description': playlist_data.get('description', ''),
                    'image_url': playlist_data['images'][0]['url'] if playlist_data.get('images') else None,
                    'external_url': playlist_data.get('external_urls', {}).get('spotify')
                }
                logging.info(f"Playlist Name: {playlist_info['name']}")

                # 2. Fetch All Playlist Tracks (handles pagination)
                all_playlist_tracks = []
                limit = 100 # Max limit for playlist items is 100
                offset = 0
                logging.info("Starting fetch for all playlist tracks...")
                while True:
                    try:
                        results = sp.playlist_items(playlist_id, limit=limit, offset=offset,
                                                     fields='items(track(id, name, artists(id, name), album(name, images))), total, next') # Specify fields to fetch
                        items = results.get('items', [])
                        if not items: break

                        # Filter out None tracks or tracks without ID (can happen with local files)
                        valid_items = [item['track'] for item in items if item.get('track') and item['track'].get('id')]
                        all_playlist_tracks.extend(valid_items)

                        logging.info(f"Fetched {len(valid_items)} valid tracks, total so far: {len(all_playlist_tracks)}")
                        if results.get('next') is None: break # Check if 'next' URL is null
                        offset += len(items) # Increment offset by number of items processed
                        # time.sleep(0.1) # Optional delay
                    except spotipy.SpotifyException as e:
                         logging.error(f"Spotify API Error fetching playlist items (offset {offset}): {e}")
                         # Handle potential 404 (not found) or 403 (forbidden) for the playlist itself here too
                         if e.http_status in [403, 404]:
                              error_message = f"Cannot access playlist (ID: {playlist_id}). It might be private or does not exist."
                         else:
                             error_message = f"Failed to fetch all playlist tracks: {e.msg}"
                         break # Stop fetching on error
                    except Exception as e:
                         logging.error(f"Non-Spotify Error fetching playlist items (offset {offset}): {e}")
                         error_message = "An unexpected error occurred while fetching playlist tracks."
                         break # Stop fetching on error

                if error_message: # If error occurred during fetching, stop processing
                    pass
                elif not all_playlist_tracks:
                    message = "No valid/accessible tracks found in this playlist."
                else:
                    # 3. Process Tracks & Calculate Stats
                    num_playlist_tracks = len(all_playlist_tracks)
                    playlist_artist_ids = set()
                    processed_data = []

                    for track in all_playlist_tracks:
                        primary_artist = track['artists'][0] if track.get('artists') else None
                        artist_id = primary_artist['id'] if primary_artist and primary_artist.get('id') else None
                        artist_name = primary_artist['name'] if primary_artist else 'N/A'

                        if artist_id: playlist_artist_ids.add(artist_id)

                        processed_data.append({
                            'track_name': track.get('name', 'N/A'),
                            'track_id': track.get('id'),
                            'artist_name': artist_name,
                            'artist_id': artist_id,
                            'album_name': track.get('album', {}).get('name', 'N/A'),
                        })

                    df_playlist = pd.DataFrame(processed_data)
                    num_unique_artists = len(playlist_artist_ids)

                    # Calculate Top 5 Artists
                    top_artists_playlist = df_playlist['artist_name'].value_counts().head(10).reset_index()
                    top_artists_playlist.columns = ['artist', 'count']

                    # Get Genres & Calculate Stats/Top 5
                    logging.info(f"Fetching genres for {num_unique_artists} unique artists in playlist...")
                    playlist_artist_genres = get_artist_genres(sp, list(playlist_artist_ids))
                    logging.info("Genre fetching complete.")

                    df_playlist['genres'] = df_playlist['artist_id'].map(playlist_artist_genres)
                    df_genres_exploded_pl = df_playlist.dropna(subset=['genres', 'artist_id']).explode('genres')

                    num_unique_genres = 0
                    if not df_genres_exploded_pl.empty:
                        num_unique_genres = df_genres_exploded_pl['genres'].nunique()
                        top_genres_playlist = df_genres_exploded_pl['genres'].value_counts().head(10).reset_index()
                        top_genres_playlist.columns = ['genre', 'count']
                    else:
                        top_genres_playlist = pd.DataFrame(columns=['genre', 'count'])
                        logging.warning("No genres found for this playlist.")

                    # 4. Prepare viz_data
                    viz_data = {
                        "top_artists": top_artists_playlist.to_dict(orient='records'),
                        "top_genres": top_genres_playlist.to_dict(orient='records'),
                        "total_tracks": num_playlist_tracks,
                        "unique_artists": num_unique_artists,
                        "unique_genres": num_unique_genres
                    }

            except spotipy.SpotifyException as e:
                logging.error(f"Spotify API Error accessing playlist (ID: {playlist_id}): {e}")
                if e.http_status == 404: error_message = f"Playlist with ID '{playlist_id}' not found."
                elif e.http_status == 403: error_message = f"Access denied to playlist '{playlist_id}'. Is it private?"
                else: error_message = f"Spotify error accessing playlist: {e.msg}"
                playlist_info = None # Clear playlist info on error
            except Exception as e:
                logging.exception(f"Unexpected error analyzing playlist {playlist_id}:")
                error_message = "An unexpected error occurred during playlist analysis."
                playlist_info = None

    # Render the template, passing any data, info, or errors
    return render_template('playlist_analysis.html',
                           username=sp.current_user().get('display_name', 'User'), # Get username for consistency
                           playlist_info=playlist_info,
                           viz_data=viz_data,
                           error=error_message,
                           message=message,
                           playlist_id_input=playlist_id_input or '') # Pass input back to form


if __name__ == '__main__':
    app.run(debug=True, port=5000) # Debug=True for development ONLY
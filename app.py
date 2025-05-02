import os
import re
import time
import pandas as pd
import numpy as np
from flask import Flask, request, redirect, session, url_for, render_template, jsonify
from flask_session import Session 
import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
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

# --- Create App-Level Spotify Client (Client Credentials Flow) ---
try:
    client_credentials_manager = SpotifyClientCredentials(client_id=os.getenv('SPOTIPY_CLIENT_ID'),
                                                          client_secret=os.getenv('SPOTIPY_CLIENT_SECRET'))
    # This client authenticates the app itself, not a user
    sp_app = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
    logging.info("Created app-level Spotify client (Client Credentials Flow).")
except Exception as e:
    sp_app = None # Set to None if creation fails
    logging.error(f"Failed to create app-level Spotify client: {e}")

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
    
# --- Helper function to get artist details ---
# Simple in-memory cache for artist details
memoized_artist_details = {}

def get_artist_details(sp_client, artist_ids):
    """
    Fetches name, genres, followers, and image URL for a list of artist IDs.
    Uses a simple cache. Returns a dictionary mapping ID to details.
    """
    details_map = {}
    # Ensure IDs are unique and not None before checking cache/fetching
    unique_ids = list(filter(None, set(artist_ids)))
    ids_to_fetch = [aid for aid in unique_ids if aid not in memoized_artist_details]
    logging.info(f"Need to fetch details for {len(ids_to_fetch)} artists.")

    # Fetch in batches of 50 (API limit)
    for i in range(0, len(ids_to_fetch), 50):
        batch_ids = ids_to_fetch[i:i+50]
        logging.info(f"Fetching batch {i//50 + 1}: {batch_ids}")
        try:
            artists_info = sp_client.artists(batch_ids)
            for artist_data in artists_info['artists']:
                if artist_data: # Check if artist info was found
                    artist_id = artist_data['id']
                    memoized_artist_details[artist_id] = {
                        'name': artist_data.get('name', 'N/A'),
                        'genres': artist_data.get('genres', []),
                        'followers': artist_data.get('followers', {}).get('total', 0),
                        'image_url': artist_data['images'][0]['url'] if artist_data.get('images') else None
                    }
                # Optional: Handle case where API returns None for a requested ID within the batch
                # You might store a specific marker for 'not found' IDs in the cache
        except spotipy.SpotifyException as e:
            logging.error(f"Spotify API error fetching artist batch {batch_ids}: {e}")
            # Cache failure for these IDs to avoid constant retries in this request
            for aid in batch_ids:
                 memoized_artist_details[aid] = None # Mark as failed/unavailable
        except Exception as e:
             logging.error(f"Non-Spotify error fetching artist batch {batch_ids}: {e}")
             for aid in batch_ids:
                 memoized_artist_details[aid] = None # Mark as failed/unavailable
        # time.sleep(0.1) # Optional delay between batches

    # Populate the final map from cache or fetched details
    default_details = {'name': 'N/A', 'genres': [], 'followers': 0, 'image_url': None}
    for artist_id in unique_ids:
         # Use cached detail if valid, otherwise use default
         details_map[artist_id] = memoized_artist_details.get(artist_id) or default_details

    return details_map

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
                'name': track.get('name', 'N/A'),
                'track_id': track.get('id'),
                'artist_name': artist_name,
                'artists': [a.get('name', 'N/A') for a in track.get('artists', [])],
                'artist_id': artist_id, # Store ID for genre fetching
                'popularity': track.get('popularity', 0), # <<< Extract popularity
                'album_name': track.get('album', {}).get('name', 'N/A'),
                'album_image_url': track.get('album', {}).get('images', [{}])[0].get('url') if track.get('album', {}).get('images') else None
            })

        num_unique_artists = len(liked_artist_ids)

        df_liked = pd.DataFrame(data)
        # --- Calculate Top 10 Artists by Liked Songs ---
        top_artists_liked = df_liked['artist_name'].value_counts().head(10).reset_index()
        top_artists_liked.columns = ['artist', 'count']
        # Get image for top artists (requires matching back to original data or another call - simplified here)

        # Fetch Artist Details (Followers, Genres)
        logging.info(f"Fetching details for {num_unique_artists} unique artists in liked songs...")
        artist_details_map = get_artist_details(sp, list(liked_artist_ids))
        logging.info("Artist detail fetching complete.")

        # Calculate Stats & Top/Bottom Lists
        # Tracks by Popularity
        # Filter out tracks with pop 0 unless they are the only ones? Optional.
        valid_popularity_tracks = [t for t in data if t['popularity'] is not None]
        valid_popularity_tracks.sort(key=lambda x: x['popularity'], reverse=True)
        top_5_popular_tracks = valid_popularity_tracks[:5]
        # Avoid sorting tracks with 0 popularity as "least popular" if possible
        non_zero_pop_tracks = [t for t in valid_popularity_tracks if t['popularity'] > 0]
        if len(non_zero_pop_tracks) >= 5:
             bottom_5_popular_tracks = sorted(non_zero_pop_tracks, key=lambda x: x['popularity'])[:5]
        else:
             # Fallback if fewer than 5 tracks have > 0 popularity
             bottom_5_popular_tracks = sorted(valid_popularity_tracks, key=lambda x: x['popularity'])[:5]


        # Artists by Followers
        # Create list of {'id': ..., 'name': ..., 'followers': ...} from fetched details
        artist_follower_list = [{'id': aid, **details} for aid, details in artist_details_map.items() if details] # Filter out None details
        artist_follower_list.sort(key=lambda x: x['followers'], reverse=True)
        top_5_followed_artists = artist_follower_list[:5]
        # Filter out artists with 0 followers if possible for "least followed"
        non_zero_follower_artists = [a for a in artist_follower_list if a['followers'] > 0]
        if len(non_zero_follower_artists) >= 5:
            bottom_5_followed_artists = sorted(non_zero_follower_artists, key=lambda x: x['followers'])[:5]
        else:
             # Fallback if fewer than 5 artists have > 0 followers
            bottom_5_followed_artists = sorted(artist_follower_list, key=lambda x: x['followers'])[:5]

        # Genres (Unique Count & Top 10) - requires mapping genres back to tracks
        all_genres = []
        for track_info in data:
            artist_id = track_info.get('artist_id')
            if artist_id and artist_id in artist_details_map and artist_details_map[artist_id]:
                all_genres.extend(artist_details_map[artist_id]['genres'])

        num_unique_genres = len(set(all_genres))
        top_genres_liked = []
        if all_genres:
            genre_counts_liked = Counter(all_genres)
            top_genres_liked = [{'genre': g, 'count': c} for g, c in genre_counts_liked.most_common(10)]

        # --- Prepare Data for Template ---
        viz_data = {
            # Convert to dict records for easy JSON serialization
            "top_artists": top_artists_liked.to_dict(orient='records'),
            "top_genres": top_genres_liked,
            "total_liked_tracks": num_liked_tracks,
            "unique_liked_artists": num_unique_artists,
            "unique_liked_genres": num_unique_genres,
            "top_popular_tracks": top_5_popular_tracks,
            "bottom_popular_tracks": bottom_5_popular_tracks,
            "top_followed_artists": top_5_followed_artists,
            "bottom_followed_artists": bottom_5_followed_artists
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


# --- Route for Playlist Analysis ---
@app.route('/playlist_analysis', methods=['GET', 'POST'])
def playlist_analysis():
    sp = create_spotify_client()

    if sp: # Make sure client creation succeeded
        try:
            test_track_id = '4uLu6hFjJmix5cZBNdAamC' # Example: Publicly known track ID ("Take On Me")
            logging.info(f"Attempting test call to audio_features for track: {test_track_id}")
            test_features = sp.audio_features(tracks=[test_track_id])
            logging.info(f"Test call result: {test_features}")
        except Exception as test_e:
            logging.error(f"Test call to audio_features failed: {test_e}")
    else:
        # Redirect to login if sp creation failed
        return redirect(url_for('login'))

    if not sp:
        return redirect(url_for('login'))

    playlist_id_input = None
    playlist_info = None
    viz_data = None
    error_message = None
    message = None
    scatter_plot_data = None
    avg_stats = None

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
                # Get Playlist Metadata
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

                # Fetch All Playlist Tracks (handles pagination)
                all_playlist_tracks = []
                limit = 100 # Max limit for playlist items is 100
                offset = 0
                logging.info("Starting fetch for all playlist tracks...")
                while True:
                    try:
                        results = sp.playlist_items(playlist_id, limit=limit, offset=offset,
                                                     fields='items(track(id, name, popularity, artists(id, name), album(name, images))), total, next') # Specify fields to fetch
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
                    # Extract Track IDs for Audio Features
                    track_ids = [track['id'] for track in all_playlist_tracks if track and track.get('id')]
                    num_playlist_tracks = len(track_ids) # Count based on valid IDs found

                    # Fetch Audio Features (Batching required)
                    logging.info(f"Fetching audio features for {num_playlist_tracks} tracks...")
                    audio_features_list = []
                    for i in range(0, len(track_ids), 100): # Max 100 IDs per request
                        batch_ids = track_ids[i:i+100]
                        try:
                            batch_features = sp_app.audio_features(tracks=batch_ids)
                            # Filter out None results before extending
                            audio_features_list.extend([f for f in batch_features if f is not None])
                            logging.info(f"Fetched features for batch {i//100 + 1}")
                        except spotipy.SpotifyException as e:
                            logging.warning(f"Spotify error fetching audio features batch {i//100 + 1}: {e}")
                        except Exception as e:
                             logging.warning(f"General error fetching audio features batch {i//100 + 1}: {e}")
                        # time.sleep(0.1) # Optional delay

                    logging.info(f"Successfully fetched features for {len(audio_features_list)} tracks.")

                    for track in all_playlist_tracks:
                        primary_artist = track['artists'][0] if track.get('artists') else None
                        artist_id = primary_artist['id'] if primary_artist and primary_artist.get('id') else None
                        artist_name = primary_artist['name'] if primary_artist else 'N/A'

                    # Create DataFrame from track list
                    df_tracks = pd.DataFrame([{
                        'id': t['id'],
                        'name': t.get('name', 'N/A'),
                        'artist_name': artist_name,
                        'artists': [a.get('name', 'N/A') for a in t.get('artists', [])],
                        'artist_id': t['artists'][0]['id'] if t.get('artists') and t['artists'][0].get('id') else None,
                        'album_name': t.get('album', {}).get('name', 'N/A'),
                        'album_image_url': t.get('album', {}).get('images', [{}])[-1].get('url'), # Smallest image
                        'popularity': t.get('popularity', 0)
                    } for t in all_playlist_tracks if t and t.get('id')])

                    # Create DataFrame from features (handle potential missing features)
                    if audio_features_list:
                        df_features = pd.DataFrame(audio_features_list)
                        # Select only relevant feature columns + id for merging
                        feature_cols = ['id', 'tempo', 'energy', 'danceability', 'valence',
                                        'acousticness', 'instrumentalness', 'liveness', 'speechiness']
                        df_features = df_features[feature_cols]

                        # Merge DataFrames
                        df_combined = pd.merge(df_tracks, df_features, on='id', how='left')
                        # Fill NaN for numeric features where merge failed (optional, depends on desired avg calc)
                        numeric_feature_cols = feature_cols[1:] # Exclude 'id'
                        df_combined[numeric_feature_cols] = df_combined[numeric_feature_cols].fillna(0) # Example: fill with 0
                    else:
                        # Handle case where no audio features were fetched
                        df_combined = df_tracks
                        # Add empty columns for features if needed later, filled with NaN or 0
                        numeric_feature_cols = ['tempo', 'energy', 'danceability', 'valence',
                                        'acousticness', 'instrumentalness', 'liveness', 'speechiness']
                        for col in numeric_feature_cols:
                            df_combined[col] = 0.0 # Or np.nan if preferred

                    # Calculate Average Stats
                    avg_stats = {
                        'avg_tempo': round(df_combined['tempo'].mean()) if 'tempo' in df_combined else 0,
                        'avg_energy': round(df_combined['energy'].mean(), 2) if 'energy' in df_combined else 0.0,
                        'avg_popularity': round(df_combined['popularity'].mean()) if 'popularity' in df_combined else 0,
                        'avg_danceability': round(df_combined['danceability'].mean(), 2) if 'danceability' in df_combined else 0.0,
                        'avg_valence': round(df_combined['valence'].mean(), 2) if 'valence' in df_combined else 0.0,
                    }
                    logging.info(f"Calculated Avg Stats: {avg_stats}")


                    # Prepare Scatter Plot Data (list of dictionaries)
                    scatter_plot_cols = ['name', 'artists', 'popularity'] + numeric_feature_cols
                    # Select necessary columns, handle potential missing columns gracefully
                    cols_to_select = [col for col in scatter_plot_cols if col in df_combined.columns]
                    scatter_plot_data = df_combined[cols_to_select].to_dict(orient='records')

                    
                    playlist_artist_ids = set(df_combined['artist_id'].dropna())
                    num_unique_artists = len(playlist_artist_ids)

                    # Calculate Top 10 Artists
                    top_artists_playlist = df_tracks['artists'].value_counts().head(10).reset_index()
                    top_artists_playlist.columns = ['artist', 'count']

                   # Fetch Artist Details
                    logging.info(f"Fetching details for {num_unique_artists} unique artists in playlist...")
                    artist_details_map = get_artist_details(sp, list(playlist_artist_ids))
                    logging.info("Artist detail fetching complete.")

                    # Calculate Stats & Top/Bottom Lists (Similar logic as liked songs)
                    # Tracks by Popularity
                    # Initialize lists in case of errors or empty DataFrame
                    top_5_popular_tracks = []
                    bottom_5_popular_tracks = []

                    # Ensure DataFrame is not empty and 'popularity' column exists
                    if not df_tracks.empty and 'popularity' in df_tracks.columns:
                        try:
                            # Get Top 5 most popular tracks directly
                            top_5_popular_tracks_df = df_tracks.nlargest(5, 'popularity')
                            top_5_popular_tracks = top_5_popular_tracks_df.to_dict(orient='records')
                            # Get Bottom 5 least popular tracks (try to exclude 0 popularity)
                            non_zero_pop_df = df_tracks[df_tracks['popularity'] > 0]
                            if not non_zero_pop_df.empty:
                                # Get the 5 tracks with the smallest popularity score from the non-zero ones
                                bottom_5_popular_tracks_df = non_zero_pop_df.nsmallest(5, 'popularity')
                            else:
                                # Fallback: If all tracks have 0 popularity (or DataFrame was empty initially filtered),
                                logging.warning("No tracks with popularity > 0 found. Getting tracks with lowest popularity overall.")
                                bottom_5_popular_tracks_df = df_tracks.nsmallest(5, 'popularity')

                            bottom_5_popular_tracks = bottom_5_popular_tracks_df.to_dict(orient='records')
                        except Exception as e:
                            logging.error(f"Error processing track popularity for tables: {e}")

                    # Artists by Followers
                    artist_follower_list = [{'id': aid, **details} for aid, details in artist_details_map.items() if details]
                    artist_follower_list.sort(key=lambda x: x['followers'], reverse=True)
                    top_5_followed_artists = artist_follower_list[:5]
                    non_zero_follower_artists = [a for a in artist_follower_list if a['followers'] > 0]
                    if len(non_zero_follower_artists) >= 5:
                        bottom_5_followed_artists = sorted(non_zero_follower_artists, key=lambda x: x['followers'])[:5]
                    else:
                         bottom_5_followed_artists = sorted(artist_follower_list, key=lambda x: x['followers'])[:5]

                    # Genres (Unique Count & Top 10)
                    all_genres_pl = []
                    # Ensure required columns exist and map is valid before iterating
                    if 'artist_id' in df_tracks.columns and artist_details_map is not None:
                        # Use df_tracks.itertuples() for efficient row iteration
                        # name='Track' allows accessing columns like track_row.artist_id
                        for track_row in df_tracks.itertuples(index=False, name='Track'):
                            try:
                                artist_id = track_row.artist_id
                                # Check if artist_id exists, is in the map, and the map entry is valid
                                # Use pd.notna to handle potential None or NaN artist_id values
                                if pd.notna(artist_id) and artist_id in artist_details_map and artist_details_map[artist_id]:
                                    # Extend the list with the genres for this artist (handle potential None genres)
                                    genres = artist_details_map[artist_id].get('genres', []) # Default to empty list
                                    if genres: # Only extend if the list is not empty
                                        all_genres_pl.extend(genres)
                            except AttributeError:
                                # Handle cases where a row might not have the expected attribute if tuple name wasn't used correctly
                                logging.warning(f"Skipping row due to missing attribute during genre processing: {track_row}")
                                continue
                    else:
                        # Log warnings if prerequisites are missing
                        if 'artist_id' not in df_tracks.columns:
                            logging.warning("'artist_id' column not found in DataFrame for genre processing.")
                        if artist_details_map is None:
                            logging.warning("'artist_details_map' is None, cannot process genres.")

                    # Calculate unique count from the collected list
                    # Use try-except in case set() fails on unexpected data types, though unlikely here
                    try:
                        num_unique_genres = len(set(all_genres_pl))
                    except TypeError as e:
                        logging.error(f"Could not calculate unique genres, potential type issue in list: {e}")
                        num_unique_genres = 0


                    # Calculate top 10 from the collected list (this part was already correct conceptually)
                    top_genres_playlist = []
                    if all_genres_pl:
                        try:
                            genre_counts_pl = Counter(all_genres_pl)
                            # Format for viz_data: list of dictionaries
                            top_genres_playlist = [{'genre': g, 'count': c} for g, c in genre_counts_pl.most_common(10)]
                        except Exception as e:
                            logging.error(f"Error calculating top genres with Counter: {e}")

                    # Prepare viz_data
                    viz_data = {
                        "top_artists": top_artists_playlist.to_dict(orient='records'),
                        "top_genres": top_genres_playlist,
                        "total_tracks": num_playlist_tracks,
                        "unique_artists": num_unique_artists,
                        "unique_genres": num_unique_genres,
                        "top_popular_tracks": top_5_popular_tracks,
                        "bottom_popular_tracks": bottom_5_popular_tracks,
                        "top_followed_artists": top_5_followed_artists,
                        "bottom_followed_artists": bottom_5_followed_artists,
                        "avg_stats": avg_stats,
                        "scatter_plot_data": scatter_plot_data
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
"""YouTube Music bridge for Lynxos Music v2.2.32.
Uses ytmusicapi to talk to YouTube Music's InnerTube API.
Called from Java via Chaquopy, exposed to JavaScript via WebView bridge.
Python-only: all music data comes through here, no JavaScript fallbacks.
"""
import json
from ytmusicapi import YTMusic

# Global instance, initialized on first use
_ytm = None

def _get_ytm():
    global _ytm
    if _ytm is None:
        _ytm = YTMusic()
    return _ytm

def _track_from_song(item):
    """Convert a ytmusicapi song item to Lynxos track format."""
    if item.get("resultType") not in ("song", "video", None):
        # For watch playlist items, resultType may not be present
        pass
    # Only audio tracks, not music videos
    video_type = item.get("videoType", "")
    if video_type == "MUSIC_VIDEO_TYPE_OMV":
        return None
    artists = item.get("artists", [])
    if isinstance(artists, list) and artists:
        artist_name = artists[0].get("name", "") if isinstance(artists[0], dict) else str(artists[0])
    else:
        artist_name = str(artists) if artists else ""
    album = item.get("album", {})
    album_name = album.get("name", "") if isinstance(album, dict) else ""
    duration = item.get("duration", "") or item.get("length", "")
    thumbnails = item.get("thumbnails", []) or item.get("thumbnail", [])
    thumb_url = thumbnails[-1].get("url", "") if thumbnails else ""
    video_id = item.get("videoId", "")
    if not video_id:
        return None
    return {
        "videoId": video_id,
        "title": item.get("title", ""),
        "channel": artist_name,
        "ownerChannel": artist_name,
        "album": album_name,
        "dur": duration,
        "thumb": thumb_url,
        "art": thumb_url,
    }

def search_songs(query, max_results=20):
    """Search YouTube Music for songs. Returns JSON array of tracks."""
    try:
        ytm = _get_ytm()
        results = ytm.search(query, filter="songs", limit=max_results)
        tracks = []
        for item in results:
            t = _track_from_song(item)
            if t:
                tracks.append(t)
        return json.dumps(tracks)
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_radio(video_id, limit=50):
    """Get radio queue for a video. Returns JSON array of tracks."""
    try:
        ytm = _get_ytm()
        playlist = ytm.get_watch_playlist(videoId=video_id, limit=limit)
        tracks = []
        for item in playlist.get("tracks", []):
            t = _track_from_song(item)
            if t:
                tracks.append(t)
        return json.dumps(tracks)
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_artist_top_songs(artist_id, limit=20):
    """Get top songs for an artist. Returns JSON array."""
    try:
        ytm = _get_ytm()
        artist = ytm.get_artist(artist_id)
        songs = artist.get("songs", {}).get("results", [])[:limit]
        tracks = []
        for item in songs:
            t = _track_from_song(item)
            if t:
                tracks.append(t)
        return json.dumps(tracks)
    except Exception as e:
        return json.dumps({"error": str(e)})

def search_artists(query, limit=10):
    """Search for artists. Returns JSON array."""
    try:
        ytm = _get_ytm()
        results = ytm.search(query, filter="artists", limit=limit)
        artists = []
        for item in results:
            thumbnails = item.get("thumbnails", [])
            thumb_url = thumbnails[-1].get("url", "") if thumbnails else ""
            artists.append({
                "browseId": item.get("browseId", ""),
                "name": item.get("artist", ""),
                "thumb": thumb_url,
            })
        return json.dumps(artists)
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_mood_genre_categories():
    """Get YouTube Music mood/genre categories. Returns JSON."""
    try:
        ytm = _get_ytm()
        result = ytm.get_mood_categories()
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_mood_playlists(params, limit=50):
    """Get playlists for a mood/genre params. Returns JSON array of tracks."""
    try:
        ytm = _get_ytm()
        result = ytm.get_mood_playlists(params)
        tracks = []
        # get_mood_playlists returns playlists, need to get tracks from each
        for pl in result[:5]:  # Top 5 playlists for the genre
            playlist_id = pl.get("playlistId", "")
            if not playlist_id:
                continue
            try:
                playlist = ytm.get_playlist(playlist_id, limit=limit//5)
                for item in playlist.get("tracks", []):
                    t = _track_from_song(item)
                    if t:
                        tracks.append(t)
                        if len(tracks) >= limit:
                            break
            except:
                continue
            if len(tracks) >= limit:
                break
        return json.dumps(tracks)
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_charts(country="US", limit=50):
    """Get charts (new releases/trending). Returns JSON."""
    try:
        ytm = _get_ytm()
        charts = ytm.get_charts(country=country)
        tracks = []
        for item in charts.get("songs", {}).get("items", [])[:limit]:
            t = _track_from_song(item)
            if t:
                tracks.append(t)
        return json.dumps(tracks)
    except Exception as e:
        return json.dumps({"error": str(e)})

def search_albums(query, limit=20):
    """Search for albums. Returns JSON array."""
    try:
        ytm = _get_ytm()
        results = ytm.search(query, filter="albums", limit=limit)
        albums = []
        for item in results:
            thumbnails = item.get("thumbnails", [])
            thumb_url = thumbnails[-1].get("url", "") if thumbnails else ""
            artists = item.get("artists", [])
            artist_name = artists[0].get("name", "") if artists else ""
            albums.append({
                "browseId": item.get("browseId", ""),
                "title": item.get("title", ""),
                "artist": artist_name,
                "year": item.get("year", ""),
                "thumb": thumb_url,
            })
        return json.dumps(albums)
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_album(browse_id, limit=50):
    """Get album tracks. Returns JSON array."""
    try:
        ytm = _get_ytm()
        album = ytm.get_album(browse_id)
        tracks = []
        for item in album.get("tracks", [])[:limit]:
            t = _track_from_song(item)
            if t:
                # Add album info
                t["album"] = album.get("title", "")
                tracks.append(t)
        return json.dumps(tracks)
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_stream_url(video_id):
    """Get playable audio stream URL for a video ID using yt-dlp.
    Returns JSON with url or error. This is the fallback when NewPipe fails."""
    try:
        import yt_dlp
        url = "https://www.youtube.com/watch?v=" + video_id
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'noplaylist': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            # Get the best audio URL
            stream_url = info.get('url', '')
            if not stream_url:
                # Try formats list
                for f in info.get('formats', []):
                    if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                        stream_url = f.get('url', '')
                        if stream_url:
                            break
                if not stream_url and info.get('formats'):
                    stream_url = info['formats'][0].get('url', '')
            if stream_url:
                return json.dumps({"url": stream_url})
            else:
                return json.dumps({"error": "No stream URL found"})
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_new_releases(limit=100):
    """Get new album releases. Returns JSON array of albums."""
    try:
        ytm = _get_ytm()
        # Use charts to get trending, which includes new releases
        # ytmusicapi doesn't have a direct new releases endpoint,
        # so we search for recent albums across genres
        albums = []
        seen = set()
        # Search for new albums by year
        import datetime
        year = datetime.datetime.now().year
        for query in [f"new album {year}", f"new releases {year}", "new music"]:
            try:
                results = ytm.search(query, filter="albums", limit=30)
                for item in results:
                    browse_id = item.get("browseId", "")
                    if not browse_id or browse_id in seen:
                        continue
                    seen.add(browse_id)
                    thumbnails = item.get("thumbnails", [])
                    thumb_url = thumbnails[-1].get("url", "") if thumbnails else ""
                    artists = item.get("artists", [])
                    artist_name = artists[0].get("name", "") if artists else ""
                    albums.append({
                        "browseId": browse_id,
                        "title": item.get("title", ""),
                        "artist": artist_name,
                        "year": item.get("year", ""),
                        "thumb": thumb_url,
                    })
                    if len(albums) >= limit:
                        break
            except:
                continue
            if len(albums) >= limit:
                break
        return json.dumps(albums[:limit])
    except Exception as e:
        return json.dumps({"error": str(e)})

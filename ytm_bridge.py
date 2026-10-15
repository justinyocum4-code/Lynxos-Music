"""YouTube Music bridge for Lynxos Music v2.2.30.
Uses ytmusicapi to talk to YouTube Music's InnerTube API.
Called from Java via Chaquopy, exposed to JavaScript via WebView bridge.
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

def search_songs(query, max_results=20):
    """Search YouTube Music for songs. Returns JSON array of tracks."""
    try:
        ytm = _get_ytm()
        results = ytm.search(query, filter="songs", limit=max_results)
        tracks = []
        for item in results:
            if item.get("resultType") not in ("song", "video"):
                continue
            # Only audio tracks, not music videos
            video_type = item.get("videoType", "")
            if video_type == "MUSIC_VIDEO_TYPE_OMV":
                continue
            artists = item.get("artists", [])
            artist_name = artists[0].get("name", "") if artists else ""
            album = item.get("album", {})
            album_name = album.get("name", "") if isinstance(album, dict) else ""
            duration = item.get("duration", "")
            thumbnails = item.get("thumbnails", [])
            thumb_url = thumbnails[-1].get("url", "") if thumbnails else ""
            tracks.append({
                "videoId": item.get("videoId", ""),
                "title": item.get("title", ""),
                "channel": artist_name,
                "ownerChannel": artist_name,
                "album": album_name,
                "dur": duration,
                "thumb": thumb_url,
                "art": thumb_url,
            })
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
            artists = item.get("artists", [])
            if isinstance(artists, list) and artists:
                artist_name = artists[0].get("name", "") if isinstance(artists[0], dict) else str(artists[0])
            else:
                artist_name = str(artists) if artists else ""
            thumbnails = item.get("thumbnail", [])
            thumb_url = thumbnails[-1].get("url", "") if thumbnails else ""
            tracks.append({
                "videoId": item.get("videoId", ""),
                "title": item.get("title", ""),
                "channel": artist_name,
                "ownerChannel": artist_name,
                "dur": item.get("length", ""),
                "thumb": thumb_url,
                "art": thumb_url,
            })
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
            artists = item.get("artists", [])
            artist_name = artists[0].get("name", "") if artists else ""
            thumbnails = item.get("thumbnails", [])
            thumb_url = thumbnails[-1].get("url", "") if thumbnails else ""
            tracks.append({
                "videoId": item.get("videoId", ""),
                "title": item.get("title", ""),
                "channel": artist_name,
                "ownerChannel": artist_name,
                "dur": "",
                "thumb": thumb_url,
                "art": thumb_url,
            })
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

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

def is_latin_text(s):
    """v2.2.97: English-only feed filter — True when every alphabetic
    character in the text is Latin-script (ASCII or Latin Extended, which
    covers accented letters in names like Beyoncé or Motörhead). Digits,
    spaces, punctuation and symbols are ignored. Any letter from a
    non-Latin script (Han, Hiragana, Katakana, Hangul, Arabic, Cyrillic,
    Greek, Thai, Devanagari, Hebrew, Armenian, Georgian, ...) fails.
    Latin-script non-English (Spanish, French) cannot be told apart from
    English without a language detector and passes — accepted trade-off."""
    if not s:
        return True
    for ch in str(s):
        if ch.isalpha():
            o = ord(ch)
            if o < 0x80:
                continue  # ASCII letter
            if 0x00C0 <= o <= 0x024F:
                continue  # Latin-1 Supplement + Latin Extended-A/B letters
            if 0x1E00 <= o <= 0x1EFF:
                continue  # Latin Extended Additional (e.g. Vietnamese)
            if 0x2C60 <= o <= 0x2C7F or 0xA720 <= o <= 0xA7FF or 0xAB30 <= o <= 0xAB6F:
                continue  # Latin Extended-C / -D / -E letters
            if 0xFF21 <= o <= 0xFF3A or 0xFF41 <= o <= 0xFF5A:
                continue  # Fullwidth Latin letters
            return False
    return True

def _is_latin_item(title, artist):
    """An item is kept only when BOTH its title and artist are Latin-script."""
    return is_latin_text(title) and is_latin_text(artist)

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

def get_song(video_id):
    """Get song details by video ID. Returns JSON object."""
    try:
        ytm = _get_ytm()
        song = ytm.get_song(videoId=video_id)
        details = song.get("videoDetails", {})
        thumbs = details.get("thumbnail", {}).get("thumbnails", [])
        thumb = thumbs[-1].get("url", "") if thumbs else ""
        return json.dumps({
            "videoId": video_id,
            "title": details.get("title", ""),
            "channel": details.get("author", ""),
            "thumb": thumb,
            "art": thumb,
        })
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

def get_artist_info(artist_id):
    """Get artist bio, image, and details. Returns JSON object."""
    try:
        ytm = _get_ytm()
        artist = ytm.get_artist(artist_id)
        thumbnails = artist.get("thumbnails", [])
        thumb_url = thumbnails[-1].get("url", "") if thumbnails else ""
        description = artist.get("description", "")
        return json.dumps({
            "name": artist.get("name", ""),
            "description": description,
            "thumb": thumb_url,
            "browseId": artist_id,
        })
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_artist_albums(artist_id):
    """Get ALL albums and singles from the artist's page. Returns JSON object with albums and singles arrays."""
    try:
        ytm = _get_ytm()
        artist = ytm.get_artist(artist_id)
        albums = []
        singles = []
        # Albums section - try to get full list via browse
        albums_data = artist.get("albums", {})
        for item in albums_data.get("results", []):
            thumbnails = item.get("thumbnails", [])
            thumb_url = thumbnails[-1].get("url", "") if thumbnails else ""
            albums.append({
                "browseId": item.get("browseId", ""),
                "title": item.get("title", ""),
                "year": item.get("year", ""),
                "thumb": thumb_url,
            })
        # v2.2.52: Try to fetch more albums via the browse endpoint if available
        try:
            abid = albums_data.get("browseId", "")
            aparams = albums_data.get("params", "")
            if abid and aparams:
                more = ytm.get_artist_albums(abid, aparams)
                for item in more if isinstance(more, list) else []:
                    thumbnails = item.get("thumbnails", [])
                    thumb_url = thumbnails[-1].get("url", "") if thumbnails else ""
                    bid = item.get("browseId", "")
                    # Deduplicate
                    if bid and not any(a.get("browseId") == bid for a in albums):
                        albums.append({
                            "browseId": bid,
                            "title": item.get("title", ""),
                            "year": item.get("year", ""),
                            "thumb": thumb_url,
                        })
        except Exception:
            pass
        # Singles section
        singles_data = artist.get("singles", {})
        for item in singles_data.get("results", []):
            thumbnails = item.get("thumbnails", [])
            thumb_url = thumbnails[-1].get("url", "") if thumbnails else ""
            singles.append({
                "browseId": item.get("browseId", ""),
                "title": item.get("title", ""),
                "year": item.get("year", ""),
                "thumb": thumb_url,
            })
        # v2.2.52: Try to fetch more singles too
        try:
            sbid = singles_data.get("browseId", "")
            sparams = singles_data.get("params", "")
            if sbid and sparams:
                more = ytm.get_artist_albums(sbid, sparams)
                for item in more if isinstance(more, list) else []:
                    thumbnails = item.get("thumbnails", [])
                    thumb_url = thumbnails[-1].get("url", "") if thumbnails else ""
                    bid = item.get("browseId", "")
                    if bid and not any(s.get("browseId") == bid for s in singles):
                        singles.append({
                            "browseId": bid,
                            "title": item.get("title", ""),
                            "year": item.get("year", ""),
                            "thumb": thumb_url,
                        })
        except Exception:
            pass
        return json.dumps({"albums": albums, "singles": singles})
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

def _get_ytm_authed(provider_token):
    """Create YTMusic with user's OAuth token for personal library access."""
    from ytmusicapi import YTMusic
    # ytmusicapi OAuth format needs refresh token flow; use headers directly
    ytm = YTMusic()
    ytm._headers["Authorization"] = "Bearer " + provider_token
    return ytm

def get_ytm_liked(provider_token, limit=100):
    """Get user's YouTube Music liked songs. Needs YouTube OAuth scope."""
    try:
        ytm = _get_ytm_authed(provider_token)
        songs = ytm.get_liked_songs(limit=limit)
        tracks = []
        for item in songs.get("tracks", [])[:limit]:
            t = _track_from_song(item)
            if t:
                tracks.append(t)
        return json.dumps(tracks)
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_ytm_playlists(provider_token, limit=50):
    """Get user's YouTube Music playlists."""
    try:
        ytm = _get_ytm_authed(provider_token)
        playlists = ytm.get_library_playlists(limit=limit)
        out = []
        for p in playlists[:limit]:
            thumbs = p.get("thumbnails", [])
            out.append({
                "playlistId": p.get("playlistId", ""),
                "title": p.get("title", ""),
                "thumb": thumbs[-1].get("url", "") if thumbs else "",
                "count": p.get("count", ""),
            })
        return json.dumps(out)
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_ytm_history(provider_token):
    """Get user's YouTube Music history."""
    try:
        ytm = _get_ytm_authed(provider_token)
        history = ytm.get_history()
        tracks = []
        for item in history:
            t = _track_from_song(item)
            if t:
                tracks.append(t)
        return json.dumps(tracks)
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_charts(country="US", limit=50):
    """Get charts (top singles/trending). Returns JSON.
    v2.2.70: YouTube removed the songs list from charts - now pulls
    tracks from a charts playlist instead.
    v2.2.88: the old code grabbed the first "trending" playlist, which is now
    "Trending 20" (20 tracks max) - the shelf looked short. Prefer the
    "Top 100 Music Videos" playlist (100 tracks) instead; fall back to the
    old first-trending-match only if the Top 100 entry is absent."""
    try:
        ytm = _get_ytm()
        charts = ytm.get_charts(country=country)
        tracks = []
        # Prefer the Top 100 playlist; fall back to the first trending match.
        videos = charts.get("videos", []) or []
        chart_id = None
        for v in videos:
            title = (v.get("title") or "").lower()
            if "top 100" in title:
                chart_id = v.get("playlistId")
                break
        if not chart_id:
            for v in videos:
                title = (v.get("title") or "").lower()
                if "trending" in title:
                    chart_id = v.get("playlistId")
                    break
        if chart_id:
            pl = ytm.get_playlist(chart_id, limit=limit)
            for item in pl.get("tracks", [])[:limit]:
                artists = item.get("artists", [])
                artist = artists[0].get("name", "") if artists else ""
                thumbs = item.get("thumbnails", [])
                thumb = thumbs[-1].get("url", "") if thumbs else ""
                t = {
                    "videoId": item.get("videoId", ""),
                    "title": item.get("title", ""),
                    "channel": artist,
                    "ownerChannel": artist,
                    "thumb": thumb,
                    "art": thumb,
                }
                if t["title"] and t["videoId"]:
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

def find_album_browse_id(album_name, artist_name=""):
    """Find album browseId by searching. Returns JSON with browseId or error."""
    try:
        ytm = _get_ytm()
        # v2.2.57: Try multiple search strategies
        queries = []
        if artist_name:
            queries.append(artist_name + " " + album_name)
        queries.append(album_name)
        
        for query in queries:
            try:
                # Try with albums filter first
                results = ytm.search(query, filter="albums", limit=10)
                for r in results:
                    rtitle = r.get("title", "").lower()
                    aname = album_name.lower()
                    # Fuzzy match
                    if aname in rtitle or rtitle in aname:
                        bid = r.get("browseId", "")
                        if bid:
                            return json.dumps({"browseId": bid})
                # If no fuzzy match, try first result
                if results:
                    bid = results[0].get("browseId", "")
                    if bid:
                        return json.dumps({"browseId": bid})
            except Exception:
                continue
            # Try without filter as fallback
            try:
                results = ytm.search(query, limit=10)
                for r in results:
                    if r.get("resultType") in ("album", "single"):
                        rtitle = r.get("title", "").lower()
                        aname = album_name.lower()
                        if aname in rtitle or rtitle in aname:
                            bid = r.get("browseId", "")
                            if bid:
                                return json.dumps({"browseId": bid})
            except Exception:
                continue
        return json.dumps({"error": "Not found: " + album_name})
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_album(browse_id, limit=50):
    """Get album tracks. Returns JSON array."""
    try:
        ytm = _get_ytm()
        album = ytm.get_album(browse_id)
        album_title = album.get("title", "")
        # Get artist name from album info
        artists = album.get("artists", [])
        artist_name = artists[0].get("name", "") if artists else ""
        # v2.2.51: Get album art for tracks
        athumbs = album.get("thumbnails", [])
        album_thumb = athumbs[-1].get("url", "") if athumbs else ""
        tracks = []
        for item in album.get("tracks", [])[:limit]:
            t = _track_from_song(item)
            if t:
                t["album"] = album_title
                # Fill in artist if missing
                if not t.get("channel") and artist_name:
                    t["channel"] = artist_name
                    t["ownerChannel"] = artist_name
                # v2.2.51: Use album art if track has no thumb
                if not t.get("thumb") and album_thumb:
                    t["thumb"] = album_thumb
                    t["art"] = album_thumb
                tracks.append(t)
            else:
                # v2.2.50: Fallback - try to construct track manually if _track_from_song failed
                video_id = item.get("videoId", "")
                if video_id:
                    tracks.append({
                        "videoId": video_id,
                        "title": item.get("title", ""),
                        "channel": artist_name,
                        "ownerChannel": artist_name,
                        "album": album_title,
                        "dur": item.get("duration", "") or item.get("length", ""),
                        "thumb": album_thumb,
                        "art": album_thumb,
                    })
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

def get_album_info(browse_id):
    """Get album metadata (title, artist, artistId, year, thumb). Returns JSON object."""
    try:
        ytm = _get_ytm()
        album = ytm.get_album(browse_id)
        artists = album.get("artists", [])
        artist = artists[0] if artists else {}
        thumbs = album.get("thumbnails", [])
        thumb_url = thumbs[-1].get("url", "") if thumbs else ""
        return json.dumps({
            "title": album.get("title", ""),
            "artist": artist.get("name", "") if isinstance(artist, dict) else "",
            "artistId": artist.get("id", "") if isinstance(artist, dict) else "",
            "year": str(album.get("year", "") or ""),
            "type": album.get("type", ""),
            "thumb": thumb_url,
            "browseId": browse_id,
            # v2.2.84: album description for the album page ("...More" expander).
            # ytmusicapi's get_album() carries this (e.g. "Dead Reflection is the
            # ninth studio album by the Canadian post-hardcore band ...").
            "description": album.get("description", "") or "",
        })
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_new_releases(limit=50):
    """Get new album/single releases. Returns JSON array of typed items.
    v2.2.82: was ytm.search("new album <year>") which is relevance-ranked, not
    date-ranked — the same popular albums matched that query day after day, so
    the shelf never looked fresh. Now uses YouTube Music's real "New releases"
    home section via ytm.get_home(), which YouTube updates with genuinely new
    items.
    v2.2.88: the curated section holds only ~10 items, so the shelf looked
    short. Keep the curated items FIRST (freshness), then top up with the
    search-based queries (deduped) until the list reaches `limit` (~40-50)
    or the searches run dry."""
    TARGET = limit or 50
    try:
        ytm = _get_ytm()
        items = []
        seen = set()
        try:
            home = ytm.get_home(limit=10) or []
            section = None
            for s in home:
                t = (s.get("title") or "").lower()
                if "new release" in t:
                    section = s
                    break
            if section:
                for item in section.get("contents", []):
                    browse_id = item.get("browseId", "") or ""
                    if not browse_id.startswith("MPRE") or browse_id in seen:
                        continue
                    thumbnails = item.get("thumbnails", [])
                    thumb_url = thumbnails[-1].get("url", "") if thumbnails else ""
                    artists = item.get("artists", [])
                    artist_name = artists[0].get("name", "") if artists else ""
                    # v2.2.97: English-only filter (Latin-script title + artist).
                    if not _is_latin_item(item.get("title", ""), artist_name):
                        continue
                    seen.add(browse_id)
                    rtype = (item.get("type") or "").lower()
                    kind = "single" if rtype == "single" else ("ep" if rtype == "ep" else "album")
                    items.append({
                        "browseId": browse_id,
                        "title": item.get("title", ""),
                        "artist": artist_name,
                        "year": str(item.get("year", "") or ""),
                        "thumb": thumb_url,
                        "explicit": bool(item.get("isExplicit", False)),
                        "kind": kind,
                    })
        except Exception:
            pass
        # Top-up: search-based queries for depth (curated items stay first).
        if len(items) < TARGET:
            import datetime
            year = datetime.datetime.now().year
            for query in ["new album %s" % year, "new releases %s" % year, "new music"]:
                try:
                    # v2.2.97: wider net (60/query) so the list still fills to
                    # TARGET after the English-only filter drops items.
                    results = ytm.search(query, filter="albums", limit=60)
                    for item in results:
                        browse_id = item.get("browseId", "") or ""
                        if not browse_id or browse_id in seen:
                            continue
                        thumbnails = item.get("thumbnails", [])
                        thumb_url = thumbnails[-1].get("url", "") if thumbnails else ""
                        artists = item.get("artists", [])
                        artist_name = artists[0].get("name", "") if artists else ""
                        # v2.2.97: English-only filter — applied BEFORE the
                        # item counts toward TARGET, so topping up continues
                        # with later results instead of the list going short.
                        if not _is_latin_item(item.get("title", ""), artist_name):
                            continue
                        seen.add(browse_id)
                        items.append({
                            "browseId": browse_id,
                            "title": item.get("title", ""),
                            "artist": artist_name,
                            "year": str(item.get("year", "") or ""),
                            "thumb": thumb_url,
                            "explicit": False,
                            "kind": "album",
                        })
                        if len(items) >= TARGET:
                            break
                except Exception:
                    continue
                if len(items) >= TARGET:
                    break
        return json.dumps(items[:TARGET])
    except Exception as e:
        return json.dumps({"error": str(e)})

def get_playable_stream(title, artist, video_id, max_alternatives=2):
    """Get a playable stream URL, trying alternatives if the primary fails.
    Returns JSON with url and videoId, or error if all fail.
    This is the permanent fix for skipped tracks."""
    import yt_dlp
    
    def try_video_id(vid):
        """Try to get stream URL for a video ID. Returns URL or None."""
        try:
            url = "https://www.youtube.com/watch?v=" + vid
            ydl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'noplaylist': True,
                'socket_timeout': 10,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                stream_url = info.get('url', '')
                if not stream_url:
                    for f in info.get('formats', []):
                        if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                            stream_url = f.get('url', '')
                            if stream_url:
                                break
                    if not stream_url and info.get('formats'):
                        stream_url = info['formats'][0].get('url', '')
                return stream_url if stream_url else None
        except:
            return None
    
    # Try the primary video ID first
    url = try_video_id(video_id)
    if url:
        return json.dumps({"url": url, "videoId": video_id})
    
    # Primary failed - search for alternatives
    try:
        ytm = _get_ytm()
        query = f"{artist} {title}".strip()
        if not query:
            return json.dumps({"error": "No query for alternatives"})
        
        results = ytm.search(query, filter="songs", limit=10)
        tried = {video_id}
        for item in results:
            vid = item.get("videoId", "")
            if not vid or vid in tried:
                continue
            # Skip music videos
            if item.get("videoType", "") == "MUSIC_VIDEO_TYPE_OMV":
                continue
            tried.add(vid)
            url = try_video_id(vid)
            if url:
                return json.dumps({"url": url, "videoId": vid, "alternative": True})
            if len(tried) > max_alternatives + 1:
                break
    except Exception as e:
        pass
    
    return json.dumps({"error": "All alternatives failed"})

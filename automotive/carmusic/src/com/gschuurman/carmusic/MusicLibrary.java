package com.gschuurman.carmusic;

import android.content.ContentResolver;
import android.content.ContentUris;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.provider.MediaStore;
import android.provider.MediaStore.Audio;
import android.support.v4.media.MediaBrowserCompat.MediaItem;
import android.support.v4.media.MediaDescriptionCompat;
import android.support.v4.media.MediaMetadataCompat;

import java.util.ArrayList;
import java.util.List;
import java.util.TreeSet;

/**
 * The music library: audio files in the Driver user's Music folder (primary external volume),
 * read through MediaStore. USB volumes are not part of the library; their music is imported.
 *
 * <p>Media ids: browsable nodes are ROOT, PLAYLISTS, SONGS, ALBUMS, ARTISTS, FOLDERS, the app
 * playlists FAVORITES, PLAYED and RECENT, "album:<id>", "artist:<id>", "playlist:<MediaStore
 * playlist id>" and "folder:<relative path>". A playable song is "<parent id>|<audio id>", so
 * playing it queues the songs of the node it was picked from; "shuffle:<parent id>" plays that
 * node shuffled.
 */
final class MusicLibrary {
    static final String ROOT = "root";
    static final String PLAYLISTS = "playlists";
    static final String FAVORITES = "favorites";
    static final String PLAYED = "played";
    static final String SONGS = "songs";
    static final String ALBUMS = "albums";
    static final String ARTISTS = "artists";
    static final String FOLDERS = "folders";
    static final String RECENT = "recent";
    static final String SHUFFLE = "shuffle:";
    private static final String ALBUM = "album:";
    private static final String PLAYLIST = "playlist:";
    private static final String ARTIST = "artist:";
    private static final String FOLDER = "folder:";
    private static final String SEPARATOR = "|";
    /** Root of the folder view; files are imported below it. */
    static final String MUSIC_DIR = "Music/";
    private static final long RECENT_SECONDS = 30L * 24 * 3600;
    private static final int RECENT_LIMIT = 200;

    // Content style hints for the car Media app: grid for albums/artists, list for songs.
    private static final String CONTENT_STYLE_BROWSABLE =
            "android.media.browse.CONTENT_STYLE_BROWSABLE_HINT";
    private static final String CONTENT_STYLE_PLAYABLE =
            "android.media.browse.CONTENT_STYLE_PLAYABLE_HINT";
    private static final int STYLE_LIST = 1, STYLE_GRID = 2;

    private static final Uri AUDIO = Audio.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
    private static final Uri ALBUMS_URI = Audio.Albums.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
    private static final Uri ARTISTS_URI = Audio.Artists.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
    private static final Uri PLAYLISTS_URI =
            Audio.Playlists.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
    private static final String[] SONG_COLUMNS = {
            Audio.Media._ID, Audio.Media.TITLE, Audio.Media.ARTIST, Audio.Media.ALBUM,
            Audio.Media.ALBUM_ID, Audio.Media.DURATION, Audio.Media.RELATIVE_PATH};
    private static final String MUSIC_ONLY = Audio.Media.IS_MUSIC + " != 0";

    /** A song from the library. */
    static final class Song {
        final long id;
        final String title, artist, album;
        final long albumId, durationMs;

        Song(Cursor c) {
            id = c.getLong(0);
            title = c.getString(1);
            artist = c.getString(2);
            album = c.getString(3);
            albumId = c.getLong(4);
            durationMs = c.getLong(5);
        }

        Uri uri() {
            return ContentUris.withAppendedId(AUDIO, id);
        }

        MediaMetadataCompat metadata() {
            return new MediaMetadataCompat.Builder()
                    .putString(MediaMetadataCompat.METADATA_KEY_MEDIA_ID, String.valueOf(id))
                    .putString(MediaMetadataCompat.METADATA_KEY_TITLE, title)
                    .putString(MediaMetadataCompat.METADATA_KEY_ARTIST, artist)
                    .putString(MediaMetadataCompat.METADATA_KEY_ALBUM, album)
                    .putString(MediaMetadataCompat.METADATA_KEY_DISPLAY_ICON_URI, artUri(albumId).toString())
                    .putString(MediaMetadataCompat.METADATA_KEY_ALBUM_ART_URI, artUri(albumId).toString())
                    .putLong(MediaMetadataCompat.METADATA_KEY_DURATION, durationMs)
                    .build();
        }
    }

    private final Context mContext;
    private final ContentResolver mResolver;
    private final PlaylistStore mStore;

    MusicLibrary(Context context, PlaylistStore store) {
        mContext = context;
        mResolver = context.getContentResolver();
        mStore = store;
    }

    static Uri artUri(long albumId) {
        return Uri.parse("content://" + ArtProvider.AUTHORITY + "/album/" + albumId);
    }

    static String songId(String parentId, long audioId) {
        return parentId + SEPARATOR + audioId;
    }

    /** Parent node of a playable song id, or null. */
    static String parentOf(String mediaId) {
        final int i = mediaId.lastIndexOf(SEPARATOR);
        return i > 0 ? mediaId.substring(0, i) : null;
    }

    /** Audio id of a playable song id, or -1. */
    static long audioIdOf(String mediaId) {
        final int i = mediaId.lastIndexOf(SEPARATOR);
        try {
            return i > 0 ? Long.parseLong(mediaId.substring(i + 1)) : -1;
        } catch (NumberFormatException e) {
            return -1;
        }
    }

    /** Children of a browsable node, for MediaBrowserService.onLoadChildren. */
    List<MediaItem> children(String parentId) {
        final List<MediaItem> items = new ArrayList<>();
        if (ROOT.equals(parentId)) {
            items.add(browsable(PLAYLISTS, mContext.getString(R.string.browse_playlists), STYLE_LIST));
            items.add(browsable(SONGS, mContext.getString(R.string.browse_songs), STYLE_LIST));
            items.add(browsable(ALBUMS, mContext.getString(R.string.browse_albums), STYLE_GRID));
            items.add(browsable(ARTISTS, mContext.getString(R.string.browse_artists), STYLE_LIST));
            items.add(browsable(FOLDERS, mContext.getString(R.string.browse_folders), STYLE_LIST));
        } else if (PLAYLISTS.equals(parentId)) {
            items.add(browsable(FAVORITES, mContext.getString(R.string.playlist_favorites), STYLE_LIST));
            items.add(browsable(PLAYED, mContext.getString(R.string.playlist_played), STYLE_LIST));
            items.add(browsable(RECENT, mContext.getString(R.string.browse_recent), STYLE_LIST));
            try (Cursor c = mResolver.query(PLAYLISTS_URI, new String[] {Audio.Playlists._ID,
                    Audio.Playlists.NAME}, null, null, Audio.Playlists.NAME)) {
                while (c != null && c.moveToNext()) {
                    items.add(browsable(PLAYLIST + c.getLong(0), c.getString(1), STYLE_LIST));
                }
            }
        } else if (ALBUMS.equals(parentId)) {
            try (Cursor c = mResolver.query(ALBUMS_URI, new String[] {Audio.Albums._ID,
                    Audio.Albums.ALBUM, Audio.Albums.ARTIST}, null, null, Audio.Albums.ALBUM)) {
                while (c != null && c.moveToNext()) {
                    items.add(new MediaItem(new MediaDescriptionCompat.Builder()
                            .setMediaId(ALBUM + c.getLong(0))
                            .setTitle(c.getString(1))
                            .setSubtitle(c.getString(2))
                            .setIconUri(artUri(c.getLong(0)))
                            .build(), MediaItem.FLAG_BROWSABLE));
                }
            }
        } else if (ARTISTS.equals(parentId)) {
            try (Cursor c = mResolver.query(ARTISTS_URI, new String[] {Audio.Artists._ID,
                    Audio.Artists.ARTIST, Audio.Artists.NUMBER_OF_TRACKS}, null, null,
                    Audio.Artists.ARTIST)) {
                while (c != null && c.moveToNext()) {
                    items.add(new MediaItem(new MediaDescriptionCompat.Builder()
                            .setMediaId(ARTIST + c.getLong(0))
                            .setTitle(c.getString(1))
                            .setSubtitle(mContext.getResources().getQuantityString(
                                    R.plurals.song_count, c.getInt(2), c.getInt(2)))
                            .build(), MediaItem.FLAG_BROWSABLE));
                }
            }
        } else if (FOLDERS.equals(parentId) || parentId.startsWith(FOLDER)) {
            final String path = FOLDERS.equals(parentId) ? MUSIC_DIR : parentId.substring(FOLDER.length());
            for (String sub : subfolders(path)) {
                final String name = sub.substring(path.length(), sub.length() - 1);
                items.add(browsable(FOLDER + sub, name, STYLE_LIST));
            }
            addSongs(items, FOLDER + path, songs(FOLDER + path));
        } else {
            addSongs(items, parentId, songs(parentId));
        }
        return items;
    }

    /** Songs of a browsable node (also the play queue for a song picked from it). */
    List<Song> songs(String parentId) {
        if (FAVORITES.equals(parentId)) return songsById(mStore.favorites());
        if (PLAYED.equals(parentId)) return songsById(mStore.recentlyPlayed());
        if (parentId.startsWith(PLAYLIST)) return playlist(parentId.substring(PLAYLIST.length()));
        String selection = MUSIC_ONLY;
        String[] args = null;
        String order = Audio.Media.TITLE;
        if (parentId.startsWith(ALBUM)) {
            selection += " AND " + Audio.Media.ALBUM_ID + " = ?";
            args = new String[] {parentId.substring(ALBUM.length())};
            order = Audio.Media.DISC_NUMBER + ", " + Audio.Media.TRACK + ", " + Audio.Media.TITLE;
        } else if (parentId.startsWith(ARTIST)) {
            selection += " AND " + Audio.Media.ARTIST_ID + " = ?";
            args = new String[] {parentId.substring(ARTIST.length())};
            order = Audio.Media.ALBUM + ", " + Audio.Media.TRACK;
        } else if (parentId.startsWith(FOLDER)) {
            // Folder contents are files in any audio category (audiobooks, etc. included).
            selection = Audio.Media.RELATIVE_PATH + " = ?";
            args = new String[] {parentId.substring(FOLDER.length())};
            order = Audio.Media.TRACK + ", " + Audio.Media.DISPLAY_NAME;
        } else if (RECENT.equals(parentId)) {
            selection += " AND " + Audio.Media.DATE_ADDED + " > ?";
            args = new String[] {String.valueOf(System.currentTimeMillis() / 1000 - RECENT_SECONDS)};
            return query(selection, args, Audio.Media.DATE_ADDED + " DESC", RECENT_LIMIT);
        } else if (!SONGS.equals(parentId)) {
            return new ArrayList<>();
        }
        return query(selection, args, order);
    }

    private static final String GROUP_TITLE = "android.media.browse.CONTENT_STYLE_GROUP_TITLE_HINT";
    private static final int SEARCH_LIMIT = 50;

    /**
     * Search results for the Media app, grouped: artists, albums and playlists matching the query
     * (browsable), then the matching songs. Every word of the query has to occur in one of the
     * searched fields (case-insensitive), so "daft discovery" finds the album.
     */
    List<MediaItem> searchItems(String query) {
        final List<MediaItem> items = new ArrayList<>();
        final String[] words = words(query);
        if (words.length == 0) return items;

        final String artistGroup = mContext.getString(R.string.browse_artists);
        try (Cursor c = query(ARTISTS_URI, new String[] {Audio.Artists._ID,
                Audio.Artists.ARTIST, Audio.Artists.NUMBER_OF_TRACKS},
                allWords(words.length, Audio.Artists.ARTIST), likeArgs(words, 1),
                Audio.Artists.ARTIST, SEARCH_LIMIT)) {
            while (c != null && c.moveToNext()) {
                items.add(new MediaItem(new MediaDescriptionCompat.Builder()
                        .setMediaId(ARTIST + c.getLong(0))
                        .setTitle(c.getString(1))
                        .setSubtitle(mContext.getResources().getQuantityString(
                                R.plurals.song_count, c.getInt(2), c.getInt(2)))
                        .setExtras(group(artistGroup))
                        .build(), MediaItem.FLAG_BROWSABLE));
            }
        }
        final String albumGroup = mContext.getString(R.string.browse_albums);
        try (Cursor c = query(ALBUMS_URI, new String[] {Audio.Albums._ID,
                Audio.Albums.ALBUM, Audio.Albums.ARTIST},
                allWords(words.length, Audio.Albums.ALBUM, Audio.Albums.ARTIST), likeArgs(words, 2),
                Audio.Albums.ALBUM, SEARCH_LIMIT)) {
            while (c != null && c.moveToNext()) {
                items.add(new MediaItem(new MediaDescriptionCompat.Builder()
                        .setMediaId(ALBUM + c.getLong(0))
                        .setTitle(c.getString(1))
                        .setSubtitle(c.getString(2))
                        .setIconUri(artUri(c.getLong(0)))
                        .setExtras(group(albumGroup))
                        .build(), MediaItem.FLAG_BROWSABLE));
            }
        }
        final String playlistGroup = mContext.getString(R.string.browse_playlists);
        try (Cursor c = query(PLAYLISTS_URI, new String[] {Audio.Playlists._ID,
                Audio.Playlists.NAME}, allWords(words.length, Audio.Playlists.NAME),
                likeArgs(words, 1), Audio.Playlists.NAME, SEARCH_LIMIT)) {
            while (c != null && c.moveToNext()) {
                items.add(new MediaItem(new MediaDescriptionCompat.Builder()
                        .setMediaId(PLAYLIST + c.getLong(0))
                        .setTitle(c.getString(1))
                        .setExtras(group(playlistGroup))
                        .build(), MediaItem.FLAG_BROWSABLE));
            }
        }
        final String songGroup = mContext.getString(R.string.browse_songs);
        final String parent = "search:" + query;
        for (Song song : search(query)) {
            items.add(new MediaItem(new MediaDescriptionCompat.Builder()
                    .setMediaId(songId(parent, song.id))
                    .setTitle(song.title).setSubtitle(song.artist).setDescription(song.album)
                    .setIconUri(artUri(song.albumId))
                    .setExtras(group(songGroup))
                    .build(), MediaItem.FLAG_PLAYABLE));
        }
        return items;
    }

    /**
     * Songs matching every word of 'query' in title, artist, album or folder (untagged music is
     * found by its folder names); also the queue of a picked hit.
     */
    List<Song> search(String query) {
        final String[] words = words(query);
        if (words.length == 0) return new ArrayList<>();
        return query(MUSIC_ONLY + " AND " + allWords(words.length, Audio.Media.TITLE,
                Audio.Media.ARTIST, Audio.Media.ALBUM, Audio.Media.RELATIVE_PATH), likeArgs(words, 4),
                Audio.Media.ARTIST + ", " + Audio.Media.ALBUM + ", " + Audio.Media.TRACK,
                SEARCH_LIMIT * 4);
    }

    private static String[] words(String query) {
        final String q = query == null ? "" : query.trim().replace("%", "").replace("_", " ");
        return q.isEmpty() ? new String[0] : q.split("\\s+");
    }

    /** "(f1 LIKE ? OR f2 LIKE ?) AND ..." with one group per word. */
    private static String allWords(int words, String... fields) {
        final StringBuilder sb = new StringBuilder();
        for (int w = 0; w < words; ++w) {
            if (w > 0) sb.append(" AND ");
            sb.append('(');
            for (int f = 0; f < fields.length; ++f) {
                if (f > 0) sb.append(" OR ");
                sb.append(fields[f]).append(" LIKE ?");
            }
            sb.append(')');
        }
        return sb.toString();
    }

    private static String[] likeArgs(String[] words, int fields) {
        final String[] args = new String[words.length * fields];
        for (int w = 0; w < words.length; ++w) {
            for (int f = 0; f < fields; ++f) args[w * fields + f] = "%" + words[w] + "%";
        }
        return args;
    }

    private static Bundle group(String title) {
        final Bundle extras = new Bundle();
        extras.putString(GROUP_TITLE, title);
        return extras;
    }

    /** Looks up songs by audio id, in the given order; ids no longer in the library are dropped. */
    List<Song> songsById(List<Long> ids) {
        final List<Song> songs = new ArrayList<>();
        if (ids.isEmpty()) return songs;
        final java.util.Map<Long, Song> found = new java.util.HashMap<>();
        // In chunks, to stay below SQLite's bound-parameter limit.
        for (int from = 0; from < ids.size(); from += 500) {
            final List<Long> chunk = ids.subList(from, Math.min(ids.size(), from + 500));
            final StringBuilder in = new StringBuilder();
            final String[] args = new String[chunk.size()];
            for (int i = 0; i < chunk.size(); ++i) {
                in.append(i == 0 ? "?" : ",?");
                args[i] = String.valueOf(chunk.get(i));
            }
            for (Song s : query(Audio.Media._ID + " IN (" + in + ")", args, null)) found.put(s.id, s);
        }
        for (long id : ids) {
            final Song s = found.get(id);
            if (s != null) songs.add(s);
        }
        return songs;
    }

    /** Members of a MediaStore playlist (M3U/PLS file in the Music folder), in play order. */
    private List<Song> playlist(String playlistId) {
        final List<Long> ids = new ArrayList<>();
        try {
            final Uri members = Audio.Playlists.Members.getContentUri(
                    MediaStore.VOLUME_EXTERNAL_PRIMARY, Long.parseLong(playlistId));
            try (Cursor c = mResolver.query(members, new String[] {Audio.Playlists.Members.AUDIO_ID},
                    null, null, Audio.Playlists.Members.PLAY_ORDER)) {
                while (c != null && c.moveToNext()) ids.add(c.getLong(0));
            }
        } catch (NumberFormatException e) {
            // Not a playlist id.
        }
        return songsById(ids);
    }

    private List<Song> query(String selection, String[] args, String order) {
        return query(selection, args, order, 0);
    }

    private List<Song> query(String selection, String[] args, String order, int limit) {
        final List<Song> songs = new ArrayList<>();
        try (Cursor c = query(AUDIO, SONG_COLUMNS, selection, args, order, limit)) {
            while (c != null && c.moveToNext()) songs.add(new Song(c));
        }
        return songs;
    }

    /** ContentResolver query with an optional row limit (MediaProvider rejects "LIMIT" in the order). */
    private Cursor query(Uri uri, String[] projection, String selection, String[] args, String order,
            int limit) {
        final Bundle q = new Bundle();
        if (selection != null) q.putString(ContentResolver.QUERY_ARG_SQL_SELECTION, selection);
        if (args != null) q.putStringArray(ContentResolver.QUERY_ARG_SQL_SELECTION_ARGS, args);
        if (order != null) q.putString(ContentResolver.QUERY_ARG_SQL_SORT_ORDER, order);
        if (limit > 0) q.putInt(ContentResolver.QUERY_ARG_LIMIT, limit);
        return mResolver.query(uri, projection, q, null);
    }

    /** Direct subfolders of 'path' (e.g. "Music/") that contain audio, as relative paths. */
    private List<String> subfolders(String path) {
        final TreeSet<String> result = new TreeSet<>(String.CASE_INSENSITIVE_ORDER);
        try (Cursor c = mResolver.query(AUDIO, new String[] {Audio.Media.RELATIVE_PATH},
                Audio.Media.RELATIVE_PATH + " LIKE ? AND " + Audio.Media.RELATIVE_PATH + " != ?",
                new String[] {path.replace("%", "") + "%", path}, null)) {
            while (c != null && c.moveToNext()) {
                final String rel = c.getString(0);
                final int slash = rel.indexOf('/', path.length());
                if (slash > 0) result.add(rel.substring(0, slash + 1));
            }
        }
        return new ArrayList<>(result);
    }

    private void addSongs(List<MediaItem> items, String parentId, List<Song> songs) {
        // "Shuffle" plays the whole node in random order; "Shuffle all" for the library.
        if (songs.size() > 1) {
            items.add(new MediaItem(new MediaDescriptionCompat.Builder()
                    .setMediaId(SHUFFLE + parentId)
                    .setTitle(mContext.getString(SONGS.equals(parentId) ? R.string.shuffle_all
                            : R.string.shuffle))
                    .setSubtitle(mContext.getResources().getQuantityString(
                            R.plurals.song_count, songs.size(), songs.size()))
                    // By name: the Media app's UriUtils can't resolve numeric resource ids.
                    .setIconUri(Uri.parse("android.resource://" + mContext.getPackageName()
                            + "/drawable/ic_shuffle_on"))
                    .build(), MediaItem.FLAG_PLAYABLE));
        }
        for (Song s : songs) {
            items.add(new MediaItem(new MediaDescriptionCompat.Builder()
                    .setMediaId(songId(parentId, s.id))
                    .setTitle(s.title)
                    .setSubtitle(s.artist)
                    .setDescription(s.album)
                    .setIconUri(artUri(s.albumId))
                    .build(), MediaItem.FLAG_PLAYABLE));
        }
    }

    private static MediaItem browsable(String id, String title, int childStyle) {
        final Bundle extras = new Bundle();
        extras.putInt(CONTENT_STYLE_BROWSABLE, childStyle);
        extras.putInt(CONTENT_STYLE_PLAYABLE, STYLE_LIST);
        return new MediaItem(new MediaDescriptionCompat.Builder()
                .setMediaId(id).setTitle(title).setExtras(extras).build(), MediaItem.FLAG_BROWSABLE);
    }
}

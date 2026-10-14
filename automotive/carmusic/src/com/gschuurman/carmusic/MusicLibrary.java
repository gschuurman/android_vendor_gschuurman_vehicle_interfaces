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
 * <p>Media ids: browsable nodes are ROOT, SONGS, ALBUMS, ARTISTS, FOLDERS, RECENT, "album:<id>",
 * "artist:<id>" and "folder:<relative path>". A playable song is "<parent id>|<audio id>", so
 * playing it queues the songs of the node it was picked from.
 */
final class MusicLibrary {
    static final String ROOT = "root";
    static final String SONGS = "songs";
    static final String ALBUMS = "albums";
    static final String ARTISTS = "artists";
    static final String FOLDERS = "folders";
    static final String RECENT = "recent";
    static final String SHUFFLE_ALL = "shuffle_all";
    private static final String ALBUM = "album:";
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

    MusicLibrary(Context context) {
        mContext = context;
        mResolver = context.getContentResolver();
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
            items.add(browsable(SONGS, mContext.getString(R.string.browse_songs), STYLE_LIST));
            items.add(browsable(ALBUMS, mContext.getString(R.string.browse_albums), STYLE_GRID));
            items.add(browsable(ARTISTS, mContext.getString(R.string.browse_artists), STYLE_LIST));
            items.add(browsable(FOLDERS, mContext.getString(R.string.browse_folders), STYLE_LIST));
            items.add(browsable(RECENT, mContext.getString(R.string.browse_recent), STYLE_LIST));
        } else if (SONGS.equals(parentId)) {
            final List<Song> songs = songs(SONGS);
            if (!songs.isEmpty()) {
                items.add(new MediaItem(new MediaDescriptionCompat.Builder()
                        .setMediaId(SHUFFLE_ALL)
                        .setTitle(mContext.getString(R.string.shuffle_all))
                        .setSubtitle(mContext.getResources().getQuantityString(
                                R.plurals.song_count, songs.size(), songs.size()))
                        .build(), MediaItem.FLAG_PLAYABLE));
            }
            addSongs(items, parentId, songs);
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
            order = Audio.Media.DATE_ADDED + " DESC LIMIT " + RECENT_LIMIT;
        } else if (!SONGS.equals(parentId)) {
            return new ArrayList<>();
        }
        return query(selection, args, order);
    }

    /** Songs whose title, artist or album contains 'query'. */
    List<Song> search(String query) {
        final String like = "%" + query.replace("%", "") + "%";
        return query(MUSIC_ONLY + " AND (" + Audio.Media.TITLE + " LIKE ? OR " + Audio.Media.ARTIST
                + " LIKE ? OR " + Audio.Media.ALBUM + " LIKE ?)", new String[] {like, like, like},
                Audio.Media.ARTIST + ", " + Audio.Media.ALBUM + ", " + Audio.Media.TRACK);
    }

    /** Looks up songs by audio id, in the given order (for restoring the last queue). */
    List<Song> songsById(List<Long> ids) {
        final List<Song> songs = new ArrayList<>();
        for (long id : ids) {
            final List<Song> s = query(Audio.Media._ID + " = ?", new String[] {String.valueOf(id)}, null);
            songs.addAll(s);
        }
        return songs;
    }

    private List<Song> query(String selection, String[] args, String order) {
        final List<Song> songs = new ArrayList<>();
        try (Cursor c = mResolver.query(AUDIO, SONG_COLUMNS, selection, args, order)) {
            while (c != null && c.moveToNext()) songs.add(new Song(c));
        }
        return songs;
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

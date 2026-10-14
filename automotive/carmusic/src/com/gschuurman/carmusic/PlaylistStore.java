package com.gschuurman.carmusic;

import android.content.Context;
import android.content.SharedPreferences;
import android.text.TextUtils;

import java.util.ArrayList;
import java.util.List;

/**
 * The app's own playlists, as ordered lists of audio ids: Favorites (starred in Now Playing,
 * newest first) and Recently played (last RECENT_MAX songs, newest first).
 */
final class PlaylistStore {
    private static final String PREFS = "playlists";
    private static final String KEY_FAVORITES = "favorites";
    private static final String KEY_PLAYED = "played";
    private static final int RECENT_MAX = 100;

    private final SharedPreferences mPrefs;

    PlaylistStore(Context context) {
        mPrefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    synchronized List<Long> favorites() {
        return read(KEY_FAVORITES);
    }

    synchronized List<Long> recentlyPlayed() {
        return read(KEY_PLAYED);
    }

    synchronized boolean isFavorite(long audioId) {
        return read(KEY_FAVORITES).contains(audioId);
    }

    /** Adds or removes a favorite; returns the new state. */
    synchronized boolean toggleFavorite(long audioId) {
        final List<Long> ids = read(KEY_FAVORITES);
        final boolean add = !ids.remove(audioId);
        if (add) ids.add(0, audioId);
        write(KEY_FAVORITES, ids);
        return add;
    }

    synchronized void played(long audioId) {
        final List<Long> ids = read(KEY_PLAYED);
        ids.remove(audioId);
        ids.add(0, audioId);
        while (ids.size() > RECENT_MAX) ids.remove(ids.size() - 1);
        write(KEY_PLAYED, ids);
    }

    private List<Long> read(String key) {
        final List<Long> ids = new ArrayList<>();
        for (String s : mPrefs.getString(key, "").split(",")) {
            if (s.isEmpty()) continue;
            try {
                ids.add(Long.parseLong(s));
            } catch (NumberFormatException ignored) {
                // Skip.
            }
        }
        return ids;
    }

    private void write(String key, List<Long> ids) {
        mPrefs.edit().putString(key, TextUtils.join(",", ids)).apply();
    }
}

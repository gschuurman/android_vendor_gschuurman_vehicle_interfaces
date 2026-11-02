package com.gschuurman.carmusic;

import android.app.job.JobInfo;
import android.app.job.JobParameters;
import android.app.job.JobScheduler;
import android.app.job.JobService;
import android.content.ComponentName;
import android.content.Context;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.net.Uri;
import android.provider.MediaStore;
import android.provider.MediaStore.Audio;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;

/**
 * Fetches covers for albums that have none (no embedded art, no folder cover) from the open
 * MusicBrainz database and the Cover Art Archive: release search on artist + album, then the
 * front cover (500 px), stored as the folder cover (Covers). Runs daily and after an import, on
 * an unmetered network. Only artist and album names are sent. Follows the MusicBrainz rules: an
 * identifying User-Agent and at most one request per second.
 */
public final class CoverFetchJob extends JobService {
    private static final String TAG = "CarMusic";
    private static final int JOB_DAILY = 1, JOB_NOW = 2;
    private static final String USER_AGENT =
            "CarMusic/1.0 ( https://github.com/gschuurman/vehicle_interfaces )";
    private static final String SEARCH =
            "https://musicbrainz.org/ws/2/release/?fmt=json&limit=5&query=";
    private static final String COVER = "https://coverartarchive.org/release/%s/front-500";
    /** MusicBrainz search score (0-100) a release needs to count as the album. */
    private static final int MIN_SCORE = 90;
    private static final long REQUEST_INTERVAL_MS = 1100;
    private static final long RETRY_AFTER_MS = TimeUnit.DAYS.toMillis(30);
    private static final String PREFS = "cover_fetch";
    private static final String UNKNOWN = "<unknown>";

    private volatile boolean mStopped;
    private long mLastRequest;

    /** Daily run, plus one as soon as possible (e.g. after an import). */
    static void schedule(Context context, boolean now) {
        final JobScheduler js = context.getSystemService(JobScheduler.class);
        final ComponentName service = new ComponentName(context, CoverFetchJob.class);
        if (js.getPendingJob(JOB_DAILY) == null) {
            js.schedule(new JobInfo.Builder(JOB_DAILY, service)
                    .setRequiredNetworkType(JobInfo.NETWORK_TYPE_UNMETERED)
                    .setPeriodic(TimeUnit.DAYS.toMillis(1))
                    .setPersisted(true)
                    .build());
        }
        if (now) {
            js.schedule(new JobInfo.Builder(JOB_NOW, service)
                    .setRequiredNetworkType(JobInfo.NETWORK_TYPE_UNMETERED)
                    .build());
        }
    }

    @Override
    public boolean onStartJob(JobParameters params) {
        mStopped = false;
        new Thread(() -> {
            boolean changed = false;
            try {
                changed = fetchMissing();
            } catch (RuntimeException e) {
                Log.w(TAG, "Cover fetch failed", e);
            }
            if (changed) ArtProvider.invalidate(this);
            jobFinished(params, false);
        }, "CarMusicCovers").start();
        return true;
    }

    @Override
    public boolean onStopJob(JobParameters params) {
        mStopped = true;
        return true;  // Try again later.
    }

    /** Returns true if a cover was added. */
    private boolean fetchMissing() {
        final SharedPreferences tried = getSharedPreferences(PREFS, MODE_PRIVATE);
        boolean changed = false;
        try (Cursor c = getContentResolver().query(
                Audio.Albums.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY),
                new String[] {Audio.Albums._ID, Audio.Albums.ALBUM, Audio.Albums.ARTIST},
                null, null, null)) {
            while (c != null && c.moveToNext() && !mStopped) {
                final long albumId = c.getLong(0);
                String album = c.getString(1), artist = c.getString(2);
                final String folder = folderOf(albumId);
                if (folder == null) continue;
                // Untagged files: take "Music/<artist>/<album>/" from the folders.
                final String[] parts = folder.split("/");
                if ((artist == null || UNKNOWN.equals(artist)) && parts.length == 3
                        && parts[2].equals(album)) {
                    artist = parts[1];
                }
                if (album == null || artist == null || UNKNOWN.equals(album) || UNKNOWN.equals(artist)) {
                    continue;
                }
                final String key = artist + "\u0000" + album;
                if (System.currentTimeMillis() - tried.getLong(key, 0) < RETRY_AFTER_MS) continue;
                if (Covers.file(this, folder).exists() || hasEmbeddedArt(albumId)) continue;
                try {
                    if (fetch(artist, album, Covers.file(this, folder))) {
                        changed = true;
                        Log.i(TAG, "Cover found for " + artist + " - " + album);
                    } else {
                        tried.edit().putLong(key, System.currentTimeMillis()).apply();
                    }
                } catch (IOException e) {
                    // Network trouble: not remembered, so the next run tries again.
                    Log.w(TAG, "Cover lookup for " + artist + " - " + album + ": " + e.getMessage());
                    break;
                }
            }
        }
        return changed;
    }

    private String folderOf(long albumId) {
        try (Cursor c = getContentResolver().query(
                Audio.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY),
                new String[] {Audio.Media.RELATIVE_PATH}, Audio.Media.ALBUM_ID + " = ?",
                new String[] {String.valueOf(albumId)}, null)) {
            return c != null && c.moveToFirst() ? c.getString(0) : null;
        }
    }

    private boolean hasEmbeddedArt(long albumId) {
        try {
            getContentResolver().loadThumbnail(android.content.ContentUris.withAppendedId(
                    Audio.Albums.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY), albumId),
                    new android.util.Size(64, 64), null);
            return true;
        } catch (IOException e) {
            return false;
        }
    }

    /** Looks the album up and stores its front cover in 'target'; false if there is none. */
    private boolean fetch(String artist, String album, File target) throws IOException {
        final String query = "release:\"" + escape(album) + "\" AND artist:\"" + escape(artist) + "\"";
        final JSONArray releases;
        try {
            releases = new JSONObject(new String(get(SEARCH + Uri.encode(query)),
                    StandardCharsets.UTF_8)).optJSONArray("releases");
        } catch (org.json.JSONException e) {
            throw new IOException("bad search response");
        }
        if (releases == null) return false;
        for (int i = 0; i < releases.length() && !mStopped; ++i) {
            final JSONObject r = releases.optJSONObject(i);
            if (r == null || r.optInt("score") < MIN_SCORE) break;  // sorted by score
            final byte[] image;
            try {
                image = get(String.format(COVER, r.optString("id")));
            } catch (FileNotFoundException404 e) {
                continue;  // This release has no cover; try the next one.
            }
            final File tmp = new File(target.getPath() + ".tmp");
            try (FileOutputStream out = new FileOutputStream(tmp)) {
                out.write(image);
            }
            return tmp.renameTo(target);
        }
        return false;
    }

    private static final class FileNotFoundException404 extends IOException {
        FileNotFoundException404() {
            super("404");
        }
    }

    /**
     * HTTP GET with the MusicBrainz rate limit; follows the archive's redirects to the image and
     * backs off (2, 4, 8 s) when MusicBrainz answers 503 (rate limited).
     */
    private byte[] get(String url) throws IOException {
        long backoffMs = 2000;
        for (int attempt = 0; attempt < 8; ++attempt) {
            final long wait = mLastRequest + REQUEST_INTERVAL_MS - System.currentTimeMillis();
            if (wait > 0) {
                try {
                    Thread.sleep(wait);
                } catch (InterruptedException e) {
                    throw new IOException("interrupted");
                }
            }
            mLastRequest = System.currentTimeMillis();
            final HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
            conn.setRequestProperty("User-Agent", USER_AGENT);
            conn.setRequestProperty("Accept", "application/json, image/*");
            conn.setConnectTimeout(15000);
            conn.setReadTimeout(30000);
            conn.setInstanceFollowRedirects(false);
            try {
                final int code = conn.getResponseCode();
                if (code / 100 == 3) {
                    url = new URL(new URL(url), conn.getHeaderField("Location")).toString();
                    continue;
                }
                if (code == 404) throw new FileNotFoundException404();
                if (code == 503 && backoffMs <= 8000) {
                    try {
                        Thread.sleep(backoffMs);
                    } catch (InterruptedException e) {
                        throw new IOException("interrupted");
                    }
                    backoffMs *= 2;
                    continue;
                }
                if (code != 200) throw new IOException("HTTP " + code);
                try (InputStream in = conn.getInputStream()) {
                    final ByteArrayOutputStream out = new ByteArrayOutputStream();
                    final byte[] buffer = new byte[16384];
                    int n;
                    while ((n = in.read(buffer)) > 0) out.write(buffer, 0, n);
                    return out.toByteArray();
                }
            } finally {
                conn.disconnect();
            }
        }
        throw new IOException("too many redirects or retries");
    }

    /** Escapes Lucene query syntax inside a quoted phrase. */
    private static String escape(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }
}

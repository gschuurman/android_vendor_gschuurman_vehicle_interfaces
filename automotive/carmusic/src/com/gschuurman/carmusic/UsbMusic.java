package com.gschuurman.carmusic;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.os.Environment;
import android.os.storage.StorageManager;
import android.os.storage.StorageVolume;
import android.provider.MediaStore;
import android.provider.MediaStore.Audio;
import android.util.Log;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Music on USB storage: finds mounted removable volumes, lists their audio files and copies them
 * into the Music folder (MediaStore, primary volume), keeping the folder structure and skipping
 * files that are already there. Files are read through the media FUSE view (READ_MEDIA_AUDIO).
 */
final class UsbMusic {
    private static final String TAG = "CarMusic";
    private static final int BUFFER = 1 << 20;

    private static final Map<String, String> MIME_TYPES = Map.of(
            "mp3", "audio/mpeg", "flac", "audio/flac", "m4a", "audio/mp4", "aac", "audio/aac",
            "ogg", "audio/ogg", "oga", "audio/ogg", "opus", "audio/ogg", "wav", "audio/wav",
            "wma", "audio/x-ms-wma");
    /** Folders that never hold the user's music. */
    private static final List<String> SKIP_DIRS = Arrays.asList(
            "android", "lost.dir", "system volume information", "$recycle.bin", ".trashes");

    /** A USB volume with music on it. */
    static final class Volume {
        final String label;
        final File root;

        Volume(String label, File root) {
            this.label = label;
            this.root = root;
        }
    }

    /** An audio file on a USB volume; 'relativeDir' is its folder below the volume root. */
    static final class Track {
        final File file;
        final String relativeDir;

        Track(File file, String relativeDir) {
            this.file = file;
            this.relativeDir = relativeDir;
        }
    }

    /** Import progress; calls arrive on the import thread. */
    interface Progress {
        void onProgress(int done, int total, Track current);

        boolean isCancelled();
    }

    /** Result of an import. */
    static final class Result {
        int copied, skipped, failed;
    }

    private UsbMusic() {
    }

    /** Mounted removable (USB) volumes. */
    static List<Volume> volumes(Context context) {
        final List<Volume> result = new ArrayList<>();
        for (StorageVolume v : context.getSystemService(StorageManager.class).getStorageVolumes()) {
            if (v.isPrimary() || !v.isRemovable() || v.getDirectory() == null) continue;
            if (!Environment.MEDIA_MOUNTED.equals(v.getState())
                    && !Environment.MEDIA_MOUNTED_READ_ONLY.equals(v.getState())) continue;
            result.add(new Volume(v.getDescription(context), v.getDirectory()));
        }
        return result;
    }

    /** Audio files on a volume, sorted by path. */
    static List<Track> scan(File root) {
        final List<Track> tracks = new ArrayList<>();
        scan(root, "", tracks);
        return tracks;
    }

    private static void scan(File dir, String relative, List<Track> tracks) {
        final File[] entries = dir.listFiles();
        if (entries == null) return;
        Arrays.sort(entries, (a, b) -> a.getName().compareToIgnoreCase(b.getName()));
        for (File f : entries) {
            final String name = f.getName();
            if (name.startsWith(".")) continue;
            if (f.isDirectory()) {
                if (relative.isEmpty() && SKIP_DIRS.contains(name.toLowerCase(Locale.ROOT))) continue;
                scan(f, relative + name + "/", tracks);
            } else if (mimeType(name) != null) {
                tracks.add(new Track(f, relative));
            }
        }
    }

    static String mimeType(String fileName) {
        final int dot = fileName.lastIndexOf('.');
        return dot < 0 ? null : MIME_TYPES.get(fileName.substring(dot + 1).toLowerCase(Locale.ROOT));
    }

    /** Folder below Music/ for a track: the USB folder, without a leading "Music/" of its own. */
    static String destination(Track track) {
        String dir = track.relativeDir;
        if (dir.regionMatches(true, 0, MusicLibrary.MUSIC_DIR, 0, MusicLibrary.MUSIC_DIR.length())) {
            dir = dir.substring(MusicLibrary.MUSIC_DIR.length());
        }
        return MusicLibrary.MUSIC_DIR + dir;
    }

    /** Copies 'tracks' into the Music folder. */
    static Result copy(Context context, List<Track> tracks, Progress progress) {
        final ContentResolver resolver = context.getContentResolver();
        final Uri audio = Audio.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
        final Result result = new Result();
        final byte[] buffer = new byte[BUFFER];
        for (int i = 0; i < tracks.size(); ++i) {
            if (progress.isCancelled()) break;
            final Track t = tracks.get(i);
            progress.onProgress(i, tracks.size(), t);
            final String relativePath = destination(t);
            final String name = t.file.getName();
            if (exists(resolver, audio, relativePath, name, t.file.length())) {
                result.skipped++;
                continue;
            }
            final ContentValues values = new ContentValues();
            values.put(Audio.Media.DISPLAY_NAME, name);
            values.put(Audio.Media.RELATIVE_PATH, relativePath);
            values.put(Audio.Media.MIME_TYPE, mimeType(name));
            values.put(Audio.Media.IS_PENDING, 1);
            Uri item = null;
            try {
                item = resolver.insert(audio, values);
                if (item == null) throw new IOException("insert failed");
                try (InputStream in = new FileInputStream(t.file);
                        OutputStream out = resolver.openOutputStream(item)) {
                    int n;
                    while ((n = in.read(buffer)) > 0) {
                        if (progress.isCancelled()) throw new IOException("cancelled");
                        out.write(buffer, 0, n);
                    }
                }
                values.clear();
                values.put(Audio.Media.IS_PENDING, 0);
                resolver.update(item, values, null, null);
                result.copied++;
            } catch (IOException | RuntimeException e) {
                Log.w(TAG, "Import of " + t.file + " failed: " + e.getMessage());
                if (item != null) resolver.delete(item, null, null);
                if (!progress.isCancelled()) result.failed++;
            }
        }
        progress.onProgress(tracks.size(), tracks.size(), null);
        return result;
    }

    /** True if Music already has this file (same folder, name and size). */
    private static boolean exists(ContentResolver resolver, Uri audio, String relativePath,
            String name, long size) {
        try (Cursor c = resolver.query(audio, new String[] {Audio.Media.SIZE},
                Audio.Media.RELATIVE_PATH + " = ? AND " + Audio.Media.DISPLAY_NAME + " = ?",
                new String[] {relativePath, name}, null)) {
            while (c != null && c.moveToNext()) {
                if (c.getLong(0) == size) return true;
            }
        }
        return false;
    }
}

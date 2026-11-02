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
 * Music on USB storage: finds mounted removable volumes, lists their audio files and playlists and
 * copies them into the Music folder (MediaStore, primary volume), keeping the folder structure and
 * skipping files that are already there. Playlists (M3U/M3U8/PLS) are written as UTF-8 M3U with their
 * entries rewritten to the imported files, so MediaProvider can resolve them. Files are read
 * through the media FUSE view (READ_MEDIA_AUDIO).
 */
final class UsbMusic {
    private static final String TAG = "CarMusic";
    private static final int BUFFER = 1 << 20;

    private static final Map<String, String> MIME_TYPES = Map.of(
            "mp3", "audio/mpeg", "flac", "audio/flac", "m4a", "audio/mp4", "aac", "audio/aac",
            "ogg", "audio/ogg", "oga", "audio/ogg", "opus", "audio/ogg", "wav", "audio/wav",
            "wma", "audio/x-ms-wma");
    private static final List<String> PLAYLIST_EXTENSIONS = Arrays.asList("m3u", "m3u8", "pls");
    private static final String PLAYLIST_MIME = "audio/x-mpegurl";

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

    /**
     * An audio file or playlist on a USB volume; 'relativeDir' is its folder below the volume root.
     */
    static final class Track {
        final File file;
        final String relativeDir;
        final boolean playlist;
        /** True for the cover image of its folder (see Covers). */
        final boolean cover;

        Track(File file, String relativeDir, boolean playlist) {
            this(file, relativeDir, playlist, false);
        }

        Track(File file, String relativeDir, boolean playlist, boolean cover) {
            this.file = file;
            this.relativeDir = relativeDir;
            this.playlist = playlist;
            this.cover = cover;
        }

        /** Path below the volume root, lower case, for matching playlist entries. */
        String key() {
            return (relativeDir + file.getName()).toLowerCase(Locale.ROOT);
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

    /** Number of audio files (not playlists or covers) in a scan. */
    static int audioCount(List<Track> tracks) {
        int n = 0;
        for (Track t : tracks) if (!t.playlist && !t.cover) n++;
        return n;
    }

    /** Audio files and playlists on a volume, sorted by path. */
    static List<Track> scan(File root) {
        final List<Track> tracks = new ArrayList<>();
        scan(root, "", tracks);
        return tracks;
    }

    private static void scan(File dir, String relative, List<Track> tracks) {
        final File[] entries = dir.listFiles();
        if (entries == null) return;
        Arrays.sort(entries, (a, b) -> a.getName().compareToIgnoreCase(b.getName()));
        File cover = null;
        boolean hasAudio = false;
        for (File f : entries) {
            final String name = f.getName();
            if (name.startsWith(".")) continue;
            if (f.isDirectory()) {
                if (relative.isEmpty() && SKIP_DIRS.contains(name.toLowerCase(Locale.ROOT))) continue;
                scan(f, relative + name + "/", tracks);
            } else if (mimeType(name) != null) {
                tracks.add(new Track(f, relative, false));
                hasAudio = true;
            } else if (PLAYLIST_EXTENSIONS.contains(extension(name))) {
                tracks.add(new Track(f, relative, true));
            } else {
                final int rank = Covers.rank(name);
                if (rank >= 0 && (cover == null || rank < Covers.rank(cover.getName()))) cover = f;
            }
        }
        // One cover per folder with music.
        if (cover != null && hasAudio) tracks.add(new Track(cover, relative, false, true));
    }

    static String mimeType(String fileName) {
        return MIME_TYPES.get(extension(fileName));
    }

    private static String extension(String fileName) {
        final int dot = fileName.lastIndexOf('.');
        return dot < 0 ? "" : fileName.substring(dot + 1).toLowerCase(Locale.ROOT);
    }

    /** Folder below Music/ for a track: the USB folder, without a leading "Music/" of its own. */
    static String destination(Track track) {
        String dir = track.relativeDir;
        if (dir.regionMatches(true, 0, MusicLibrary.MUSIC_DIR, 0, MusicLibrary.MUSIC_DIR.length())) {
            dir = dir.substring(MusicLibrary.MUSIC_DIR.length());
        }
        return MusicLibrary.MUSIC_DIR + dir;
    }

    /** Copies 'tracks' into the Music folder: the audio first, then the playlists. */
    static Result copy(Context context, List<Track> tracks, Progress progress) {
        final ContentResolver resolver = context.getContentResolver();
        final Uri audio = Audio.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
        final Result result = new Result();
        final byte[] buffer = new byte[BUFFER];
        final List<Track> playlists = new ArrayList<>();
        // Source path (lower case) -> imported path below the primary volume, for playlists.
        final Map<String, String> imported = new java.util.HashMap<>();
        for (Track t : tracks) {
            if (t.playlist) playlists.add(t);
            else if (!t.cover) imported.put(t.key(), destination(t) + t.file.getName());
        }
        for (int i = 0; i < tracks.size(); ++i) {
            if (progress.isCancelled()) break;
            final Track t = tracks.get(i);
            if (t.playlist) continue;
            if (t.cover) {
                copyCover(context, t);
                continue;
            }
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
        for (Track t : playlists) {
            if (progress.isCancelled()) break;
            try {
                if (copyPlaylist(resolver, t, imported)) result.copied++; else result.skipped++;
            } catch (IOException | RuntimeException e) {
                Log.w(TAG, "Import of playlist " + t.file + " failed: " + e.getMessage());
                result.failed++;
            }
        }
        progress.onProgress(tracks.size(), tracks.size(), null);
        return result;
    }

    /** Stores a folder cover for ArtProvider (replacing an older one of that folder). */
    private static void copyCover(Context context, Track t) {
        final File target = Covers.file(context, destination(t));
        final File tmp = new File(target.getPath() + ".tmp");
        final byte[] buffer = new byte[BUFFER];
        try (InputStream in = new FileInputStream(t.file);
                OutputStream out = new java.io.FileOutputStream(tmp)) {
            int n;
            while ((n = in.read(buffer)) > 0) out.write(buffer, 0, n);
        } catch (IOException e) {
            Log.w(TAG, "Cover " + t.file + " not imported: " + e.getMessage());
            tmp.delete();
            return;
        }
        if (!tmp.renameTo(target)) tmp.delete();
        ArtProvider.invalidate(context);
    }

    /** Writes a playlist as UTF-8 M3U next to its songs; false if it is already there. */
    private static boolean copyPlaylist(ContentResolver resolver, Track t,
            Map<String, String> imported) throws IOException {
        final Uri playlists = Audio.Playlists.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
        final String dir = destination(t);
        String base = t.file.getName();
        base = base.substring(0, base.lastIndexOf('.'));
        // ".m3u": MediaProvider names files after the MIME type (audio/x-mpegurl); UTF-8 content.
        final String name = base + ".m3u";
        try (Cursor c = resolver.query(playlists, new String[] {Audio.Playlists._ID},
                Audio.Playlists.RELATIVE_PATH + " = ? AND " + Audio.Playlists.DISPLAY_NAME + " = ?",
                new String[] {dir, name}, null)) {
            if (c != null && c.moveToFirst()) return false;
        }
        final StringBuilder out = new StringBuilder("#EXTM3U\n");
        int entries = 0;
        for (String entry : playlistEntries(t.file)) {
            final String target = resolveEntry(entry, t.relativeDir, imported);
            if (target == null) continue;
            out.append(relativize(dir, target)).append('\n');
            entries++;
        }
        if (entries == 0) throw new IOException("no entries match the imported music");

        final ContentValues values = new ContentValues();
        values.put(Audio.Playlists.DISPLAY_NAME, name);
        values.put(Audio.Playlists.RELATIVE_PATH, dir);
        values.put(Audio.Playlists.MIME_TYPE, PLAYLIST_MIME);
        values.put(Audio.Playlists.IS_PENDING, 1);
        final Uri item = resolver.insert(playlists, values);
        if (item == null) throw new IOException("insert failed");
        try (OutputStream os = resolver.openOutputStream(item)) {
            os.write(out.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
        } catch (IOException | RuntimeException e) {
            resolver.delete(item, null, null);
            throw e;
        }
        values.clear();
        values.put(Audio.Playlists.IS_PENDING, 0);
        resolver.update(item, values, null, null);
        return true;
    }

    /** The file entries of an M3U/M3U8 (one per line, # = comment) or PLS (FileN=) playlist. */
    static List<String> playlistEntries(File file) throws IOException {
        final List<String> entries = new ArrayList<>();
        final boolean pls = "pls".equals(extension(file.getName()));
        final String text;
        try (InputStream in = new FileInputStream(file)) {
            text = new String(in.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8);
        }
        for (String line : text.split("\r?\n")) {
            line = line.trim();
            if (line.startsWith("\uFEFF")) line = line.substring(1);
            if (line.isEmpty()) continue;
            if (pls) {
                final int eq = line.indexOf('=');
                if (eq > 0 && line.regionMatches(true, 0, "File", 0, 4)) entries.add(line.substring(eq + 1).trim());
            } else if (!line.startsWith("#")) {
                entries.add(line);
            }
        }
        return entries;
    }

    /**
     * Maps a playlist entry to an imported file (path below the primary volume), or null. Relative
     * entries are resolved against the playlist's folder; absolute ones ("E:\\Music\\a.mp3",
     * "/media/usb/a.mp3") match by their longest path suffix that is a file on the stick.
     */
    static String resolveEntry(String entry, String playlistDir, Map<String, String> imported) {
        String e = entry;
        if (e.regionMatches(true, 0, "http://", 0, 7) || e.regionMatches(true, 0, "https://", 0, 8)) {
            return null;
        }
        if (e.regionMatches(true, 0, "file://", 0, 7)) {
            e = Uri.decode(e.substring(7));
        }
        e = e.replace('\\', '/');
        final boolean absolute = e.startsWith("/") || e.matches("^[A-Za-z]:/.*");
        if (!absolute) {
            final String direct = imported.get(normalize(playlistDir + e));
            if (direct != null) return direct;
        }
        final String[] parts = normalize(e.replaceFirst("^[A-Za-z]:", "")).split("/");
        for (int i = 0; i < parts.length; ++i) {
            final String suffix = String.join("/", Arrays.copyOfRange(parts, i, parts.length));
            final String hit = imported.get(suffix);
            if (hit != null) return hit;
        }
        return null;
    }

    /** Lower case, '/' separated, without empty, "." and ".." segments. */
    private static String normalize(String path) {
        final List<String> out = new ArrayList<>();
        for (String seg : path.split("/")) {
            if (seg.isEmpty() || seg.equals(".")) continue;
            if (seg.equals("..")) {
                if (!out.isEmpty()) out.remove(out.size() - 1);
                continue;
            }
            out.add(seg.toLowerCase(Locale.ROOT));
        }
        return String.join("/", out);
    }

    /** Path of 'target' relative to directory 'fromDir' (both below the same root). */
    static String relativize(String fromDir, String target) {
        final String[] from = fromDir.split("/");
        final String[] to = target.split("/");
        int common = 0;
        while (common < from.length && common < to.length - 1 && from[common].equals(to[common])) {
            common++;
        }
        final StringBuilder sb = new StringBuilder();
        for (int i = common; i < from.length; ++i) if (!from[i].isEmpty()) sb.append("../");
        for (int i = common; i < to.length; ++i) {
            sb.append(to[i]);
            if (i < to.length - 1) sb.append('/');
        }
        return sb.toString();
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

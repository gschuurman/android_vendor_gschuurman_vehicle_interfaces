package com.gschuurman.carmusic;

import android.content.Context;
import android.net.Uri;

import java.io.File;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;

/**
 * Cover images of album folders (cover.jpg, folder.png, ...), imported from USB. Android keeps
 * images out of Music/, so they are stored in the app's files dir, one per folder of the Music
 * library (keyed by its MediaStore relative path, e.g. "Music/Artist/Album/").
 */
final class Covers {
    private static final List<String> EXTENSIONS = Arrays.asList("jpg", "jpeg", "png", "webp");
    /** File name stems, best first; "albumart*" (Windows Media Player) matches by prefix. */
    private static final List<String> NAMES = Arrays.asList("cover", "folder", "front", "album");
    private static final String ALBUMART = "albumart";

    private Covers() {
    }

    /** Rank of an image file name as a cover (lower is better), or -1 if it isn't one. */
    static int rank(String fileName) {
        final int dot = fileName.lastIndexOf('.');
        if (dot < 0) return -1;
        final String ext = fileName.substring(dot + 1).toLowerCase(Locale.ROOT);
        if (!EXTENSIONS.contains(ext)) return -1;
        final String stem = fileName.substring(0, dot).toLowerCase(Locale.ROOT);
        final int i = NAMES.indexOf(stem);
        if (i >= 0) return i;
        return stem.startsWith(ALBUMART) ? NAMES.size() : -1;
    }

    /** Where the cover of a Music folder is stored. */
    static File file(Context context, String relativePath) {
        final File dir = new File(context.getFilesDir(), "covers");
        dir.mkdirs();
        return new File(dir, Uri.encode(relativePath.toLowerCase(Locale.ROOT)));
    }
}

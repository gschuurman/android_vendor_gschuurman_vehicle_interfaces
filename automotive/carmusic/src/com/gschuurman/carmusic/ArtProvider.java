package com.gschuurman.carmusic;

import android.content.ContentProvider;
import android.content.ContentUris;
import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Binder;
import android.os.ParcelFileDescriptor;
import android.provider.MediaStore;
import android.provider.MediaStore.Audio;
import android.util.Size;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;

/**
 * Album art for the car Media app: content://com.gschuurman.carmusic.art/album/<album id>. The
 * Media app has no access to this app's music, so the art is rendered here and cached as PNG:
 * the art embedded in the songs (MediaStore album thumbnail), else the cover image of the album's
 * folder imported from USB (Covers).
 */
public final class ArtProvider extends ContentProvider {
    static final String AUTHORITY = "com.gschuurman.carmusic.art";
    private static final int SIZE_PX = 512;
    private static final String CACHE_PREFIX = "album_";

    /** Drops the cached art, after covers changed. */
    static void invalidate(Context context) {
        final File[] files = context.getCacheDir().listFiles();
        if (files == null) return;
        for (File f : files) if (f.getName().startsWith(CACHE_PREFIX)) f.delete();
    }

    @Override
    public boolean onCreate() {
        return true;
    }

    @Override
    public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        final long albumId;
        try {
            albumId = Long.parseLong(uri.getLastPathSegment());
        } catch (NumberFormatException e) {
            throw new FileNotFoundException(uri.toString());
        }
        final File file = new File(getContext().getCacheDir(), CACHE_PREFIX + albumId + ".png");
        if (!file.exists()) {
            final long token = Binder.clearCallingIdentity();
            try {
                Bitmap art = embeddedArt(albumId);
                if (art == null) art = folderCover(albumId);
                if (art == null) throw new FileNotFoundException(uri.toString());
                final File tmp = new File(file.getPath() + ".tmp");
                try (FileOutputStream out = new FileOutputStream(tmp)) {
                    art.compress(Bitmap.CompressFormat.PNG, 100, out);
                } catch (IOException e) {
                    throw new FileNotFoundException(uri.toString());
                }
                if (!tmp.renameTo(file)) throw new FileNotFoundException(uri.toString());
            } finally {
                Binder.restoreCallingIdentity(token);
            }
        }
        return ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY);
    }

    private Bitmap embeddedArt(long albumId) {
        final Uri album = ContentUris.withAppendedId(
                Audio.Albums.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY), albumId);
        try {
            return getContext().getContentResolver().loadThumbnail(album, new Size(SIZE_PX, SIZE_PX), null);
        } catch (IOException e) {
            return null;  // No embedded art.
        }
    }

    /** The imported cover of the folder of the album's first song, scaled to about SIZE_PX. */
    private Bitmap folderCover(long albumId) {
        String relativePath = null;
        try (Cursor c = getContext().getContentResolver().query(
                Audio.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY),
                new String[] {Audio.Media.RELATIVE_PATH}, Audio.Media.ALBUM_ID + " = ?",
                new String[] {String.valueOf(albumId)}, null)) {
            if (c != null && c.moveToFirst()) relativePath = c.getString(0);
        }
        if (relativePath == null) return null;
        final File cover = Covers.file(getContext(), relativePath);
        if (!cover.exists()) return null;
        final BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        BitmapFactory.decodeFile(cover.getPath(), bounds);
        final BitmapFactory.Options options = new BitmapFactory.Options();
        options.inSampleSize = 1;
        while (bounds.outWidth / (options.inSampleSize * 2) >= SIZE_PX
                && bounds.outHeight / (options.inSampleSize * 2) >= SIZE_PX) {
            options.inSampleSize *= 2;
        }
        return BitmapFactory.decodeFile(cover.getPath(), options);
    }

    @Override
    public String getType(Uri uri) {
        return "image/png";
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection, String[] args, String order) {
        return null;
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        return null;
    }

    @Override
    public int delete(Uri uri, String selection, String[] args) {
        return 0;
    }

    @Override
    public int update(Uri uri, ContentValues values, String selection, String[] args) {
        return 0;
    }
}
